"""
Sessão, middleware e proteção de rotas (NiceGUI).

- Sessão: `app.storage.user` (exige `storage_secret` no `ui.run`).
- `MiddlewareAutenticacao`: exige login em todas as rotas, exceto `/login` e os
  caminhos internos do NiceGUI (`/_nicegui`). Também bloqueia as rotas
  restritas (`core.auth.ROTAS_RESTRITAS`) para alunos.
"""

from __future__ import annotations

from nicegui import app, ui
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from core import auth, state

CAMINHO_LOGIN = "/login"
PREFIXO_INTERNO = "/_nicegui"
CAMINHOS_LIVRES = {CAMINHO_LOGIN, "/sync", "/syncing", "/favicon.ico"}


# --------------------------------------------------------------------------
# Sessão
# --------------------------------------------------------------------------
def usuario_atual() -> dict | None:
    """Usuário logado (ou None). Lê de `app.storage.user`."""
    dados = app.storage.user
    if not dados.get("autenticado"):
        return None
    return {
        "username": dados.get("username"),
        "name": dados.get("name"),
        "ra": dados.get("ra"),
        "role": dados.get("role"),
    }


def papel_atual() -> str | None:
    usuario = usuario_atual()
    return usuario.get("role") if usuario else None


def sessao_valida() -> bool:
    """Autenticado e com um papel reconhecido (evita redirecionamento circular)."""
    dados = app.storage.user
    return bool(dados.get("autenticado")) and dados.get("role") in auth.PAPEIS


def entrar(usuario: dict) -> None:
    """Grava os dados do usuário na sessão."""
    app.storage.user.update(
        {
            "autenticado": True,
            "username": usuario.get("username"),
            "name": usuario.get("name"),
            "ra": usuario.get("ra"),
            "role": usuario.get("role"),
        }
    )


def sair() -> None:
    """Encerra a sessão (mantém o destino pendente, se houver)."""
    app.storage.user.clear()


def definir_destino(caminho: str | None) -> None:
    app.storage.user["destino"] = caminho or ""


def consumir_destino() -> str | None:
    destino = app.storage.user.get("destino") or ""
    app.storage.user["destino"] = ""
    return destino or None


def sair_e_ir_para_login() -> None:
    """Registra a saída, limpa a sessão e volta para o login."""
    usuario = usuario_atual()
    if usuario and usuario.get("username"):
        auth.registrar_atividade(usuario["username"], "Saiu do SysAVA")
    sair()
    ui.navigate.to(CAMINHO_LOGIN)


# --------------------------------------------------------------------------
# Middleware
# --------------------------------------------------------------------------
class MiddlewareAutenticacao(BaseHTTPMiddleware):
    """Exige login e aplica as restrições de papel por rota."""

    async def dispatch(self, request, call_next):
        caminho = request.url.path

        if caminho.startswith(PREFIXO_INTERNO) or caminho in CAMINHOS_LIVRES:
            return await call_next(request)

        # Enquanto o sync inicial não termina, redireciona para /syncing
        if not state.sync_pronta.is_set():
            if caminho != "/syncing":
                return RedirectResponse("/syncing")
            return await call_next(request)

        sessao = app.storage.user
        if not sessao.get("autenticado") or sessao.get("role") not in auth.PAPEIS:
            definir_destino(caminho)
            return RedirectResponse(CAMINHO_LOGIN)

        papel = sessao.get("role")
        if not auth.pode_acessar(papel, caminho):
            return RedirectResponse(auth.rota_inicial(papel))

        return await call_next(request)


def instalar() -> None:
    """Registra o middleware de autenticação no app."""
    app.add_middleware(MiddlewareAutenticacao)
