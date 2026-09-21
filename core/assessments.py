"""
Provas/avaliações: questões, submissões, notas e export da prova em branco.
"""

from __future__ import annotations

from core import db, parsing

TIPO_OBJETIVA = "objective"
TIPO_SUBJETIVA = "subjective"


def _dedupe_por_id(linhas: list[dict]) -> list[dict]:
    """Remove linhas repetidas pelo `id` (o backup legado duplicou registros)."""
    vistos: set[str] = set()
    resultado = []
    for linha in linhas:
        chave = str(linha.get("id"))
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(linha)
    return resultado


def listar_avaliacoes(subject_id) -> list[dict]:
    if subject_id is None:
        return []
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT * FROM assessments WHERE subject_id = ? ORDER BY type, title",
                (str(subject_id),),
            ).fetchall()
    except Exception:
        return []
    return _dedupe_por_id([dict(linha) for linha in linhas])


def questoes_avaliacao(assessment_id) -> list[dict]:
    if assessment_id is None:
        return []
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT * FROM assessment_questions WHERE assessment_id = ? ORDER BY id",
                (str(assessment_id),),
            ).fetchall()
    except Exception:
        return []
    questoes = []
    for linha in linhas:
        item = dict(linha)
        item["options"] = parsing.para_lista(item.get("options"))
        item["correct_option_index"] = parsing.para_int(item.get("correct_option_index"), 0)
        questoes.append(item)
    return questoes


def submissoes_avaliacao(assessment_id) -> list[dict]:
    """Submissões da avaliação com nome e RA do aluno."""
    if assessment_id is None:
        return []
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT s.*, u.name AS student_name, u.ra AS student_ra "
                "FROM student_assessments s "
                "LEFT JOIN app_users u ON u.username = s.user_username "
                "WHERE s.assessment_id = ? "
                "ORDER BY u.name",
                (str(assessment_id),),
            ).fetchall()
    except Exception:
        return []
    return [dict(linha) for linha in linhas]


def respostas_submissao(submission_id) -> list[dict]:
    if submission_id is None:
        return []
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT * FROM student_assessment_answers WHERE submission_id = ? ORDER BY id",
                (str(submission_id),),
            ).fetchall()
    except Exception:
        return []
    return [dict(linha) for linha in linhas]


def submissoes_aluno(username, assessment_id) -> list[dict]:
    if not username or assessment_id is None:
        return []
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT * FROM student_assessments WHERE user_username = ? AND assessment_id = ? "
                "ORDER BY submitted_at DESC",
                (str(username), str(assessment_id)),
            ).fetchall()
    except Exception:
        return []
    return [dict(linha) for linha in linhas]


def atualizar_nota(submission_id, nota) -> bool:
    """Atualiza a nota final de uma submissão (grava no SQLite local)."""
    try:
        valor = parsing.para_float(nota)
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                "UPDATE student_assessments SET score = ? WHERE id = ?",
                (valor, str(submission_id)),
            )
            con.commit()
        _push_nota(submission_id, valor)
        return True
    except Exception:
        return False


def _push_nota(submission_id, score) -> None:
    """Envia a nota atualizada para o Supabase em background."""
    import threading

    def _enviar():
        try:
            from core import sync
            cli = sync.cliente()
            cli.table("student_assessments").upsert({
                "id": str(submission_id),
                "score": score,
            }).execute()
        except Exception:
            pass

    threading.Thread(target=_enviar, daemon=True).start()


def _letra(indice: int | None) -> str:
    return chr(65 + indice) if isinstance(indice, int) and 0 <= indice < 26 else "?"


def markdown_prova(
    avaliacao: dict,
    questoes: list[dict],
    subject_name: str = "",
    class_name: str = "",
    school_name: str = "",
    em_branco: bool = True,
) -> str:
    """Gera a prova em Markdown (em branco ou com gabarito)."""
    linhas = [
        f"# {school_name or 'Avaliação'}",
        "",
        f"**Disciplina:** {subject_name} | **Turma:** {class_name}",
        f"**Avaliação:** {avaliacao.get('type') or ''} - {avaliacao.get('title') or ''}",
        "",
        "---",
        "",
    ]
    for indice, questao in enumerate(questoes, start=1):
        linhas.append(f"**{indice}. {questao.get('question_text')}**")
        opcoes = questao.get("options", [])
        if questao.get("question_type") == TIPO_OBJETIVA:
            for posicao, opcao in enumerate(opcoes):
                linhas.append(f"- ({_letra(posicao)}) {opcao}")
        else:
            if any(str(opcao) == "LINK_REQUIRED" for opcao in opcoes):
                linhas.append("- Link para envio: ______________________")
            else:
                linhas.append("- Resposta: ______________________")
        linhas.append("")

    if not em_branco:
        linhas += ["---", "", "## Gabarito", ""]
        for indice, questao in enumerate(questoes, start=1):
            if questao.get("question_type") == TIPO_OBJETIVA:
                correta = questao.get("correct_option_index") or 0
                linhas.append(f"- **{indice}.** {_letra(correta)}")
            else:
                linhas.append(f"- **{indice}.** (subjetiva)")
    return "\n".join(linhas)
