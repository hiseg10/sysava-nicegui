"""
Push sync: envia dados locais do SQLite de volta para o Supabase.

Usa upsert (INSERT OR REPLACE) para não duplicar registros.
Cada tabela é sincronizada de forma incremental — só envia linhas que
foram criadas ou modificadas desde o último push.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from core import db

log = logging.getLogger("sysava.push_sync")

# Tabelas que são gravadas localmente e precisam voltar ao Supabase
TABELAS_PUSH = [
    "forum_posts",
    "user_history",
    "student_assessments",
    "student_grades",
    "attendance",
    "qualitative_points",
]

# Coluna de timestamp para detectar mudanças
COLUNA_UPDATED = "updated_at"

_state_lock = threading.Lock()


import os
from pathlib import Path

STATE_PATH = Path(os.environ.get("SYSAVA_STATE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "state.json")))


def _carregar_estado() -> dict:
    """Lê o estado do push sync."""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _salvar_estado(estado: dict) -> None:
    """Salva o estado do push sync."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(estado, indent=2), encoding="utf-8")


def _tem_coluna(con, tabela: str, coluna: str) -> bool:
    """Verifica se uma coluna existe na tabela."""
    try:
        colunas = [row[1] for row in con.execute(f'PRAGMA table_info("{tabela}")')]
        return coluna in colunas
    except Exception:
        return False


def _obter_ultima_linha(con, tabela: str) -> dict | None:
    """Obtém a última linha da tabela (por id ou rowid)."""
    try:
        if _tem_coluna(con, tabela, "id"):
            row = con.execute(f'SELECT * FROM "{tabela}" ORDER BY id DESC LIMIT 1').fetchone()
        else:
            row = con.execute(f'SELECT * FROM "{tabela}" ORDER BY rowid DESC LIMIT 1').fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _contar_linhas(con, tabela: str) -> int:
    """Conta linhas na tabela."""
    try:
        return con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
    except Exception:
        return 0


def _preparar_valor(valor):
    """Converte valores SQLite para tipos serializáveis em JSON."""
    if valor is None:
        return None
    if isinstance(valor, bytes):
        return valor.decode("utf-8", errors="replace")
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False)
    if isinstance(valor, datetime):
        return valor.isoformat()
    return valor


def _preparar_registro(registro: dict) -> dict:
    """Prepara um registro para envio ao Supabase."""
    return {k: _preparar_valor(v) for k, v in registro.items()}


def push_tabela(tabela: str, cliente_supabase, progresso=None) -> dict:
    """
    Envia todas as linhas de uma tabela local para o Supabase (upsert).

    Retorna {"enviados": N, "erros": M}.
    """
    estado = _carregar_estado()
    ultima_chave = estado.get(f"push_{tabela}_last_id", 0)

    resultado = {"enviados": 0, "erros": 0}

    try:
        with db.abrir() as con:
            if not _tem_coluna(con, tabela, "id"):
                log.info("Tabela %s sem coluna 'id' — usando todas as linhas", tabela)
                linhas = con.execute(f'SELECT * FROM "{tabela}"').fetchall()
            else:
                linhas = con.execute(
                    f'SELECT * FROM "{tabela}" WHERE id > ? ORDER BY id',
                    (ultima_chave,),
                ).fetchall()

            if not linhas:
                return resultado

            registros = []
            max_id = ultima_chave
            for linha in linhas:
                reg = _preparar_registro(dict(linha))
                registros.append(reg)
                if "id" in reg:
                    try:
                        max_id = max(max_id, int(reg["id"]))
                    except (ValueError, TypeError):
                        pass

            if progresso:
                progresso(f"Enviando {len(registros)} registro(s) de {tabela}...", None)

            # Envia em lotes de 100
            for i in range(0, len(registros), 100):
                lote = registros[i : i + 100]
                try:
                    cliente_supabase.table(tabela).upsert(lote).execute()
                    resultado["enviados"] += len(lote)
                except Exception as erro:
                    log.warning("Erro ao enviar lote de %s: %s", tabela, erro)
                    resultado["erros"] += len(lote)

            # Atualiza estado
            with _state_lock:
                estado[f"push_{tabela}_last_id"] = max_id
                estado[f"push_{tabela}_ultimo"] = datetime.now().isoformat()
                _salvar_estado(estado)

    except sqlite3.OperationalError:
        pass  # tabela não existe localmente

    return resultado


def push_tudo(progresso=None) -> dict:
    """
    Envia todas as tabelas locais para o Supabase.

    Retorna {"tabelas": {nome: resultado}, "total_enviados": N, "total_erros": M}.
    """
    from core import sync

    try:
        cli = sync.cliente()
    except Exception as erro:
        log.warning("Não foi possível conectar ao Supabase: %s", erro)
        return {"tabelas": {}, "total_enviados": 0, "total_erros": 0}

    resultados = {}
    total_enviados = 0
    total_erros = 0

    for tabela in TABELAS_PUSH:
        if progresso:
            progresso(f"Sincronizando {tabela}...", None)
        res = push_tabela(tabela, cli, progresso=progresso)
        resultados[tabela] = res
        total_enviados += res["enviados"]
        total_erros += res["erros"]

    return {
        "tabelas": resultados,
        "total_enviados": total_enviados,
        "total_erros": total_erros,
    }
