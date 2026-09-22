import streamlit as st
import time
from legados.sysava.services import database as db

def show_page():
    # Verifica se a página foi chamada a partir de uma aula específica
    lesson_id = st.session_state.get('context_lesson_id')

    if lesson_id:
        lesson = db.get_lesson_by_id(lesson_id)
        lesson_title = f": {lesson['title']}" if lesson else ""
        st.header(f"💬 Fórum{lesson_title}")
        if st.button("⬅️ Voltar para as Aulas"):
            st.session_state.page = 'Aulas'
            st.rerun()
    else:
        st.header("💬 Fórum Geral")
    
    with st.form("novo_post"):
        nova_msg = st.text_area("Escreva sua dúvida ou comentário:")
        submit_btn = st.form_submit_button("Enviar")
        
        if submit_btn and nova_msg:
            if db.is_db_connected():
                # Passa o lesson_id se existir
                _, error = db.add_forum_post(st.session_state['usuario'], nova_msg, lesson_id=lesson_id)
                if error:
                    st.error(f"Erro: {error}")
                else:
                    activity_log = "Enviou mensagem no fórum"
                    if lesson_id:
                        lesson = db.get_lesson_by_id(lesson_id)
                        if lesson and lesson.get('subject_id'):
                            activity_log += f" | subject_id:{lesson['subject_id']}"
                    db.add_user_history(st.session_state.get('username'), activity_log)
                    st.success("Mensagem enviada!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("Fórum indisponível offline.")

    st.divider()
    st.subheader("Últimas Discussões")
    
    # Passa o lesson_id para buscar os posts corretos
    posts = db.get_forum_posts(lesson_id=lesson_id)
    
    if not posts:
        st.info("Nenhuma discussão neste fórum ainda.")
    
    for post in posts:
        col_msg, col_action = st.columns([0.9, 0.1])
        with col_msg:
            # Formata a hora simples para exibição
            ts = post.get("created_at", "")
            hora = ts.split("T")[1][:5] if "T" in ts else ts
            
            with st.chat_message("user" if post['user_name'] == st.session_state['usuario'] else "assistant"):
                st.write(f"**{post['user_name']}** ({hora}):")
                st.write(post['message'])
        
        if st.session_state.get('role') == 'admin':
            with col_action:
                if st.button("🗑️", key=f"del_{post['id']}", help="Excluir post"):
                    db.delete_forum_post(post['id'])
                    st.rerun()
