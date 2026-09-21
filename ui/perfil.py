"""
Página "Perfil": configurações pessoais, notas, lembretes e histórico.

Acessível por todos os papéis (aluno, professor, admin).
"""

from __future__ import annotations

from nicegui import ui, app

from core import auth, scores, repositories as repo, user_profile
from ui import layout, security


def _cartao(titulo: str, valor, cor: str = "") -> None:
    with ui.card().classes("items-center q-pa-md min-w-28"):
        ui.label(str(valor)).classes(f"text-h5 {cor}".strip())
        ui.label(titulo).classes("text-caption text-grey-7 text-center")


def _formatar_nota(valor) -> str:
    if valor is None or valor == "":
        return "-"
    try:
        return f"{float(valor):.1f}"
    except (TypeError, ValueError):
        return str(valor)


PRIORIDADES = {
    "baixa": ("low", "grey-6"),
    "normal": ("normal", "primary"),
    "alta": ("high", "orange"),
    "urgente": ("urgent", "negative"),
}


@ui.page("/perfil")
def perfil_page():
    usuario = security.usuario_atual() or {}
    username = usuario.get("username")
    papel = usuario.get("role")
    staff = papel in (auth.PAPEL_ADMIN, auth.PAPEL_PROFESSOR)

    layout.inicio_pagina(
        "Meu Perfil",
        "Configurações pessoais, notas e lembretes.",
        ativo="/perfil",
    )

    if not username:
        ui.label("Você precisa estar logado para acessar o perfil.").classes("text-grey-7")
        return

    perfil = user_profile.obter_perfil(username)

    # === Card: Informações pessoais ==========================================
    ui.label("Informações Pessoais").classes("text-h6 q-mt-md")
    with ui.card().classes("w-full max-w-3xl"):
        with ui.row().classes("items-center gap-4"):
            avatar_src = perfil.get("avatar_url") or ""
            if avatar_src:
                ui.avatar(icon=f"img:{avatar_src}", size="xl", color="primary")
            else:
                ui.avatar(icon="person", size="xl", color="primary")
            with ui.column().classes("gap-0"):
                ui.label(usuario.get("name") or username).classes("text-h5")
                ui.label(f"@{username}").classes("text-subtitle1 text-grey-7")
                if usuario.get("ra"):
                    ui.label(f"RA: {usuario['ra']}").classes("text-caption text-grey-6")
                ui.label(auth.ROTULO_PAPEL.get(papel, papel or "")).classes(
                    "text-caption text-primary"
                )

        ui.separator().classes("q-my-sm")

        bio_input = ui.textarea(
            "Bio",
            value=perfil.get("bio") or "",
            placeholder="Conte um pouco sobre você...",
        ).classes("w-full").props("outlined autogrow dense")

        def salvar_bio():
            user_profile.salvar_perfil(username, bio=bio_input.value)
            ui.notify("Bio atualizada!", type="positive")

        ui.button("Salvar Bio", icon="save", on_click=salvar_bio).props("outline dense")

    # === Configurações =======================================================
    ui.label("Configurações").classes("text-h6 q-mt-md")
    with ui.card().classes("w-full max-w-3xl"):
        notif_switch = ui.switch(
            "Receber notificações",
            value=bool(perfil.get("notificacoes", 1)),
        )

        dark_pref = app.storage.user.get("dark_mode", False)
        dark_switch = ui.switch(
            "Modo escuro",
            value=bool(dark_pref),
        )

        ui.separator().classes("q-my-sm")

        ui.label("Aparência").classes("text-subtitle2")

        font_size_pref = app.storage.user.get("font_size", "14px")
        font_size_select = ui.select(
            {"12px": "Pequeno (12px)", "14px": "Médio (14px)", "16px": "Grande (16px)", "18px": "Extra Grande (18px)"},
            value=font_size_pref,
            label="Tamanho da Fonte",
        ).classes("w-full")

        font_family_pref = app.storage.user.get("font_family", "sans-serif")
        font_family_select = ui.select(
            {
                "sans-serif": "Sans Serif (Padrão)",
                "serif": "Serif",
                "monospace": "Monospace",
                "cursive": "Cursive",
            },
            value=font_family_pref,
            label="Família da Fonte",
        ).classes("w-full")

        def aplicar_fonte():
            size = font_size_select.value or "14px"
            family = font_family_select.value or "sans-serif"
            ui.query("body").style(f"font-size: {size}; font-family: {family};")

        font_size_select.on_value_change(lambda e: aplicar_fonte())
        font_family_select.on_value_change(lambda e: aplicar_fonte())

        def salvar_config():
            user_profile.salvar_perfil(
                username,
                notificacoes=1 if notif_switch.value else 0,
            )
            app.storage.user["dark_mode"] = dark_switch.value
            app.storage.user["font_size"] = font_size_select.value
            app.storage.user["font_family"] = font_family_select.value
            aplicar_fonte()
            ui.notify("Configurações salvas!", type="positive")

        ui.button("Salvar Configurações", icon="save", on_click=salvar_config).props("outline dense")

    # === Notas (resumo) ======================================================
    ui.label("Resumo de Notas").classes("text-h6 q-mt-md")
    contexto = repo.contexto_aluno(username)
    notas = contexto.get("notas", [])
    if notas:
        with ui.card().classes("w-full max-w-3xl"):
            colunas = [
                {"name": "disciplina", "label": "Disciplina", "field": "disciplina", "align": "left"},
                {"name": "trimestre", "label": "Trim.", "field": "trimestre", "align": "center"},
                {"name": "nm1", "label": "NM1", "field": "nm1", "align": "center"},
                {"name": "nm2", "label": "NM2", "field": "nm2", "align": "center"},
                {"name": "nm3", "label": "NM3", "field": "nm3", "align": "center"},
                {"name": "final", "label": "Final", "field": "final", "align": "center"},
            ]
            linhas = [
                {
                    "_idx": i,
                    "disciplina": n.get("subject"),
                    "trimestre": n.get("trimester"),
                    "nm1": _formatar_nota(n.get("nm1")),
                    "nm2": _formatar_nota(n.get("nm2")),
                    "nm3": _formatar_nota(n.get("nm3")),
                    "final": _formatar_nota(n.get("final_grade")),
                }
                for i, n in enumerate(notas)
            ]
            ui.table(columns=colunas, rows=linhas, row_key="_idx", pagination=8) \
                .classes("w-full").props("dense flat bordered")
    else:
        ui.label("Nenhuma nota lançada ainda.").classes("text-grey-7")

    # === Pontos e progresso ==================================================
    ui.label("Meus Pontos").classes("text-h6 q-mt-md")
    resumo = scores.resumo_pontos(username)
    with ui.row().classes("gap-3 q-mt-sm flex-wrap"):
        _cartao("Aulas", resumo["aulas"], "text-positive")
        _cartao("Quizzes", resumo["quizzes"], "text-info")
        _cartao("Fórum", resumo["forum"], "text-accent")
        _cartao("Part.NM1", f"{resumo['participacao_nm1']:.2f}")
        _cartao("Part.NM2", f"{resumo['participacao_nm2']:.2f}")
        _cartao("NM1", f"{resumo['nm1']:.2f}", "text-primary")
        _cartao("NM2", f"{resumo['nm2']:.2f}", "text-accent")
        _cartao("NM3", f"{resumo['nm3']:.2f}", "text-info")

    # === Presença ============================================================
    if not staff:
        ui.label("Frequência").classes("text-h6 q-mt-md")
        presencas = contexto.get("presencas", 0)
        faltas = contexto.get("faltas", 0)
        total_dias = presencas + faltas
        with ui.row().classes("gap-3 q-mt-sm flex-wrap"):
            _cartao("Presenças", presencas, "text-positive")
            _cartao("Faltas", faltas, "text-negative" if faltas else "")
            if total_dias > 0:
                perc = presencas / total_dias * 100
                _cartao("Frequência", f"{perc:.0f}%", "text-primary")

    # === Lembretes ===========================================================
    ui.label("Lembretes").classes("text-h6 q-mt-md")

    with ui.card().classes("w-full max-w-3xl"):
        with ui.row().classes("items-center gap-2 w-full"):
            titulo_input = ui.input("Novo lembrete", placeholder="Título...").classes("flex-1")
            prioridade_select = ui.select(
                {"baixa": "Baixa", "normal": "Normal", "alta": "Alta", "urgente": "Urgente"},
                value="normal",
                label="Prioridade",
            ).classes("w-36")
            prazo_input = ui.input("Prazo", placeholder="DD/MM/AAAA").classes("w-36").props("outlined dense")

        msg_input = ui.textarea(
            "Mensagem",
            placeholder="Detalhes do lembrete (opcional)...",
        ).classes("w-full").props("outlined autogrow dense")

        def adicionar_lembrete():
            if not titulo_input.value or not titulo_input.value.strip():
                ui.notify("Informe o título do lembrete.", type="warning")
                return
            ok = user_profile.criar_lembrete(
                username,
                titulo_input.value.strip(),
                msg_input.value or "",
                prioridade_select.value or "normal",
                prazo_input.value or None,
            )
            if ok:
                ui.notify("Lembrete criado!", type="positive")
                titulo_input.value = ""
                msg_input.value = ""
                lista_lembretes.refresh()
            else:
                ui.notify("Erro ao criar lembrete.", type="negative")

        ui.button("Adicionar", icon="add", on_click=adicionar_lembrete).props("outline dense")

    @ui.refreshable
    def lista_lembretes():
        lembretes = user_profile.listar_lembretes(username)
        if not lembretes:
            ui.label("Nenhum lembrete pendente.").classes("text-grey-7 q-mt-sm")
            return

        with ui.column().classes("w-full max-w-3xl gap-2 q-mt-sm"):
            for lem in lembretes:
                icone, cor = PRIORIDADES.get(lem.get("prioridade", "normal"), ("normal", "primary"))
                with ui.card().classes("w-full"):
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.icon(icone, color=cor)
                        with ui.column().classes("flex-1 gap-0"):
                            ui.label(lem.get("titulo", "")).classes("font-medium")
                            if lem.get("mensagem"):
                                ui.label(lem["mensagem"]).classes("text-caption text-grey-7")
                            if lem.get("prazo"):
                                ui.label(f"Prazo: {lem['prazo']}").classes("text-caption text-orange")

                        def toggle_concluido(lid=lem["id"], atual=lem.get("concluido", 0)):
                            user_profile.atualizar_lembrete(lid, concluido=not atual)
                            lista_lembretes.refresh()

                        def remover(lid=lem["id"]):
                            user_profile.remover_lembrete(lid)
                            lista_lembretes.refresh()

                        ui.button(icon="check", on_click=toggle_concluido).props("flat dense round")
                        ui.button(icon="delete", on_click=remover).props("flat dense round color=negative")

    lista_lembretes()

    # === Atividade recente ===================================================
    ui.label("Atividade Recente").classes("text-h6 q-mt-md")
    historico = scores.historico_aluno(username)[:10]
    if historico:
        with ui.card().classes("w-full max-w-3xl"):
            for item in historico:
                ts = item.get("timestamp", "")
                hora = ts.split(" ")[-1][:5] if " " in ts else ""
                with ui.row().classes("items-center gap-2 q-py-xs").style(
                    "border-bottom: 1px solid #eef2f7"
                ):
                    ui.label(hora).classes("text-caption text-grey-6 w-12")
                    ui.label(item.get("activity", "")).classes("text-body2")
    else:
        ui.label("Nenhuma atividade registrada.").classes("text-grey-7")

    layout.rodape_navegacao(
        ("Aulas", "menu_book", "/aulas"),
        ("Pontos", "stars", "/pontos"),
        ("Início", "home", "/aluno" if not staff else "/dashboard"),
    )
