"""
Autenticação e autorização do SysAVA (SQLite local).

As senhas em `app_users` são hashes bcrypt (`password_hash`). Durante a
transição com o SysAVA Streamlit também é aceito o texto puro da coluna
`password` (elevado a hash no primeiro login bem-sucedido). O login aceita
`username` ou `ra`. Os papéis vêm de `app_users.role`: `admin`, `teacher`
ou `student`.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime
from pathlib import Path

from core import db

PAPEL_ADMIN = "admin"
PAPEL_PROFESSOR = "teacher"
PAPEL_ALUNO = "student"

PAPEIS = (PAPEL_ADMIN, PAPEL_PROFESSOR, PAPEL_ALUNO)
ROTULO_PAPEL = {
    PAPEL_ADMIN: "Administrador",
    PAPEL_PROFESSOR: "Professor",
    PAPEL_ALUNO: "Aluno",
}

# Rotas exclusivas de admin/professor (os alunos são redirecionados para /aluno).
ROTAS_RESTRITAS = (
    "/dashboard",
    "/manage-turmas",
    "/frequencia",
    "/radar",
    "/sync",
    "/config",
    "/database",
)

# Rota inicial de cada papel.
ROTA_INICIAL = {
    PAPEL_ALUNO: "/aluno",
    PAPEL_PROFESSOR: "/dashboard",
    PAPEL_ADMIN: "/dashboard",
}

_STATUS_INATIVO = {"inactive", "inativo", "bloqueado", "suspenso", "desativado"}

SECRET_PATH = Path(os.environ.get("SYSAVA_STORAGE_SECRET_PATH", ""))

log = logging.getLogger("sysava.auth")


# --------------------------------------------------------------------------
# Segredo de sessão
# --------------------------------------------------------------------------
def storage_secret() -> str:
    """
    Segredo do `ui.run(storage_secret=...)`.
    Usa `SYSAVA_STORAGE_SECRET` se definido; senão gera um novo.
    """
    ambiente = os.environ.get("SYSAVA_STORAGE_SECRET")
    if ambiente:
        return ambiente
    ambiente = os.environ.get("SYSAVA_STORAGE_SECRET_PATH")
    if ambiente and Path(ambiente).exists():
        try:
            return Path(ambiente).read_text(encoding="utf-8").strip()
        except OSError:
            pass
    valor = secrets.token_urlsafe(48)
    return valor


# --------------------------------------------------------------------------
# Usuários
# --------------------------------------------------------------------------
def _buscar(login: str) -> dict | None:
    """Busca a linha crua do usuário pelo `username` ou `ra`."""
    login = (login or "").strip()
    if not login:
        return None
    sql = "SELECT * FROM app_users WHERE username = ? OR ra = ? LIMIT 1"
    try:
        with db.abrir() as con:
            linha = con.execute(sql, (login, login)).fetchone()
    except Exception:
        # Banco antigo ainda com `users`: renomeia e tenta de novo.
        db.garantir_app_users()
        try:
            with db.abrir() as con:
                linha = con.execute(sql, (login, login)).fetchone()
        except Exception as erro2:
            log.warning("Falha ao consultar app_users: %s", erro2)
            return None
    return dict(linha) if linha else None


def obter_usuario(login: str) -> dict | None:
    """Busca o usuário pelo `username` ou pelo `ra` (sem expor a senha)."""
    usuario = _buscar(login)
    if not usuario:
        return None
    usuario.pop("password_hash", None)
    usuario.pop("password", None)
    return usuario


def verificar_senha(senha: str, hash_armazenado: str | None) -> bool:
    """Compara a senha com o hash bcrypt armazenado."""
    if not senha or not hash_armazenado:
        return False
    try:
        import bcrypt

        return bcrypt.checkpw(senha.encode("utf-8"), str(hash_armazenado).encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _senha_legacy_igual(senha: str, password_legado: str | None) -> bool:
    """Compara com a senha em texto puro do Streamlit (coluna `password`)."""
    if not senha or not password_legado:
        return False
    return secrets.compare_digest(str(senha), str(password_legado))


def _promover_hash(dados: dict, senha: str | None = None, hash_novo: str | None = None) -> None:
    """Grava `password_hash` (best-effort).

    - `hash_novo` informado (origem já era bcrypt): espelha o hash sem tocar em `password`.
    - `senha` informada (origem texto puro): grava bcrypt em `password_hash` **e** em
      `password` — nunca apaga a senha, para o Streamlit legado continuar funcionando.
    """
    username = dados.get("username")
    if not username:
        return
    try:
        if hash_novo is None:
            if not senha:
                return
            import bcrypt

            hash_novo = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            reescrever_password = True
        else:
            # Origem já era bcrypt: só espelha; mantém `password` como está.
            reescrever_password = not _eh_hash_bcrypt(str(dados.get("password") or ""))
        with db.abrir(somente_leitura=False) as con:
            if reescrever_password:
                con.execute(
                    "UPDATE app_users SET password_hash = ?, password = ? WHERE username = ?",
                    (hash_novo, hash_novo, username),
                )
            else:
                con.execute(
                    "UPDATE app_users SET password_hash = ? WHERE username = ?",
                    (hash_novo, username),
                )
            con.commit()
        dados["password_hash"] = hash_novo
        if reescrever_password:
            dados["password"] = hash_novo
        log.info("Senha de %s gravada em password_hash.", username)
    except Exception as erro:
        log.warning("Não foi possível promover senha de %s: %s", username, erro)


def esta_ativo(usuario: dict) -> bool:
    """Considera inativo apenas quando `status`/`is_active` dizem isso."""
    status = str(usuario.get("status") or "").strip().lower()
    if status in _STATUS_INATIVO:
        return False
    if "is_active" in usuario and usuario["is_active"] is not None:
        valor = str(usuario["is_active"]).strip().lower()
        if valor in {"0", "false", "f", "no", "não", "nao"}:
            return False
    return True


def _eh_hash_bcrypt(texto: str) -> bool:
    """Verifica se um texto parece um hash bcrypt (começa com $2a, $2b, $2y ou $2p)."""
    return bool(texto and isinstance(texto, str) and texto.startswith(("$2a", "$2b", "$2y", "$2p")))

def autenticar(login: str, senha: str) -> dict | None:
    """Devolve o usuário autenticado (sem senha) ou None.

    Compatibilidade com os layouts de `app_users`:
    - `password_hash` com bcrypt (Supabase principal / NiceGUI canônico);
    - `password` com bcrypt (Supabase 2 do Streamlit / SQLite local legado);
    - `password` em texto puro (seeds antigos) — promove para bcrypt nos dois
      campos no primeiro login.
    """
    dados = _buscar(login)
    if not dados:
        return None

    senha_hash = None
    ph = dados.get("password_hash")
    if _eh_hash_bcrypt(ph):
        senha_hash = ph
    elif _eh_hash_bcrypt(dados.get("password")):
        senha_hash = dados.get("password")

    if senha_hash is not None:
        if not verificar_senha(senha, senha_hash):
            return None
        # Cura de dados: espelha o hash em password_hash sem apagar password.
        if not dados.get("password_hash"):
            _promover_hash(dados, hash_novo=senha_hash)
    else:
        # Transição: senha legada em texto puro (Streamlit/seeds).
        if not _senha_legacy_igual(senha, dados.get("password")):
            return None
        _promover_hash(dados, senha=senha)

    if not esta_ativo(dados):
        return None
    dados.pop("password_hash", None)
    dados.pop("password", None)
    return dados


def rota_inicial(papel: str | None) -> str:
    """Rota inicial do papel (padrão: dashboard)."""
    return ROTA_INICIAL.get(papel or "", "/dashboard")


def pode_acessar(papel: str | None, rota: str) -> bool:
    """Indica se o papel pode acessar a rota (admin/professor: tudo)."""
    if papel in (PAPEL_ADMIN, PAPEL_PROFESSOR):
        return True
    return rota not in ROTAS_RESTRITAS


def nome_exibicao(usuario: dict) -> str:
    """Nome curto para exibição (primeiro nome, capitalizado)."""
    nome = (usuario or {}).get("name") or (usuario or {}).get("username") or ""
    primeiro = str(nome).strip().split(" ")[0]
    return primeiro.title() if primeiro else ""


# --------------------------------------------------------------------------
# Log de atividades
# --------------------------------------------------------------------------
def registrar_atividade(username: str | None, atividade: str) -> None:
    """Grava uma linha em `user_history` (best-effort; nunca quebra a página)."""
    if not username:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                "INSERT INTO user_history (username, activity, timestamp) VALUES (?, ?, ?)",
                (username, atividade, ts),
            )
            con.commit()
    except Exception as erro:
        log.warning("Não foi possível registrar atividade: %s", erro)
    _push_user_history(username, atividade, ts)


def _push_user_history(username: str, activity: str, timestamp: str) -> None:
    """Envia o registro para o Supabase em background."""
    import threading

    def _enviar():
        try:
            from core import sync
            sync.upsert_filtrado("user_history", [{
                "username": username,
                "activity": activity,
                "timestamp": timestamp,
            }])
        except Exception:
            pass

    threading.Thread(target=_enviar, daemon=True).start()
