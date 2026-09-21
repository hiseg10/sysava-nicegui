"""
Conversão de valores guardados como TEXT no SQLite.

Colunas como `options` (listas) e `correct_option_index` vieram do Supabase
como JSON, mas no banco local podem estar como texto no formato Python
(`['a', 'b']`). Estas funções aceitam os dois formatos.
"""

from __future__ import annotations

import ast
import json


def para_lista(valor) -> list:
    """Converte um valor em lista (JSON, repr de Python ou item único)."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    if isinstance(valor, (tuple, set)):
        return list(valor)
    texto = str(valor).strip()
    if not texto:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            dado = parser(texto)
        except (ValueError, SyntaxError, TypeError):
            continue
        if isinstance(dado, (list, tuple, set)):
            return list(dado)
        return [dado]
    return [texto]


def para_dict(valor) -> dict:
    """Converte um valor em dicionário (JSON ou repr de Python)."""
    if valor is None:
        return {}
    if isinstance(valor, dict):
        return valor
    texto = str(valor).strip()
    if not texto:
        return {}
    for parser in (json.loads, ast.literal_eval):
        try:
            dado = parser(texto)
        except (ValueError, SyntaxError, TypeError):
            continue
        if isinstance(dado, dict):
            return dado
    return {}


def para_int(valor, padrao: int | None = None) -> int | None:
    """Converte um valor em inteiro, aceitando float e strings numéricas."""
    if valor is None or valor == "":
        return padrao
    if isinstance(valor, bool):
        return int(valor)
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        return padrao


def para_float(valor, padrao: float | None = None) -> float | None:
    """Converte um valor em float, aceitando strings numéricas."""
    if valor is None or valor == "":
        return padrao
    try:
        return float(valor)
    except (ValueError, TypeError):
        return padrao
