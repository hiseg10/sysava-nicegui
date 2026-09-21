"""
Pagina "Forum": discussoes por aula.

Exibe e permite criar posts no forum da aula indicada via URL (?lesson_id=).
"""

from __future__ import annotations

from datetime import datetime
from nicegui import ui

from core import db, repositories as repo
from ui import layout, security


def _push_forum_post(username: str, message: str, lesson_id: int | None) -> None:
    """Envia o post para o Supabase em background."""
    import threading

    def _enviar():
        try:
            from core import sync
            cli = sync.cliente()
            cli.table("forum_posts").upsert({
                "user_name": username,
                "message": message,
                "lesson_id": lesson_id,
                "created_at": datetime.now().isoformat(),
            }).execute()
        except Exception:
            pass

    threading.Thread(target=_enviar, daemon=True).start()


@ui.page("/forum")
def forum_page(client):
    usuario = security.usuario_atual() or {}
    username = usuario.get("username")

    layout.inicio_pagina(
        "Forum",
        "Discussoes por aula",
        ativo="/forum",
    )

    if not username:
        ui.label("Voce precisa estar logado para acessar o forum.").classes("text-grey-7")
        return

    lesson_id_str = client.request.query_params.get("lesson_id")
    lesson_id = int(lesson_id_str) if lesson_id_str else None

    if lesson_id:
        aula = repo.obter_aula(lesson_id)
        titulo_aula = aula.get("title") if aula else None
        ui.label(f"Forum: {titulo_aula}" if titulo_aula else "Forum").classes("text-h4 q-mb-sm")
        ui.button("Voltar para as Aulas", on_click=lambda: ui.navigate.to("/aulas")).classes("q-mt-md")
    else:
        ui.label("Forum Geral").classes("text-h4 q-mb-sm")

    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("Nova Mensagem").classes("text-subtitle1")
        mensagem = ui.text_area("Escreva sua mensagem:").classes("w-full").props("outlined autogrow")

        def enviar_post():
            if not mensagem.value or not mensagem.value.strip():
                return
            try:
                with db.abrir(somente_leitura=False) as con:
                    con.execute(
                        "INSERT INTO forum_posts (user_name, message, lesson_id, created_at) VALUES (?, ?, ?, ?)",
                        (username, mensagem.value, lesson_id, datetime.now().isoformat()),
                    )
                    con.commit()
                _push_forum_post(username, mensagem.value, lesson_id)
                ui.notify("Mensagem enviada com sucesso!", type="positive")
                mensagem.value = ""
                ui.reload()
            except Exception as e:
                ui.notify(f"Erro ao enviar mensagem: {e}", type="negative")

        ui.button("Enviar", icon="send", on_click=enviar_post).props("outline dense")

    ui.separator().classes("q-my-md")
    ui.label("Ultimas Discussoes").classes("text-subtitle1")

    try:
        posts = repo.listar_posts_forum(lesson_id)
    except Exception:
        posts = []

    if not posts:
        ui.label("Nenhuma discussao neste forum ainda.").classes("text-grey-7")

    for post in reversed(posts):
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ts = post.get("created_at", "") or ""
            hora = ts.split("T")[1][:5] if "T" in ts else ts[:16]
            with ui.row().classes("w-full items-center gap-2 q-mb-sm"):
                ui.label(post.get("user_name", "Anonimo")).classes("font-medium")
                ui.space()
                ui.label(hora).classes("text-caption text-grey-7")
            ui.label(post.get("message", "")).classes("q-mb-xs")

    layout.rodape_navegacao(
        ("Aulas", "menu_book", "/aulas"),
        ("Quiz", "quiz", f"/quiz?lesson_id={lesson_id}" if lesson_id else "/quiz"),
        ("Pontos", "stars", "/pontos"),
    )
