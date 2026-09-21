"""
Home do aluno: turma, disciplinas, notas e frequência (somente leitura).
"""

from __future__ import annotations

from nicegui import ui

from core import auth, repositories
from ui import layout, security


def _cartao(titulo: str, valor, cor: str = "") -> None:
    with ui.card().classes("items-center q-pa-md min-w-32"):
        ui.label(str(valor)).classes(f"text-h5 {cor}".strip())
        ui.label(titulo).classes("text-caption text-grey-7 text-center")


def _formatar_nota(valor) -> str:
    if valor is None or valor == "":
        return "-"
    try:
        return f"{float(valor):.1f}"
    except (TypeError, ValueError):
        return str(valor)


def _secao_notas(notas: list[dict]) -> None:
    ui.label("Notas").classes("text-h6 q-mt-md")
    if not notas:
        ui.label("Nenhuma nota lançada ainda.").classes("text-grey-7")
        return
    linhas = [
        {
            "_idx": indice,
            "disciplina": item.get("subject"),
            "nm1": _formatar_nota(item.get("nm1")),
            "nm2": _formatar_nota(item.get("nm2")),
            "nm3": _formatar_nota(item.get("nm3")),
            "final": _formatar_nota(item.get("final_grade")),
            "trimestre": item.get("trimester"),
        }
        for indice, item in enumerate(notas)
    ]
    colunas = [
        {"name": "disciplina", "label": "Disciplina", "field": "disciplina", "align": "left"},
        {"name": "trimestre", "label": "Trim.", "field": "trimestre", "align": "center"},
        {"name": "nm1", "label": "NM1", "field": "nm1", "align": "center"},
        {"name": "nm2", "label": "NM2", "field": "nm2", "align": "center"},
        {"name": "nm3", "label": "NM3", "field": "nm3", "align": "center"},
        {"name": "final", "label": "Final", "field": "final", "align": "center"},
    ]
    ui.table(columns=colunas, rows=linhas, row_key="_idx", pagination=10) \
        .classes("w-full max-w-4xl").props("dense flat bordered")


def _secao_disciplinas(disciplinas: list[dict]) -> None:
    ui.label("Disciplinas").classes("text-h6 q-mt-md")
    if not disciplinas:
        ui.label("Nenhuma disciplina vinculada à sua turma.").classes("text-grey-7")
        return
    with ui.row().classes("gap-2 flex-wrap"):
        for disciplina in disciplinas:
            ui.chip(disciplina.get("name") or "-", icon="menu_book").props("outline")


@ui.page("/aluno")
def aluno_page() -> None:
    usuario = security.usuario_atual() or {}
    contexto = repositories.contexto_aluno(usuario.get("username"))

    layout.inicio_pagina(
        f"Olá, {auth.nome_exibicao(usuario) or 'aluno'}!",
        "Seu espaço no SysAVA.",
        ativo="/aluno",
    )

    turma = contexto["turma"] or {}
    with ui.row().classes("gap-3 q-mt-sm flex-wrap"):
        _cartao("Turma", turma.get("name") or "Sem turma")
        _cartao("Disciplinas", len(contexto["disciplinas"]))
        _cartao("Presenças", contexto["presencas"], "text-positive")
        _cartao("Faltas", contexto["faltas"], "text-negative" if contexto["faltas"] else "")

    _secao_disciplinas(contexto["disciplinas"])
    _secao_notas(contexto["notas"])

    ui.label(
        "Em breve: aulas, quizzes, avaliações e fórum por aqui."
    ).classes("text-caption text-grey-6 q-mt-md")

    layout.rodape_navegacao(
        ("Aulas", "menu_book", "/aulas"),
        ("Pontos", "stars", "/pontos"),
        ("Provas", "quiz", "/provas"),
    )
