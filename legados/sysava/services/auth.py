# services/auth.py
import bcrypt
import streamlit as st
import uuid

def hash_password(password: str) -> str:
    """Criptografa uma senha para armazenamento."""
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

def check_password(password: str, hashed_password: str) -> bool:
    """Verifica se a senha fornecida corresponde ao hash armazenado."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

# --- Gerenciamento de Sessão ---
@st.cache_resource
def get_active_sessions():
    """Retorna um dicionário compartilhado para gerenciar sessões ativas."""
    return {}

def create_session(username, role, name):
    session_id = str(uuid.uuid4())
    sessions = get_active_sessions()
    sessions[session_id] = {
        "username": username,
        "role": role,
        "name": name
    }
    return session_id

def get_session(session_id):
    sessions = get_active_sessions()
    return sessions.get(session_id)

def logout_session(session_id):
    sessions = get_active_sessions()
    if session_id in sessions:
        del sessions[session_id]