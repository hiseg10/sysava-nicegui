"""
Plugin de Atividades Diárias e Engajamento (SysAva)

Permite criar atividades vinculadas a aulas, postar automaticamente no fórum
e atribuir pontos qualitativos com limite de 6 pontos por bloco de 20 aulas.
"""

import streamlit as st
import json
import os
import sys
import pandas as pd
import re
from datetime import datetime

# --- Configurações de Caminho ---
PLUGIN_DIR = os.path.dirname(__file__)
SCORES_FILE = os.path.join(PLUGIN_DIR, "student_scores.json")

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from legados.sysava.services import database as db
except ImportError:
    db = None

def load_json(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_lesson_number(title):
    match = re.search(r'Aula\s*(\d+)', title, re.IGNORECASE)
    return int(match.group(1)) if match else 0

def show_daily_activities():
    st.title("🎯 Gestor de Atividades Diárias")
    
    if db is None:
        st.error("Banco de dados não disponível.")
        return

    # --- SIDEBAR: Filtros ---
    with st.sidebar:
        st.header("Filtros")
        classes = db.get_classes()
        class_options = {c['name']: c['id'] for c in classes}
        sel_class_name = st.selectbox("Turma", ["-- Selecione --"] + list(class_options.keys()))

        if sel_class_name == "-- Selecione --":
            st.stop()

        class_id = class_options[sel_class_name]
        subjects = db.get_subjects_for_class(class_id)
        subject_options = {s['name']: s['id'] for s in subjects}
        sel_subject_name = st.selectbox("Disciplina", list(subject_options.keys()))
        subject_id = subject_options[sel_subject_name]

    # --- CARREGAMENTO DE DADOS ---
    lessons = db.get_lessons_for_subject(subject_id)
    if not lessons:
        st.warning("Nenhuma aula encontrada para esta disciplina.")
        return

    lesson_map = {f"{l['title']}": l for l in lessons}
    selected_lesson_title = st.selectbox("Escolha a Aula para a Atividade:", list(lesson_map.keys()))
    selected_lesson = lesson_map[selected_lesson_title]
    lesson_num = get_lesson_number(selected_lesson_title)

    # Identifica o bloco (1-20 ou 21-40)
    bloco = "1-20" if lesson_num <= 20 else "21-40"
    st.info(f"📍 Aula selecionada pertence ao **Bloco {bloco}**. (Limite: 6 pontos acumulados)")

    # --- CRIAÇÃO DA ATIVIDADE ---
    st.subheader("📝 Descrição da Atividade")
    activity_text = st.text_area("O que os alunos devem fazer?", 
                                placeholder="Ex: Resolver os exercícios da página 50 e enviar o print do código...")
    
    col1, col2 = st.columns(2)
    if col1.button("📢 Publicar no Fórum como EduBot", use_container_width=True):
        if activity_text:
            msg = f"🤖 **ATIVIDADE DO DIA ({selected_lesson_title})**:\n\n{activity_text}"
            _, error = db.add_forum_post("EduBot", msg, lesson_id=selected_lesson['id'])
            if error:
                st.error(f"Erro ao publicar: {error}")
            else:
                st.success("Atividade publicada no fórum da aula!")
        else:
            st.warning("Escreva a atividade antes de publicar.")

    st.divider()

    # --- LANÇAMENTO DE PONTOS ---
    st.subheader("⭐ Atribuir Pontos para esta Aula")
    students = db.get_students_by_class(class_id)
    all_scores_data = load_json(SCORES_FILE)
    if "students_data" not in all_scores_data: all_scores_data["students_data"] = {}

    # Otimização: Criamos um mapa de blocos para todas as aulas da disciplina de uma vez só
    lesson_block_map = {l['id']: ("1-20" if get_lesson_number(l['title']) <= 20 else "21-40") 
                       for l in lessons}

    table_data = []
    for s in students:
        uname = s['username']
        if uname not in all_scores_data["students_data"]:
            all_scores_data["students_data"][uname] = {"name": s['name'], "daily_qualitative_points": []}
        
        student_json = all_scores_data["students_data"][uname]
        
        # Cálculo de engajamento do sistema (conforme home.py)
        calc = db.get_student_score(uname, filter_subject_id=subject_id)
        system_score = calc['total']
        
        # Filtra pontos qualitativos JÁ ATRIBUÍDOS no bloco atual (1-20 ou 21-40)
        qual_points_bloco = 0
        for p in student_json.get("daily_qualitative_points", []):
            p_lesson_id = p.get('lesson_id')
            p_bloco = lesson_block_map.get(p_lesson_id)
            if p_bloco == bloco:
                qual_points_bloco += p.get('points', 0)

        total_atual = system_score + qual_points_bloco
        restante = max(0.0, 6.0 - total_atual)

        table_data.append({
            "Username": uname,
            "Nome": s['name'],
            "🌐 Sis": system_score,
            "⭐ Qualit": round(qual_points_bloco, 1),
            "📈 Total": round(total_atual, 2),
            "Limite": round(restante, 1),
            "Nota de Hoje": 0.0
        })

    df_atividades = pd.DataFrame(table_data)
    
    edited_df = st.data_editor(
        df_atividades,
        column_config={
            "Username": None,
            "Nome": st.column_config.TextColumn("Estudante", disabled=True, width="large"),
            "🌐 Sis": st.column_config.NumberColumn(disabled=True, format="%.2f"),
            "⭐ Qualit": st.column_config.NumberColumn(disabled=True, format="%.1f"),
            "📈 Total": st.column_config.NumberColumn(disabled=True, format="%.2f"),
            "Limite": st.column_config.NumberColumn("Disponível", help="Quanto o aluno ainda pode ganhar neste bloco", disabled=True, format="%.1f"),
            "Nota de Hoje": st.column_config.NumberColumn("Pontuar", min_value=0.0, max_value=2.0, step=0.1)
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_atividades_{selected_lesson['id']}"
    )

    if st.button("💾 Salvar Pontos de Hoje", type="primary", use_container_width=True):
        saved_count = 0
        for _, row in edited_df.iterrows():
            if row["Nota de Hoje"] > 0:
                uname = row['Username']
                s_json = all_scores_data["students_data"][uname]
                
                # Garante que os novos pontos não ultrapassem o teto de 6.0 do bloco
                pontos_novos = row["Nota de Hoje"]
                if row["📈 Total"] + pontos_novos > 6.0:
                    pontos_novos = max(0.0, 6.0 - row["📈 Total"])
                
                if pontos_novos > 0:
                    s_json["daily_qualitative_points"].append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "points": round(pontos_novos, 1),
                        "lesson_id": selected_lesson['id'],
                        "notes": f"Atividade Aula {lesson_num}: {selected_lesson_title}"
                    })
                    saved_count += 1
        
        if saved_count > 0:
            save_json(SCORES_FILE, all_scores_data)
            st.success(f"Pontuação de {saved_count} alunos registrada com sucesso!")
            st.rerun()
        else:
            st.info("Nenhuma pontuação nova para salvar ou todos já atingiram o teto de 6.0.")

if __name__ == "__main__":
    is_streamlit = False
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(): is_streamlit = True
    except: pass

    if is_streamlit:
        show_daily_activities()