"""
Gerenciamento de Turmas: CRUD de turmas, disciplinas e vinculos.
"""
from __future__ import annotations
from nicegui import ui
from core import auth, turmas as svc
from ui import layout, security


@ui.page("/manage-turmas")
def manage_turmas():
    usuario = security.usuario_atual() or {}
    papel = usuario.get("role")
    staff = papel in (auth.PAPEL_ADMIN, auth.PAPEL_PROFESSOR)
    layout.inicio_pagina(
        "Gerenciar Turmas",
        "Crie, edite ou remova turmas e disciplinas.",
        ativo="/manage-turmas",
    )
    if not staff:
        ui.label("Acesso restrito a administradores e professores.").classes("text-grey-7")
        return

    _secao_turmas()
    ui.separator().classes("q-mt-lg")
    _secao_disciplinas()
    ui.separator().classes("q-mt-lg")
    _secao_vinculos()

    layout.rodape_navegacao(
        ("Dashboard", "dashboard", "/dashboard"),
        ("Frequencia", "checklist", "/frequencia"),
        ("Inicio", "home", "/dashboard"),
    )


def _secao_turmas() -> None:
    ui.label("Turmas").classes("text-h6 q-mt-md")
    dlg = ui.dialog()
    est: dict = {"edit_id": None}
    with dlg, ui.card().classes("w-full max-w-lg"):
        ui.label("Turma").classes("text-h6")
        nome = ui.input("Nome", placeholder="Ex: 2 SERIE - Turma I-A").classes("w-full")
        codigo = ui.input("Codigo (iSeduc)", placeholder="Opcional").classes("w-full")
        tipo = ui.select(
            {"normal": "Normal (Anual)", "modular": "Modular (Mensal)"},
            value="normal", label="Tipo",
        ).classes("w-full")
        ano = ui.input("Ano letivo", value="2026").classes("w-full")

        def _salvar():
            if not nome.value or not nome.value.strip():
                ui.notify("Informe o nome.", type="warning")
                return
            if est["edit_id"]:
                svc.atualizar_turma(est["edit_id"], name=nome.value, code=codigo.value,
                                    tipo_turma=tipo.value, ano_letivo=ano.value)
                ui.notify("Turma atualizada!", type="positive")
            else:
                svc.criar_turma(nome.value, codigo.value or "", tipo.value or "normal", ano.value or "")
                ui.notify("Turma criada!", type="positive")
            dlg.close()
            painel.refresh()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Salvar", icon="save", on_click=_salvar)

    def _editar(t):
        est["edit_id"] = t["id"]
        nome.value = t.get("name", "")
        codigo.value = t.get("code", "")
        tipo.value = t.get("tipo_turma", "normal")
        ano.value = t.get("ano_letivo", "")
        dlg.open()

    def _nova():
        est["edit_id"] = None
        nome.value = ""
        codigo.value = ""
        tipo.value = "normal"
        ano.value = "2026"
        dlg.open()

    def _remover(t):
        svc.remover_turma(t["id"])
        ui.notify("Turma removida.", type="positive")
        painel.refresh()

    ui.button("Nova Turma", icon="add", on_click=_nova).props("outline")

    @ui.refreshable
    def painel():
        lista = svc.listar_turmas()
        if not lista:
            ui.label("Nenhuma turma cadastrada.").classes("text-grey-7 q-mt-sm")
            return
        cols = [
            {"name": "id", "label": "ID", "field": "id", "align": "left"},
            {"name": "name", "label": "Nome", "field": "name", "align": "left", "sortable": True},
            {"name": "code", "label": "Codigo", "field": "code", "align": "left"},
            {"name": "tipo", "label": "Tipo", "field": "tipo_turma", "align": "center"},
            {"name": "ano", "label": "Ano", "field": "ano_letivo", "align": "center"},
            {"name": "alunos", "label": "Alunos", "field": "alunos", "align": "right", "sortable": True},
            {"name": "acao", "label": "Acao", "field": "acao", "align": "center"},
        ]
        rows = [
            {
                "_idx": i, "id": t["id"], "name": t.get("name", ""),
                "code": t.get("code", ""),
                "tipo_turma": "Modular" if t.get("tipo_turma") == "modular" else "Normal",
                "ano_letivo": t.get("ano_letivo", ""),
                "alunos": t.get("alunos", 0),
            }
            for i, t in enumerate(lista)
        ]
        tb = ui.table(columns=cols, rows=rows, row_key="_idx", pagination=10) \
            .classes("w-full max-w-5xl").props("dense flat bordered")
        tb.add_slot("body-cell-acao", """
            <q-td :props="props">
                <q-btn dense flat icon="edit" @click="$parent.$emit('editar', props.row)" />
                <q-btn dense flat icon="delete" color="negative" @click="$parent.$emit('remover', props.row)" />
            </q-td>
        """)
        tb.on("editar", lambda e: _editar(lista[e.args["_idx"]]))
        tb.on("remover", lambda e: _remover(lista[e.args["_idx"]]))

    painel()


def _secao_disciplinas() -> None:
    ui.label("Disciplinas").classes("text-h6")
    dlg = ui.dialog()
    est: dict = {"edit_id": None}
    with dlg, ui.card().classes("w-full max-w-lg"):
        ui.label("Disciplina").classes("text-h6")
        nome = ui.input("Nome", placeholder="Ex: MATEMATICA").classes("w-full")
        tipo = ui.select(
            {"regular": "Regular", "training": "Treinamento"},
            value="regular", label="Tipo",
        ).classes("w-full")
        modularidade = ui.select(
            {"anual": "Anual", "mensal": "Mensal (Modular)"},
            value="anual", label="Modularidade",
        ).classes("w-full")
        carga = ui.number("Carga horaria (horas)", value=0, min=0, step=1).classes("w-full")
        status_select = ui.select(
            {"incompleta": "Incompleta", "completa": "Completa", "inativa": "Inativa"},
            value="incompleta", label="Status",
        ).classes("w-full")

        def _salvar():
            if not nome.value or not nome.value.strip():
                ui.notify("Informe o nome.", type="warning")
                return
            if est["edit_id"]:
                svc.atualizar_disciplina(est["edit_id"], name=nome.value, tipo=tipo.value,
                                         carga_horaria=int(carga.value or 0),
                                         duration_type=modularidade.value,
                                         status=status_select.value)
                ui.notify("Disciplina atualizada!", type="positive")
            else:
                svc.criar_disciplina(nome.value, tipo.value or "regular", int(carga.value or 0),
                                     modularidade.value or "anual", status_select.value or "incompleta")
                ui.notify("Disciplina criada!", type="positive")
            dlg.close()
            painel.refresh()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Salvar", icon="save", on_click=_salvar)

    def _editar(d):
        est["edit_id"] = d["id"]
        nome.value = d.get("name", "")
        tipo.value = d.get("type", "regular")
        modularidade.value = d.get("duration_type", "anual")
        carga.value = d.get("carga_horaria", 0) or 0
        status_select.value = d.get("status", "incompleta")
        dlg.open()

    def _nova():
        est["edit_id"] = None
        nome.value = ""
        tipo.value = "regular"
        modularidade.value = "anual"
        carga.value = 0
        status_select.value = "incompleta"
        dlg.open()

    def _remover(d):
        svc.remover_disciplina(d["id"])
        ui.notify("Disciplina removida.", type="positive")
        painel.refresh()

    def _alternar_status(d):
        novo_status = svc.alternar_status_disciplina(d["id"])
        if novo_status:
            ui.notify(f"Status alterado para: {novo_status.capitalize()}", type="positive")
            painel.refresh()
        else:
            ui.notify("Erro ao alterar status.", type="negative")

    ui.button("Nova Disciplina", icon="add", on_click=_nova).props("outline")

    @ui.refreshable
    def painel():
        lista = svc._ler_disciplinas()
        if not lista:
            ui.label("Nenhuma disciplina cadastrada.").classes("text-grey-7 q-mt-sm")
            return
        cols = [
            {"name": "id", "label": "ID", "field": "id", "align": "left"},
            {"name": "name", "label": "Nome", "field": "name", "align": "left", "sortable": True},
            {"name": "tipo", "label": "Tipo", "field": "type", "align": "center"},
            {"name": "modularidade", "label": "Modularidade", "field": "duration_type", "align": "center"},
            {"name": "carga", "label": "Carga Horaria", "field": "carga_horaria", "align": "right", "sortable": True},
            {"name": "status", "label": "Status", "field": "status", "align": "center"},
            {"name": "acao", "label": "Acao", "field": "acao", "align": "center"},
        ]
        
        status_cores = {
            "incompleta": "orange",
            "completa": "positive",
            "inativa": "grey",
        }
        
        rows = [
            {
                "_idx": i, "id": d["id"], "name": d.get("name", ""),
                "type": "Treinamento" if d.get("type") == "training" else "Regular",
                "duration_type": "Mensal" if d.get("duration_type") == "mensal" else "Anual",
                "carga_horaria": d.get("carga_horaria", 0) or 0,
                "status": (d.get("status") or "incompleta").capitalize(),
            }
            for i, d in enumerate(lista)
        ]
        tb = ui.table(columns=cols, rows=rows, row_key="_idx", pagination=10) \
            .classes("w-full max-w-6xl").props("dense flat bordered")
        tb.add_slot("body-cell-status", """
            <q-td :props="props">
                <q-badge :color="props.row.status === 'Completa' ? 'positive' : props.row.status === 'Inativa' ? 'grey' : 'orange'" :label="props.row.status" />
            </q-td>
        """)
        tb.add_slot("body-cell-acao", """
            <q-td :props="props">
                <q-btn dense flat icon="edit" @click="$parent.$emit('editar', props.row)" />
                <q-btn dense flat icon="swap_horiz" @click="$parent.$emit('alternar', props.row)" />
                <q-btn dense flat icon="delete" color="negative" @click="$parent.$emit('remover', props.row)" />
            </q-td>
        """)
        tb.on("editar", lambda e: _editar(lista[e.args["_idx"]]))
        tb.on("alternar", lambda e: _alternar_status(lista[e.args["_idx"]]))
        tb.on("remover", lambda e: _remover(lista[e.args["_idx"]]))

    painel()


def _secao_vinculos() -> None:
    ui.label("Vinculos Turma x Disciplina").classes("text-h6")
    turmas = svc.listar_turmas()
    if not turmas:
        ui.label("Cadastre turmas primeiro.").classes("text-grey-7")
        return

    opcoes_t = {str(t["id"]): t.get("name", "") for t in turmas}
    todas_disc = svc._ler_disciplinas()
    opcoes_d = {str(d["id"]): d.get("name", "") for d in todas_disc}

    with ui.row().classes("items-center gap-4 q-mt-sm flex-wrap"):
        sel_turma = ui.select(opcoes_t, label="Turma").classes("w-72")
        sel_disc = ui.select(opcoes_d, label="Disciplina").classes("w-72")

    def _vincular():
        if not sel_turma.value or not sel_disc.value:
            ui.notify("Selecione turma e disciplina.", type="warning")
            return
        svc.vincular_disciplina(int(sel_turma.value), int(sel_disc.value))
        ui.notify("Vinculo criado!", type="positive")
        lista_vinculos.refresh()

    def _desvincular():
        if not sel_turma.value or not sel_disc.value:
            ui.notify("Selecione turma e disciplina.", type="warning")
            return
        svc.desvincular_disciplina(int(sel_turma.value), int(sel_disc.value))
        ui.notify("Vinculo removido.", type="positive")
        lista_vinculos.refresh()

    with ui.row().classes("q-gutter-sm"):
        ui.button("Vincular", icon="link", on_click=_vincular).props("outline")
        ui.button("Desvincular", icon="link_off", on_click=_desvincular).props("outline color=negative")

    @ui.refreshable
    def lista_vinculos():
        if not sel_turma.value:
            ui.label("Selecione uma turma para ver os vinculos.").classes("text-grey-7 q-mt-sm")
            return
        vinculos = svc.listar_disciplinas_da_turma(int(sel_turma.value))
        if not vinculos:
            ui.label("Nenhuma disciplina vinculada.").classes("text-grey-7 q-mt-sm")
            return
        with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
            for d in vinculos:
                carga = d.get("carga_horaria", 0) or 0
                texto = f"{d.get('name', '')}"
                if carga:
                    texto += f" ({ carga}h)"
                ui.chip(texto, icon="school").props("outline")

    sel_turma.on_value_change(lambda e: lista_vinculos.refresh())
    lista_vinculos()
