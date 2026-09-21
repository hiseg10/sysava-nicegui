"""
Conteúdo das aulas: agrupamento, questões do quiz, status do aluno e export.

Porte (sem Streamlit) da lógica de `views/aulas.py`.
"""

from __future__ import annotations

import re
import sqlite3

from core import db, parsing, repositories as repo

STATUS_CONCLUIDA = "concluida"
STATUS_VISITADA = "visitada"
STATUS_NAO = "nao"

_ANUAL = ("MENTORIA TECH II", "PCII", "PROJETO DE VIDA")
_GRUPO_DS = ("DS", "DESENVOLVIMENTO DE SISTEMAS")
_GRUPO_IA = ("INTELIGÊNCIA ARTIFICIAL", "INTELIGENCIA ARTIFICIAL", "ROBÓTICA", "ROBOTICA")


# --------------------------------------------------------------------------
# Quiz
# --------------------------------------------------------------------------
def questoes_do_quiz(quiz_id) -> list[dict]:
    """Questões de um quiz, com `options` como lista e índice correto como int."""
    if quiz_id is None:
        return []
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT * FROM quiz_questions WHERE quiz_id = ? ORDER BY id", (str(quiz_id),)
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    questoes = []
    for linha in linhas:
        item = dict(linha)
        item["options"] = parsing.para_lista(item.get("options"))
        item["correct_option_index"] = parsing.para_int(item.get("correct_option_index"), 0)
        questoes.append(item)
    return questoes


def numero_aula(titulo: str) -> int | None:
    """Extrai o número da aula do título ('Aula 7 ...' → 7)."""
    encontrado = re.search(r"Aula\s*(\d+)", str(titulo or ""), re.IGNORECASE)
    return int(encontrado.group(1)) if encontrado else None


def agrupar_aulas(aulas: list[dict], subject_name: str, class_name: str) -> dict[str, list[dict]]:
    """Agrupa as aulas por semana/unidade conforme a disciplina e a turma."""
    nome_disciplina = (subject_name or "").upper()
    nome_turma = (class_name or "").upper()

    if any(chave in nome_disciplina for chave in _ANUAL):
        return {"Anual": aulas}

    if any(chave in nome_turma for chave in _GRUPO_DS):
        tamanho, prefixo = 10, "Semana"
    elif any(chave in nome_disciplina for chave in _GRUPO_IA):
        tamanho, prefixo = 8, "Unidade"
    else:
        return {"Aulas": aulas}

    numeradas = sorted(
        (aula for aula in aulas if numero_aula(aula.get("title")) is not None),
        key=lambda aula: numero_aula(aula.get("title")),
    )
    grupos: dict[str, list[dict]] = {}
    for aula in numeradas:
        numero = numero_aula(aula.get("title"))
        indice = (numero - 1) // tamanho + 1
        inicio = (indice - 1) * tamanho + 1
        fim = inicio + tamanho - 1
        chave = f"{prefixo} {indice:02d} (Aulas {inicio:02d}-{fim:02d})"
        grupos.setdefault(chave, []).append(aula)
    return grupos


# --------------------------------------------------------------------------
# Status do aluno
# --------------------------------------------------------------------------
def _historico(username) -> list[dict]:
    if not username:
        return []
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT activity FROM user_history WHERE username = ?", (str(username),)
            ).fetchall()
    except Exception:
        return []
    return [str(linha["activity"] or "") for linha in linhas]


def _titulos_do_historico(username) -> tuple[set[str], set[str]]:
    visitadas: set[str] = set()
    quizzes: set[str] = set()
    for atividade in _historico(username):
        limpo = atividade.split("|")[0].strip()
        if limpo.startswith("Acessou a aula:"):
            visitadas.add(limpo.split(":", 1)[1].strip())
        elif limpo.startswith("Concluiu Quiz:"):
            bruto = limpo.split(":", 1)[1].strip()
            quizzes.add(re.sub(r"\s*\(\d+/\d+\)$", "", bruto).strip())
    return visitadas, quizzes


def status_aulas(username, subject_id) -> dict[str, str]:
    """Mapa {lesson_id: concluida|visitada|nao} para as aulas da disciplina."""
    aulas = repo.listar_aulas(subject_id)
    quizzes = repo.mapa_quizzes_por_aula()
    visitadas, quizzes_feitos = _titulos_do_historico(username)

    resultado: dict[str, str] = {}
    for aula in aulas:
        lesson_id = str(aula.get("id"))
        titulo = str(aula.get("title") or "")
        visitada = titulo in visitadas
        quiz = quizzes.get(lesson_id)
        if not visitada:
            resultado[lesson_id] = STATUS_NAO
        elif not quiz or str(quiz.get("title")) in quizzes_feitos:
            resultado[lesson_id] = STATUS_CONCLUIDA
        else:
            resultado[lesson_id] = STATUS_VISITADA
    return resultado


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------
def markdown_aula(aula: dict, quiz: dict | None, questoes: list[dict]) -> str:
    """Gera o conteúdo da aula (e do quiz) em Markdown."""
    partes = [f"# {aula.get('title') or 'Aula'}", ""]
    if aula.get("video_url"):
        partes += [f"**Vídeo:** {aula['video_url']}", ""]
    partes += [str(aula.get("description") or aula.get("full_content") or ""), ""]

    if quiz and questoes:
        partes += ["---", "", f"## Quiz: {quiz.get('title')}", ""]
        for indice, questao in enumerate(questoes, start=1):
            partes.append(f"**{indice}. {questao.get('question_text')}**")
            for opcao in questao.get("options", []):
                partes.append(f"- [ ] {opcao}")
            partes.append("")
        partes += ["---", "", "### Gabarito", ""]
        for indice, questao in enumerate(questoes, start=1):
            opcoes = questao.get("options", [])
            correta = questao.get("correct_option_index") or 0
            letra = chr(65 + correta) if 0 <= correta < 26 else "?"
            texto = opcoes[correta] if 0 <= correta < len(opcoes) else "?"
            partes.append(f"- **{indice}.** {letra} - {texto}")
    return "\n".join(partes)
