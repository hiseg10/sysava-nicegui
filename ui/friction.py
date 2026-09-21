"""
Página "Radar de Atrito": porte do plugin friction_radar.py para NiceGUI.
"""

from __future__ import annotations

import csv
import io

from nicegui import ui

from core import friction
from ui import layout


def _gerar_csv(resultado: dict) -> bytes:
    """Monta o CSV do relatório (com BOM para abrir certo no Excel)."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";")
    escritor.writerow(["Disciplina", "Aula", "Tipo", "Descricao"])
    for disciplina in resultado["disciplinas"]:
        for aula in disciplina["aulas"]:
            for problema in aula["problemas"]:
                escritor.writerow([
                    disciplina["nome"], aula["titulo"],
                    friction.ROTULOS.get(problema["tipo"], problema["tipo"]),
                    problema["descricao"],
                ])
    return buffer.getvalue().encode("utf-8-sig")


def _cartao(titulo: str, valor, destaque: bool = False) -> None:
    with ui.card().classes("items-center q-pa-md"):
        ui.label(str(valor)).classes("text-h5 " + ("text-negative" if destaque else ""))
        ui.label(titulo).classes("text-caption text-grey-7 text-center")


@ui.page("/radar")
def radar_page() -> None:
    layout.inicio_pagina(
        "Radar de Atrito",
        "Aulas sem quiz, com fórum fraco ou conteúdo muito curto.",
        ativo="/radar",
    )

    estado = {"incluir_treinamento": False, "apenas_com_problemas": True, "resultado": None}

    def baixar_csv() -> None:
        if not estado["resultado"]:
            ui.notify("Nada para exportar ainda.", type="warning")
            return
        ui.download(_gerar_csv(estado["resultado"]), "radar_atrito.csv")

    with ui.row().classes("items-center gap-4 q-mt-sm"):
        ui.switch(
            "Incluir disciplinas de treinamento",
            value=estado["incluir_treinamento"],
            on_change=lambda evento: (
                estado.update(incluir_treinamento=evento.value), painel.refresh()
            ),
        )
        ui.switch(
            "Mostrar só disciplinas com problemas",
            value=estado["apenas_com_problemas"],
            on_change=lambda evento: (
                estado.update(apenas_com_problemas=evento.value), painel.refresh()
            ),
        )
        ui.button("Baixar CSV", icon="download", on_click=baixar_csv).props("outline")

    @ui.refreshable
    def painel() -> None:
        resultado = friction.analisar_atrito(
            incluir_treinamento=estado["incluir_treinamento"]
        )
        estado["resultado"] = resultado

        with ui.row().classes("gap-3 q-mt-sm"):
            _cartao("Disciplinas", resultado["total_disciplinas"])
            _cartao("Aulas analisadas", resultado["total_aulas"])
            _cartao("Problemas", resultado["total_problemas"], destaque=True)
            for tipo, rotulo in friction.ROTULOS.items():
                _cartao(rotulo, resultado["por_tipo"][tipo])

        if resultado["total_problemas"] == 0:
            ui.label("Nenhum ponto de fricção encontrado.").classes("text-positive q-mt-md")
            return

        visiveis = [
            disciplina for disciplina in resultado["disciplinas"]
            if not estado["apenas_com_problemas"] or disciplina["total_problemas"] > 0
        ]
        ui.label(f"{len(visiveis)} disciplina(s) listada(s)").classes("text-subtitle2 q-mt-md")

        for disciplina in visiveis:
            titulo = (
                f"{disciplina['nome']} — {disciplina['total_aulas']} aula(s), "
                f"{disciplina['total_problemas']} problema(s)"
            )
            icone = "warning" if disciplina["total_problemas"] else "check_circle"
            with ui.expansion(titulo, icon=icone).classes("w-full"):
                if not disciplina["aulas"]:
                    ui.label("Nenhum ponto de fricção nesta disciplina.").classes("text-positive")
                    continue

                linhas = [
                    {
                        "_idx": indice,
                        "aula": item["titulo"],
                        "tipos": " • ".join(
                            friction.ROTULOS.get(p["tipo"], p["tipo"]) for p in item["problemas"]
                        ),
                        "detalhes": " | ".join(p["descricao"] for p in item["problemas"]),
                    }
                    for indice, item in enumerate(disciplina["aulas"])
                ]
                colunas = [
                    {"name": "aula", "label": "Aula", "field": "aula", "align": "left", "sortable": True},
                    {"name": "tipos", "label": "Problemas", "field": "tipos", "align": "left"},
                    {"name": "detalhes", "label": "Detalhes", "field": "detalhes", "align": "left"},
                ]
                ui.table(columns=colunas, rows=linhas, row_key="_idx", pagination=10) \
                    .classes("w-full").props("dense flat bordered wrap-cells")

    painel()

    layout.rodape_navegacao(
        ("Dashboard", "dashboard", "/dashboard"),
        ("Aulas", "menu_book", "/aulas"),
        ("Início", "home", "/aluno"),
    )
