"""
Página "Configuração": `settings` editável e `master_config` (leitura).
"""

from __future__ import annotations

import json

from nicegui import ui

from core import parsing, settings
from ui import layout


@ui.page("/config")
def config_page() -> None:
    layout.inicio_pagina(
        "Configuração",
        "Parâmetros do SysAVA e configurações mestras.",
        ativo="/config",
    )

    estado: dict = {"chave": None}

    # --- Diálogo de edição ----------------------------------------------------
    dialogo = ui.dialog()
    with dialogo, ui.card().classes("w-full max-w-2xl"):
        ui.label("Editar configuração").classes("text-h6")
        chave_label = ui.label("").classes("text-caption text-grey-7")
        valor_input = ui.textarea("Valor").classes("w-full").props("outlined autogrow")

        def salvar() -> None:
            chave = estado.get("chave")
            if chave and settings.salvar_setting(chave, valor_input.value or ""):
                ui.notify(f"'{chave}' atualizado.", type="positive")
                dialogo.close()
                painel_settings.refresh()
            else:
                ui.notify("Não foi possível salvar.", type="negative")

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Salvar", icon="save", on_click=salvar)

    def editar(item: dict) -> None:
        estado["chave"] = item.get("chave")
        chave_label.text = item.get("chave") or ""
        valor_input.value = str(item.get("valor") or "")
        dialogo.open()

    # --- Settings -------------------------------------------------------------
    @ui.refreshable
    def painel_settings() -> None:
        itens = settings.listar_settings()
        ui.label(f"Parâmetros ({len(itens)})").classes("text-h6")
        if not itens:
            ui.label("Nenhum parâmetro cadastrado.").classes("text-grey-7")
            return

        registros = [
            {
                "_idx": indice,
                "chave": item.get("chave"),
                "valor": str(item.get("valor") or ""),
                "descricao": item.get("descricao") or "",
                "atualizado": item.get("atualizado_em") or "",
            }
            for indice, item in enumerate(itens)
        ]
        colunas = [
            {"name": "chave", "label": "Chave", "field": "chave", "align": "left", "sortable": True},
            {"name": "valor", "label": "Valor", "field": "valor", "align": "left"},
            {"name": "descricao", "label": "Descrição", "field": "descricao", "align": "left"},
            {"name": "atualizado", "label": "Atualizado em", "field": "atualizado", "align": "left"},
            {"name": "acao", "label": "Ação", "field": "acao", "align": "center"},
        ]
        tabela = ui.table(columns=colunas, rows=registros, row_key="_idx", pagination=15) \
            .classes("w-full max-w-5xl").props("dense flat bordered wrap-cells")
        tabela.add_slot("body-cell-acao", """
            <q-td :props="props">
                <q-btn dense flat icon="edit" @click="$parent.$emit('editar', props.row)" />
            </q-td>
        """)
        tabela.on("editar", lambda evento: editar(itens[evento.args["_idx"]]))

    painel_settings()

    # --- master_config --------------------------------------------------------
    ui.separator().classes("q-mt-lg")
    itens_master = settings.listar_master_config()
    ui.label(f"Configurações mestras ({len(itens_master)})").classes("text-h6")
    if not itens_master:
        ui.label("Nenhuma configuração mestra encontrada.").classes("text-grey-7")
    else:
        for item in itens_master:
            with ui.expansion(f"{item['key']}  ·  {item['resumo']}", icon="settings").classes("w-full max-w-5xl"):
                valor = settings.obter_master_config(item["key"])
                dado = parsing.para_dict(valor) or parsing.para_lista(valor)
                if dado:
                    texto = json.dumps(dado, ensure_ascii=False, indent=2)
                else:
                    texto = str(valor or "")
                ui.code(texto[:20000]).classes("w-full").style("max-height: 24rem; overflow: auto")
                ui.button(
                    "Baixar JSON",
                    icon="download",
                    on_click=lambda k=item["key"], v=texto: ui.download(
                        v.encode("utf-8"), f"{k}"
                    ),
                ).props("outline dense")

    layout.rodape_navegacao(
        ("Sincronização", "cloud_sync", "/sync"),
        ("Banco de Dados", "storage", "/database"),
        ("Início", "home", "/aluno"),
    )
