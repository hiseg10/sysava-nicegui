"""
Plugin de Agenda e Gerenciamento de Atividades (SysAva)

Este plugin utiliza a 'grade_horaria.json' para criar uma linha do tempo interativa,
permitindo marcar o status das aulas e gerenciar tarefas via Kanban.

Uso: streamlit run data/repo/plugins/agenda.py
"""

import streamlit as st
import json
import os
from datetime import datetime

# --- Configurações de Caminho ---
PLUGIN_DIR = os.path.dirname(__file__)
GRADE_FILE = os.path.join(PLUGIN_DIR, "grade_horaria.json")
AGENDA_FILE = os.path.join(PLUGIN_DIR, "agenda_status.json")
# Horários padrão do sistema caso não estejam definidos na turma
HORARIOS_PADRAO = ["07:10", "08:10", "09:10", "10:10", "10:30", "11:30", "12:30", "13:30", "14:30", "14:50", "15:50", "16:50"]

def load_json(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Erro ao carregar {file_path}: {e}")
            return {}
    return {}

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_day_name(date_obj):
    days = {
        0: "Segunda", 1: "Terça", 2: "Quarta", 
        3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"
    }
    return days.get(date_obj.weekday())

def show_agenda():
    """Renderiza a interface da agenda. Pode ser chamada pelo app.py principal."""
    grade = load_json(GRADE_FILE)
    agenda = load_json(AGENDA_FILE)

    if not grade:
        st.warning("Arquivo 'grade_horaria.json' não encontrado. Cadastre a grade primeiro.")
        return

    # Inicializa estrutura se necessário
    updated_init = False
    if "aulas" not in agenda:
        agenda["aulas"] = {}
        updated_init = True
    if "kanban" not in agenda:
        agenda["kanban"] = {"Pendente": [], "Em Andamento": [], "Finalizado": []}
        updated_init = True
    
    if updated_init:
        st.info("Inicializando arquivo de status da agenda.")
        save_json(AGENDA_FILE, agenda)

    # --- FILTROS E CONFIGURAÇÕES NO SIDEBAR ---
    edit_mode = False
    with st.sidebar:
        st.header("⚙️ Configurações")
        turmas_list = list(grade.keys())
        user_role = st.session_state.get('role') # Define user_role aqui

        # Check if turmas_list is empty
        if not turmas_list:
            st.warning("Nenhuma turma encontrada no arquivo de grade horária. Verifique 'grade_horaria.json'.")
            return # Exit early if no turmas
        
        # Tenta identificar a turma do usuário logado para facilitar a vida
        default_index = 0
        if 'username' in st.session_state and user_role not in ['admin', 'teacher']: # Only try to auto-select for students

            try:
                from legados.sysava.services import database as db
                enrollment = db.get_user_enrollment(st.session_state['username'])
                if enrollment:
                    classes = db.get_classes()
                    user_class_info = next((c for c in classes if c['id'] == enrollment['class_id']), None)
                    if user_class_info:
                        db_class_name = user_class_info['name'].lower()
                        # Busca a turma no JSON que contenha o nome vindo do banco (mais flexível)
                        for i, name in enumerate(turmas_list):
                            if db_class_name in name.lower() or name.lower() in db_class_name:
                                default_index = i
                                break
            except Exception:
                pass
        
        # Ensure default_index is within bounds
        default_index = min(default_index, len(turmas_list) - 1)

        selected_turma = st.selectbox(
            "Selecione a Turma", 
            turmas_list, 
            index=default_index,
            key="agenda_turma_selector"
        )
        selected_date = st.date_input("Selecione a Data", datetime.now(), key="agenda_date_selector")
        
        # Add a message for admin/teacher if they need to manually select a class
        if user_role in ['admin', 'teacher'] and len(turmas_list) > 1:
            st.info(f"Visualizando a grade de **{selected_turma}**. Use o seletor acima para trocar de turma.")
        
        st.divider()
        edit_mode = st.checkbox("📝 Modo Edição de Grade", value=st.session_state.get('agenda_edit_mode', False), help="Ative para alterar as matérias deste dia diretamente aqui.")
        st.session_state['agenda_edit_mode'] = edit_mode

        st.divider()
        st.markdown("### Legenda")
        st.markdown("- 🟢 **Concluída**: Aula finalizada com sucesso.")
        st.markdown("- 🟡 **Pendente**: Aula finalizada mas com tarefas/estudos extras.")
        st.markdown("- ⚪ **Normal**: Aula ainda não realizada ou sem registro.")

    dia_semana = get_day_name(selected_date)
    data_iso = selected_date.isoformat()
    
    # --- LINHA DO TEMPO DAS AULAS ---
    st.header(f"📍 {selected_turma}")
    st.subheader(f"{dia_semana}, {selected_date.strftime('%d/%m/%Y')}")
    
    turma_info = grade.get(selected_turma, {}) # Use .get() for safety
    # Tenta pegar os horários da turma, senão usa a lista padrão
    horarios = turma_info.get("config_horarios")
    if not horarios:
        horarios = HORARIOS_PADRAO
        
    aulas_do_dia = turma_info.get(dia_semana, {})

    # --- INTERFACE DE EDIÇÃO DA GRADE ---
    if edit_mode:
        st.info(f"🛠️ Editando Grade de **{dia_semana}** para **{selected_turma}**")
        with st.form("edit_grade_form"):
            new_aulas_input = {}
            for h in horarios:
                current_val = aulas_do_dia.get(h, "")
                new_aulas_input[h] = st.text_input(f"Matéria das {h}", value=current_val, key=f"edit_{h}")
            
            if st.form_submit_button("💾 Salvar Alterações na Grade"):
                # Atualiza o dicionário da grade (remove vazios)
                grade[selected_turma][dia_semana] = {h: v for h, v in new_aulas_input.items() if v.strip()}
                save_json(GRADE_FILE, grade)
                st.success("Grade atualizada com sucesso!")
                st.rerun()

    # Verifica se há disciplinas cadastradas para o dia selecionado
    if not aulas_do_dia or not any(aulas_do_dia.values()):
        st.info(f"📭 Nenhuma aula registrada para a **{selected_turma}** na **{dia_semana}**.")
        if st.session_state.get('role') in ['admin', 'teacher']:
            if not edit_mode:
                if st.button("📝 Adicionar aulas para este dia", use_container_width=True):
                    st.session_state['agenda_edit_mode'] = True
                    st.rerun()
    else:
        # Cálculo de Progresso
        total_aulas = len([h for h in horarios if h in aulas_do_dia])
        concluidas = 0
        for h in horarios:
            if h in aulas_do_dia:
                key = f"{selected_turma}_{data_iso}_{h}"
                if agenda["aulas"].get(key, {}).get("status") == "Concluída":
                    concluidas += 1
        
        col_prog, col_stat = st.columns([0.7, 0.3])
        with col_prog:
            st.progress(concluidas / total_aulas if total_aulas > 0 else 0)
        with col_stat:
            st.write(f"✅ {concluidas} de {total_aulas} concluídas")

        st.divider()

        for h in horarios:
            if h in aulas_do_dia:
                disciplina = aulas_do_dia[h]
                key_aula = f"{selected_turma}_{data_iso}_{h}"
                
                # Recupera estado salvo
                saved_state = agenda["aulas"].get(key_aula, {"status": "Normal", "nota": ""})
                
                # Estilização visual (Marcador Colorido)
                color = "#6c757d" # Cinza (Normal)
                if saved_state["status"] == "Concluída": color = "#28a745"
                elif saved_state["status"] == "Pendente": color = "#f39c12"

                with st.container():
                    c1, c2, c3, c4 = st.columns([0.1, 0.3, 0.2, 0.4])
                    c1.markdown(f"### {h}")
                    c2.markdown(f"<div style='background-color:{color}; padding:10px; border-radius:10px; color:white; font-weight:bold; text-align:center;'>{disciplina}</div>", unsafe_allow_html=True)
                    
                    new_status = c3.selectbox("Marcar como", ["Normal", "Concluída", "Pendente"], 
                                            index=["Normal", "Concluída", "Pendente"].index(saved_state["status"]),
                                            key=f"sel_{key_aula}")
                    
                    new_note = saved_state.get("nota", "")
                    if new_status == "Pendente":
                        new_note = c4.text_input("Lembrete da Pendência", value=new_note, key=f"note_{key_aula}", placeholder="Ex: Terminar exercício pág 40")
                    
                    # Salva alterações se houver mudança
                    if new_status != saved_state["status"] or new_note != saved_state.get("nota", ""):
                        agenda["aulas"][key_aula] = {"status": new_status, "nota": new_note}
                        save_json(AGENDA_FILE, agenda)
                        st.rerun()
                st.divider()

    # --- GERENCIADOR KANBAN ---
    st.divider()
    c_kanban, c_clear = st.columns([0.7, 0.3])
    c_kanban.header("📋 Quadro Kanban de Atividades")
    if agenda["kanban"].get("Finalizado") and c_clear.button("🗑️ Limpar Concluídos", use_container_width=True):
        agenda["kanban"]["Finalizado"] = []
        save_json(AGENDA_FILE, agenda)
        st.rerun()
    
    # Formulário para nova tarefa
    with st.expander("🆕 Adicionar Nova Atividade"):
        with st.form("form_kanban"):
            nova_tarefa = st.text_input("Descrição da tarefa (ex: Estudar para prova de IA)")
            if st.form_submit_button("Criar Tarefa"):
                if nova_tarefa:
                    agenda["kanban"]["Pendente"].append(nova_tarefa)
                    save_json(AGENDA_FILE, agenda)
                    st.rerun()

    cols = st.columns(3)
    kanban_titles = list(agenda["kanban"].keys())

    for i, title in enumerate(kanban_titles):
        with cols[i]:
            st.subheader(f" {title}")
            tasks = agenda["kanban"][title]
            for j, task in enumerate(tasks):
                with st.chat_message("user", avatar="📝"): # Container estilizado para o card
                    st.write(task)
                    b_cols = st.columns(3)
                    if i > 0:
                        if b_cols[0].button("⬅️", key=f"move_l_{i}_{j}"):
                            agenda["kanban"][kanban_titles[i-1]].append(tasks.pop(j))
                            save_json(AGENDA_FILE, agenda)
                            st.rerun()
                    if i < 2:
                        if b_cols[1].button("➡️", key=f"move_r_{i}_{j}"):
                            agenda["kanban"][kanban_titles[i+1]].append(tasks.pop(j))
                            save_json(AGENDA_FILE, agenda)
                            st.rerun()
                    
                    if b_cols[2].button("🗑️", key=f"del_{i}_{j}"):
                        tasks.pop(j)
                        save_json(AGENDA_FILE, agenda)
                        st.rerun()

if __name__ == "__main__":
    # Configura a página apenas se executado sozinho
    st.set_page_config(page_title="Agenda SysAva", layout="wide", page_icon="📅")
    show_agenda()