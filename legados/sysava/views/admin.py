import streamlit as st
import streamlit.components.v1 as components
from legados.sysava.services import database as db
from legados.sysava.services import auth
from legados.sysava.services import ai_generation as ai
from legados.sysava.services import quiz_parser
import re
import json
import pandas as pd
import time
import os
import random

def generate_printable_answer_key_html(school_name, subject_name, type_label, export_data):
    """Gera uma visualização HTML formatada para impressão do gabarito."""
    date_str = pd.Timestamp.now().strftime("%d/%m/%Y")
    
    rows_html = ""
    for item in export_data:
        rows_html += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">{item['Nº']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-size: 1.1em;"><strong>{item['Letra']}</strong></td>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">{item['Enunciado']}</td>
            <td style="padding: 10px; border-bottom: 1px solid #eee;">{item['Resposta Correta']}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Gabarito - {subject_name}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 30px; }}
            .header h1 {{ margin: 0; font-size: 22px; }}
            .header p {{ margin: 5px 0; color: #666; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ background-color: #f8f9fa; padding: 12px; border-bottom: 2px solid #dee2e6; text-align: left; }}
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ margin: 0; padding: 0; }}
            }}
        </style>
    </head>
    <body>
        <div class="no-print" style="text-align: center; margin-bottom: 20px;">
            <button onclick="window.print()" style="background-color: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">🖨️ CLIQUE PARA IMPRIMIR / PDF</button>
        </div>
        <div class="header">
            <h1>{school_name}</h1>
            <p><strong>Gabarito Oficial:</strong> {subject_name} | <strong>Origem:</strong> {type_label}</p>
            <p><strong>Data de Emissão:</strong> {date_str}</p>
        </div>
        <table style="font-size: 0.9em;">
            <thead><tr><th style="text-align: center; width: 40px;">Nº</th><th style="text-align: center; width: 50px;">Letra</th><th>Enunciado</th><th style="width: 250px;">Resposta Correta</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </body>
    </html>
    """
    return html

def show_page():
    st.header("🛡️ Painel Administrativo")

    if not db.is_db_connected():
        st.warning("Funcionalidade disponível apenas com banco de dados conectado.")
        # Não retornamos aqui para permitir que a aba de configuração apareça mesmo offline

    db_structure_exists = db.check_db_structure()

    main_section = st.radio("Seção", ["⚙️ Configurações Gerais", "📚 Configurações de Conteúdos"], horizontal=True)

    tab_config = tab1 = tab5 = tab6 = tab2 = tab_training = tab3 = tab4 = tab_audit = tab_reviewer = tab7 = None
    
    if main_section == "⚙️ Configurações Gerais":
        tab_config, tab1, tab5, tab6 = st.tabs(["⚙️ Setup", "👥 Usuários", "🤖 Simulador", "📊 Relatórios"])
    else:
        tab2, tab_training, tab3, tab4, tab_audit, tab_reviewer = st.tabs(["📖 Aulas", "🚀 Treinamentos", "📝 Quizzes", "🎓 Avaliações", "🔍 Auditoria", "🔑 Gabaritos"])

    if tab_config:
        with tab_config:
            st.subheader("🛠️ Setup Inicial do Sistema")

            with st.expander("1️⃣ Conexão com Banco de Dados (Supabase)", expanded=not db.is_db_connected()):
                st.markdown("""
                1. Crie uma conta em [supabase.com](https://supabase.com).
                2. Crie um novo projeto.
                3. Vá em **Project Settings > API**.
                4. Copie a **Project URL** e a **anon public key**.
                """)

                c1, c2 = st.columns(2)
                url_input = c1.text_input("Project URL", value=os.environ.get("SUPABASE_URL", ""))
                key_input = c2.text_input("Anon Public Key", type="password", value=os.environ.get("SUPABASE_KEY", ""))

                if st.button("💾 Salvar Credenciais (Sessão Atual)"):
                    if url_input and key_input:
                        os.environ["SUPABASE_URL"] = url_input
                        os.environ["SUPABASE_KEY"] = key_input
                        st.cache_resource.clear() # Limpa o cache para forçar reconexão
                        st.success("Credenciais salvas na memória! A página será recarregada.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Preencha ambos os campos.")

                if db.is_db_connected():
                    st.success("✅ Conectado ao Supabase com sucesso!")
                else:
                    st.error("❌ Desconectado.")

            with st.expander("2️⃣ Criar Estrutura do Banco (Primeira Vez)", expanded=db.is_db_connected() and not db_structure_exists):
                st.warning("Atenção: As tabelas do banco de dados parecem não existir.")
                st.info("Copie o código abaixo e execute-o no 'SQL Editor' do seu projeto Supabase para criar toda a estrutura necessária.")

                try:
                    # O caminho deve ser relativo à raiz do projeto, onde o app.py é executado
                    with open("docs/DATABASE_MODEL.md", "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extrai o bloco de código SQL do arquivo markdown
                    sql_match = re.search(r"```sql\n(.*?)```", content, re.DOTALL)
                    if sql_match:
                        sql_code = sql_match.group(1).strip()
                        st.text_area("Código SQL para criar tabelas", sql_code, height=300, key="sql_code_area")
                        if st.button("Já executei o SQL, verificar novamente"):
                            st.rerun()
                    else:
                        st.error("Não foi possível ler o bloco SQL do arquivo 'docs/DATABASE_MODEL.md'.")
                except FileNotFoundError:
                    st.error("Arquivo 'docs/DATABASE_MODEL.md' não encontrado. Verifique se ele está na pasta 'docs/'.")

            with st.expander("3️⃣ Dados da Escola", expanded=db.is_db_connected() and db_structure_exists):
                current_school = db.get_school()
                s_name = st.text_input("Nome da Escola", value=current_school['name'] if current_school else "Escola Modelo", disabled=not db_structure_exists)
                s_gre = st.text_input("Regional (GRE)", value=current_school['gre'] if current_school else "GRE-01", disabled=not db_structure_exists)

                if st.button("Salvar Dados da Escola", disabled=not db_structure_exists):
                    if db.upsert_school(s_name, s_gre):
                        st.success("Dados da escola atualizados!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar.")

            with st.expander("4️⃣ Importar Estrutura (Turmas e Disciplinas)", expanded=db.is_db_connected() and db_structure_exists):
                st.info("Cole aqui o conteúdo do seu arquivo `Escola.txt` para criar turmas e disciplinas em lote.")
                import_text = st.text_area("Conteúdo do Arquivo", height=200, placeholder="Nome da Escola\nGRE: 21\nNome da Turma\nCódigo da Turma: 123\nDisciplina 1\nDisciplina 2...", disabled=not db_structure_exists)

                if st.button("🚀 Processar Importação", disabled=not db_structure_exists):
                    if import_text:
                        with st.spinner("Processando..."):
                            success, msg = db.import_school_structure(import_text)
                            if success:
                                st.success("Importação concluída!")
                                st.text_area("Log de Importação", value=msg, height=150)
                            else:
                                st.error(f"Erro: {msg}")

            if db.is_db_connected() and db_structure_exists:
                st.divider()
                st.success("🎉 Configuração básica concluída!")
                st.markdown("""
                    O sistema está pronto para ser utilizado. Você já pode começar a gerenciar usuários, aulas e avaliações nas outras abas.

                    Para mais informações, tutoriais e atualizações, visite o repositório oficial do projeto no GitHub:

                    **[https://github.com/helioprofcaic/SysAva](https://github.com/helioprofcaic/SysAva)**
                """)

                st.warning("""
                ⚠️ **Importante: Privacidade e Deploy Próprio**

                Se você está acessando este sistema através de um link compartilhado (ex: Streamlit Cloud de outro professor), saiba que **você está utilizando o banco de dados dele**.

                Para utilizar o SysAva na **sua escola** com total privacidade e controle sobre os dados dos seus alunos:
                1. Acesse o GitHub acima e faça um **Fork** (cópia) do projeto.
                2. Crie sua própria conta no **Streamlit Cloud**.
                3. Faça o deploy do **seu** repositório.
                4. Configure suas próprias credenciais do Supabase na aba de Configuração do seu novo link.
                """)

    if tab1:
        with tab1:
            with st.expander("➕ Cadastrar Novo Usuário", expanded=False):
                with st.form("register_user_form", clear_on_submit=True):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        new_name = st.text_input("Nome Completo")
                        new_user = st.text_input("Usuário (Login)")
                        new_ra = st.text_input("RA (Registro Acadêmico)")
                    with col_b:
                        new_pass = st.text_input("Senha", type="password")
                        new_role = st.selectbox("Função", ["student", "teacher", "admin"], format_func=lambda x: {"student": "Aluno", "teacher": "Professor", "admin": "Administrador"}.get(x, x))

                    if st.form_submit_button("Cadastrar"):
                        if new_name and new_user and new_pass and new_ra:
                            hashed = auth.hash_password(new_pass)
                            _, error = db.create_user(new_user, hashed, new_name, new_ra, new_role)
                            if error:
                                st.error(f"Erro: {error}")
                            else:
                                st.success("Usuário cadastrado com sucesso!")
                                st.rerun()
                        else:
                            st.warning("Preencha todos os campos.")

            st.divider()
            st.subheader("Filtros de Usuários")

            # --- FILTROS ---
            col_f1, col_f2 = st.columns(2)

            role_map_filter = {"Todos": None, "Alunos": "student", "Professores": "teacher", "Administradores": "admin"}
            selected_role_key = col_f1.selectbox("Filtrar por Função", list(role_map_filter.keys()))

            selected_class_id = None
            if selected_role_key == "Alunos":
                classes = db.get_classes()
                class_options = {"Todas as Turmas": None}
                class_options.update({c['name']: c['id'] for c in classes})

                selected_class_name = col_f2.selectbox("Filtrar por Turma", list(class_options.keys()))
                selected_class_id = class_options[selected_class_name]

            # --- LÓGICA DE BUSCA E EXIBIÇÃO ---
            st.subheader("Usuários Cadastrados")
            users = []
            if selected_role_key == "Alunos" and selected_class_id is not None:
                # Caso específico: Alunos de uma turma
                users = db.get_students_by_class(selected_class_id)
            else:
                # Outros casos: buscar todos e filtrar em memória
                all_users = db.get_all_users()
                target_role = role_map_filter[selected_role_key]
                if target_role:
                    users = [u for u in all_users if u.get('role') == target_role]
                else:
                    users = all_users

            if users:
                # Cabeçalho da tabela customizada
                col_h1, col_h2, col_h3, col_h4 = st.columns([0.3, 0.3, 0.2, 0.2])
                col_h1.markdown("**Nome**")
                col_h2.markdown("**Usuário**")
                col_h3.markdown("**Função**")
                col_h4.markdown("**Ação**")
                st.divider()

                for u in users:
                    c1, c2, c3, c4 = st.columns([0.3, 0.3, 0.2, 0.2])
                    c1.write(u['name'])
                    c2.write(u['username'])
                    role_map = {"student": "Aluno", "teacher": "Professor", "admin": "Administrador"}
                    c3.write(role_map.get(u['role'], u['role']))

                    # Impede que o usuário exclua a si mesmo
                    if u['username'] != st.session_state.get('username'):
                        if c4.button("🗑️ Excluir", key=f"del_user_{u['username']}"):
                            _, err = db.delete_user(u['username'])
                            if err:
                                st.error(f"Erro: {err}")
                            else:
                                st.success(f"Usuário {u['username']} removido.")
                                st.rerun()
                    else:
                        c4.caption("Atual")
                    st.divider()
            else:
                st.info("Nenhum usuário encontrado com os filtros selecionados.")

    if tab2:
        with tab2:
            st.subheader("Aulas")

            with st.expander("➕ Criar Nova Turma"):
                with st.form("new_class_form", clear_on_submit=True):
                    class_name = st.text_input("Nome da Turma (ex: 3º Ano A - 2024)")
                    class_code = st.text_input("Código Único da Turma (ex: 3A2024)")
                    submitted_class = st.form_submit_button("Criar Turma")
                    if submitted_class and class_name and class_code:
                        # Use a default school for simplicity, as school management is not a primary UI feature
                        school_id = db.upsert_school("Escola Padrão", "N/A")
                        if school_id:
                            new_class_id = db.upsert_class(class_name, class_code, school_id)
                            if new_class_id:
                                st.success(f"Turma '{class_name}' criada com sucesso!")
                                st.rerun()
                            else:
                                st.error("Erro ao criar a turma. O código pode já existir.")
                        else:
                            st.error("Erro ao acessar a escola padrão.")

            # Seletor de Turma
            classes = db.get_classes()
            class_options = {c['name']: c['id'] for c in classes}
            selected_class_name = st.selectbox("Selecione a Turma para gerenciar", options=["-- Selecione --"] + list(class_options.keys()))

            if selected_class_name != "-- Selecione --":
                class_id = int(class_options[selected_class_name])

                with st.expander("➕ Criar Nova Disciplina e Vincular a esta Turma"):
                    with st.form("new_subject_form", clear_on_submit=True):
                        subject_name = st.text_input("Nome da Disciplina (ex: Programação com Python)")
                        submitted_subject = st.form_submit_button("Criar e Vincular Disciplina")
                        if submitted_subject and subject_name:
                            subject_id = db.upsert_subject(subject_name)
                            if subject_id:
                                db.link_subject_to_class(class_id, subject_id)
                                st.success(f"Disciplina '{subject_name}' vinculada à turma '{selected_class_name}'!")
                                st.rerun()
                            else:
                                st.error("Erro ao criar a disciplina.")

                # Seletor de Disciplina (baseado na turma)
                subjects = db.get_subjects_for_class(class_id)
                subject_options = {s['name']: s['id'] for s in subjects}

                if not subjects:
                    st.warning("Esta turma não possui disciplinas vinculadas. Crie e vincule uma no formulário acima.")
                else:
                    selected_subject_name = st.selectbox("Selecione a Disciplina", options=list(subject_options.keys()))
                    subject_id = subject_options[selected_subject_name]

                    st.divider()

                    # Formulário de Criação (Agora vinculado à disciplina selecionada)
                    with st.expander(f"Adicionar Nova Aula em {selected_subject_name}", expanded=False):
                        with st.form("new_lesson_form", clear_on_submit=True):
                            st.markdown("##### Preencher manualmente ou importar de arquivo .md")
                            uploaded_file = st.file_uploader("Importar Aula de arquivo Markdown", type=['md'])

                            title_val, desc_val, video_val = "", "", ""

                            if uploaded_file is not None:
                                # Lê o conteúdo do arquivo
                                content = uploaded_file.getvalue().decode("utf-8")

                                # Extrai o título (linha que começa com #)
                                title_match = re.search(r"^#\s*(.*)", content, re.MULTILINE)
                                if title_match:
                                    title_val = title_match.group(1).strip()
                                    # Remove a linha do título do conteúdo restante
                                    content = content[title_match.end():].strip()

                                # Extrai a URL do vídeo
                                video_match = re.search(r"\*\*Vídeo:\*\*\s*(https?://[^\s\n]+)", content, re.IGNORECASE)
                                if video_match:
                                    video_val = video_match.group(1).strip()
                                    # Remove a linha do vídeo do conteúdo restante
                                    content = content.replace(video_match.group(0), "").strip()

                                desc_val = content

                            title = st.text_input("Título da Aula", value=title_val)
                            description = st.text_area("Descrição", value=desc_val, height=250)
                            video_url = st.text_input("URL do Vídeo (YouTube)", value=video_val)
                            submitted = st.form_submit_button("Salvar Aula")

                            if submitted and title:
                                _, error = db.create_lesson(title, subject_id, description, video_url)
                                if error: st.error(f"Erro ao criar aula: {error}")
                                else: st.success(f"Aula criada com sucesso na disciplina {selected_subject_name}!"); st.rerun()

                    st.write(f"Aulas de **{selected_subject_name}** ({selected_class_name}):")
                    lessons = db.get_lessons_for_subject(subject_id)
                    st.dataframe(lessons, use_container_width=True, column_config={"id": "ID", "title": "Título", "video_url": "Link", "created_at": "Criado em"})

                    if lessons:
                        with st.expander("🗑️ Excluir Aulas (Individual ou Lote)"):
                            st.warning("Atenção: A exclusão é permanente e removerá também os quizzes e posts do fórum associados.")

                            lesson_options = {f"{l['id']} - {l['title']}": l['id'] for l in lessons}
                            selected_to_delete = st.multiselect("Selecione as aulas para excluir:", options=list(lesson_options.keys()))

                            if selected_to_delete:
                                if st.button(f"Confirmar Exclusão de {len(selected_to_delete)} aula(s)"):
                                    errors = []
                                    for lesson_key in selected_to_delete:
                                        lid = lesson_options[lesson_key]
                                        data, err = db.delete_lesson(lid)
                                        if err:
                                            errors.append(f"Erro em {lesson_key}: {err}")
                                        elif not data:
                                            errors.append(f"Não excluído (RLS/Permissão): {lesson_key}")
                                        time.sleep(0.1)

                                    if errors:
                                        for e in errors: st.error(e)
                                    else:
                                        st.success("Aulas excluídas com sucesso!")
                                        time.sleep(0.5)
                                        st.rerun()

    if tab_training:
        with tab_training:
            st.subheader("🚀 Gerenciar Treinamentos e Olimpíadas")
            st.markdown("Crie disciplinas flutuantes e vincule-as a múltiplas turmas. Ideal para preparatórios, olimpíadas e revisões.")

            with st.expander("➕ Criar Novo Treinamento/Olimpíada"):
                with st.form("new_training_form", clear_on_submit=True):
                    training_name = st.text_input("Nome do Treinamento (ex: Olimpíada de Informática 2024)")
                    if st.form_submit_button("Criar Treinamento"):
                        if training_name:
                            # Cria a disciplina com o tipo 'training'
                            training_id = db.upsert_subject(training_name, type='training')
                            if training_id:
                                st.success(f"Treinamento '{training_name}' criado! Agora vincule as turmas abaixo.")
                                st.rerun()
                            else:
                                st.error("Erro ao criar o treinamento.")

            st.divider()
            st.subheader("Vincular Turmas e Gerenciar Aulas")

            # 1. Selecionar o treinamento
            all_subjects = db.get_subjects()
            training_subjects = {s['name']: s['id'] for s in all_subjects if s.get('type') == 'training'}

            if not training_subjects:
                st.info("Nenhum treinamento criado ainda. Crie um no formulário acima.")
            else:
                selected_training_name = st.selectbox("Selecione o Treinamento para gerenciar:", options=list(training_subjects.keys()))
                training_id = int(training_subjects[selected_training_name])

                # 2. Vincular turmas
                st.markdown("#### Vincular Turmas a este Treinamento")
                all_classes = db.get_classes()
                class_map = {c['id']: c['name'] for c in all_classes}

                # Turmas atualmente vinculadas
                linked_class_ids = db.get_classes_for_subject(training_id)

                selected_class_ids = st.multiselect(
                    "Selecione todas as turmas que participarão deste treinamento:",
                    options=list(class_map.keys()),
                    format_func=lambda class_id: class_map[class_id],
                    default=list(linked_class_ids) if linked_class_ids else []
                )

                if st.button("💾 Salvar Vínculos de Turmas"):
                    db.update_training_links(training_id, selected_class_ids)
                    st.success("Vínculos de turmas atualizados com sucesso!")
                    st.rerun()

                st.divider()

                # 3. Gerenciar aulas do treinamento (reaproveitando a lógica anterior)
                st.markdown(f"#### Aulas de **{selected_training_name}**")
                with st.expander(f"Adicionar Nova Aula em {selected_training_name}", expanded=False):
                    with st.form(f"new_lesson_training_form_{training_id}", clear_on_submit=True):
                        title = st.text_input("Título da Aula")
                        description = st.text_area("Descrição")
                        video_url = st.text_input("URL do Vídeo (YouTube)")
                        submitted = st.form_submit_button("Salvar Aula")

                        if submitted and title:
                            _, error = db.create_lesson(title, training_id, description, video_url)
                            if error:
                                st.error(f"Erro ao criar aula: {error}")
                            else:
                                st.success(f"Aula criada com sucesso no treinamento {selected_training_name}!")
                                st.rerun()

                lessons = db.get_lessons_for_subject(training_id)
                st.dataframe(lessons, use_container_width=True, column_config={"id": "ID", "title": "Título", "video_url": "Link", "created_at": "Criado em"})


    if tab3:
        with tab3:
            st.subheader("Gerenciar Quizzes")

            # --- Seletor de Contexto em Cascata ---
            classes = db.get_classes()
            if not classes:
                st.warning("Cadastre turmas primeiro no sistema.")
            else:
                class_options = {c['name']: c['id'] for c in classes}
                selected_class_name_qz = st.selectbox("Selecione a Turma", options=["-- Selecione --"] + list(class_options.keys()), key="sel_class_qz_t3")

                if selected_class_name_qz != "-- Selecione --":
                    class_id_qz = int(class_options[selected_class_name_qz])
                    subjects = db.get_subjects_for_class(class_id_qz)

                    if not subjects:
                        st.warning("Esta turma ainda não possui disciplinas cadastradas.")
                    else:
                        subject_options = {s['name']: s['id'] for s in subjects}
                        selected_subject_name_qz = st.selectbox("Selecione a Disciplina", options=["-- Selecione --"] + list(subject_options.keys()), key="sel_subj_qz_t3")

                        if selected_subject_name_qz != "-- Selecione --":
                            subject_id_qz = int(subject_options[selected_subject_name_qz])
                            lessons = db.get_lessons_for_subject(subject_id_qz)

                            if not lessons:
                                st.warning("Nenhuma aula cadastrada nesta disciplina para receber um quiz.")
                            else:
                                lesson_map = {lesson['title']: lesson['id'] for lesson in lessons}
                                selected_lesson_title = st.selectbox("Selecione a Aula", options=["-- Selecione --"] + list(lesson_map.keys()), key="sel_lesson_qz_t3")

                                if selected_lesson_title != "-- Selecione --":
                                    lesson_id = int(lesson_map[selected_lesson_title])
                                    st.divider()

                                    # Verifica se já existe quiz para esta aula
                                    quiz = db.get_quiz_for_lesson(lesson_id)

                                    if not quiz:
                                        st.info("Nenhum quiz encontrado para esta aula.")
                                        with st.form("create_quiz_form"):
                                            st.write("Criar Novo Quiz")
                                            quiz_title = st.text_input("Título do Quiz")
                                            submitted = st.form_submit_button("Criar Quiz")
                                            if submitted and quiz_title:
                                                _, error = db.create_quiz(lesson_id, quiz_title)
                                                if error:
                                                    st.error(f"Erro ao criar quiz: {error}")
                                                else:
                                                    st.success("Quiz criado com sucesso! Agora você pode adicionar questões.")
                                                    st.rerun()
                                    else:
                                        st.markdown(f"### Editando Quiz: {quiz['title']}")

                                        # Exibir questões existentes
                                        questions = db.get_quiz_questions(quiz['id'])
                                        if questions:
                                            with st.expander(f"Ver {len(questions)} questões cadastradas", expanded=False):
                                                for i, q in enumerate(questions):
                                                    col_q, col_del = st.columns([0.9, 0.1])
                                                    with col_q:
                                                        st.markdown(f"**{i+1}. {q['question_text']}**")
                                                        st.caption(f"Opções: {', '.join(q['options'])} | Correta: {q['options'][q['correct_option_index']]}")
                                                    with col_del:
                                                        if st.button("🗑️", key=f"del_qq_{q['id']}", help="Excluir questão"):
                                                            db.delete_quiz_question(q['id'])
                                                            st.rerun()
                                                    st.divider()

                                        st.markdown("#### Adicionar Nova Questão")
                                        with st.form("add_question_form", clear_on_submit=True):
                                            question_text = st.text_input("Enunciado da Questão")
                                            options_str = st.text_area("Opções (separadas por vírgula)", help="Ex: Azul, Vermelho, Verde")
                                            correct_option_index = st.number_input("Índice da Opção Correta (0 = 1ª opção)", min_value=0, step=1)

                                            submitted = st.form_submit_button("Adicionar Questão")

                                            if submitted and question_text and options_str:
                                                options = [opt.strip() for opt in options_str.split(',') if opt.strip()]
                                                if len(options) < 2:
                                                    st.error("Adicione pelo menos 2 opções.")
                                                elif correct_option_index >= len(options):
                                                    st.error(f"Índice inválido. Máximo: {len(options)-1}")
                                                else:
                                                    _, error = db.create_quiz_question(quiz['id'], question_text, options, correct_option_index)
                                                    if error:
                                                        st.error(f"Erro ao adicionar questão: {error}")
                                                    else:
                                                        st.success("Questão adicionada com sucesso!")
                                                        st.rerun()

    if tab4:
        with tab4:
            st.subheader("Gerenciar Avaliações (Provas)")

            # --- Seletor de Contexto (Igual ao de Aulas) ---
            classes = db.get_classes()
            class_options = {c['name']: c['id'] for c in classes}
            selected_class_name_av = st.selectbox("Selecione a Turma", options=["-- Selecione --"] + list(class_options.keys()), key="sel_class_av")

            if selected_class_name_av != "-- Selecione --":
                class_id_av = int(class_options[selected_class_name_av])
                subjects = db.get_subjects_for_class(class_id_av)
                subject_options = {s['name']: s['id'] for s in subjects}

                if not subjects:
                    st.warning("Turma sem disciplinas.")
                else:
                    selected_subject_name_av = st.selectbox("Selecione a Disciplina", options=["-- Selecione --"] + list(subject_options.keys()), key="sel_subj_av")

                    if selected_subject_name_av != "-- Selecione --":
                        subject_id_av = int(subject_options[selected_subject_name_av])

                        st.divider()

                        # --- Listagem e Criação de Avaliações ---
                        assessments = db.get_assessments_by_subject(subject_id_av)

                        col_list, col_create = st.columns([0.6, 0.4])

                        with col_create:
                            st.markdown("#### Nova Avaliação")
                            with st.form("create_assessment_form"):
                                av_type = st.selectbox("Tipo", ["MN1", "MN2", "MN3", "RM", "Outros"])
                                av_title = st.text_input("Título (ex: Prova de Python Básico)")
                                if st.form_submit_button("Criar Avaliação"):
                                    # Verifica se já existe esse tipo para a disciplina (opcional, mas recomendado)
                                    existing = [a for a in assessments if a['type'] == av_type]
                                    if existing and av_type != "Outros":
                                        st.warning(f"Já existe uma avaliação {av_type} para esta disciplina.")
                                    else:
                                        _, err = db.create_assessment(subject_id_av, av_type, av_title)
                                        if err: st.error(err)
                                        else: st.rerun()

                        with col_list:
                            st.markdown("#### Avaliações Existentes")
                            if not assessments:
                                st.info("Nenhuma avaliação criada.")

                            # Seletor para editar uma avaliação específica
                            assessment_map = {f"{a['type']} - {a['title']}": a for a in assessments}
                            selected_assessment_key = st.selectbox("Selecione para editar questões:", options=["-- Selecione --"] + list(assessment_map.keys()))

                        # --- Gerenciamento de Questões da Avaliação Selecionada ---
                        if selected_assessment_key != "-- Selecione --":
                            assessment = assessment_map[selected_assessment_key]
                            st.divider()
                            st.markdown(f"### Editando: {assessment['title']} ({assessment['type']})")

                            # Lista questões atuais
                            questions = db.get_assessment_questions(assessment['id'])
                            st.write(f"Questões cadastradas: {len(questions)}/10")
                            for i, q in enumerate(questions):
                                col_q, col_del = st.columns([0.9, 0.1])
                                with col_q:
                                    tipo_icon = "📝" if q.get('question_type') == 'subjective' else "🔘"
                                    st.text(f"{i+1}. {tipo_icon} {q['question_text']}")
                                    if q.get('question_type') == 'subjective' and q.get('options') and "LINK_REQUIRED" in q['options']:
                                        st.caption("   ↳ 🔗 Solicita link externo (GitHub/Drive)")
                                with col_del:
                                    if st.button("🗑️", key=f"del_aq_{q['id']}", help="Excluir questão"):
                                        db.delete_assessment_question(q['id'])
                                        st.rerun()

                            st.divider()

                            # --- Importação de Questões de Quizzes ---
                            with st.expander("📂 Importar do Banco de Questões (Quizzes)", expanded=False):
                                st.caption(f"Questões disponíveis para {assessment['type']} (filtradas por conteúdo).")

                                # Lógica para sugerir o escopo
                                is_ds_class = any(term in selected_class_name_av.upper() for term in ["DS", "SIS", "DESENVOLVIMENTO"])
                                default_scope_index = 0 if is_ds_class else 1

                                scope_mode_option = st.radio(
                                    "Escopo de Busca:",
                                    ["Automático (Cursos Técnicos)", "Manual (por intervalo de aulas)"],
                                    index=default_scope_index,
                                    horizontal=True,
                                    key=f"scope_{assessment['id']}"
                                )
                                scope_mode = "auto" if "Automático" in scope_mode_option else "manual"

                                workload_val = 80
                                start_lesson, end_lesson = None, None

                                if scope_mode == 'auto':
                                    workload_opt = st.radio("Carga Horária da Disciplina:", ["40h (8 aulas/sem)", "80h (10 aulas/sem)"], horizontal=True, key=f"wl_{assessment['id']}", index=1 if is_ds_class else 0)
                                    workload_val = 80 if "80h" in workload_opt else 40
                                else: # Manual
                                    col_start, col_end = st.columns(2)
                                    start_lesson = col_start.number_input("Da Aula (Nº):", min_value=1, value=1, step=1)
                                    end_lesson = col_end.number_input("Até a Aula (Nº):", min_value=start_lesson, value=5, step=1)

                                quiz_questions = db.get_all_quiz_questions_for_subject(subject_id_av, assessment['type'], workload_val, scope_mode, start_lesson, end_lesson)                            

                                if not quiz_questions:
                                    st.info(f"Nenhuma questão encontrada nos quizzes para o escopo selecionado.")
                                else:
                                    # Mapeia questões para seleção
                                    q_options = {f"{q['id']} - {q['question_text']}": q for q in quiz_questions}

                                    # Sorteio prévio de 10 questões
                                    session_key_rand = f"rand_q_{assessment['id']}_{workload_val}_{start_lesson}_{end_lesson}"
                                    if session_key_rand not in st.session_state:
                                        all_keys = list(q_options.keys())
                                        st.session_state[session_key_rand] = random.sample(all_keys, min(10, len(all_keys)))

                                    if st.button("🎲 Sortear Novamente (10 questões)", key=f"reroll_{assessment['id']}"):
                                        all_keys = list(q_options.keys())
                                        st.session_state[session_key_rand] = random.sample(all_keys, min(10, len(all_keys)))
                                        st.rerun()

                                    selected_keys = st.multiselect(
                                        "Selecione as questões para importar:",
                                        options=list(q_options.keys()),
                                        default=list(st.session_state.get(session_key_rand, []))
                                    )

                                    if st.button(f"📥 Importar {len(selected_keys)} Questões Selecionadas", key=f"imp_sel_{assessment['id']}"):
                                        count = 0
                                        for key in selected_keys:
                                            q = q_options[key]
                                            _, err = db.create_assessment_question(assessment['id'], q['question_text'], 'objective', q.get('options', []), q.get('correct_option_index', 0))
                                            if not err: count += 1
                                        st.success(f"{count} questões importadas com sucesso!")
                                        st.rerun()

                            st.markdown("#### Adicionar Questão")
                            with st.form("add_assessment_question"):
                                q_type = st.radio("Tipo da Questão", ["Objetiva", "Subjetiva"], horizontal=True)
                                q_text = st.text_area("Enunciado da Questão")

                                options = []
                                correct_idx = 0

                                if q_type == "Objetiva":
                                    opts_str = st.text_input("Opções (separadas por vírgula)", help="Ex: A, B, C, D")
                                    correct_idx = st.number_input("Índice da Correta (0 = 1ª opção)", min_value=0, step=1)
                                    if opts_str:
                                        options = [o.strip() for o in opts_str.split(',') if o.strip()]
                                else:
                                    st.info("ℹ️ O aluno terá um campo de texto para a resposta.")
                                    require_link = st.checkbox("Adicionar campo para envio de Link (GitHub/Drive)?", value=True)
                                    options = ["LINK_REQUIRED"] if require_link else []
                                    correct_idx = 0 # Padrão 0 conforme solicitado

                                if st.form_submit_button("Salvar Questão"):
                                    type_db = 'subjective' if q_type == "Subjetiva" else 'objective'
                                    _, err = db.create_assessment_question(assessment['id'], q_text, type_db, options, correct_idx)
                                    if err: st.error(err)
                                    else: 
                                        st.success("Questão adicionada!")
                                        st.rerun()

    if tab_audit:
        with tab_audit:
            st.subheader("🔍 Auditoria de Questões de Quizzes")
            st.markdown("Esta ferramenta analisa todas as questões de quizzes em busca de problemas comuns, como opções duplicadas ou caracteres inválidos, e permite a correção.")

            # Filtros de Contexto
            audit_type_label = st.radio("Alvo da Auditoria", ["Banco Mestre (Quizzes)", "Provas Geradas (Avaliações)"], horizontal=True)
            audit_type = 'quiz' if 'Quizzes' in audit_type_label else 'assessment'

            classes = db.get_classes()
            class_options_aud = {c['name']: c['id'] for c in classes} if classes else {}
            selected_class_name_aud = st.selectbox("Selecione a Turma (Opcional)", options=["-- Todas as Turmas --"] + list(class_options_aud.keys()), key="sel_class_aud")
            
            subject_id_aud = None
            if selected_class_name_aud != "-- Todas as Turmas --":
                class_id_aud = int(class_options_aud[selected_class_name_aud])
                subjects_aud = db.get_subjects_for_class(class_id_aud)
                subj_opt_aud = {s['name']: s['id'] for s in subjects_aud}
                selected_subject_name_aud = st.selectbox("Selecione a Disciplina", options=["-- Todas as Disciplinas --"] + list(subj_opt_aud.keys()), key="sel_subj_aud")
                if selected_subject_name_aud != "-- Todas as Disciplinas --":
                    subject_id_aud = int(subj_opt_aud[selected_subject_name_aud])

            if 'audit_results' not in st.session_state:
                st.session_state.audit_results = None

            if st.button("🚀 Iniciar Análise de Questões"):
                with st.spinner("Analisando o banco de questões... Isso pode levar um momento."):
                    if audit_type == 'quiz':
                        if subject_id_aud:
                            all_questions = db.get_all_quiz_questions_for_subject(subject_id_aud, assessment_type=None)
                            quizzes_for_subj = db.get_quizzes_for_subject(subject_id_aud)
                            context_map = {q['id']: q['title'] for q in quizzes_for_subj}
                        else:
                            all_questions = db.get_all_quiz_questions()
                            context_map = {}
                    else:
                        if subject_id_aud:
                            assessments = db.get_assessments_by_subject(subject_id_aud)
                            context_map = {a['id']: a['title'] for a in assessments}
                            all_questions = []
                            for a in assessments:
                                all_questions.extend(db.get_assessment_questions(a['id']))
                        else:
                            all_questions = db.get_all_assessment_questions()
                            assessments = db.get_all_assessments()
                            context_map = {a['id']: a['title'] for a in assessments}

                    issues = []
                    evaluated_count = len(all_questions) if all_questions else 0
                    
                    for q in all_questions:
                        q_issues = []
                        # 1. Verifica opções duplicadas
                        # Protege contra q['options'] nulo (caso subjetiva)
                        opts = q.get('options')
                        if opts and isinstance(opts, list) and len(opts) != len(set(opts)):
                            q_issues.append("Opções duplicadas encontradas.")

                        # 2. Verifica caracteres suspeitos nas opções
                        suspicious_pattern = r'\[x\]|\(x\)|\*$'
                        if opts and isinstance(opts, list):
                            for opt in opts:
                                if opt.strip() in ['*', '**']:
                                    continue
                                if re.search(suspicious_pattern, opt, re.IGNORECASE):
                                    q_issues.append(f"Caracteres suspeitos (ex: '[x]') na opção: '{opt}'.")
                                    break 

                        # 3. Verifica iframe/embed com erro (about:blank)
                        q_text = q.get('question_text', '')
                        if 'about:blank' in q_text:
                            q_issues.append("O texto da questão contém um erro de embed/PDF (about:blank).")
                        if opts and isinstance(opts, list):
                            for opt in opts:
                                if 'about:blank' in opt:
                                    q_issues.append("Uma das opções contém um erro de embed/PDF (about:blank).")

                        # 4. Verifica opções genéricas/vazias (ex: "Opção A")
                        if opts and isinstance(opts, list) and len(opts) > 1:
                            # Verifica se todas as opções correspondem ao padrão "Opção [Letra]"
                            is_generic = all(re.match(r'^\s*Opção\s+[A-Z]\s*$', opt, re.IGNORECASE) for opt in opts)
                            if is_generic:
                                q_issues.append("Opções parecem ser genéricas (ex: 'Opção A', 'Opção B') e podem indicar um erro de importação.")

                        if q_issues:
                            issues.append({"question": q, "problems": q_issues})

                    st.session_state.audit_results = {
                        "issues": issues,
                        "evaluated_count": evaluated_count,
                        "quiz_map": context_map,
                        "audit_type": audit_type
                    }
                    st.rerun()

            if st.session_state.audit_results is not None:
                st.divider()
                res_dict = st.session_state.audit_results
                
                # Suporte para cache antigo ou o novo formato
                if isinstance(res_dict, list):
                    results = res_dict
                    evaluated = len(results)
                    context_map = {}
                    saved_audit_type = 'quiz'
                else:
                    results = res_dict.get("issues", [])
                    evaluated = res_dict.get("evaluated_count", 0)
                    context_map = res_dict.get("quiz_map", {})
                    saved_audit_type = res_dict.get("audit_type", "quiz")

                st.markdown(f"### 🚨 Análise Concluída: {len(results)} problemas encontrados em {evaluated} questões avaliadas.")

                if not results:
                    st.success("Nenhum problema óbvio encontrado nas questões selecionadas!")
                else:
                    prefix = "Quiz:" if saved_audit_type == "quiz" else "Avaliação:"
                    foreign_id_key = "quiz_id" if saved_audit_type == "quiz" else "assessment_id"
                    
                    for item in results:
                        q = item['question']
                        context_name = context_map.get(q.get(foreign_id_key), f"ID {q.get(foreign_id_key)}")
                        with st.expander(f"[{prefix} {context_name}] Questão {q['id']}: {q.get('question_text', '')[:80]}"):
                            st.error("Problemas Identificados:")
                            for prob in item['problems']:
                                st.write(f"- {prob}")

                            curr_opts = q.get('options', [])
                            st.markdown("**Opções Atuais:**")
                            st.json(curr_opts)

                            if curr_opts and isinstance(curr_opts, list):
                                st.markdown("---")
                                st.markdown("**Sugerir Correção:**")

                                # Sugestão de limpeza
                                cleaned_options = [re.sub(r'\s*\[x\]|\s*\(x\)', '', opt).strip() for opt in curr_opts]
                                unique_cleaned_options = list(dict.fromkeys(cleaned_options)) # Remove duplicadas mantendo a ordem

                                st.info("A sugestão abaixo remove caracteres como '[x]' e opções duplicadas. Verifique se a opção correta permanece válida.")

                                new_options_str = st.text_area("Opções Corrigidas (separadas por vírgula)", 
                                                               value=", ".join(unique_cleaned_options), 
                                                               key=f"new_opts_{saved_audit_type}_{q['id']}")

                                if st.button("💾 Salvar Correção", key=f"save_aud_{saved_audit_type}_{q['id']}"):
                                    final_options = [opt.strip() for opt in new_options_str.split(',') if opt.strip()]
                                    
                                    if saved_audit_type == 'quiz':
                                        _, err = db.update_quiz_question_options(q['id'], final_options)
                                    else:
                                        _, err = db.update_assessment_question_options(q['id'], final_options)
                                        
                                    if err: st.error(f"Erro ao salvar: {err}")
                                    else: st.success("Opções da questão atualizadas! Re-analise para confirmar.")

    if tab_reviewer:
        with tab_reviewer:
            st.subheader("🔑 Revisor de Gabaritos")
            st.info("Utilize esta aba para deslizar rapidamente pelas questões e revisar/corrigir se o Gabarito (bolinha preenchida) está correto.")

            # Seletores básicos
            classes = db.get_classes()
            if not classes:
                st.warning("Nenhuma turma cadastrada.")
            else:
                class_options = {c['name']: c['id'] for c in classes}
                if 'rev_sel_class' not in st.session_state: st.session_state.rev_sel_class = list(class_options.keys())[0]
                sel_class = st.selectbox("Selecione a Turma:", list(class_options.keys()), key="rev_class_sel", index=list(class_options.keys()).index(st.session_state.rev_sel_class) if st.session_state.rev_sel_class in class_options else 0)
                st.session_state.rev_sel_class = sel_class

                subjects = db.get_subjects_for_class(int(class_options[sel_class]))
                if not subjects:
                    st.warning("Nenhuma disciplina vinculada.")
                else:
                    subject_options = {s['name']: s['id'] for s in subjects}
                    if 'rev_sel_subject' not in st.session_state: st.session_state.rev_sel_subject = list(subject_options.keys())[0]
                    sel_subject = st.selectbox("Selecione a Disciplina:", list(subject_options.keys()), key="rev_subj_sel", index=list(subject_options.keys()).index(st.session_state.rev_sel_subject) if st.session_state.rev_sel_subject in subject_options else 0)
                    st.session_state.rev_sel_subject = sel_subject

                    subject_id = int(subject_options[sel_subject])

                    review_type = st.radio("Qual banco revisar?", ["Banco Mestre (Quizzes)", "Provas Geradas (Avaliações)"], horizontal=True, key="rev_type_radio")
                    
                    if st.button("🚀 Carregar Questões para Revisão", use_container_width=True):
                        if review_type == "Banco Mestre (Quizzes)":
                            questions = db.get_all_quiz_questions_for_subject(subject_id)
                            st.session_state.rev_questions = questions
                            st.session_state.rev_type = "quiz"
                            st.rerun()
                        else:
                            assessments = db.get_assessments_by_subject(subject_id)
                            ass_ids = [a['id'] for a in assessments]
                            all_ass_q = db.get_all_assessment_questions()
                            questions = [q for q in all_ass_q if q['assessment_id'] in ass_ids]
                            st.session_state.rev_questions = questions
                            st.session_state.rev_type = "assessment"
                            st.rerun()
                            
            if 'rev_questions' in st.session_state and st.session_state.rev_questions:
                st.divider()
                st.markdown(f"**Total de Questões Carregadas:** {len(st.session_state.rev_questions)}")
                
                # --- Funcionalidade de Exportação de Gabarito ---
                export_data = []
                for idx, q in enumerate(st.session_state.rev_questions):
                    opts = q.get('options', [])
                    c_idx = q.get('correct_option_index', 0)
                    # Fallback para caso o índice esteja fora do range
                    correct_text = opts[c_idx] if 0 <= c_idx < len(opts) else "N/A"
                    correct_letter = chr(65 + c_idx) if 0 <= c_idx < len(opts) else "?"
                    
                    export_data.append({
                        "Nº": idx + 1,
                        "ID": q['id'],
                        "Enunciado": q['question_text'],
                        "Letra": correct_letter,
                        "Resposta Correta": correct_text
                    })
                
                df_export = pd.DataFrame(export_data)

                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    st.download_button(
                        label="📥 Exportar Gabarito (CSV)",
                        data=df_export.to_csv(index=False).encode('utf-8-sig'),
                        file_name=f"gabarito_{sel_subject.replace(' ', '_')}_{st.session_state.rev_type}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_exp2:
                    if st.button("🖨️ PDF para Impressão", use_container_width=True):
                        school_info = db.get_school()
                        school_name = school_info['name'] if school_info else "Escola Técnica"
                        html_print = generate_printable_answer_key_html(school_name, sel_subject, st.session_state.rev_type.upper(), export_data)
                        components.html(html_print, height=600, scrolling=True)
                        st.stop()
                
                for i, q in enumerate(st.session_state.rev_questions):
                    q_id = q['id']
                    c_txt, c_action = st.columns([0.8, 0.2])
                    
                    with c_txt:
                        # Identificador de Quiz/Avaliação se possível
                        if st.session_state.rev_type == "quiz":
                            ctx_label = f"[Quiz {q.get('quiz_id')}] "
                        else:
                            ctx_label = f"[Avaliação {q.get('assessment_id')}] "
                            
                        st.markdown(f"**{i+1}.** {ctx_label} {q['question_text']}")
                        current_idx = q.get('correct_option_index', 0)
                        opts = q.get('options', [])
                        
                        # Fallback se current_idx estiver out of bounds
                        if current_idx >= len(opts): current_idx = 0
                        
                        # st.radio precisa do index
                        new_idx = st.radio(
                            f"Opções da Questão {q_id}:", 
                            opts, 
                            index=current_idx, 
                            key=f"rev_rad_{st.session_state.rev_type}_{q_id}",
                            label_visibility="collapsed"
                        )
                        
                    with c_action:
                        real_new_idx = opts.index(new_idx) if new_idx in opts else current_idx
                        if real_new_idx != current_idx:
                            st.warning("⚠️ Alterado (Não salvo)")
                            
                        if st.button("💾 Atualizar Gabarito", key=f"rev_btn_{st.session_state.rev_type}_{q_id}"):
                            if st.session_state.rev_type == "quiz":
                                _, err = db.update_quiz_question_correct_index(q_id, real_new_idx)
                            else:
                                _, err = db.update_assessment_question_correct_index(q_id, real_new_idx)
                                
                            if err: 
                                st.error(err)
                            else: 
                                # Atualiza cache local
                                q['correct_option_index'] = real_new_idx
                                st.rerun()

                    st.markdown("---")

    if tab5:
        with tab5:
            st.subheader("🤖 Simulador de Atividades de Aluno")
            st.info("Esta ferramenta preenche o histórico de um aluno com todas as aulas e quizzes para fins de teste. A ação de 'Zerar' apaga permanentemente o histórico e as provas realizadas pelo aluno.")

            users = db.get_all_users()
            students = {u['username']: u['name'] for u in users if u['role'] == 'student'}

            if not students:
                st.warning("Nenhum aluno cadastrado para simular.")
            else:
                selected_student_username = st.selectbox(
                    "Selecione o Aluno (por login/RA) para gerenciar:", 
                    options=list(students.keys()),
                    format_func=lambda username: f"{students[username]} ({username})"
                )

                if selected_student_username:
                    st.markdown("---")
                    st.markdown(f"#### Progresso Atual de **{students[selected_student_username]}**")

                    progress = db.get_user_progress_stats(selected_student_username)
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Aulas Vistas", progress.get('lessons', 0))
                    col2.metric("Quizzes Feitos", progress.get('quizzes', 0))
                    col3.metric("Posts no Fórum", progress.get('forum', 0))

                    st.markdown("---")

                    col_sim, col_reset = st.columns(2)

                    with col_sim:
                        st.markdown("#### ✅ Simular Conclusão Total")
                        if st.button("🚀 Simular Todas as Atividades"):
                            with st.spinner("Simulando..."):
                                _, err = db.simulate_student_activities(selected_student_username)
                                if err: st.error(f"Erro na simulação: {err}")
                                else: st.rerun()

                    with col_reset:
                        st.markdown("#### ⚠️ Zerar Dados do Aluno")
                        st.warning("Apaga histórico e provas. Use para liberar o RA para um aluno real.")

                        confirm_reset = st.checkbox(f"Confirmo que desejo zerar todos os dados de {students[selected_student_username]}")

                        if st.button("🗑️ Zerar Dados Agora", disabled=not confirm_reset):
                            with st.spinner("Apagando dados..."):
                                _, err = db.reset_student_data(selected_student_username)
                                if err: st.error(f"Erro ao zerar dados: {err}")
                                else: st.rerun()

    if tab6:
        with tab6:
            st.subheader("📊 Relatórios de Atividades")
            st.markdown("Visualize as ações recentes dos usuários na plataforma.")

            # Filtros
            users = db.get_all_users()
            user_options = ["Todos"] + [u['username'] for u in users]
            selected_user_filter = st.selectbox("Filtrar por Usuário", user_options)

            # Busca dados
            if selected_user_filter != "Todos":
                history_data = db.get_user_history(selected_user_filter)
            else:
                history_data = db.get_all_history(limit=500)

            if history_data:
                # Exibe tabela
                st.dataframe(history_data, use_container_width=True, column_config={
                    "username": "Usuário",
                    "activity": "Ação Realizada",
                    "timestamp": "Data/Hora"
                })

                # Botão de Exportação
                df = pd.DataFrame(history_data)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Baixar Relatório Completo (CSV)", data=csv, file_name="relatorio_atividades.csv", mime="text/csv")
            else:
                st.info("Nenhuma atividade registrada com os filtros atuais.")