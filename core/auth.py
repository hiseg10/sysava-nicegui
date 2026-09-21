"""
Autenticação e autorização do SysAVA (SQLite local).

As senhas em `app_users` são hashes bcrypt. O login aceita o `username` ou o
`ra`. Os papéis vêm de `app_users.role`: `admin`, `teacher` ou `student`.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime

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

SECRET_PATH = db.PROJETO_DIR / "data" / "storage_secret.txt"

log = logging.getLogger("sysava.auth")


# --------------------------------------------------------------------------
# Segredo de sessão
# --------------------------------------------------------------------------
def storage_secret() -> str:
    """
    Segredo do `ui.run(storage_secret=...)`.

    Usa `SYSAVA_STORAGE_SECRET` se definido; senão lê/gera
    `data/storage_secret.txt` (uma única vez, para não invalidar sessões a cada
    reinício).
    """
    ambiente = os.environ.get("SYSAVA_STORAGE_SECRET")
    if ambiente:
        return ambiente
    if SECRET_PATH.exists():
        try:
            valor = SECRET_PATH.read_text(encoding="utf-8").strip()
            if valor:
                return valor
        except OSError:
            pass
    valor = secrets.token_urlsafe(48)
    try:
        SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
        SECRET_PATH.write_text(valor, encoding="utf-8")
    except OSError:
        log.warning("Não foi possível gravar o storage_secret em %s", SECRET_PATH)
    return valor


# --------------------------------------------------------------------------
# Usuários
# --------------------------------------------------------------------------
def _buscar(login: str) -> dict | None:
    """Busca a linha crua do usuário pelo `username` ou `ra`."""
    login = (login or "").strip()
    if not login:
        return None
    try:
        with db.abrir() as con:
            linha = con.execute(
                "SELECT * FROM app_users WHERE username = ? OR ra = ? LIMIT 1",
                (login, login),
            ).fetchone()
    except Exception as erro:
        log.warning("Falha ao consultar app_users: %s", erro)
        return None
    return dict(linha) if linha else None


def obter_usuario(login: str) -> dict | None:
    """Busca o usuário pelo `username` ou pelo `ra` (sem expor a senha)."""
    usuario = _buscar(login)
    if not usuario:
        return None
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


def autenticar(login: str, senha: str) -> dict | None:
    """Devolve o usuário autenticado (sem senha) ou None."""
    dados = _buscar(login)
    if not dados:
        return None
    if not verificar_senha(senha, dados.get("password")):
        return None
    if not esta_ativo(dados):
        return None
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
            cli = sync.cliente()
            cli.table("user_history").upsert({
                "username": username,
                "activity": activity,
                "timestamp": timestamp,
            }).execute()
        except Exception:
            pass

    threading.Thread(target=_enviar, daemon=True).start()
