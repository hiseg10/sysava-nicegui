"""
Configurações do SysAVA: `settings` (editável) e `master_config` (leitura).
"""

from __future__ import annotations

from datetime import datetime

from core import db, parsing, repositories as repo


def listar_settings() -> list[dict]:
    """Todas as configurações, ordenadas pela chave."""
    return repo.listar_settings()


def obter_setting(chave: str, padrao=None):
    return repo.obter_setting(chave, padrao)


def salvar_setting(chave: str, valor: str) -> bool:
    """Atualiza o valor de uma configuração (grava no SQLite local)."""
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


def listar_master_config() -> list[dict]:
    """Chaves do `master_config` com o valor já interpretado."""
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT key, value, updated_at FROM master_config ORDER BY key"
            ).fetchall()
    except Exception:
        return []
    itens = []
    for linha in linhas:
        item = dict(linha)
        bruto = item.get("value")
        item["resumo"] = _resumo(bruto)
        item["tamanho"] = len(str(bruto or ""))
        itens.append(item)
    return itens


def obter_master_config(chave: str):
    try:
        with db.abrir() as con:
            linha = con.execute(
                "SELECT value FROM master_config WHERE key = ?", (chave,)
            ).fetchone()
    except Exception:
        return None
    return linha["value"] if linha else None


def _resumo(valor) -> str:
    """Resumo curto do valor (dict/list → chaves ou tamanho)."""
    dado = parsing.para_dict(valor)
    if dado:
        return ", ".join(list(dado.keys())[:8])
    lista = parsing.para_lista(valor)
    if lista:
        return f"{len(lista)} item(ns)"
    texto = str(valor or "").strip().replace("\n", " ")
    return texto[:120] + ("..." if len(texto) > 120 else "")
