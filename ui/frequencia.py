"""
Página "Frequência": chamada diária por turma/disciplina, resumo e export CSV.
"""

from __future__ import annotations

from datetime import date

from nicegui import ui

from core import attendance, auth
from ui import layout, security


def _cartao(titulo: str, valor, cor: str = "") -> None:
    with ui.card().classes("items-center q-pa-md min-w-28"):
        ui.label(str(valor)).classes(f"text-h5 {cor}".strip())
        ui.label(titulo).classes("text-caption text-grey-7 text-center")


@ui.page("/frequencia")
def frequencia_page() -> None:
    layout.inicio_pagina(
        "Frequência de Alunos",
        "Registre a presença dos alunos por dia.",
        ativo="/frequencia",
    )

    opcoes_turma = {str(turma["id"]): turma["name"] for turma in attendance.listar_turmas()}
    estado: dict = {
        "turma_id": None,
        "disciplina_id": None,
        "data": date.today().isoformat(),
        "status": {},
        "alunos": [],
        "turma_nome": None,
        "disciplina_nome": None,
        "disc_opcoes": {},
    }

    # --- Seleções -------------------------------------------------------------
    with ui.row().classes("items-center gap-4 q-mt-sm flex-wrap"):
        turma_select = ui.select(opcoes_turma, label="Turma").classes("w-72").props("outlined dense")
        disc_select = ui.select({}, label="Disciplina").classes("w-72").props("outlined dense")
        data_input = ui.input("Data", value=estado["data"]).classes("w-48").props(
            "outlined dense type=date"
        )

    def carregar() -> None:
        turma_id = estado["turma_id"]
        disciplina_id = estado["disciplina_id"]
        if not (turma_id and disciplina_id and estado["data"]):
            estado.update(alunos=[], status={}, turma_nome=None, disciplina_nome=None)
            painel_chamada.refresh()
            painel_resumo.refresh()
            painel_relatorio.refresh()
            return

        estado["turma_nome"] = opcoes_turma.get(str(turma_id))
        estado["disciplina_nome"] = estado["disc_opcoes"].get(str(disciplina_id))
        alunos = attendance.listar_alunos(turma_id)
        chamada = attendance.carregar_chamada(
            estado["turma_nome"], disciplina_id, estado["data"]
        )
        estado["alunos"] = alunos
        # Alunos inativos (lista negra em users.is_active) já entram como Falta.
        estado["status"] = {
            aluno["name"]: chamada.get(
                aluno["name"],
                attendance.STATUS_FALTA if not auth.esta_ativo(aluno) else attendance.STATUS_PRESENTE,
            )
            for aluno in alunos
        }
        painel_chamada.refresh()
        painel_resumo.refresh()
        painel_relatorio.refresh()

    def ao_mudar_turma(evento) -> None:
        estado["turma_id"] = evento.value
        estado["disciplina_id"] = None
        disciplinas = attendance.listar_disciplinas(evento.value) if evento.value else []
        estado["disc_opcoes"] = {str(d["id"]): d["name"] for d in disciplinas}
        disc_select.set_options(estado["disc_opcoes"], value=None)
        carregar()

    def ao_mudar_disciplina(evento) -> None:
        estado["disciplina_id"] = evento.value
        carregar()

    def ao_mudar_data(evento) -> None:
        estado["data"] = evento.value
        carregar()

    turma_select.on_value_change(ao_mudar_turma)
    disc_select.on_value_change(ao_mudar_disciplina)
    data_input.on_value_change(ao_mudar_data)

    def definir_status(nome: str, valor: str) -> None:
        estado["status"][nome] = valor
        painel_resumo.refresh()

    # --- Chamada --------------------------------------------------------------
    @ui.refreshable
    def painel_chamada() -> None:
        if not (estado["turma_nome"] and estado["disciplina_nome"]):
            ui.label(
                "Selecione a turma, a disciplina e a data para iniciar a chamada."
            ).classes("text-grey-7 q-mt-md")
            return

        alunos = estado["alunos"]
        if not alunos:
            ui.label("Nenhum aluno matriculado nesta turma.").classes("text-warning q-mt-md")
            return

        with ui.row().classes("items-center gap-3 q-mt-md"):
            ui.label(
                f"{estado['turma_nome']} — {estado['disciplina_nome']}"
            ).classes("text-subtitle1")
            ui.button(
                "Marcar todos presentes",
                icon="done_all",
                on_click=lambda: (
                    [
                        estado["status"].update(
                            {
                                a["name"]: (
                                    attendance.STATUS_FALTA
                                    if not auth.esta_ativo(a)
                                    else attendance.STATUS_PRESENTE
                                )
                            }
                        )
                        for a in alunos
                    ],
                    painel_chamada.refresh(),
                    painel_resumo.refresh(),
                ),
            ).props("flat dense")

        with ui.column().classes("w-full max-w-3xl gap-0 q-mt-sm"):
            for indice, aluno in enumerate(alunos, start=1):
                nome = aluno["name"]
                with ui.row().classes("w-full items-center gap-3 q-py-xs").style(
                    "border-bottom: 1px solid #e5e7eb"
                ):
                    ui.label(str(indice)).classes("w-8 text-right text-grey-7")
                    ui.label(nome).classes("flex-1")
                    if not auth.esta_ativo(aluno):
                        ui.label("inativo").classes("text-caption text-negative")
                    ui.select(
                        list(attendance.STATUS),
                        value=estado["status"].get(nome, attendance.STATUS_PRESENTE),
                        on_change=lambda evento, n=nome: definir_status(n, evento.value),
                    ).classes("w-36").props("dense outlined")

        ui.button("Salvar chamada do dia", icon="save", on_click=salvar).classes("q-mt-md")

    def salvar() -> None:
        if not (estado["turma_nome"] and estado["disciplina_id"]):
            ui.notify("Selecione turma e disciplina.", type="warning")
            return
        registros = []
        for indice, aluno in enumerate(estado["alunos"], start=1):
            nome = aluno["name"]
            # Lista negra (inativo) sempre grava Falta, independentemente do select.
            if not auth.esta_ativo(aluno):
                status = attendance.STATUS_FALTA
                estado["status"][nome] = status
            else:
                status = estado["status"].get(nome, attendance.STATUS_PRESENTE)
            registros.append(
                {
                    "student_name": nome,
                    "student_number": indice,
                    "status": status,
                }
            )
        usuario = security.usuario_atual() or {}
        resultado = attendance.salvar_chamada(
            estado["turma_nome"],
            estado["disciplina_id"],
            estado["data"],
            registros,
            professor=usuario.get("name") or usuario.get("username") or "",
        )
        ui.notify(
            f"Chamada salva: {resultado['inseridos']} novo(s), "
            f"{resultado['atualizados']} atualizado(s).",
            type="positive",
        )
        painel_relatorio.refresh()

    # --- Resumo do dia --------------------------------------------------------
    @ui.refreshable
    def painel_resumo() -> None:
        valores = estado.get("status") or {}
        if not valores:
            return
        presencas = sum(1 for v in valores.values() if v == attendance.STATUS_PRESENTE)
        faltas = sum(1 for v in valores.values() if v == attendance.STATUS_FALTA)
        atrasos = sum(1 for v in valores.values() if v == attendance.STATUS_ATRASO)
        with ui.row().classes("gap-3 q-mt-md"):
            _cartao("Presenças", presencas, "text-positive")
            _cartao("Faltas", faltas, "text-negative" if faltas else "")
            _cartao("Atrasos", atrasos)

    # --- Relatório acumulado --------------------------------------------------
    @ui.refreshable
    def painel_relatorio() -> None:
        if not (estado["turma_nome"] and estado["disciplina_id"]):
            return
        linhas = attendance.resumo_disciplina(estado["turma_nome"], estado["disciplina_id"])
        ui.separator().classes("q-mt-lg")
        with ui.row().classes("items-center gap-4 w-full max-w-3xl"):
            ui.label("Relatório de frequência (acumulado)").classes("text-h6")
            ui.space()
            ui.button(
                "Resumo (CSV)", icon="download", on_click=baixar_resumo
            ).props("outline dense")
            ui.button(
                "Histórico da turma (CSV)", icon="download", on_click=baixar_historico
            ).props("outline dense")

        if not linhas:
            ui.label("Nenhum registro acumulado para esta disciplina.").classes("text-grey-7")
            return

        registros = [
            {
                "_idx": indice,
                "estudante": item["student_name"],
                "presencas": item["presencas"],
                "faltas": item["faltas"],
                "atrasos": item["atrasos"],
                "percentual": f"{item['percentual']:.1f}%",
            }
            for indice, item in enumerate(linhas)
        ]
        colunas = [
            {"name": "estudante", "label": "Estudante", "field": "estudante", "align": "left", "sortable": True},
            {"name": "presencas", "label": "Presenças", "field": "presencas", "align": "right", "sortable": True},
            {"name": "faltas", "label": "Faltas", "field": "faltas", "align": "right", "sortable": True},
            {"name": "atrasos", "label": "Atrasos", "field": "atrasos", "align": "right", "sortable": True},
            {"name": "percentual", "label": "% Freq.", "field": "percentual", "align": "right"},
        ]
        ui.table(columns=colunas, rows=registros, row_key="_idx", pagination=15) \
            .classes("w-full max-w-3xl").props("dense flat bordered")

    def _nome_arquivo(prefixo: str) -> str:
        turma = (estado["turma_nome"] or "turma").replace(" ", "_")
        return f"{prefixo}_{turma}_{date.today().strftime('%Y%m%d')}.csv"

    def baixar_resumo() -> None:
        linhas = attendance.resumo_disciplina(estado["turma_nome"], estado["disciplina_id"])
        if not linhas:
            ui.notify("Nada para exportar ainda.", type="warning")
            return
        ui.download(attendance.gerar_csv_resumo(linhas), _nome_arquivo("resumo_frequencia"))

    def baixar_historico() -> None:
        linhas = attendance.historico_turma(estado["turma_nome"])
        if not linhas:
            ui.notify("Nada para exportar ainda.", type="warning")
            return
        ui.download(attendance.gerar_csv_historico(linhas), _nome_arquivo("historico_frequencia"))

    painel_chamada()
    painel_resumo()
    painel_relatorio()

    layout.rodape_navegacao(
        ("Dashboard", "dashboard", "/dashboard"),
        ("Turmas", "groups", "/manage-turmas"),
        ("Início", "home", "/aluno"),
    )
