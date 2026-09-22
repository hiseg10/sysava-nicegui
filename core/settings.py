"""Configurações do SysAVA (`settings` editáveis)."""

from __future__ import annotations

from datetime import datetime

from core import db


def listar_settings() -> list[dict]:
    """Todas as configurações, ordenadas pela chave."""
    try:
        with db.abrir() as con:
            return [dict(l) for l in con.execute(
                "SELECT * FROM settings ORDER BY chave"
            ).fetchall()]
    except Exception:
        return []


def obter_setting(chave: str, padrao=None):
    """Retorna o valor de uma configuração."""
    try:
        with db.abrir() as con:
            linha = con.execute(
                "SELECT valor FROM settings WHERE chave = ?", (chave,)
            ).fetchone()
        return linha["valor"] if linha else padrao
    except Exception:
        return padrao


def salvar_setting(chave: str, valor: str) -> bool:
    """Atualiza o valor de uma configuração."""
    if not chave:
        return False
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                "UPDATE settings SET valor = ?, atualizado_em = ? WHERE chave = ?",
                (valor, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), chave),
            )
            con.commit()
        return True
    except Exception:
        return False
