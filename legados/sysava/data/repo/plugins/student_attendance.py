"""
Plugin de Gerenciamento de Frequência (SysAva)

Este plugin permite registrar a presença diária dos alunos por turma,
salvando os dados em um arquivo JSON local.
"""

import streamlit as st
import json
import os
import sys
import pandas as pd
from datetime import datetime

# --- Configurações de Caminho ---
PLUGIN_DIR = os.path.dirname(__file__)
ATTENDANCE_FILE = os.path.join(PLUGIN_DIR, "student_attendance.json")

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
BACKUP_DIR = os.path.join(project_root, "data", "frequencia")

try:
    from legados.sysava.services import database as db
except ImportError:
    db = None

def load_json(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_json(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def show_attendance_plugin():
    st.title("📅 Diário de Frequência")

    if db is None:
        st.error("Serviço de banco de dados não disponível.")
        return

    # 1. Seleção de Turma e Data na Sidebar
    with st.sidebar:
        st.header("Configurações")
        classes = db.get_classes()
        class_options = {c['name']: c['id'] for c in classes}
        class_display = {c['name']: f"{c['name']} ({c.get('official_name', 'S/N')})" for c in classes}
        
        selected_class_name = st.selectbox(
            "Selecione a Turma", 
            ["-- Selecione --"] + list(class_options.keys()),
            format_func=lambda x: class_display.get(x, x)
        )

        selected_subject_id = None
        selected_subject_name = ""

        if selected_class_name != "-- Selecione --":
            class_id = class_options[selected_class_name]
            subjects = db.get_subjects_for_class(class_id)
            subjects = [s for s in subjects if s.get('is_active', True)]
            subject_options = {}
            for s in subjects:
                s_name = s['name'].strip()
                if s_name not in subject_options:
                    subject_options[s_name] = s['id']
            selected_subject_name = st.selectbox("Selecione a Disciplina", list(subject_options.keys()))
            selected_subject_id = subject_options.get(selected_subject_name)

        selected_date = st.date_input("Data da Aula", datetime.now())
        date_key = selected_date.isoformat()

    if selected_class_name == "-- Selecione --":
        st.info("Selecione uma turma na barra lateral para iniciar a chamada.")
        return

    if not selected_subject_name:
        st.info("Selecione uma disciplina para registrar a frequência.")
        return

    subject_key = str(selected_subject_id)
    class_id = class_options[selected_class_name]
    students = db.get_students_by_class(class_id)
    
    if not students:
        st.warning(f"Nenhum aluno encontrado na turma {selected_class_name}.")
        return

    # Ordenar alunos por nome para definir o número na lista (Nº)
    students = sorted(students, key=lambda x: x['name'])

    # 2. Carregar Dados de Frequência
    attendance_data = load_json(ATTENDANCE_FILE)
    class_key = str(class_id)

    # Mapeamento auxiliar para converter Nome em Username (necessário para banco e backups)
    name_to_user = {s['name']: s['username'] for s in students}

    # --- Sincronização Cloud: Carregar do Banco de Dados ---
    if db and hasattr(db, 'supabase'):
        try:
            # Busca registros existentes para esta turma e disciplina no banco
            res = db.supabase.table("attendance")\
                .select("*")\
                .eq("class_name", selected_class_name)\
                .eq("subject_name", selected_subject_name)\
                .execute()
            if res.data:
                if class_key not in attendance_data: attendance_data[class_key] = {}
                if subject_key not in attendance_data[class_key]: attendance_data[class_key][subject_key] = {}
                
                for rec in res.data:
                    dt = rec['date']
                    u_name = name_to_user.get(rec['student_name'])
                    if u_name:
                        if dt not in attendance_data[class_key][subject_key]: attendance_data[class_key][subject_key][dt] = {}
                        attendance_data[class_key][subject_key][dt][u_name] = "Presente" if rec['is_present'] else "Falta"
        except Exception:
            pass # Falha silenciosa: se o banco falhar, usa o cache local/backups

    # Procurar outras datas anteriores em backups json na pasta data/frequencia
    if os.path.exists(BACKUP_DIR):
        for file in os.listdir(BACKUP_DIR):
            if file.endswith(".json"):
                backup_json = load_json(os.path.join(BACKUP_DIR, file))
                
                # Caso 1: Formato Legado (Lista)
                if isinstance(backup_json, list):
                    for entry in backup_json:
                        # Filtra pela turma selecionada no backup
                        if entry.get("Turma") == selected_class_name:
                            d_k = entry.get("Data")
                            u_name = name_to_user.get(entry.get("Nome do Aluno"))
                            
                            if u_name and d_k:
                                if class_key not in attendance_data: attendance_data[class_key] = {}
                                if subject_key not in attendance_data[class_key]: attendance_data[class_key][subject_key] = {}
                                if d_k not in attendance_data[class_key][subject_key]: attendance_data[class_key][subject_key][d_k] = {}
                                # Prioriza o dado do arquivo principal se já existir
                                if u_name not in attendance_data[class_key][subject_key][d_k]:
                                    status = "Presente" if entry.get("Presença") else "Falta"
                                    attendance_data[class_key][subject_key][d_k][u_name] = status
                
                # Caso 2: Formato Novo (Dicionário)
                elif isinstance(backup_json, dict):
                    for c_k, dates in backup_json.items():
                        if c_k not in attendance_data: attendance_data[c_k] = {}
                        attendance_data[c_k].update(dates)

    if class_key not in attendance_data:
        attendance_data[class_key] = {}
    if subject_key not in attendance_data[class_key]:
        attendance_data[class_key][subject_key] = {}
    if date_key not in attendance_data[class_key][subject_key]:
        attendance_data[class_key][subject_key][date_key] = {}

    day_attendance = attendance_data[class_key][subject_key][date_key]

    st.subheader(f"Lista de Presença: {selected_class_name} - {selected_subject_name}")
    st.caption(f"Registro para o dia {selected_date.strftime('%d/%m/%Y')}")

    # 3. Interface da Chamada (Tabela Condensada)
    # Preparamos um DataFrame para o editor
    df_attendance = pd.DataFrame([
        {
            "Nº": i + 1,
            "Username": s['username'], 
            "Nome": s['name'], 
            "Status": day_attendance.get(s['username'], "Presente")
        }
        for i, s in enumerate(students)
    ])

    # O data_editor permite editar o status como um dropdown em uma tabela compacta
    edited_df = st.data_editor(
        df_attendance,
        column_config={
            "Nº": st.column_config.NumberColumn("Nº", disabled=True, width="small"),
            "Username": None, # Oculta a coluna de ID técnico
            "Nome": st.column_config.TextColumn("Estudante", disabled=True, width="large"),
            "Status": st.column_config.SelectboxColumn(
                "Presença",
                options=["Presente", "Falta", "Atraso"],
                required=True,
                width="medium"
            )
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_{class_key}_{date_key}"
    )

    new_entries = {row['Username']: row['Status'] for _, row in edited_df.iterrows()}

    if st.button("💾 Salvar Chamada do Dia", use_container_width=True, type="primary"):
        attendance_data[class_key][subject_key][date_key] = new_entries
        
        # 1. Atualiza o JSON de origem (student_attendance.json) com todos os dados mesclados
        save_json(ATTENDANCE_FILE, attendance_data)

        # 2. Popula tudo no banco de dados (Sincronização completa da turma)
        if db and hasattr(db, 'supabase'):
            professor = st.session_state.get('usuario', 'Professor')
            db_records = []
            
            # Mapeamento auxiliar para recuperar nome e número rapidamente
            user_info_map = {s['username']: {"name": s['name'], "n": i+1} for i, s in enumerate(students)}
            
            # Percorre todas as datas desta turma e disciplina
            for d_key, entries in attendance_data[class_key][subject_key].items():
                for u_name, status in entries.items():
                    if u_name in user_info_map:
                        db_records.append({
                            "student_name": user_info_map[u_name]["name"],
                            "student_number": user_info_map[u_name]["n"],
                            "is_present": status in ["Presente", "Atraso"],
                            "class_name": selected_class_name,
                            "subject_id": selected_subject_id,
                            "subject_name": selected_subject_name,
                            "date": d_key,
                            "professor_name": professor
                        })
            
            if db_records:
                try:
                    # O parâmetro on_conflict usa subject_id conforme constraint do banco
                    db.supabase.table("attendance").upsert(
                        db_records, 
                        on_conflict="student_name, class_name, subject_id, date"
                    ).execute()
                    st.info(f"Sincronizados {len(db_records)} registros (incluindo backups) com o servidor.")
                except Exception as e:
                    st.error(f"Erro ao sincronizar com o banco de dados: {e}")

        st.success(f"Chamada de {selected_date.strftime('%d/%m/%Y')} salva com sucesso!")
        st.rerun()

    # 4. Resumo rápido
    presencas = list(new_entries.values()).count("Presente")
    faltas = list(new_entries.values()).count("Falta")
    atrasos = list(new_entries.values()).count("Atraso")

    c1, c2, c3 = st.columns(3)
    c1.metric("Presenças", presencas)
    c2.metric("Faltas", faltas)
    c3.metric("Atrasos", atrasos)

    # 5. Tabela Geral de Histórico (Acumulado)
    st.divider()
    st.subheader(f"📊 Relatório de Faltas e Presenças: {selected_subject_name}")
    
    subject_history = attendance_data.get(class_key, {}).get(subject_key, {})
    if not subject_history:
        st.info(f"Nenhum histórico acumulado para {selected_subject_name} nesta turma.")
    else:
        summary_list = []
        all_dates = subject_history.keys()
        
        for s in students:
            u = s['username']
            p_count = 0
            f_count = 0
            a_count = 0
            for d_key in all_dates:
                stat = subject_history[d_key].get(u)
                if stat == "Presente": p_count += 1
                elif stat == "Falta": f_count += 1
                elif stat == "Atraso": a_count += 1
            
            total_days = p_count + f_count + a_count
            freq_val = (p_count + a_count) / total_days * 100 if total_days > 0 else 0
            
            summary_list.append({
                "Nome": s['name'],
                "Presenças ✅": p_count,
                "Faltas ❌": f_count,
                "Atrasos 🕒": a_count,
                "% Freq.": f"{freq_val:.1f}%"
            })
        
        # Ordenamos por quem tem mais faltas para facilitar a atenção do professor
        df_summary = pd.DataFrame(summary_list).sort_values(by="Faltas ❌", ascending=False)
        st.dataframe(df_summary, hide_index=True, use_container_width=True)

        # 6. Seção de Exportação para Relatórios Externos
        st.markdown("### 📥 Exportar Registros")
        c_exp1, c_exp2 = st.columns(2)

        # Exportar Resumo da Disciplina Atual (Cálculo acumulado)
        csv_summary = df_summary.to_csv(index=False).encode('utf-8')
        c_exp1.download_button(
            label=f"📊 Baixar Resumo ({selected_subject_name})",
            data=csv_summary,
            file_name=f"resumo_frequencia_{selected_class_name}_{selected_subject_name}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Exporta a tabela de porcentagem de frequência da disciplina selecionada."
        )

        # Exportar Histórico Detalhado (Todas as datas e disciplinas da turma)
        full_log = []
        class_history_all = attendance_data.get(class_key, {})
        user_to_name = {v: k for k, v in name_to_user.items()}
        
        # Mapeia IDs para nomes de disciplinas para o relatório geral
        all_subjects_class = db.get_subjects_for_class(class_id)
        sub_map = {str(s['id']): s['name'] for s in all_subjects_class}

        for key, value in class_history_all.items():
            if not isinstance(value, dict): continue
            
            # Verifica se o valor é um dicionário de datas (Formato Novo) 
            # ou um dicionário de alunos (Formato Antigo/Legado)
            first_inner = next(iter(value.values()), None)
            
            if isinstance(first_inner, dict):
                # Formato Novo: key=subject_id, value={data: {user: status}}
                s_name_full = sub_map.get(key, f"Cod:{key}")
                for dk, entries in value.items():
                    if isinstance(entries, dict):
                        for un, st_val in entries.items():
                            full_log.append({
                                "Data": dk, "Disciplina": s_name_full,
                                "Estudante": user_to_name.get(un, un), "Status": st_val
                            })
            else:
                # Formato Legado: key=data, value={user: status}
                for un, st_val in value.items():
                    full_log.append({
                        "Data": key, "Disciplina": "Histórico Legado",
                        "Estudante": user_to_name.get(un, un), "Status": st_val
                    })
        
        if full_log:
            df_full = pd.DataFrame(full_log).sort_values(by=["Data", "Disciplina", "Estudante"])
            csv_full = df_full.to_csv(index=False).encode('utf-8')
            c_exp2.download_button(
                label="📁 Baixar Histórico Geral (Turma)",
                data=csv_full,
                file_name=f"historico_completo_{selected_class_name}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                help="Exporta um log detalhado de todas as chamadas realizadas para esta turma em todas as matérias."
            )

if __name__ == "__main__":
    is_streamlit = False
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(): is_streamlit = True
    except: pass

    if is_streamlit:
        show_attendance_plugin()
    else:
        print("Este plugin deve ser executado dentro do SysAva.")