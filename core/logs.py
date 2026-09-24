"""
Configuração de logging do SysAVA.

Grava em `data/logs/sysava.log` (rotativo) e no console. Também centraliza o
registro de exceções não tratadas, usado pelos handlers globais do NiceGUI.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from core import db

LOG_DIR = db.PROJETO_DIR / "data" / "logs"
LOG_PATH = LOG_DIR / "sysava.log"

_configurado = False


def configurar() -> None:
    """Liga o logging em arquivo + console (idempotente)."""
    global _configurado
    if _configurado:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)

    if not any(isinstance(h, RotatingFileHandler) for h in raiz.handlers):
        arquivo = RotatingFileHandler(
            LOG_PATH, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        arquivo.setFormatter(formato)
        raiz.addHandler(arquivo)

    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in raiz.handlers
    ):
        console = logging.StreamHandler()
        console.setFormatter(formato)
        raiz.addHandler(console)

    logging.getLogger("nicegui").setLevel(logging.WARNING)
    # Evita o loop "N change detected" -> grava no sysava.log -> nova detecção.
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    _configurado = True


def registrar_excecao(erro: Exception | None = None, contexto: str = "") -> None:
    """Registra uma exceção não tratada no log."""
    logger = logging.getLogger("sysava")
    mensagem = "Erro não tratado" + (f" ({contexto})" if contexto else "")
    if erro is None:
        logger.error(mensagem)
    else:
        logger.exception(mensagem, exc_info=erro)
