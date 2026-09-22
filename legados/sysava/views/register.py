import streamlit as st
import time
from legados.sysava.services import database as db
from legados.sysava.services import auth

def show_page():
    st.title("📝 Cadastro de Novo Aluno")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("registration_form"):
            role_option = st.selectbox("Tipo de Conta", ["Aluno", "Administrador"])
            name = st.text_input("Nome Completo")
            username = st.text_input("Usuário (para login)")
            ra = st.text_input("RA (Registro do Aluno)")
            password = st.text_input("Senha", type="password")
            password_confirm = st.text_input("Confirme a Senha", type="password")
            admin_code = st.text_input("Código de Administrador (Necessário para Admin)", type="password")
            
            submitted = st.form_submit_button("Cadastrar")

            if submitted:
                # Limpeza de dados
                username = username.strip()
                ra = ra.strip()

                if not all([name, username, password, password_confirm, ra]):
                    st.warning("Por favor, preencha todos os campos.")
                elif password != password_confirm:
                    st.error("As senhas não coincidem.")
                elif not db.is_db_connected():
                    st.error("Modo offline. Não é possível registrar novos usuários.")
                else:
                    # Verifica se o usuário já existe
                    if db.get_user(username.strip()):
                        st.error("Este nome de usuário já existe.")
                    elif any(u.get('ra') == ra for u in db.get_all_users()):
                        st.error("Este RA já está cadastrado no sistema. Não é permitido duplicar registros.")
                    else:
                        hashed = auth.hash_password(password)
                        user_role = 'student'
                        valid_registration = True

                        if role_option == 'Administrador':
                            secret_admin_code = st.secrets.get("ADMIN_REGISTRATION_CODE")
                            if not admin_code:
                                st.error("O código de administrador é obrigatório para contas de administrador.")
                                valid_registration = False
                            elif secret_admin_code and admin_code == secret_admin_code:
                                user_role = 'admin'
                                st.toast("Código de administrador correto!")
                            else:
                                st.error("Código de administrador incorreto.")
                                valid_registration = False
                        
                        if valid_registration:
                            data, error = db.create_user(username, hashed, name, ra, role=user_role)
                            if error:
                                st.error(f"Erro no cadastro: {error}")
                            else:
                                st.success("Usuário cadastrado com sucesso! Redirecionando...")
                                time.sleep(2)
                                st.session_state.page = 'login'
                                st.rerun()
        
        st.divider()
        if st.button("Já tem uma conta? Faça o login"):
            st.session_state.page = 'login'
            st.rerun()