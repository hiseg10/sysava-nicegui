"""
Página "Fórum": discussões por aula.

Exibe e permite criar posts no fórum da aula indicada via URL (?lesson_id=).
"""

from __future__ import annotations

from datetime import datetime
from nicegui import ui, app

from core import db, repositories as repo
from ui import layout, security


@ui.page("/forum")
def forum_page(client):
    usuario = security.usuario_atual() or {}
    username = usuario.get("username")

    layout.inicio_pagina(
        "Fórum",
        "Discussões por aula",
        ativo="/forum",
    )

    if not username:
        ui.label("Você precisa estar logado para acessar o fórum.").classes("text-grey-7")
        return

    lesson_id_str = client.request.query_params.get("lesson_id")
    lesson_id = int(lesson_id_str) if lesson_id_str else None

    if lesson_id:
        aula = repo.obter_aula(lesson_id)
        titulo_aula = aula.get("title") if aula else None
        ui.label(f"💬 Fórum: {titulo_aula}" if titulo_aula else "💬 Fórum").classes("text-h4 q-mb-sm")

        ui.button("⬅️ Voltar para as Aulas", on_click=lambda: ui.navigate.to("/aulas")).classes("q-mt-md")
    else:
        ui.label("💬 Fórum Geral").classes("text-h4 q-mb-sm")

    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("Nova Mensagem").classes("text-subtitle1")
        mensagem = ui.text_area("Escreva sua mensagem:").classes("w-full").props("outlined autogrow")

        def enviar_post():
            if not mensagem.value.strip():
                return
            try:
                with db.abrir(somente_leitura=False) as con:
                    con.execute(
                        "INSERT INTO forum_posts (user_name, message, lesson_id, created_at) VALUES (?, ?, ?, ?)",
                        (username, mensagem.value, lesson_id, datetime.now().isoformat()),
                    )
                    con.commit()
                ui.notify("Mensagem enviada com sucesso!", type="positive")
                mensagem.value = ""
                ui.reload()
            except Exception as e:
                ui.notify(f"Erro ao enviar mensagem: {e}", type="negative")

        ui.button("Enviar", icon="send", on_click=enviar_post).props("outline dense")

    ui.separator().classes("q-my-md")
    ui.label("Últimas Discussões").classes("text-subtitle1")

    posts = repo.listar_posts_forum(lesson_id)
    if not posts:
        ui.label("Nenhuma discussão neste fórum ainda.").classes("text-grey-7")

    for post in reversed(posts):
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ts = post.get("created_at", "")
            hora = ts.split("T")[1][:5] if "T" in ts else ""
            with ui.row().classes("w-full items-center gap-2 q-mb-sm"):
                ui.label(f"👤 {post.get('user_name', 'Anônimo')}").classes("font-medium")
                ui.space()
                ui.label(hora).classes("text-caption text-grey-7")
            ui.label(post.get("message", "")).classes("q-mb-xs")

    layout.rodape_navegacao(
        ("Aulas", "menu_book", "/aulas"),
        ("Quiz", "quiz", f"/quiz?lesson_id={lesson_id}" if lesson_id else "/quiz"),
        ("Pontos", "stars", "/pontos"),
    )

