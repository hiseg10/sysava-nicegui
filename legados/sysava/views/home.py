import streamlit as st
from legados.sysava.services import database as db
import pandas as pd

def show_student_home():
    """Exibe a home page padrão para o aluno, com seu histórico de atividades."""
    
    username = st.session_state.get('username')
    if not username:
        st.warning("Por favor, faça login para ver seu histórico.")
        return

    # --- Seletor de Disciplina para o Score ---
    enrollment = db.get_user_enrollment(username)
    subjects = []
    if enrollment:
        subjects = db.get_subjects_for_class(enrollment['class_id'])
    
    subject_options = {"Visão Geral (Todas)": None}
    if subjects:
        subject_options.update({s['name']: s['id'] for s in subjects})

    selected_subject_name = st.selectbox("Filtrar progresso por disciplina:", list(subject_options.keys()))
    selected_subject_id = subject_options[selected_subject_name]

    # --- Score do Aluno ---
    st.subheader("🏆 Seu Progresso (Score)")
    score = db.get_student_score(username, filter_subject_id=selected_subject_id)
    
    c1, c2, c3, c4 = st.columns(4)
    total_label = "Pontuação Total" if selected_subject_id is None else f"Score em {selected_subject_name}"
    c1.metric(total_label, score['total'])
    c2.metric("Aulas Vistas (+1)", score['lesson'])
    c3.metric("Pontos em Quizzes", score['quiz'])
    c4.metric("Fórum por Aula (+1)", score['forum'])
    
    st.caption("Critério: 1 ponto por aula visualizada + Nota dos Quizzes + 1 ponto por participação no fórum da aula.")
    st.divider()

    st.subheader("📅 Seu Histórico de Atividades")

    user_history = db.get_user_history(username)
    
    if user_history:
        with st.container():
            for item in user_history:
                col1, col2 = st.columns([0.7, 0.3])
                with col1:
                    st.markdown(f"**{item.get('activity', 'Atividade')}**")
                with col2:
                    ts = str(item.get('timestamp', ''))
                    if 'T' in ts:
                        data, hora = ts.split('T')
                        st.caption(f"{data} {hora[:5]}")
                    else:
                        st.caption(ts)
                st.divider()
    else:
        st.info("Nenhuma atividade registrada recentemente.")

def show_teacher_dashboard():
    """Exibe um painel com atalhos e métricas para o professor."""
    st.subheader("👨‍🏫 Painel do Professor")
    st.markdown("Acesso rápido e visão geral do engajamento das turmas.")

    # 1. Atalhos
    st.markdown("#### Ações Rápidas")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📝 Gerenciar Avaliações", use_container_width=True):
            st.session_state.page = "Avaliações"
            st.rerun()
    with col2:
        if st.button("📚 Gerenciar Conteúdo (Aulas, Quizzes)", use_container_width=True):
            st.session_state.page = "Admin"
            st.rerun()
    with col3:
        if st.button("🧩 Central de Plugins", use_container_width=True):
            st.session_state.page = "Plugins"
            st.rerun()
    
    st.divider()

    # --- Consulta de Score Individual ---
    st.markdown("#### 🏆 Consulta de Score Individual")
    
    # 1. Seletor de Turma (Necessário para filtrar disciplinas e alunos)
    classes = db.get_classes()
    class_options = {c['name']: c['id'] for c in classes}
    selected_class_score = st.selectbox("1. Selecione a Turma:", ["-- Selecione --"] + list(class_options.keys()), key="score_class_sel")

    if selected_class_score != "-- Selecione --":
        class_id_score = class_options[selected_class_score]
        
        # 2. Seletor de Disciplina
        subjects = db.get_subjects_for_class(class_id_score)
        subject_options_teacher = {"Visão Geral (Todas)": None}
        if subjects:
            subject_options_teacher.update({s['name']: s['id'] for s in subjects})

        selected_subject_name_teacher = st.selectbox(
            "2. Selecione a Disciplina (Score):", 
            list(subject_options_teacher.keys()),
            key="score_subject_sel"
        )
        selected_subject_id_teacher = subject_options_teacher[selected_subject_name_teacher]

        # 3. Seletor de Aluno (Filtrado pela Turma)
        if db.is_db_connected():
            students = db.get_students_by_class(class_id_score)
        else:
            students = [
                {'id': 'mock-1', 'name': 'Aluno Teste 1', 'username': 'aluno1', 'role': 'student'},
                {'id': 'mock-2', 'name': 'Aluno Teste 2', 'username': 'aluno2', 'role': 'student'}
            ]
            st.info("💡 Exibindo alunos de teste (Modo Offline)")

        if not students:
            st.warning("Nenhum aluno encontrado nesta turma.")
        else:
            student_options = {f"{s['name']} ({s['username']})": s['username'] for s in students}
            selected_student_key = st.selectbox("3. Selecione o Aluno:", ["-- Selecione --"] + list(student_options.keys()), key="score_student_sel")
        
            if selected_student_key != "-- Selecione --":
                target_username = student_options[selected_student_key]
                st_score = db.get_student_score(target_username, filter_subject_id=selected_subject_id_teacher)
                
                st.info(f"**Score Detalhado de {selected_student_key}:**")
                sc1, sc2, sc3, sc4 = st.columns(4)
                total_label_teacher = "Total" if selected_subject_id_teacher is None else f"Score em {selected_subject_name_teacher}"
                sc1.metric(total_label_teacher, st_score['total'])
                sc2.metric("Aulas", st_score['lesson'])
                sc3.metric("Quizzes", st_score['quiz'])
                sc4.metric("Fórum", st_score['forum'])
    
    st.divider()

    # 2. Dashboard de Participação
    st.markdown("#### 📈 Dashboard de Participação da Turma")
    classes = db.get_classes()
    if not classes:
        st.warning("Nenhuma turma cadastrada no sistema.")
        return

    class_map = {c['name']: c['id'] for c in classes}
    selected_class_name = st.selectbox("Selecione uma turma para analisar:", ["-- Selecione --"] + list(class_map.keys()))

    if selected_class_name != "-- Selecione --":
        class_id = class_map[selected_class_name]
        
        with st.spinner(f"Analisando dados da turma {selected_class_name}..."):
            students = db.get_students_by_class(class_id)
            if not students:
                st.info("Esta turma não possui alunos matriculados.")
                return

            combined_data = []
            for s in students:
                progress = db.get_user_progress_stats(s['username'])
                progress['Aluno'] = s['name'] # Adiciona o nome do aluno ao dicionário de progresso
                combined_data.append(progress)
            
            df = pd.DataFrame(combined_data)

            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("Nº de Alunos", len(students))
            m_col2.metric("Média de Aulas Vistas", f"{df['lessons'].mean():.1f}")
            m_col3.metric("Média de Quizzes Feitos", f"{df['quizzes'].mean():.1f}")

            st.markdown("##### Engajamento por Aluno")
            st.dataframe(df[['Aluno', 'lessons', 'quizzes', 'forum']].rename(columns={'lessons': 'Aulas', 'quizzes': 'Quizzes', 'forum': 'Fórum'}), use_container_width=True)

def show_page():
    school_info = db.get_school()
    school_name = school_info.get('name') if school_info else None
    user_name = st.session_state.get('usuario', 'Usuário')
    st.title(f"Bem-vindo, {user_name}!")
    if school_name:
        st.caption(f"Instituição: **{school_name}**")
    st.markdown("---")

    role = st.session_state.get('role')

    if role in ['teacher', 'admin']:
        show_teacher_dashboard()
    else: # student or default
        show_student_home()