"""
Página "Sincronização": baixa o Supabase para o SQLite local.

Mantém o escola_ativa.db como cache local: mostra o status da conexão, o
resultado do último sync, uma auditoria de contagens (local × nuvem) e permite
sincronizar manualmente (incremental ou full, com dry-run e backup opcionais).
Também oferece agendamento diário.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from datetime import datetime

from nicegui import app, ui

from core import sync
from ui import layout

ROTULO_STATUS = {
    "ok": ("OK", "positive"),
    "sem_novidades": ("Sem novidades", "grey-7"),
    "dry-run": ("Simulação", "info"),
    "erro": ("Erro", "negative"),
}


def _formatar_quando(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        return iso


def _formatar_duracao(segundos) -> str:
    if segundos is None:
        return "-"
    try:
        return f"{float(segundos):.1f}s"
    except (TypeError, ValueError):
        return str(segundos)


def _tabela_auditoria(linhas: list[dict]) -> None:
    colunas = [
        {"name": "tabela", "label": "Tabela", "field": "tabela", "align": "left"},
        {"name": "remoto", "label": "Nuvem", "field": "remoto", "align": "right"},
        {"name": "local", "label": "Local", "field": "local", "align": "right"},
        {"name": "diferenca", "label": "Diferença", "field": "diferenca", "align": "right"},
        {"name": "status", "label": "Status", "field": "status", "align": "left"},
    ]
    registros = [
        {
            "tabela": item["tabela"],
            "remoto": item.get("remoto"),
            "local": item.get("local"),
            "diferenca": item.get("diferenca"),
            "status": item.get("erro") or item.get("status"),
        }
        for item in linhas
    ]
    ui.table(columns=colunas, rows=registros, row_key="tabela", pagination=15) \
        .classes("w-full max-w-4xl") \
        .props("dense flat bordered")


@ui.page("/sync")
def sync_page() -> None:
    """Página de sincronização Supabase -> SQLite."""
    fila: queue.Queue = queue.Queue()
    estado = {"rodando": False, "auditoria": None}

    layout.inicio_pagina(
        "Sincronização",
        "Baixa os dados do Supabase para o SQLite local (cache).",
        ativo="/sync",
    )

    # --- Conexão ---------------------------------------------------------------
    @ui.refreshable
    def card_conexao() -> None:
        info = sync.descrever_conexao()
        with ui.card().classes("w-full max-w-4xl"):
            with ui.row().classes("items-center gap-2"):
                if info["configurado"]:
                    ui.icon("cloud_done", color="positive").classes("text-2xl")
                    ui.label("Credenciais configuradas").classes("text-h6")
                else:
                    ui.icon("cloud_off", color="negative").classes("text-2xl")
                    ui.label("Credenciais ausentes").classes("text-h6 text-negative")

            with ui.column().classes("w-full gap-1"):
                with ui.row().classes("items-baseline gap-2"):
                    ui.label("Projeto:").classes("text-grey-7")
                    ui.label(info["host"] or "-").classes("font-medium")
                with ui.row().classes("items-baseline gap-2"):
                    ui.label("Arquivo .env:").classes("text-grey-7")
                    ui.label(info["env_file"]).classes("font-medium break-all")
                with ui.row().classes("items-baseline gap-2"):
                    ui.label("Chave:").classes("text-grey-7")
                    ui.label(info["chave"] or "-").classes("font-medium")

            if not info["configurado"]:
                ui.label(
                    "Defina SUPABASE_URL e SUPABASE_KEY em um arquivo .env na raiz do "
                    "projeto (ou aponte SYSAVA_ENV_FILE para o arquivo existente)."
                ).classes("text-warning")

    def testar_conexao() -> None:
        resultado = sync.testar_conexao()
        if resultado.get("ok"):
            ui.notify("Conexão com o Supabase OK.", type="positive")
        else:
            ui.notify(f"Falha na conexão: {resultado.get('erro')}", type="negative")

    card_conexao()
    with ui.row().classes("items-center q-gutter-sm"):
        ui.button("Testar conexão", icon="cloud_sync", on_click=testar_conexao).props("outline")
        ui.button("Recarregar status", icon="refresh", on_click=card_conexao.refresh).props("flat")

    # --- Controles de sincronização -------------------------------------------
    ui.separator()
    ui.label("Sincronizar agora").classes("text-h6")

    with ui.card().classes("w-full max-w-4xl"):
        with ui.row().classes("items-center gap-6 flex-wrap"):
            modo_select = ui.select(
                {"incremental": "Incremental (só o que mudou)", "full": "Completo (tudo)"},
                value="incremental",
                label="Modo",
            ).classes("w-64")
            backup_switch = ui.switch("Backup antes de gravar", value=True)
            dry_run_switch = ui.switch("Simular (dry-run)", value=False)

        barra = ui.linear_progress(value=0.0, show_value=False).classes("w-full")
        log = ui.log(max_lines=1000).classes("w-full h-64 rounded-borders").style(
            "background: #111; color: #ddd"
        )

        def _progresso(mensagem: str, fracao: float | None = None) -> None:
            fila.put(("log", mensagem))
            fila.put(("fracao", fracao))

        def _trabalho_sync() -> dict:
            return sync.sincronizar(
                modo=modo_select.value or "incremental",
                dry_run=bool(dry_run_switch.value),
                backup=bool(backup_switch.value),
                progresso=_progresso,
            )

        def _trabalho_auditoria() -> list[dict]:
            return sync.auditar(progresso=_progresso)

        def _rodar_em_thread(funcao, evento_fim: str) -> None:
            if estado["rodando"]:
                ui.notify("Já existe uma operação em andamento.", type="warning")
                return
            estado["rodando"] = True
            botao_sync.disable()
            botao_auditar.disable()
            barra.value = 0.0

            def alvo() -> None:
                try:
                    fila.put((evento_fim, funcao()))
                except Exception as erro:
                    fila.put(("erro", str(erro)))

            threading.Thread(target=alvo, daemon=True).start()

        def sincronizar_agora() -> None:
            log.clear()
            _rodar_em_thread(_trabalho_sync, "fim_sync")

        with ui.row().classes("items-center q-gutter-sm"):
            botao_sync = ui.button("Sincronizar", icon="cloud_download", on_click=sincronizar_agora)
            botao_auditar = ui.button(
                "Auditar contagens",
                icon="fact_check",
                on_click=lambda: (log.clear(), _rodar_em_thread(_trabalho_auditoria, "fim_auditoria")),
            ).props("outline")

    # --- Último sync -----------------------------------------------------------
    @ui.refreshable
    def card_ultimo_sync() -> None:
        dados = sync.carregar_estado()
        with ui.card().classes("w-full max-w-4xl"):
            ui.label("Último sync").classes("text-h6")
            if not dados:
                ui.label("Nenhuma sincronização registrada ainda.").classes("text-grey-7")
                return
            with ui.column().classes("w-full gap-1"):
                with ui.row().classes("items-baseline gap-2"):
                    ui.label("Quando:").classes("text-grey-7")
                    ui.label(_formatar_quando(dados.get("ultimo_sync"))).classes("font-medium")
                with ui.row().classes("items-baseline gap-2"):
                    ui.label("Modo:").classes("text-grey-7")
                    ui.label(str(dados.get("modo") or "-")).classes("font-medium")
                with ui.row().classes("items-baseline gap-2"):
                    ui.label("Duração:").classes("text-grey-7")
                    ui.label(_formatar_duracao(dados.get("duracao"))).classes("font-medium")
                with ui.row().classes("items-baseline gap-2"):
                    ui.label("Backup:").classes("text-grey-7")
                    ui.label(str(dados.get("backup") or "-")).classes("font-medium break-all")

            totais = dados.get("totais") or {}
            if totais:
                ui.label(
                    f"{totais.get('inseridos', 0)} inseridos · "
                    f"{totais.get('atualizados', 0)} atualizados · "
                    f"{totais.get('inalterados', 0)} inalterados · "
                    f"{totais.get('ignorados', 0)} ignorados · "
                    f"{totais.get('erros', 0)} erro(s)"
                ).classes("text-subtitle1")

            tabelas = dados.get("tabelas") or {}
            if tabelas:
                registros = []
                for nome, item in sorted(tabelas.items()):
                    registros.append({
                        "tabela": nome,
                        "remoto": item.get("remoto"),
                        "local_depois": item.get("local_depois"),
                        "inseridos": item.get("inseridos"),
                        "atualizados": item.get("atualizados"),
                        "ignorados": item.get("ignorados"),
                        "status": item.get("erro") or item.get("status"),
                    })
                colunas = [
                    {"name": "tabela", "label": "Tabela", "field": "tabela", "align": "left"},
                    {"name": "remoto", "label": "Nuvem", "field": "remoto", "align": "right"},
                    {"name": "local_depois", "label": "Local", "field": "local_depois", "align": "right"},
                    {"name": "inseridos", "label": "+", "field": "inseridos", "align": "right"},
                    {"name": "atualizados", "label": "~", "field": "atualizados", "align": "right"},
                    {"name": "ignorados", "label": "!", "field": "ignorados", "align": "right"},
                    {"name": "status", "label": "Status", "field": "status", "align": "left"},
                ]
                with ui.expansion("Detalhe por tabela", icon="table_chart").classes("w-full"):
                    ui.table(columns=colunas, rows=registros, row_key="tabela", pagination=15) \
                        .classes("w-full") \
                        .props("dense flat bordered")

    card_ultimo_sync()

    # --- Auditoria -------------------------------------------------------------
    @ui.refreshable
    def painel_auditoria() -> None:
        if estado["auditoria"] is None:
            return
        ui.label("Contagens (nuvem × local)").classes("text-subtitle1")
        _tabela_auditoria(estado["auditoria"])

    painel_auditoria()

    # --- Agendamento -----------------------------------------------------------
    ui.separator()
    ui.label("Agendamento").classes("text-h6")
    config = sync.carregar_config()
    agendamento = config.get("agendamento") or {}

    with ui.card().classes("w-full max-w-4xl"):
        with ui.row().classes("items-center gap-6 flex-wrap"):
            agendar_switch = ui.switch("Sincronizar automaticamente todo dia", value=bool(agendamento.get("ativo")))
            hora_input = ui.time(value=agendamento.get("hora") or "03:00").classes("w-40")

        def salvar_agendamento() -> None:
            sync.salvar_config({
                "agendamento": {
                    "ativo": bool(agendar_switch.value),
                    "hora": hora_input.value or "03:00",
                }
            })
            if agendar_switch.value:
                proxima = sync.proxima_execucao(hora_input.value or "03:00")
                ui.notify(
                    f"Agendamento ativo para {proxima.strftime('%d/%m %H:%M')} "
                    "(aplica-se a cada ciclo do servidor).",
                    type="positive",
                )
            else:
                ui.notify("Agendamento desativado.", type="info")

        ui.button("Salvar agendamento", icon="schedule", on_click=salvar_agendamento).props("outline")

    # --- Fila de eventos (worker -> UI) ---------------------------------------
    def drenar() -> None:
        while True:
            try:
                tipo, dado = fila.get_nowait()
            except queue.Empty:
                break

            if tipo == "log":
                log.push(str(dado))
            elif tipo == "fracao":
                if dado is not None:
                    barra.value = max(0.0, min(1.0, float(dado)))
            elif tipo == "fim_sync":
                estado["rodando"] = False
                botao_sync.enable()
                botao_auditar.enable()
                barra.value = 1.0
                totais = (dado or {}).get("totais") or {}
                prefixo = "Simulação" if (dado or {}).get("dry_run") else "Sincronização"
                ui.notify(
                    f"{prefixo} concluída: +{totais.get('inseridos', 0)} / "
                    f"~{totais.get('atualizados', 0)} / {totais.get('erros', 0)} erro(s)",
                    type="negative" if totais.get("erros") else "positive",
                )
                card_ultimo_sync.refresh()
            elif tipo == "fim_auditoria":
                estado["rodando"] = False
                botao_sync.enable()
                botao_auditar.enable()
                barra.value = 1.0
                estado["auditoria"] = dado
                painel_auditoria.refresh()
                ui.notify("Auditoria concluída.", type="positive")
            elif tipo == "erro":
                estado["rodando"] = False
                botao_sync.enable()
                botao_auditar.enable()
                barra.value = 0.0
                log.push(f"ERRO: {dado}")
                ui.notify(str(dado), type="negative")

    ui.timer(0.25, drenar)

    layout.rodape_navegacao(
        ("Configuração", "settings", "/config"),
        ("Banco de Dados", "storage", "/database"),
        ("Início", "home", "/aluno"),
    )


async def _agendador_loop() -> None:
    """Dispara o sync no horário configurado (verifica a cada minuto)."""
    while True:
        config = sync.carregar_config().get("agendamento") or {}
        if not config.get("ativo"):
            await asyncio.sleep(60)
            continue
        alvo = sync.proxima_execucao(config.get("hora") or "03:00")
        espera = max((alvo - datetime.now()).total_seconds(), 5)
        await asyncio.sleep(espera)
        try:
            await asyncio.to_thread(sync.sincronizar, modo="incremental", backup=True)
        except Exception:
            pass


def _iniciar_agendador() -> None:
    asyncio.create_task(_agendador_loop())


app.on_startup(_iniciar_agendador)
