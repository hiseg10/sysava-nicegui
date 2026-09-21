"""
Página "Quiz": questionários por aula.

Exibe as questões do quiz associado à aula indicada via URL (?lesson_id=).
Permite que o aluno responda e veja o resultado.
"""

from __future__ import annotations

from nicegui import ui, app

from core import auth, conteudo, repositories as repo
from ui import layout, security


@ui.page("/quiz")
def quiz_page(client):
    usuario = security.usuario_atual() or {}
    username = usuario.get("username")
    staff = usuario.get("role") in (auth.PAPEL_ADMIN, auth.PAPEL_PROFESSOR)

    layout.inicio_pagina(
        "Quiz",
        "Questionário da aula",
        ativo="/quiz",
    )

    if not username:
        ui.label("Você precisa estar logado para acessar o quiz.").classes("text-grey-7")
        return

    lesson_id_str = client.request.query_params.get("lesson_id")
    if not lesson_id_str:
        ui.label("Nenhuma aula selecionada. Volte para a página de aulas.").classes("text-grey-7")
        ui.button("📚 Voltar para as Aulas", on_click=lambda: ui.navigate.to("/aulas")).classes("q-mt-md")
        return

    lesson_id = int(lesson_id_str)
    quiz = repo.obter_quiz_da_aula(lesson_id)
    if not quiz:
        ui.label("Nenhum quiz encontrado para esta aula.").classes("text-grey-7")
        ui.button("📚 Voltar para as Aulas", on_click=lambda: ui.navigate.to("/aulas")).classes("q-mt-md")
        return

    questoes = conteudo.questoes_do_quiz(quiz["id"])
    if not questoes:
        ui.label("Nenhuma questão encontrada.").classes("text-grey-7")
        ui.button("📚 Voltar para as Aulas", on_click=lambda: ui.navigate.to("/aulas")).classes("q-mt-md")
        return

    radio_refs: dict = {}
    estado_quiz: dict = {"submetido": False, "score": 0}

    ui.label(f"📝 {quiz.get('title')}").classes("text-h4 q-mb-sm")
    ui.label(f"Aula ID: {lesson_id}").classes("text-subtitle1 text-grey-7")
    ui.separator().classes("q-my-md")

    for indice, questao in enumerate(questoes, start=1):
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.markdown(f"**{indice}. {questao.get('question_text')}**").classes("q-mb-md")
            labels = [f"{chr(65 + i)}) {opcao}" for i, opcao in enumerate(questao.get("options", []))]
            r = ui.radio(labels).classes("q-mb-sm")
            radio_refs[questao["id"]] = r

    def submeter_quiz():
        score = 0
        for questao in questoes:
            questao_id = questao["id"]
            correta = questao.get("correct_option_index") or 0
            selected = radio_refs.get(questao_id)
            if selected and selected.value:
                letter = selected.value[0].upper()
                selected_idx = ord(letter) - 65
                if selected_idx == correta:
                    score += 1

        estado_quiz["score"] = score
        estado_quiz["submetido"] = True

        auth.registrar_atividade(
            username,
            f"Concluiu Quiz: {quiz.get('title')} ({score}/{len(questoes)})",
        )

        ui.label(f"🎯 Resultado: {score}/{len(questoes)}").classes("text-h5 q-my-md")

        if score == len(questoes):
            ui.label("Parabéns! Acertou todas as questões!").classes("text-positive")
        elif score >= len(questoes) // 2:
            ui.label("Bom trabalho! Revise as questões erradas.").classes("text-positive")
        else:
            ui.label("Estude o conteúdo e tente novamente.").classes("text-negative")

        ui.separator().classes("q-my-md")

        for indice, questao in enumerate(questoes, start=1):
            with ui.card().classes("w-full q-pa-md q-mb-md"):
                correta = questao.get("correct_option_index") or 0
                selected = radio_refs.get(questao["id"])
                selected_letter = selected.value[0].upper() if selected and selected.value else "?"
                selected_idx = ord(selected_letter) - 65 if selected_letter != "?" else -1
                is_correct = selected_idx == correta

                if staff:
                    ui.markdown(f"**{indice}. {questao.get('question_text')}**")
                    for posicao, opcao in enumerate(questao.get("options", [])):
                        letra = chr(65 + posicao)
                        if posicao == correta:
                            ui.label(f"✅ {letra}) {opcao}").classes("text-positive")
                        else:
                            ui.label(f"  {letra}) {opcao}")
                else:
                    ui.markdown(f"**{indice}. {questao.get('question_text')}**")
                    for posicao, opcao in enumerate(questao.get("options", [])):
                        letra = chr(65 + posicao)
                        if letra == selected_letter and is_correct:
                            ui.label(f"✅ {letra}) {opcao}").classes("text-positive")
                        elif letra == selected_letter and not is_correct:
                            ui.label(f"❌ {letra}) {opcao}").classes("text-negative")

        ui.button("📚 Voltar para as Aulas", icon="home", on_click=lambda: ui.navigate.to("/aulas")).classes("q-mt-md")

    ui.button("Enviar Respostas", icon="check", on_click=submeter_quiz).props("outline dense").classes("q-mt-md")

    layout.rodape_navegacao(
        ("Aulas", "menu_book", "/aulas"),
        ("Fórum", "forum", f"/forum?lesson_id={lesson_id_str}" if lesson_id_str else "/forum"),
        ("Pontos", "stars", "/pontos"),
    )

