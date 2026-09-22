"""
Perfil do usuário: configurações pessoais (local apenas, sem sync).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from core import db

# --------------------------------------------------------------------------
# Inicialização (cria tabelas se não existirem)
# --------------------------------------------------------------------------
_SQL_PROFILES = """
CREATE TABLE IF NOT EXISTS user_profiles (
    username    TEXT PRIMARY KEY,
    bio         TEXT DEFAULT '',
    avatar_url  TEXT DEFAULT '',
    notificacoes INTEGER DEFAULT 1,
    idioma      TEXT DEFAULT 'pt_BR',
    prefs       TEXT DEFAULT '{}',
    atualizado_em TEXT
)
"""

_SQL_REMINDERS = """
CREATE TABLE IF NOT EXISTS user_reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL,
    titulo      TEXT NOT NULL,
    mensagem    TEXT DEFAULT '',
    prioridade  TEXT DEFAULT 'normal',
    concluido   INTEGER DEFAULT 0,
    criado_em   TEXT,
    prazo       TEXT
)
"""


def _ensure_tables() -> None:
    """Garante que as tabelas existem (cria se necessário)."""
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(_SQL_PROFILES)
            con.execute(_SQL_REMINDERS)
            con.commit()
    except Exception:
        pass


_ensure_tables()


# --------------------------------------------------------------------------
# Perfil
# --------------------------------------------------------------------------
def obter_perfil(username: str) -> dict:
    """Retorna o perfil do usuário (cria um vazio se não existir)."""
    if not username:
        return {}
    try:
        with db.abrir() as con:
            linha = con.execute(
                "SELECT * FROM user_profiles WHERE username = ?", (username,)
            ).fetchone()
    except Exception:
        linha = None

    if linha:
        dados = dict(linha)
        try:
            dados["prefs"] = json.loads(dados.get("prefs") or "{}")
        except (json.JSONDecodeError, TypeError):
            dados["prefs"] = {}
        return dados

    return {
        "username": username,
        "bio": "",
        "avatar_url": "",
        "notificacoes": 1,
        "idioma": "pt_BR",
        "prefs": {},
    }


def salvar_perfil(username: str, *, bio: str = None, avatar_url: str = None,
                  notificacoes: int = None, idioma: str = None,
                  prefs: dict = None) -> bool:
    """Salva (ou atualiza) o perfil do usuário."""
    if not username:
        return False
    _ensure_tables()
    atual = obter_perfil(username)
    dados = {
        "bio": bio if bio is not None else atual.get("bio", ""),
        "avatar_url": avatar_url if avatar_url is not None else atual.get("avatar_url", ""),
        "notificacoes": notificacoes if notificacoes is not None else atual.get("notificacoes", 1),
        "idioma": idioma if idioma is not None else atual.get("idioma", "pt_BR"),
        "prefs": json.dumps(prefs if prefs is not None else atual.get("prefs", {}), ensure_ascii=False),
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                """INSERT INTO user_profiles (username, bio, avatar_url, notificacoes, idioma, prefs, atualizado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(username) DO UPDATE SET
                       bio=excluded.bio, avatar_url=excluded.avatar_url,
                       notificacoes=excluded.notificacoes, idioma=excluded.idioma,
                       prefs=excluded.prefs, atualizado_em=excluded.atualizado_em""",
                (username, dados["bio"], dados["avatar_url"], dados["notificacoes"],
                 dados["idioma"], dados["prefs"], dados["atualizado_em"]),
            )
            con.commit()
        _push_perfil(username, dados)
        return True
    except Exception:
        return False


def _push_perfil(username: str, dados: dict) -> None:
    """Envia o perfil atualizado para o Supabase em background."""
    import threading

    def _enviar():
        try:
            from core import sync
            cli = sync.cliente()
            cli.table("user_profiles").upsert({
                "username": username,
                **dados,
            }).execute()
        except Exception:
            pass

    threading.Thread(target=_enviar, daemon=True).start()


# --------------------------------------------------------------------------
# Lembretes
# --------------------------------------------------------------------------
def listar_lembretes(username: str, incluir_concluidos: bool = False) -> list[dict]:
    """Lista os lembretes do usuário (mais recentes primeiro)."""
    if not username:
        return []
    _ensure_tables()
    try:
        with db.abrir() as con:
            sql = "SELECT * FROM user_reminders WHERE username = ?"
            params: list = [username]
            if not incluir_concluidos:
                sql += " AND concluido = 0"
            sql += " ORDER BY criado_em DESC"
            linhas = con.execute(sql, params).fetchall()
    except Exception:
        return []
    return [dict(linha) for linha in linhas]


def criar_lembrete(username: str, titulo: str, mensagem: str = "",
                   prioridade: str = "normal", prazo: str = None) -> bool:
    """Cria um novo lembrete."""
    if not username or not titulo:
        return False
    _ensure_tables()
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                """INSERT INTO user_reminders (username, titulo, mensagem, prioridade, criado_em, prazo)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, titulo, mensagem, prioridade,
                 datetime.now().isoformat(timespec="seconds"), prazo),
            )
            con.commit()
        return True
    except Exception:
        return False


def atualizar_lembrete(lembrete_id: int, *, titulo: str = None, mensagem: str = None,
                       prioridade: str = None, concluido: bool = None, prazo: str = None) -> bool:
    """Atualiza um lembrete existente."""
    _ensure_tables()
    campos: list[str] = []
    valores: list = []
    if titulo is not None:
        campos.append("titulo = ?")
        valores.append(titulo)
    if mensagem is not None:
        campos.append("mensagem = ?")
        valores.append(mensagem)
    if prioridade is not None:
        campos.append("prioridade = ?")
        valores.append(prioridade)
    if concluido is not None:
        campos.append("concluido = ?")
        valores.append(1 if concluido else 0)
    if prazo is not None:
        campos.append("prazo = ?")
        valores.append(prazo)
    if not campos:
        return False
    valores.append(lembrete_id)
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                f"UPDATE user_reminders SET {', '.join(campos)} WHERE id = ?",
                valores,
            )
            con.commit()
        return True
    except Exception:
        return False


def remover_lembrete(lembrete_id: int) -> bool:
    """Remove um lembrete."""
    _ensure_tables()
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute("DELETE FROM user_reminders WHERE id = ?", (lembrete_id,))
            con.commit()
        return True
    except Exception:
        return False
