"""
Página "Banco de Dados": conecta, testa e explora o escola_ativa.db.
"""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from core import db
from ui import layout


def _escolher_arquivo(caminho_inicial: str = "") -> str:
    """Abre o diálogo nativo do Windows para escolher um arquivo .db."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        pasta_inicial = ""
        if caminho_inicial:
            candidata = Path(caminho_inicial)
            pasta_inicial = str(candidata.parent if candidata.is_file() or candidata.suffix else candidata)

        raiz = tk.Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        raiz.update()
        caminho = filedialog.askopenfilename(
            title="Selecione o banco de dados SQLite",
            initialdir=pasta_inicial or None,
            filetypes=[("Bancos SQLite", "*.db *.sqlite *.sqlite3"), ("Todos os arquivos", "*.*")],
        )
        raiz.destroy()
        return caminho or ""
    except Exception as erro:  # pragma: no cover - depende do ambiente gráfico
        ui.notify(f"Não foi possível abrir o seletor de arquivos: {erro}", type="warning")
        return ""


def _formatar_valor(valor) -> str:
    """Converte valores do SQLite em texto curto para a pré-visualização."""
    if valor is None:
        return ""
    if isinstance(valor, (bytes, bytearray)):
        return f"<{len(valor)} bytes>"
    texto = str(valor)
    return texto if len(texto) <= 80 else texto[:77] + "..."


def _linha(rotulo: str, valor: str) -> None:
    with ui.row().classes("items-baseline gap-2"):
        ui.label(f"{rotulo}:").classes("text-grey-7")
        ui.label(valor or "-").classes("font-medium break-all")


@ui.page("/database")
def database_page() -> None:
    """Página de gerenciamento da conexão com o banco de dados."""
    estado = {"tabela": None}

    layout.inicio_pagina(
        "Banco de Dados",
        "Conecte, teste e explore o banco SQLite do SysAVA.",
        ativo="/database",
    )

    entrada_caminho = ui.input(
        "Caminho do arquivo .db",
        value=str(db.caminho_atual()),
    ).classes("w-full max-w-4xl")

    # --- Ações -----------------------------------------------------------------
    def escolher_arquivo() -> None:
        caminho = _escolher_arquivo(entrada_caminho.value or "")
        if caminho:
            entrada_caminho.value = caminho

    def testar_conexao() -> None:
        info = db.testar(entrada_caminho.value)
        if info["ok"]:
            ui.notify(
                f"Conexão OK — {info['tabelas']} tabela(s), {db.formatar_tamanho(info['tamanho'])}",
                type="positive",
            )
        else:
            motivo = info["erro"] or ("arquivo não encontrado" if not info["existe"] else "falha desconhecida")
            ui.notify(f"Falha na conexão: {motivo}", type="negative")

    def salvar_e_conectar() -> None:
        caminho = (entrada_caminho.value or "").strip()
        if not caminho:
            ui.notify("Informe o caminho do banco de dados.", type="warning")
            return

        info = db.testar(caminho)
        if not info["ok"]:
            ui.notify(f"Não foi possível conectar: {info['erro'] or 'verifique o caminho'}", type="negative")
            return

        db.definir_caminho(caminho)
        estado["tabela"] = None
        entrada_caminho.value = str(db.caminho_atual())
        card_conexao.refresh()
        painel_tabelas.refresh()
        ui.notify("Banco conectado e salvo como padrão.", type="positive")

    def usar_padrao() -> None:
        db.restaurar_padrao()
        estado["tabela"] = None
        entrada_caminho.value = str(db.caminho_atual())
        card_conexao.refresh()
        painel_tabelas.refresh()
        ui.notify("Caminho restaurado para o banco padrão do SysAVA.", type="info")

    with ui.row().classes("items-center q-gutter-sm mt-2"):
        ui.button("Procurar...", icon="folder_open", on_click=escolher_arquivo).props("outline")
        ui.button("Testar conexão", icon="fact_check", on_click=testar_conexao).props("outline")
        ui.button("Conectar", icon="link", on_click=salvar_e_conectar)
        ui.button("Usar padrão", icon="restore", on_click=usar_padrao).props("flat")

    # --- Status da conexão -----------------------------------------------------
    @ui.refreshable
    def card_conexao() -> None:
        info = db.testar(db.caminho_atual())

        with ui.card().classes("w-full max-w-4xl"):
            with ui.row().classes("items-center gap-2"):
                if info["ok"]:
                    ui.icon("check_circle", color="positive").classes("text-2xl")
                    ui.label("Conectado").classes("text-h6 text-positive")
                else:
                    ui.icon("cancel", color="negative").classes("text-2xl")
                    ui.label("Sem conexão").classes("text-h6 text-negative")

            with ui.column().classes("w-full gap-1"):
                _linha("Arquivo", info["caminho"])
                _linha("Tamanho", db.formatar_tamanho(info["tamanho"]) if info["existe"] else "-")
                _linha("Modificado", info["modificado"] or "-")
                _linha("Tabelas", str(info["tabelas"]))
                _linha("SQLite", info["versao_sqlite"])
                if info["erro"]:
                    _linha("Erro", info["erro"])

    card_conexao()

    # --- Tabelas ---------------------------------------------------------------
    ui.separator()
    ui.label("Tabelas").classes("text-h6")

    @ui.refreshable
    def painel_tabelas() -> None:
        info = db.testar(db.caminho_atual())
        if not info["ok"]:
            ui.label("Conecte a um banco válido para listar as tabelas.").classes("text-grey-7")
            return

        try:
            with db.abrir() as con:
                tabelas = db.listar_tabelas(con)
        except Exception as erro:
            ui.label(f"Erro ao ler as tabelas: {erro}").classes("text-negative")
            return

        if not tabelas:
            ui.label("Nenhuma tabela encontrada neste banco.").classes("text-grey-7")
            return

        if estado["tabela"] not in tabelas:
            estado["tabela"] = tabelas[0]

        with ui.row().classes("items-center gap-4"):
            ui.select(
                tabelas,
                value=estado["tabela"],
                label="Tabela",
                on_change=lambda evento: (estado.update(tabela=evento.value), painel_detalhe.refresh()),
            ).classes("w-80")
            ui.label(f"{len(tabelas)} tabela(s)").classes("text-grey-7")

        painel_detalhe()

    @ui.refreshable
    def painel_detalhe() -> None:
        nome = estado["tabela"]
        if not nome:
            return

        try:
            with db.abrir() as con:
                info = db.info_tabela(con, nome)
                colunas, linhas = db.previsualizar(con, nome)
        except Exception as erro:
            ui.label(f"Erro ao ler a tabela '{nome}': {erro}").classes("text-negative")
            return

        ui.label(f"{nome} — {info['linhas']} registro(s), {len(info['colunas'])} coluna(s)").classes("text-subtitle1")

        # Colunas
        with ui.row().classes("gap-1 flex-wrap"):
            for coluna in info["colunas"]:
                texto = f"{coluna['name']} ({coluna['type'] or 'sem tipo'})"
                cor = "primary" if coluna.get("pk") else "grey-7"
                chip = ui.chip(texto, color=cor if coluna.get("pk") else None).props("outline dense")
                if coluna.get("pk"):
                    chip.props("icon=key")

        # Pré-visualização
        if not colunas:
            ui.label("Tabela sem colunas para pré-visualizar.").classes("text-grey-7")
            return

        linhas_tabela = [
            {"_idx": indice, **{coluna: _formatar_valor(valor) for coluna, valor in zip(colunas, linha)}}
            for indice, linha in enumerate(linhas)
        ]
        colunas_tabela = [{"name": "_idx", "label": "#", "field": "_idx", "align": "left"}] + [
            {"name": coluna, "label": coluna, "field": coluna, "align": "left"} for coluna in colunas
        ]

        ui.table(columns=colunas_tabela, rows=linhas_tabela, row_key="_idx", pagination=10) \
            .classes("w-full max-w-6xl") \
            .props("dense flat bordered wrap-cells")

        ui.label(f"Mostrando até {len(linhas)} registro(s).").classes("text-caption text-grey-7")

        with ui.expansion("Ver SQL de criação", icon="code").classes("w-full max-w-4xl"):
            ui.code(info["sql"] or "-- SQL não disponível").classes("w-full")

    painel_tabelas()

    layout.rodape_navegacao(
        ("Configuração", "settings", "/config"),
        ("Sincronização", "cloud_sync", "/sync"),
        ("Início", "home", "/aluno"),
    )
