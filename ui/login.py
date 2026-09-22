"""
Página de login do SysAVA.

Aceita RA ou usuário + senha (bcrypt em `users`). Após autenticar, grava o
acesso em `user_history` e redireciona para a rota inicial do papel (ou para o
destino que o usuário tentou acessar).
"""

from __future__ import annotations

from nicegui import ui

from core import auth
from ui import security


def _tentar_entrar(login_input, senha_input) -> None:
    usuario = auth.autenticar(login_input.value or "", senha_input.value or "")
    if not usuario:
        ui.notify("Usuário/RA ou senha inválidos.", type="negative")
        senha_input.value = ""
        return

    security.entrar(usuario)
    auth.registrar_atividade(usuario.get("username"), "Entrou no SysAVA")

    destino = security.consumir_destino() or auth.rota_inicial(usuario.get("role"))
    ui.navigate.to(destino)


@ui.page("/login")
def login_page() -> None:
    if security.sessao_valida():
        ui.navigate.to(auth.rota_inicial(security.papel_atual()))
        return
    if security.usuario_atual():
        security.sair()

    ui.add_head_html("<style>body { background: #f1f5f9; }</style>")

    with ui.column().classes("w-full items-center justify-center").style("min-height: 100vh"):
        with ui.card().classes("w-80 max-w-full q-pa-lg"):
            with ui.row().classes("items-center gap-2 justify-center w-full"):
                ui.icon("school", color="primary").classes("text-3xl")
                ui.label("SysAVA").classes("text-h5 text-primary")

            ui.label("Acesse sua conta").classes("text-subtitle1 text-grey-7 self-center q-mb-md")

            login_input = ui.input("RA ou usuário").classes("w-full").props(
                "outlined dense autofocus"
            )
            senha_input = ui.input(
                "Senha", password=True, password_toggle_button=True
            ).classes("w-full").props("outlined dense")

            def entrar() -> None:
                _tentar_entrar(login_input, senha_input)

            senha_input.on("keydown.enter", entrar)

            ui.button("Entrar", icon="login", on_click=entrar).classes("w-full q-mt-sm")

            ui.label("Use o RA (somente números) ou o usuário cadastrado.").classes(
                "text-caption text-grey-6 self-center text-center q-mt-sm"
            )
