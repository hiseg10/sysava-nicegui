"""
Ponto de entrada do SysAVA (NiceGUI).

Registra as páginas, instala o middleware de autenticação, trata erros globais
e sobe o servidor com sessão persistente (`storage_secret`).
"""

import logging
import os
import threading

from nicegui import app, ui

from core import auth, logs, repositories, sync
from ui import layout, security

# Sinaliza quando o sync inicial terminou (login/queries ficam indisponíveis até lá).
sync_pronta = threading.Event()

logs.configurar()
security.instalar()
log = logging.getLogger("sysava.startup")

# O decorador @ui.page, executado na importação, é o que registra cada rota.
from ui import aluno as aluno_view
from ui import aulas as aulas_view
from ui import config as config_view
from ui import database as database_view
from ui import frequencia as frequencia_view
from ui import friction as friction_view
from ui import forum as forum_view
from ui import login as login_view
from ui import manage_turmas as manage_turmas_view
from ui import pontos as pontos_view
from ui import perfil as perfil_view
from ui import provas as provas_view
from ui import quiz as quiz_view
from ui import sync as sync_view

_ = (
    aluno_view,
    aulas_view,
    config_view,
    database_view,
    frequencia_view,
    friction_view,
    forum_view,
    login_view,
    manage_turmas_view,
    pontos_view,
    perfil_view,
    provas_view,
    quiz_view,
    sync_view,
)

ROTULOS_CONTAGEM = {
    "app_users": "Usuários",
    "classes": "Turmas",
    "subjects": "Disciplinas",
    "lessons": "Aulas",
    "quizzes": "Quizzes",
    "quiz_questions": "Questões de quiz",
    "assessments": "Avaliações",
    "assessment_questions": "Questões de prova",
    "attendance": "Frequência",
    "student_enrollments": "Matrículas",
    "student_grades": "Notas",
    "forum_posts": "Posts no fórum",
}


def _pagina_erro(erro: Exception | None = None) -> None:
    """Página de erro exibida quando uma rota falha ao montar."""
    logs.registrar_excecao(erro, contexto="página")
    layout.inicio_pagina("Erro", "Não foi possível carregar esta página.")
    with ui.column().classes("q-pa-md items-center gap-2"):
        ui.icon("error", color="negative").classes("text-5xl")
        ui.label("Ocorreu um erro inesperado.").classes("text-h6")
        ui.label(str(erro) if erro else "").classes("text-grey-7 text-center max-w-2xl")
        ui.button("Voltar ao início", icon="home", on_click=lambda: ui.navigate.to("/"))


app.on_page_exception(_pagina_erro)
app.on_exception(lambda erro=None: logs.registrar_excecao(erro, contexto="evento"))


def _sync_inicial():
    """Faz sync completo do Supabase ao iniciar (banco vazio no Render free)."""
    try:
        info = sync.descrever_conexao()
        if not info.get("configurado"):
            log.warning("Supabase não configurado — sync inicial ignorado.")
            return
        log.info("Iniciando sync completo do Supabase...")
        resultado = sync.sincronizar(modo="full", backup=False)
        totais = (resultado or {}).get("totais") or {}
        log.info(
            "Sync inicial concluído: +%s / ~%s / %s erro(s)",
            totais.get("inseridos", 0),
            totais.get("atualizados", 0),
            totais.get("erros", 0),
        )
        # Re-executa migrações de colunas que só existem localmente
        # (a tabela foi criada pelo sync a partir do schema remoto).
        from core.turmas import _ensure_columns
        _ensure_columns()
    except Exception as erro:
        log.warning("Sync inicial falhou: %s", erro)
    finally:
        sync_pronta.set()


app.on_startup(lambda: threading.Thread(target=_sync_inicial, daemon=True).start())


def _push_ao_sair():
    """Envia dados locais de volta para o Supabase ao encerrar."""
    try:
        log.info("Enviando dados locais para o Supabase...")
        resultado = sync.push_para_supabase()
        total = (resultado or {}).get("total_enviados", 0)
        erros = (resultado or {}).get("total_erros", 0)
        log.info("Push concluído: %s enviado(s), %s erro(s)", total, erros)
    except Exception as erro:
        log.warning("Push ao sair falhou: %s", erro)


app.on_shutdown(_push_ao_sair)


@ui.page("/syncing")
def syncing_page():
    """Exibida enquanto o sync inicial roda no startup."""
    ui.add_head_html("<style>body { background: #f1f5f9; }</style>")
    with ui.column().classes("w-full items-center justify-center").style("min-height: 100vh"):
        ui.spinner(size="xl", color="primary")
        ui.label("Sincronizando dados com o servidor...").classes("text-h6 q-mt-md text-grey-7")
        ui.label("Isso leva alguns segundos no primeiro acesso.").classes("text-caption text-grey-6")
        ui.timer(2.0, lambda: ui.navigate.to("/syncing") if not sync_pronta.is_set() else ui.navigate.to("/login"))


@ui.page("/")
def home():
    """Encaminha para a página inicial do papel do usuário."""
    ui.navigate.to(auth.rota_inicial(security.papel_atual()))


@ui.page("/dashboard")
def dashboard():
    layout.inicio_pagina(
        "Dashboard",
        "Visão geral do SysAVA.",
        ativo="/dashboard",
    )

    contagens = repositories.contagens_gerais()
    with ui.row().classes("gap-3 q-mt-sm flex-wrap"):
        for chave in ("app_users", "classes", "subjects", "lessons", "attendance"):
            with ui.card().classes("items-center q-pa-md min-w-32"):
                ui.label(str(contagens.get(chave, 0))).classes("text-h5")
                ui.label(ROTULOS_CONTAGEM.get(chave, chave)).classes(
                    "text-caption text-grey-7 text-center"
                )

    with ui.row().classes("items-center gap-2 q-mt-md"):
        ui.button("Gerenciar Turmas", icon="groups", on_click=lambda: ui.navigate.to("/manage-turmas"))
        ui.button("Frequência", icon="checklist", on_click=lambda: ui.navigate.to("/frequencia"))
        ui.button("Radar de Atrito", icon="radar", on_click=lambda: ui.navigate.to("/radar"))
        ui.button("Sincronização", icon="cloud_sync", on_click=lambda: ui.navigate.to("/sync"))

    linhas = [
        {"tabela": ROTULOS_CONTAGEM.get(nome, nome), "registros": total}
        for nome, total in contagens.items()
    ]
    colunas = [
        {"name": "tabela", "label": "Tabela", "field": "tabela", "align": "left", "sortable": True},
        {"name": "registros", "label": "Registros", "field": "registros", "align": "right", "sortable": True},
    ]
    ui.table(columns=colunas, rows=linhas, row_key="tabela", pagination=15) \
        .classes("w-full max-w-3xl q-mt-md").props("dense flat bordered")


if __name__ == "__main__":
    ui.run(
        port=int(os.environ.get("PORT", 8080)),
        host="0.0.0.0",
        reload=False,
        storage_secret=auth.storage_secret(),
        title="SysAVA",
    )
