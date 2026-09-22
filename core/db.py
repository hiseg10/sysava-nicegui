"""
Gerenciamento da conexão com o banco SQLite do SysAVA (escola_ativa.db).

O caminho do banco é sobrescrito pela variável de ambiente SYSAVA_DB_PATH
ou usa o padrão data/escola_ativa.db.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

PROJETO_DIR = Path(__file__).resolve().parent.parent
DB_PADRAO = PROJETO_DIR / "data" / "escola_ativa.db"

_caminho_atual: Path | None = None


def _normalizar(caminho) -> Path:
    """Expande variáveis de ambiente (~, %APPDATA%, etc.) e retorna um Path."""
    return Path(os.path.expandvars(str(caminho))).expanduser()


def caminho_atual() -> Path:
    """Caminho do banco em uso: variável de ambiente ou padrão."""
    global _caminho_atual
    if _caminho_atual is None:
        ambiente = os.environ.get("SYSAVA_DB_PATH")
        if ambiente:
            _caminho_atual = _normalizar(ambiente)
        else:
            _caminho_atual = _normalizar(DB_PADRAO)
    return _caminho_atual


def definir_caminho(caminho) -> Path:
    """Define o caminho do banco em uso."""
    global _caminho_atual
    _caminho_atual = _normalizar(caminho)
    return _caminho_atual


def restaurar_padrao() -> Path:
    """Volta o caminho para o banco padrão do SysAVA."""
    return definir_caminho(DB_PADRAO)


# --------------------------------------------------------------------------
# Conexão
# --------------------------------------------------------------------------
@contextmanager
def abrir(caminho=None, somente_leitura=True):
    """
    Abre uma conexão SQLite e garante o fechamento ao final do bloco.

    Por padrão abre em modo somente leitura (seguro para consultas); use
    somente_leitura=False quando precisar gravar.
    """
    destino = _normalizar(caminho) if caminho else caminho_atual()

    # Garante que o diretório existe
    destino.parent.mkdir(parents=True, exist_ok=True)

    if somente_leitura:
        if not destino.exists():
            sqlite3.connect(destino).close()
        con = sqlite3.connect(f"file:{destino.as_posix()}?mode=ro", uri=True)
    else:
        con = sqlite3.connect(destino)

    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def testar(caminho=None) -> dict:
    """Testa a conexão com o banco e devolve um dicionário de status."""
    destino = _normalizar(caminho) if caminho else caminho_atual()

    info = {
        "ok": False, "caminho": str(destino), "existe": destino.exists(),
        "tamanho": 0, "modificado": None, "tabelas": 0,
        "versao_sqlite": sqlite3.sqlite_version, "erro": None,
    }

    if info["existe"]:
        stat = destino.stat()
        info["tamanho"] = stat.st_size
        info["modificado"] = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")

    try:
        with abrir(destino, somente_leitura=True) as con:
            info["tabelas"] = len(listar_tabelas(con))
        info["ok"] = True
    except Exception as erro:
        info["erro"] = str(erro)

    return info


def listar_tabelas(con) -> list[str]:
    """Lista os nomes das tabelas (ignora tabelas internas do SQLite)."""
    return [linha[0] for linha in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()]


def info_tabela(con, nome: str) -> dict:
    """Retorna colunas, quantidade de linhas e o SQL de criação da tabela."""
    colunas = [dict(linha) for linha in con.execute(f'PRAGMA table_info("{nome}")').fetchall()]
    try:
        total = con.execute(f'SELECT COUNT(*) FROM "{nome}"').fetchone()[0]
    except sqlite3.Error:
        total = 0
    criacao = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (nome,)
    ).fetchone()
    return {
        "colunas": colunas, "linhas": total,
        "sql": criacao[0] if criacao else "",
    }


def previsualizar(con, nome: str, limite: int = 20) -> tuple[list[str], list[list]]:
    """Retorna (nomes_das_colunas, linhas) com no máximo 'limite' registros."""
    cur = con.execute(f'SELECT * FROM "{nome}" LIMIT ?', (limite,))
    colunas = [descricao[0] for descricao in cur.description] if cur.description else []
    linhas = [list(linha) for linha in cur.fetchall()]
    return colunas, linhas


def formatar_tamanho(bytes_: int) -> str:
    """Formata bytes em uma string legível (KB/MB/GB)."""
    tamanho = float(bytes_)
    for unidade in ("B", "KB", "MB", "GB"):
        if tamanho < 1024 or unidade == "GB":
            return f"{tamanho:.0f} {unidade}" if unidade == "B" else f"{tamanho:.2f} {unidade}"
        tamanho /= 1024
    return f"{tamanho:.2f} GB"
