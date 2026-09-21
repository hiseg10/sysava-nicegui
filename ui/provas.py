"""
Página "Provas": avaliações por turma/disciplina, questões, gabarito e notas.

Admin/professor veem questões com gabarito, submissões e podem lançar notas.
Alunos veem suas tentativas e a melhor nota.
"""

from __future__ import annotations

from nicegui import ui

from core import assessments, auth, repositories as repo, scores
from ui import layout, security


def _slug(texto: str) -> str:
    return str(texto or "prova").strip().replace(" ", "_")[:60]


@ui.page("/provas")
def provas_page() -> None:
    usuario = security.usuario_atual() or {}
    papel = usuario.get("role")
    staff = papel in (auth.PAPEL_ADMIN, auth.PAPEL_PROFESSOR)

    layout.inicio_pagina(
        "Provas e Avaliações",
        "Questões, gabarito e notas por turma e disciplina.",
        ativo="/provas",
    )

    estado: dict = {"turma_id": None, "turma_nome": None, "disciplina_id": None, "assessment_id": None}

    turmas = repo.listar_turmas()
    opcoes_turma = {str(t["id"]): t["name"] for t in turmas}
    if staff:
        if turmas:
            estado["turma_id"] = turmas[0]["id"]
            estado["turma_nome"] = turmas[0]["name"]
    else:
        turma = (repo.contexto_aluno(usuario.get("username")) or {}).get("turma")
        if turma:
            estado["turma_id"] = turma.get("id")
            estado["turma_nome"] = turma.get("name")

    def carregar_disciplinas() -> None:
        disciplinas = repo.listar_disciplinas_da_turma(estado["turma_id"], apenas_ativas=True) if estado["turma_id"] else []
        opcoes = {str(d["id"]): d["name"] for d in disciplinas}
        if estado["disciplina_id"] not in opcoes:
            estado["disciplina_id"] = next(iter(opcoes), None)
        estado["disciplina_nome"] = opcoes.get(str(estado["disciplina_id"]))
        disc_select.set_options(opcoes)
        disc_select.value = estado["disciplina_id"]
        carregar_avaliacoes()

    def carregar_avaliacoes() -> None:
        lista = assessments.listar_avaliacoes(estado["disciplina_id"])
        estado["avaliacoes"] = lista
        if staff:
            opcoes = {str(a["id"]): f"{a.get('type') or ''} - {a.get('title') or ''}".strip(" -") for a in lista}
            if estado["assessment_id"] not in opcoes:
                estado["assessment_id"] = next(iter(opcoes), None)
            avaliacao_select.set_options(opcoes)
            avaliacao_select.value = estado["assessment_id"]
        painel.refresh()

    with ui.row().classes("items-center gap-4 q-mt-sm flex-wrap"):
        if staff:
            ui.select(
                opcoes_turma,
                value=str(estado["turma_id"]) if estado["turma_id"] else None,
                label="Turma",
                on_change=lambda evento: (
                    estado.update(
                        turma_id=evento.value,
                        turma_nome=opcoes_turma.get(evento.value),
                        disciplina_id=None,
                        assessment_id=None,
                    ),
                    carregar_disciplinas(),
                ),
            ).classes("w-64").props("outlined dense")
        else:
            ui.label(f"Turma: {estado['turma_nome'] or '-'}").classes("text-subtitle1")

        disc_select = ui.select(
            {},
            label="Disciplina",
            on_change=lambda evento: (
                estado.update(disciplina_id=evento.value, assessment_id=None),
                carregar_avaliacoes(),
            ),
        ).classes("w-64").props("outlined dense")

        if staff:
            avaliacao_select = ui.select(
                {},
                label="Avaliação",
                on_change=lambda evento: (estado.update(assessment_id=evento.value), painel.refresh()),
            ).classes("w-64").props("outlined dense")

    # --- Diálogo de nota ------------------------------------------------------
    dialogo_nota = ui.dialog()
    with dialogo_nota, ui.card().classes("w-96"):
        ui.label("Lançar nota").classes("text-h6")
        nota_input = ui.number("Nota", min=0, max=10, step=0.5, format="%.2f").classes("w-full")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dialogo_nota.close).props("flat")

            def salvar_nota() -> None:
                submission_id = estado.get("submission_nota")
                if submission_id is not None and assessments.atualizar_nota(submission_id, nota_input.value):
                    ui.notify("Nota atualizada.", type="positive")
                    dialogo_nota.close()
                    painel.refresh()
                else:
                    ui.notify("Não foi possível salvar a nota.", type="negative")

            ui.button("Salvar", icon="save", on_click=salvar_nota)

    def abrir_nota(submissao: dict) -> None:
        estado["submission_nota"] = submissao.get("id")
        nota_input.value = submissao.get("score")
        dialogo_nota.open()

    # --- Painel ---------------------------------------------------------------
    @ui.refreshable
    def painel() -> None:
        if not estado["disciplina_id"]:
            ui.label("Selecione uma turma e uma disciplina.").classes("text-grey-7 q-mt-md")
            return

        if not staff:
            _painel_aluno()
            return

        avaliacao = next(
            (a for a in estado.get("avaliacoes", []) if str(a["id"]) == str(estado["assessment_id"])),
            None,
        )
        if not avaliacao:
            ui.label("Nenhuma avaliação para esta disciplina.").classes("text-grey-7 q-mt-md")
            return

        questoes = assessments.questoes_avaliacao(avaliacao["id"])
        titulo = f"{avaliacao.get('type') or ''} - {avaliacao.get('title') or ''}".strip(" -")
        with ui.row().classes("items-center gap-3 q-mt-md w-full max-w-4xl"):
            ui.label(titulo).classes("text-subtitle1")
            ui.space()
            ui.button(
                "Prova em branco (MD)",
                icon="download",
                on_click=lambda: _baixar(avaliacao, questoes, em_branco=True),
            ).props("outline dense")
            ui.button(
                "Prova + gabarito (MD)",
                icon="download",
                on_click=lambda: _baixar(avaliacao, questoes, em_branco=False),
            ).props("outline dense")

        ui.label(f"{len(questoes)} questão(ões)").classes("text-caption text-grey-6")

        for indice, questao in enumerate(questoes, start=1):
            with ui.card().classes("w-full max-w-4xl"):
                ui.markdown(f"**{indice}. {questao.get('question_text')}**")
                correta = questao.get("correct_option_index") or 0
                for posicao, opcao in enumerate(questao.get("options", [])):
                    letra = chr(65 + posicao)
                    if posicao == correta:
                        ui.label(f"✅ {letra}) {opcao}").classes("text-positive")
                    else:
                        ui.label(f"{letra}) {opcao}")

        submissoes = assessments.submissoes_avaliacao(avaliacao["id"])
        ui.separator().classes("q-mt-md")
        ui.label(f"Submissões ({len(submissoes)})").classes("text-h6")
        if not submissoes:
            ui.label("Nenhum aluno realizou esta prova ainda.").classes("text-grey-7")
            return

        registros = [
            {
                "_idx": indice,
                "aluno": item.get("student_name") or item.get("user_username"),
                "ra": item.get("student_ra"),
                "nota": "" if item.get("score") is None else f"{float(item['score']):.2f}",
                "status": item.get("status"),
                "enviado": item.get("submitted_at"),
            }
            for indice, item in enumerate(submissoes)
        ]
        colunas = [
            {"name": "aluno", "label": "Aluno", "field": "aluno", "align": "left", "sortable": True},
            {"name": "ra", "label": "RA", "field": "ra", "align": "left"},
            {"name": "nota", "label": "Nota", "field": "nota", "align": "right", "sortable": True},
            {"name": "status", "label": "Status", "field": "status", "align": "left"},
            {"name": "enviado", "label": "Enviado em", "field": "enviado", "align": "left"},
            {"name": "acao", "label": "Ação", "field": "acao", "align": "center"},
        ]
        tabela = ui.table(columns=colunas, rows=registros, row_key="_idx", pagination=15) \
            .classes("w-full max-w-4xl").props("dense flat bordered")
        tabela.add_slot("body-cell-acao", """
            <q-td :props="props">
                <q-btn dense flat icon="edit" @click="$parent.$emit('editar', props.row)" />
            </q-td>
        """)
        tabela.on("editar", lambda evento: abrir_nota(submissoes[evento.args["_idx"]]))

    def _baixar(avaliacao: dict, questoes: list[dict], em_branco: bool) -> None:
        texto = assessments.markdown_prova(
            avaliacao,
            questoes,
            subject_name=estado.get("disciplina_nome") or "",
            class_name=estado.get("turma_nome") or "",
            school_name="SysAVA",
            em_branco=em_branco,
        )
        sufixo = "branco" if em_branco else "gabarito"
        ui.download(texto.encode("utf-8"), f"prova_{_slug(avaliacao.get('title'))}_{sufixo}.md")

    def _painel_aluno() -> None:
        avaliacoes = estado.get("avaliacoes", [])
        if not avaliacoes:
            ui.label("Nenhuma avaliação agendada para esta disciplina.").classes("text-grey-7 q-mt-md")
            return
        for avaliacao in avaliacoes:
            tipo = avaliacao.get("type") or ""
            bloqueio = scores.bloqueio_avaliacao(usuario.get("username"), tipo)
            submissoes = assessments.submissoes_aluno(usuario.get("username"), avaliacao["id"])
            notas = [s.get("score") for s in submissoes if s.get("score") is not None]
            with ui.card().classes("w-full max-w-3xl"):
                with ui.row().classes("items-center gap-3 w-full"):
                    ui.label(
                        f"{tipo} - {avaliacao.get('title') or ''}".strip(" -")
                    ).classes("text-subtitle1")
                    ui.space()
                    if bloqueio:
                        ui.badge(bloqueio, color="negative").classes("text-caption")
                    elif notas:
                        ui.badge(f"Melhor nota: {max(notas):.2f}", color="positive")
                    elif submissoes:
                        ui.badge("Aguardando correção", color="orange")
                    else:
                        ui.badge("Não realizada", color="grey")
                if not bloqueio:
                    ui.label(f"{len(submissoes)} tentativa(s) de 2.").classes("text-caption text-grey-6")

    carregar_disciplinas()
    painel()

    layout.rodape_navegacao(
        ("Aulas", "menu_book", "/aulas"),
        ("Pontos", "stars", "/pontos"),
        ("Início", "home", "/aluno"),
    )
