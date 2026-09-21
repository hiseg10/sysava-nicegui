"""
Layout compartilhado: cabeçalho responsivo, menu lateral e navegação por papel.

No desktop os links ficam agrupados em menus suspensos (Ensino/Gestão/Sistema)
para não estourar a largura; no mobile tudo vai para o menu lateral. A
visibilidade usa as classes responsivas do Quasar (`gt-sm`/`lt-md`).

Inclui um botão flutuante de acesso rápido para consultar RA e notas
dos alunos sem sair da página atual.
"""

from __future__ import annotations

from nicegui import ui, app

from core import auth, repositories as repo
from ui import security

PAPEIS_TODOS = (auth.PAPEL_ALUNO, auth.PAPEL_PROFESSOR, auth.PAPEL_ADMIN)
PAPEIS_STAFF = (auth.PAPEL_PROFESSOR, auth.PAPEL_ADMIN)

# (rota, rótulo, ícone, papéis com acesso, grupo | None)
LINKS = [
    ("/aluno", "Início", "home", (auth.PAPEL_ALUNO,), None),
    ("/aulas", "Aulas", "menu_book", PAPEIS_TODOS, "Ensino"),
    ("/pontos", "Pontos", "stars", PAPEIS_TODOS, "Ensino"),
    ("/provas", "Provas", "quiz", PAPEIS_TODOS, "Ensino"),
    ("/frequencia", "Frequência", "checklist", PAPEIS_STAFF, "Ensino"),
    ("/dashboard", "Dashboard", "dashboard", PAPEIS_STAFF, "Gestão"),
    ("/manage-turmas", "Turmas", "groups", PAPEIS_STAFF, "Gestão"),
    ("/radar", "Radar de Atrito", "radar", PAPEIS_STAFF, "Gestão"),
    ("/sync", "Sincronização", "cloud_sync", PAPEIS_STAFF, "Sistema"),
    ("/config", "Configuração", "settings", PAPEIS_STAFF, "Sistema"),
    ("/database", "Banco de Dados", "storage", PAPEIS_STAFF, "Sistema"),
    ("/perfil", "Meu Perfil", "person", PAPEIS_TODOS, None),
]

ICONE_GRUPO = {
    "Ensino": "school",
    "Gestão": "insights",
    "Sistema": "tune",
}


def _estrutura(papel: str | None) -> list[tuple]:
    """
    Estrutura de navegação do papel, na ordem de `LINKS`:

        ("link", (rota, rótulo, ícone))
        ("grupo", nome, [(rota, rótulo, ícone), ...])
    """
    entradas: list[tuple] = []
    indice_grupo: dict[str, int] = {}

    for rota, rotulo, icone, papeis, grupo in LINKS:
        if papel not in papeis:
            continue
        if grupo is None:
            entradas.append(("link", (rota, rotulo, icone)))
            continue
        if grupo not in indice_grupo:
            indice_grupo[grupo] = len(entradas)
            entradas.append(("grupo", grupo, []))
        entradas[indice_grupo[grupo]][2].append((rota, rotulo, icone))

    return entradas


def _props_botao(ativo: bool) -> str:
    return (
        "unelevated dense no-caps color=white text-color=primary"
        if ativo
        else "flat dense no-caps color=white"
    )


def _menu_usuario(usuario: dict) -> None:
    """Nome (desktop) + avatar com papel e a opção de sair."""
    nome = auth.nome_exibicao(usuario) or "Conta"
    papel = auth.ROTULO_PAPEL.get(usuario.get("role"), usuario.get("role") or "")

    ui.label(nome).classes("gt-sm text-body2 q-mr-xs")
    with ui.button(icon="account_circle").props("flat color=white round"):
        with ui.menu().classes("min-w-48"):
            with ui.column().classes("q-pa-sm gap-0"):
                ui.label(usuario.get("name") or usuario.get("username") or "").classes(
                    "font-medium"
                )
                ui.label(papel).classes("text-caption text-grey-7")
            ui.separator()
            ui.menu_item("Meu Perfil", on_click=lambda: ui.navigate.to("/perfil")).props("icon=person")
            ui.menu_item("Sair", on_click=security.sair_e_ir_para_login).props("icon=logout")


def _drawer(entradas: list[tuple], ativo: str | None, gaveta) -> None:
    """Menu lateral (mobile): links agrupados com destaque do item atual."""

    def ir_para(rota: str) -> None:
        gaveta.value = False
        ui.navigate.to(rota)

    with gaveta:
        ui.label("Menu").classes("text-subtitle2 text-grey-7 q-pa-sm")
        for entrada in entradas:
            if entrada[0] == "link":
                rota, rotulo, icone = entrada[1]
                ui.button(rotulo, icon=icone, on_click=lambda r=rota: ir_para(r)).props(
                    "flat align=left no-caps" + (" color=primary" if rota == ativo else "")
                ).classes("w-full")
            else:
                _, nome, itens = entrada
                ui.label(nome).classes("text-caption text-grey-6 q-pa-sm q-pt-md")
                for rota, rotulo, icone in itens:
                    ui.button(rotulo, icon=icone, on_click=lambda r=rota: ir_para(r)).props(
                        "flat align=left no-caps"
                        + (" color=primary" if rota == ativo else "")
                    ).classes("w-full")


def _links_desktop(entradas: list[tuple], ativo: str | None) -> None:
    """Links do cabeçalho: itens soltos e grupos em menu suspenso."""
    for entrada in entradas:
        if entrada[0] == "link":
            rota, rotulo, icone = entrada[1]
            ui.button(rotulo, icon=icone, on_click=lambda r=rota: ui.navigate.to(r)).props(
                _props_botao(rota == ativo)
            )
        else:
            _, nome, itens = entrada
            grupo_ativo = any(rota == ativo for rota, _, _ in itens)
            with ui.button(nome, icon=ICONE_GRUPO.get(nome, "apps")).props(
                _props_botao(grupo_ativo)
            ):
                with ui.menu().classes("min-w-44"):
                    for rota, rotulo, icone in itens:
                        item = ui.menu_item(
                            rotulo, on_click=lambda r=rota: ui.navigate.to(r)
                        ).props(f"icon={icone}")
                        if rota == ativo:
                            item.props("active")


def navegacao(ativo: str | None = None) -> None:
    """Cabeçalho (desktop) + menu lateral (mobile), filtrados pelo papel."""
    usuario = security.usuario_atual()
    papel = usuario.get("role") if usuario else None
    entradas = _estrutura(papel)

    dark_pref = app.storage.user.get("dark_mode", False)
    dark = ui.dark_mode(dark_pref)

    font_size = app.storage.user.get("font_size", "14px")
    font_family = app.storage.user.get("font_family", "sans-serif")
    ui.query("body").style(f"font-size: {font_size}; font-family: {font_family};")

    def _toggle_dark(btn) -> None:
        dark.toggle()
        app.storage.user["dark_mode"] = dark.value is True
        btn.props(f"icon={'light_mode' if dark.value else 'dark_mode'}")

    with ui.left_drawer(value=False, bordered=True) as gaveta:
        _drawer(entradas, ativo, gaveta)

    with ui.header().classes("items-center bg-primary text-white").style(
        "min-height: 56px; padding: 2px 10px; flex-wrap: nowrap"
    ):
        ui.button(icon="menu", on_click=gaveta.toggle).props("flat color=white round").classes(
            "lt-md"
        )
        ui.button(
            "SysAVA", on_click=lambda: ui.navigate.to(auth.rota_inicial(papel))
        ).props("flat no-caps color=white").classes("text-h6")

        with ui.row().classes("gt-sm items-center gap-1 q-ml-md"):
            _links_desktop(entradas, ativo)

        ui.space()

        theme_btn = ui.button(
            icon="dark_mode" if not dark_pref else "light_mode",
        ).props("flat color=white round").classes("q-mr-sm")
        theme_btn.on("click", lambda: _toggle_dark(theme_btn))

        _montar_acesso_rapido() if usuario else None

        if usuario:
            _menu_usuario(usuario)


def inicio_pagina(titulo: str, subtitulo: str | None = None, ativo: str | None = None) -> None:
    """Renderiza a navegação e o título da página."""
    navegacao(ativo)
    ui.label(titulo).classes("text-h4 q-mt-sm")
    if subtitulo:
        ui.label(subtitulo).classes("text-subtitle1 text-grey-7")


def rodape_navegacao(*botoes: tuple[str, str, str]) -> None:
    """Adiciona um rodapé com botões de navegação entre páginas.

    Cada botão é uma tupla (rótulo, ícone, rota).
    Exemplos:
        rodape_navegacao(
            ("Aulas", "menu_book", "/aulas"),
            ("Pontos", "stars", "/pontos"),
        )
    """
    ui.separator().classes("q-mt-lg")
    with ui.row().classes("items-center gap-2 flex-wrap q-mt-sm"):
        ui.label("Navegação:").classes("text-caption text-grey-7")
        for rotulo, icone, rota in botoes:
            ui.button(
                rotulo, icon=icone,
                on_click=lambda r=rota: ui.navigate.to(r),
            ).props("flat dense no-caps")


# --------------------------------------------------------------------------
# Acesso rápido (botão flutuante)
# --------------------------------------------------------------------------
def _formatar_nota(valor) -> str:
    if valor is None or valor == "":
        return "-"
    try:
        return f"{float(valor):.1f}"
    except (TypeError, ValueError):
        return str(valor)


def _montar_acesso_rapido() -> None:
    """Botão flutuante (FAB) com acesso rápido por turma.

    Fluxo: selecionar turma → escolher consulta (RA, Notas, etc.)
    """
    from core import turmas as turmas_svc, scores, repositories

    dlg = ui.dialog().classes("no-scroll")

    with dlg, ui.card().classes("w-full max-w-5xl max-h-[85vh]"):
        ui.label("Acesso Rápido por Turma").classes("text-h6")

        turmas = turmas_svc.listar_turmas()
        opcoes_t = {str(t["id"]): f"{t.get('name', '')} ({t.get('alunos', 0)} alunos)" for t in turmas}
        sel_turma = ui.select(opcoes_t, label="Selecionar Turma", on_change=lambda e: _ao_mudar_turma(e.value)).classes("w-full")

        ui.separator().classes("q-my-sm")

        ops = ui.row().classes("gap-2 q-mb-sm")
        Conteudo = ui.column().classes("w-full gap-2")

        def _ao_mudar_turma(turma_id):
            Conteudo.clear()
            ops.clear()
            if not turma_id:
                return
            with ops:
                ui.button("RA dos Alunos", icon="badge", on_click=lambda: _mostrar_ra(turma_id)).props("outline dense")
                ui.button("Notas", icon="grade", on_click=lambda: _mostrar_notas(turma_id)).props("outline dense")
                ui.button("Frequencia", icon="checklist", on_click=lambda: _mostrar_freq(turma_id)).props("outline dense")
                ui.button("Pontos", icon="stars", on_click=lambda: _mostrar_pontos(turma_id)).props("outline dense")

        def _mostrar_ra(turma_id):
            Conteudo.clear()
            with Conteudo:
                ui.label("RA dos Alunos").classes("text-subtitle1")
                alunos = repositories.listar_alunos_da_turma(turma_id)
                if not alunos:
                    ui.label("Nenhum aluno matriculado.").classes("text-grey-7")
                    return
                colunas = [
                    {"name": "nome", "label": "Nome", "field": "name", "align": "left", "sortable": True},
                    {"name": "ra", "label": "RA", "field": "ra", "align": "left", "sortable": True},
                    {"name": "username", "label": "Username", "field": "username", "align": "left"},
                ]
                rows = [
                    {"_idx": i, "name": a.get("name", ""), "ra": a.get("ra", ""), "username": a.get("username", "")}
                    for i, a in enumerate(alunos)
                ]
                ui.table(columns=colunas, rows=rows, row_key="_idx", pagination=15) \
                    .classes("w-full").props("dense flat bordered")

        def _mostrar_notas(turma_id):
            Conteudo.clear()
            with Conteudo:
                ui.label("Notas por Disciplina").classes("text-subtitle1")
                disciplinas = repositories.listar_disciplinas_da_turma(turma_id)
                if not disciplinas:
                    ui.label("Nenhuma disciplina vinculada a esta turma.").classes("text-grey-7")
                    return
                opcoes_d = {str(d["id"]): f"{d.get('name', '')} ({d.get('duration_type', 'N/A')})" for d in disciplinas}
                sel_disc = ui.select(opcoes_d, label="Disciplina", on_change=lambda e: _carregar_notas(turma_id, e.value)).classes("w-full")

                tabela_notas = ui.column().classes("w-full")

                def _carregar_notas(tid, did):
                    tabela_notas.clear()
                    if not did:
                        return

                    # Verifica se é modular
                    disc_info = next((d for d in disciplinas if str(d["id"]) == str(did)), None)
                    is_modular = (disc_info or {}).get("duration_type", "").lower() == "mensal"

                    alunos = repositories.listar_alunos_da_turma(tid)
                    if not alunos:
                        with tabela_notas:
                            ui.label("Nenhum aluno matriculado.").classes("text-grey-7")
                        return

                    with tabela_notas:
                        if is_modular:
                            ui.label("Disciplina Modular (Mensal) - Notas replicadas de T1 para T2 e T3").classes("text-caption text-orange")
                        else:
                            ui.label("Disciplina Anual - Cada trimestre tem notas próprias").classes("text-caption text-blue")
                        ui.label("NM = Avaliação + Participação + Qualitativos  |  NM3 usa média das participações").classes("text-caption text-grey-7")
                        cols = [
                            {"name": "nome", "label": "Aluno", "field": "nome", "align": "left", "sortable": True},
                            {"name": "quali", "label": "Quali.", "field": "quali", "align": "center", "sortable": True},
                            {"name": "av1", "label": "Av.NM1", "field": "av1", "align": "center", "sortable": True},
                            {"name": "p1", "label": "Part.1", "field": "p1", "align": "center", "sortable": True},
                            {"name": "nm1", "label": "NM1", "field": "nm1", "align": "center", "sortable": True},
                            {"name": "av2", "label": "Av.NM2", "field": "av2", "align": "center", "sortable": True},
                            {"name": "p2", "label": "Part.2", "field": "p2", "align": "center", "sortable": True},
                            {"name": "nm2", "label": "NM2", "field": "nm2", "align": "center", "sortable": True},
                            {"name": "av3", "label": "Av.NM3", "field": "av3", "align": "center", "sortable": True},
                            {"name": "p3", "label": "Méd.Part", "field": "p3", "align": "center", "sortable": True},
                            {"name": "nm3", "label": "NM3", "field": "nm3", "align": "center", "sortable": True},
                        ]
                        rows = []
                        for i, a in enumerate(alunos):
                            r = scores.resumo_pontos(a.get("username"), subject_id=did)
                            det = next((d for d in r.get("por_disciplina", []) if str(d["subject_id"]) == str(did)), {})
                            p1 = det.get("participacao_nm1", 0)
                            p2 = det.get("participacao_nm2", 0)
                            p3 = round(min((p1 + p2) / 2, 3), 2)
                            rows.append({
                                "_idx": i,
                                "nome": a.get("name", ""),
                                "quali": _formatar_nota(det.get("qualitativo")),
                                "av1": _formatar_nota(det.get("avaliacao_nm1")),
                                "p1": _formatar_nota(p1),
                                "nm1": _formatar_nota(det.get("nm1")),
                                "av2": _formatar_nota(det.get("avaliacao_nm2")),
                                "p2": _formatar_nota(p2),
                                "nm2": _formatar_nota(det.get("nm2")),
                                "av3": _formatar_nota(det.get("avaliacao_nm3")),
                                "p3": _formatar_nota(p3),
                                "nm3": _formatar_nota(det.get("nm3")),
                            })
                        ui.table(columns=cols, rows=rows, row_key="_idx", pagination=15) \
                            .classes("w-full").props("dense flat bordered")

        def _mostrar_freq(turma_id):
            Conteudo.clear()
            with Conteudo:
                ui.label("Frequencia (em breve)").classes("text-subtitle1 text-grey-7")

        def _mostrar_pontos(turma_id):
            Conteudo.clear()
            with Conteudo:
                ui.label("Pontos por Disciplina").classes("text-subtitle1")
                disciplinas = repositories.listar_disciplinas_da_turma(turma_id)
                if not disciplinas:
                    ui.label("Nenhuma disciplina vinculada a esta turma.").classes("text-grey-7")
                    return
                opcoes_d = {str(d["id"]): f"{d.get('name', '')} ({d.get('duration_type', 'N/A')})" for d in disciplinas}
                sel_disc = ui.select(opcoes_d, label="Disciplina", on_change=lambda e: _carregar_pontos(turma_id, e.value)).classes("w-full")

                tabela_pontos = ui.column().classes("w-full")

                def _carregar_pontos(tid, did):
                    tabela_pontos.clear()
                    if not did:
                        return

                    # Verifica se é modular
                    disc_info = next((d for d in disciplinas if str(d["id"]) == str(did)), None)
                    is_modular = (disc_info or {}).get("duration_type", "").lower() == "mensal"

                    alunos = repositories.listar_alunos_da_turma(tid)
                    if not alunos:
                        with tabela_pontos:
                            ui.label("Nenhum aluno matriculado.").classes("text-grey-7")
                        return

                    with tabela_pontos:
                        if is_modular:
                            ui.label("Disciplina Modular (Mensal) - Participação replicada de T1 para T2 e T3").classes("text-caption text-orange")
                        else:
                            ui.label("Disciplina Anual - Participação por trimestre").classes("text-caption text-blue")
                        cols = [
                            {"name": "nome", "label": "Aluno", "field": "nome", "align": "left", "sortable": True},
                            {"name": "aulas", "label": "Aulas", "field": "aulas", "align": "right", "sortable": True},
                            {"name": "quizzes", "label": "Quizzes", "field": "quizzes", "align": "right", "sortable": True},
                            {"name": "forum", "label": "Forum", "field": "forum", "align": "right", "sortable": True},
                            {"name": "p1", "label": "Part.1", "field": "p1", "align": "right", "sortable": True},
                            {"name": "p2", "label": "Part.2", "field": "p2", "align": "right", "sortable": True},
                            {"name": "p3", "label": "Méd.Part", "field": "p3", "align": "right", "sortable": True},
                            {"name": "nm1", "label": "NM1", "field": "nm1", "align": "right", "sortable": True},
                            {"name": "nm2", "label": "NM2", "field": "nm2", "align": "right", "sortable": True},
                            {"name": "nm3", "label": "NM3", "field": "nm3", "align": "right", "sortable": True},
                        ]
                        rows = []
                        for i, a in enumerate(alunos):
                            r = scores.resumo_pontos(a.get("username"), subject_id=did)
                            det = next((d for d in r.get("por_disciplina", []) if str(d["subject_id"]) == str(did)), {})
                            p1 = det.get("participacao_nm1", 0)
                            p2 = det.get("participacao_nm2", 0)
                            p3 = round(min((p1 + p2) / 2, 3), 2)
                            rows.append({
                                "_idx": i,
                                "nome": a.get("name", ""),
                                "aulas": det.get("aulas", 0),
                                "quizzes": det.get("quizzes", 0),
                                "forum": det.get("forum", 0),
                                "p1": f"{p1:.2f}",
                                "p2": f"{p2:.2f}",
                                "p3": f"{p3:.2f}",
                                "nm1": f"{det.get('nm1', 0):.2f}",
                                "nm2": f"{det.get('nm2', 0):.2f}",
                                "nm3": f"{det.get('nm3', 0):.2f}",
                            })
                        ui.table(columns=cols, rows=rows, row_key="_idx", pagination=15) \
                            .classes("w-full").props("dense flat bordered")

        ui.button("Fechar", icon="close", on_click=dlg.close).props("flat dense")

    return ui.button(icon="dashboard_customize", on_click=dlg.open) \
        .props("flat color=white round") \
        .tooltip("Acesso Rapido por Turma")
