"""
Página "Pontos": resumo de pontos do aluno (aulas + quizzes + fórum).

Admin/professor escolhem turma e aluno; o aluno vê apenas o próprio resumo.
"""

from __future__ import annotations

from nicegui import ui

from core import auth, repositories as repo, scores
from ui import layout, security


def _cartao(titulo: str, valor, cor: str = "") -> None:
    with ui.card().classes("items-center q-pa-md min-w-28"):
        ui.label(str(valor)).classes(f"text-h5 {cor}".strip())
        ui.label(titulo).classes("text-caption text-grey-7 text-center")


@ui.page("/pontos")
def pontos_page() -> None:
    usuario = security.usuario_atual() or {}
    papel = usuario.get("role")
    staff = papel in (auth.PAPEL_ADMIN, auth.PAPEL_PROFESSOR)

    layout.inicio_pagina(
        "Resumo de Pontos",
        "Aulas assistidas + quizzes + fórum, por disciplina.",
        ativo="/pontos",
    )

    estado: dict = {"turma_id": None, "aluno": None, "subject_id": None}

    turmas = repo.listar_turmas()
    opcoes_turma = {str(t["id"]): t["name"] for t in turmas}

    if staff:
        if turmas:
            estado["turma_id"] = turmas[0]["id"]
    else:
        contexto = repo.contexto_aluno(usuario.get("username"))
        turma = contexto["turma"]
        estado["turma_id"] = (turma or {}).get("id")
        estado["aluno"] = usuario.get("username")

    def carregar() -> None:
        if staff:
            alunos = repo.listar_alunos_da_turma(estado["turma_id"]) if estado["turma_id"] else []
            opcoes_aluno = {str(a["username"]): a.get("name") or a["username"] for a in alunos}
            aluno_select.set_options(opcoes_aluno)
            if estado["aluno"] not in opcoes_aluno:
                estado["aluno"] = next(iter(opcoes_aluno), None)
            aluno_select.value = estado["aluno"]

        disciplinas = repo.listar_disciplinas_da_turma(estado["turma_id"], apenas_ativas=True) if estado["turma_id"] else []
        opcoes_disciplina = {"": "Todas as disciplinas"}
        opcoes_disciplina.update({str(d["id"]): d["name"] for d in disciplinas})
        disc_select.set_options(opcoes_disciplina)
        if str(estado["subject_id"] or "") not in opcoes_disciplina:
            estado["subject_id"] = None
        disc_select.value = estado["subject_id"] or ""
        painel.refresh()

    with ui.row().classes("items-center gap-4 q-mt-sm flex-wrap"):
        if staff:
            turma_select = ui.select(
                opcoes_turma,
                value=str(estado["turma_id"]) if estado["turma_id"] else None,
                label="Turma",
                on_change=lambda evento: (estado.update(turma_id=evento.value), carregar()),
            ).classes("w-64").props("outlined dense")
            aluno_select = ui.select({}, label="Aluno", on_change=lambda evento: (
                estado.update(aluno=evento.value), painel.refresh(),
            )).classes("w-64").props("outlined dense")
        else:
            ui.label(f"Aluno: {usuario.get('name') or usuario.get('username')}").classes("text-subtitle1")
        disc_select = ui.select(
            {"": "Todas as disciplinas"},
            label="Disciplina",
            on_change=lambda evento: (
                estado.update(subject_id=evento.value or None), painel.refresh(),
            ),
        ).classes("w-64").props("outlined dense")

    @ui.refreshable
    def painel() -> None:
        if not estado["aluno"]:
            ui.label("Selecione uma turma e um aluno.").classes("text-grey-7 q-mt-md")
            return

        resumo = scores.resumo_pontos(estado["aluno"], estado["subject_id"])
        with ui.row().classes("gap-3 q-mt-md flex-wrap"):
            _cartao("Aulas", resumo["aulas"])
            _cartao("Quizzes", resumo["quizzes"])
            _cartao("Fórum", resumo["forum"])
            _cartao("Part.NM1", f"{resumo['participacao_nm1']:.2f}")
            _cartao("Part.NM2", f"{resumo['participacao_nm2']:.2f}")
            _cartao("NM1", f"{resumo['nm1']:.2f}", "text-primary")
            _cartao("NM2", f"{resumo['nm2']:.2f}", "text-accent")
            _cartao("NM3", f"{resumo['nm3']:.2f}", "text-info")

        if not resumo["por_disciplina"]:
            ui.label(
                "Sem atividades registradas para este aluno (o histórico local pode estar vazio)."
            ).classes("text-grey-7 q-mt-md")
            return

        registros = [
            {
                "_idx": indice,
                "disciplina": item["disciplina"],
                "aulas": item["aulas"],
                "quizzes": item["quizzes"],
                "forum": item["forum"],
                "part_nm1": f"{item['participacao_nm1']:.2f}",
                "part_nm2": f"{item['participacao_nm2']:.2f}",
                "nm1": f"{item['nm1']:.2f}",
                "nm2": f"{item['nm2']:.2f}",
                "nm3": f"{item['nm3']:.2f}",
            }
            for indice, item in enumerate(resumo["por_disciplina"])
        ]
        colunas = [
            {"name": "disciplina", "label": "Disciplina", "field": "disciplina", "align": "left", "sortable": True},
            {"name": "aulas", "label": "Aulas", "field": "aulas", "align": "right", "sortable": True},
            {"name": "quizzes", "label": "Quizzes", "field": "quizzes", "align": "right", "sortable": True},
            {"name": "forum", "label": "Fórum", "field": "forum", "align": "right", "sortable": True},
            {"name": "part_nm1", "label": "Part.NM1", "field": "part_nm1", "align": "right"},
            {"name": "part_nm2", "label": "Part.NM2", "field": "part_nm2", "align": "right"},
            {"name": "nm1", "label": "NM1", "field": "nm1", "align": "right", "sortable": True},
            {"name": "nm2", "label": "NM2", "field": "nm2", "align": "right", "sortable": True},
            {"name": "nm3", "label": "NM3", "field": "nm3", "align": "right", "sortable": True},
        ]
        ui.table(columns=colunas, rows=registros, row_key="_idx", pagination=15) \
            .classes("w-full max-w-4xl").props("dense flat bordered")

        ui.label(
            "Part.NM1 = pontos 1–16 / 16 · Part.NM2 = pontos 17–32 / 16 · teto 3"
        ).classes("text-caption text-grey-6 q-mt-sm")

    carregar()
    painel()

    layout.rodape_navegacao(
        ("Aulas", "menu_book", "/aulas"),
        ("Provas", "quiz", "/provas"),
        ("Início", "home", "/aluno"),
    )
