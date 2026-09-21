"""
Página "Aulas": conteúdo por turma/disciplina, com layout dividido.

Lado esquerdo: lista de aulas (colapsável com botão toggle)
Área principal: conteúdo da aula selecionada
Rodapé: botões para fórum, quiz, download e home

Alunos veem apenas a própria turma e o acesso é registrado em `user_history`
(base dos pontos). Admin/professor escolhem qualquer turma e veem o gabarito.
"""

from __future__ import annotations

import re

from nicegui import ui

from core import auth, conteudo, repositories as repo
from ui import layout, security


def _injetar_copy_buttons() -> None:
    css = """
    <style>
    pre { position: relative; background: #1e1e1e; border-radius: 8px; padding: 16px; overflow-x: auto; }
    pre code { color: #d4d4d4; font-family: 'Consolas', 'Monaco', monospace; font-size: 14px; }
    .copy-btn:hover { opacity: 0.9 !important; transform: scale(1.05); }
    </style>
    """
    ui.add_head_html(css)
    js = """
    <script>
    (function() {
        function addCopyButtons() {
            document.querySelectorAll('pre code').forEach(function(block) {
                if (block.parentElement.querySelector('.copy-btn')) return;
                
                var btn = document.createElement('button');
                btn.className = 'copy-btn';
                btn.innerHTML = '<i class="material-icons" style="font-size:16px">content_copy</i> Copiar';
                btn.style.cssText = 'position:absolute;top:4px;right:4px;padding:4px 8px;font-size:12px;' +
                    'background:#1976d2;color:white;border:none;border-radius:4px;cursor:pointer;' +
                    'display:flex;align-items:center;gap:4px;z-index:10;';
                
                block.parentElement.style.position = 'relative';
                block.parentElement.appendChild(btn);
                
                btn.onclick = function() {
                    navigator.clipboard.writeText(block.textContent).then(function() {
                        btn.innerHTML = '<i class="material-icons" style="font-size:16px">check</i> Copiado!';
                        btn.style.background = '#388e3c';
                        setTimeout(function() {
                            btn.innerHTML = '<i class="material-icons" style="font-size:16px">content_copy</i> Copiar';
                            btn.style.background = '#1976d2';
                        }, 2000);
                    });
                };
            });
        }
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', addCopyButtons);
        } else {
            addCopyButtons();
        }
        
        new MutationObserver(addCopyButtons).observe(document.body, {childList: true, subtree: true});
    })();
    </script>
    """
    ui.add_head_html(js)

_STATUS_ICONE = {
    conteudo.STATUS_CONCLUIDA: ("check_circle", "positive", "Concluída"),
    conteudo.STATUS_VISITADA: ("pending", "orange", "Visitada (quiz pendente)"),
    conteudo.STATUS_NAO: ("radio_button_unchecked", "grey-6", "Não visitada"),
}


def _slug(texto: str) -> str:
    limpo = re.sub(r'[\\/*?:"<>|]', "", str(texto or "aula")).strip().replace(" ", "_")
    return limpo[:80] or "aula"


@ui.page("/aulas")
def aulas_page() -> None:
    usuario = security.usuario_atual() or {}
    papel = usuario.get("role")
    staff = papel in (auth.PAPEL_ADMIN, auth.PAPEL_PROFESSOR)

    layout.inicio_pagina(
        "Aulas",
        "Conteúdo das aulas por turma e disciplina.",
        ativo="/aulas",
    )

    estado: dict = {
        "turma_id": None,
        "turma_nome": None,
        "disciplina_id": None,
        "disciplina_nome": None,
    }

    turmas = repo.listar_turmas()
    if not staff:
        contexto = repo.contexto_aluno(usuario.get("username"))
        turma = contexto["turma"]
        if turma:
            estado["turma_id"] = turma.get("id")
            estado["turma_nome"] = turma.get("name")
    elif turmas:
        estado["turma_id"] = turmas[0]["id"]
        estado["turma_nome"] = turmas[0]["name"]

    opcoes_turma = {str(t["id"]): t["name"] for t in turmas}

    estado_aula: dict = {"aula_atual": None}

    toggle_btn: ui.button | None = None
    lista_aulas_ref: ui.refreshable | None = None

    def toggle_sidebar() -> None:
        if sidebar_splitter.value is None or sidebar_splitter.value == 0:
            sidebar_splitter.value = 25
            if toggle_btn:
                toggle_btn.props("icon=menu")
                toggle_btn.update()
        else:
            sidebar_splitter.value = 0
            if toggle_btn:
                toggle_btn.props("icon=chevron_right")
                toggle_btn.update()

    def carregar() -> None:
        if not estado["turma_id"]:
            estado["disciplina_id"] = None
            estado["disciplina_nome"] = None
            if lista_aulas_ref:
                lista_aulas_ref.refresh()
            return
        disciplinas = repo.listar_disciplinas_da_turma(estado["turma_id"], apenas_ativas=True)
        opcoes = {str(d["id"]): d["name"] for d in disciplinas}
        disc_select.set_options(opcoes)
        if estado["disciplina_id"] not in opcoes:
            estado["disciplina_id"] = next(iter(opcoes), None)
        estado["disciplina_nome"] = opcoes.get(str(estado["disciplina_id"]))
        disc_select.value = estado["disciplina_id"]
        if lista_aulas_ref:
            lista_aulas_ref.refresh()

    with ui.row().classes("items-center gap-4 q-mt-sm flex-wrap"):
        if staff:
            turma_select = ui.select(
                opcoes_turma,
                value=str(estado["turma_id"]) if estado["turma_id"] else None,
                label="Turma",
                on_change=lambda evento: (
                    estado.update(
                        turma_id=evento.value,
                        turma_nome=opcoes_turma.get(evento.value),
                    ),
                    carregar(),
                ),
            ).classes("w-72").props("outlined dense")
        else:
            turma_select = None
            ui.label(f"Turma: {estado['turma_nome'] or '-'}").classes("text-subtitle1")
        disc_select = ui.select(
            {}, label="Disciplina", on_change=lambda evento: (
                estado.update(disciplina_id=evento.value),
                carregar(),
            )
        ).classes("w-72").props("outlined dense")

    with ui.row().classes("w-full items-center q-mb-sm q-gutter-xs"):
        toggle_btn = ui.button(
            icon="menu",
            on_click=toggle_sidebar,
        ).props("flat dense round")
        ui.label("Lista de Aulas").classes("text-subtitle2 q-ml-xs")

    sidebar_splitter = ui.splitter(value=25, limits=(0, 40)).classes("w-full")

    with sidebar_splitter.before:
        painel_lateral = ui.column().classes("w-full bg-grey-1 q-pa-sm items-stretch")
        with painel_lateral:

            @ui.refreshable
            def lista_aulas():
                nonlocal lista_aulas_ref
                lista_aulas_ref = lista_aulas
                if not estado["disciplina_id"]:
                    ui.label("Selecione uma turma e disciplina.").classes("text-grey-7 q-mt-md")
                    return

                aulas = repo.listar_aulas(estado["disciplina_id"])
                if not aulas:
                    ui.label("Nenhuma aula cadastrada.").classes("text-grey-7 q-mt-md")
                    return

                status = conteudo.status_aulas(usuario.get("username"), estado["disciplina_id"])
                grupos = conteudo.agrupar_aulas(
                    aulas, estado["disciplina_nome"] or "", estado["turma_nome"] or ""
                )

                for titulo_grupo, aulas_grupo in grupos.items():
                    with ui.expansion(titulo_grupo, value=True).classes("w-full"):
                        for aula in aulas_grupo:
                            icone, cor, dica = _STATUS_ICONE.get(
                                status.get(str(aula["id"]), conteudo.STATUS_NAO),
                                _STATUS_ICONE[conteudo.STATUS_NAO],
                            )
                            with ui.row().classes("w-full items-center gap-2 q-py-xs").style(
                                "border-bottom: 1px solid #eef2f7"
                            ):
                                botao_aula = ui.button(
                                    aula.get("title") or "(sem título)",
                                    on_click=lambda a=aula: selecionar_aula(a),
                                ).props("flat align=left no-caps").classes("flex-1 justify-start")
                                ui.icon(icone, color=cor).tooltip(dica)
                                if (
                                    estado_aula["aula_atual"]
                                    and estado_aula["aula_atual"]["id"] == aula["id"]
                                ):
                                    botao_aula.props("color=primary")

            carregar()
            lista_aulas()

    with sidebar_splitter.after:
        conteudo_container = ui.column().classes("w-full q-gutter-sm")

        def selecionar_aula(aula: dict) -> None:
            estado_aula["aula_atual"] = aula
            if not staff:
                auth.registrar_atividade(
                    usuario.get("username"),
                    f"Acessou a aula: {aula.get('title')} | subject_id:{estado['disciplina_id']}",
                )
            sidebar_splitter.value = 0
            conteudo_container.clear()
            with conteudo_container:
                ui.label(aula.get("title") or "Aula").classes("text-h4 q-mb-sm")

                if aula.get("video_url"):
                    ui.link(
                        "🎬 Assistir ao vídeo", aula["video_url"], new_tab=True
                    ).classes("q-mb-sm")

                texto = aula.get("description") or aula.get("full_content") or ""
                if texto:
                    ui.markdown(str(texto)).classes("w-full")
                    _injetar_copy_buttons()
                else:
                    ui.label("Sem conteúdo cadastrado.").classes("text-grey-7")

                with ui.row().classes(
                    "w-full items-center q-gutter-sm flex-wrap q-mt-md"
                ):
                    quiz = repo.obter_quiz_da_aula(aula["id"])
                    questoes = conteudo.questoes_do_quiz(quiz["id"]) if quiz else []
                    ui.button(
                        "💬 Fórum",
                        icon="forum",
                        on_click=lambda: ui.navigate.to(f"/forum?lesson_id={aula['id']}"),
                    ).props("outline dense").classes("text-body2")
                    ui.button(
                        "📝 Quiz",
                        icon="quiz",
                        on_click=lambda: ui.navigate.to(f"/quiz?lesson_id={aula['id']}"),
                    ).props("outline dense").classes("text-body2")
                    ui.button(
                        "📥 Baixar",
                        icon="download",
                        on_click=lambda: ui.download(
                            conteudo.markdown_aula(aula, quiz, questoes).encode(
                                "utf-8"
                            ),
                            f"{_slug(aula.get('title'))}.md",
                        ),
                    ).props("outline dense").classes("text-body2")
                    ui.button(
                        "🏠 Home",
                        icon="home",
                        on_click=lambda: ui.navigate.to("/"),
                    ).props("outline dense").classes("text-body2")

            if lista_aulas_ref:
                lista_aulas_ref.refresh()

