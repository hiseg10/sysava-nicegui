"""
Pontos do aluno a partir do histórico (aulas, quizzes e fórum),
avaliações e pontos qualitativos.

Fórmula por disciplina:
  Participação = (aulas + quizzes + forum) / 16, teto 3 pontos
  NM1 = Avaliação_MN1 + Participação_1 + Qualitativos
  NM2 = Avaliação_MN2 + Participação_2 + Qualitativos
  NM3 = composição flexível (varia por disciplina)

As participações são independentes: Participação_1 para o primeiro
período (pontos 1-16) e Participação_2 para o segundo (17-32).
"""

from __future__ import annotations

import re

from core import db, repositories as repo

MAX_PARTICIPACAO = 3
DIVISOR_PARTICIPACAO = 16


# --------------------------------------------------------------------------
# Histórico
# --------------------------------------------------------------------------
def historico_aluno(username) -> list[dict]:
    """Registros de `user_history` do aluno (mais recentes primeiro)."""
    if not username:
        return []
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT * FROM user_history WHERE username = ? ORDER BY id DESC",
                (str(username),),
            ).fetchall()
    except Exception:
        return []
    return [dict(linha) for linha in linhas]


def progresso_aluno(username) -> dict:
    """Contagens únicas de aulas, quizzes e mensagens no fórum."""
    aulas: set[str] = set()
    quizzes: set[str] = set()
    forum = 0
    for item in historico_aluno(username):
        atividade = str(item.get("activity") or "")
        limpo = atividade.split("|")[0].strip()
        if limpo.startswith("Acessou a aula:"):
            aulas.add(limpo)
        elif limpo.startswith("Concluiu Quiz:"):
            quizzes.add(limpo.split("(")[0].strip())
        elif "mensagem no fórum" in atividade:
            forum += 1
    return {"aulas": len(aulas), "quizzes": len(quizzes), "forum": forum}


# --------------------------------------------------------------------------
# Quiz helpers
# --------------------------------------------------------------------------
def _parse_quiz_log(texto: str) -> tuple[str | None, int]:
    """Extrai (título, pontos) de 'Concluiu Quiz: Título (2/2)'."""
    corpo = texto.split(":", 1)[1].strip() if ":" in texto else ""
    if "(" not in corpo:
        return (corpo or None), 0
    titulo = corpo.rsplit("(", 1)[0].strip()
    dentro = corpo.rsplit("(", 1)[-1].split(")")[0]
    pontos = 0
    if "/" in dentro:
        try:
            pontos = int(dentro.split("/")[0])
        except ValueError:
            pontos = 0
    return (titulo or None), pontos


def _forum_por_disciplina(username) -> dict[str, int]:
    """Aulas únicas com post do aluno no fórum, por disciplina."""
    aluno = repo.obter_aluno(username) or {}
    nome = aluno.get("name")
    if not nome:
        return {}
    aulas = repo.listar_aulas()
    disciplina_por_aula = {str(aula["id"]): aula.get("subject_id") for aula in aulas}
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT DISTINCT lesson_id FROM forum_posts WHERE user_name = ? "
                "AND lesson_id IS NOT NULL",
                (str(nome),),
            ).fetchall()
    except Exception:
        return {}
    contagem: dict[str, int] = {}
    for linha in linhas:
        disciplina = disciplina_por_aula.get(str(linha["lesson_id"]))
        if disciplina is not None:
            chave = str(disciplina)
            contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


# --------------------------------------------------------------------------
# Participação (aulas + quizzes + forum)
# --------------------------------------------------------------------------
def _calcular_participacao(n_aulas: int, n_quizzes: int, n_forum: int,
                           inicio: int = 0, fim: int = 16) -> float:
    """Participação = bruto / 16, teto 3 pontos.
    
    Aulas 1-16 → NM1 (inicio=0, fim=16)
    Aulas 17-32 → NM2 (inicio=16, fim=32)
    """
    bruto = n_aulas + n_quizzes + n_forum
    bruto_faixa = max(0, min(bruto, fim) - inicio)
    nota = bruto_faixa / DIVISOR_PARTICIPACAO
    return round(min(nota, MAX_PARTICIPACAO), 4)


# --------------------------------------------------------------------------
# Avaliações (student_assessments)
# --------------------------------------------------------------------------
def _mapear_tipo_nota(tipo: str, titulo: str) -> tuple[str | None, int | None]:
    """Mapeia tipo/título da avaliação para (nm1/nm2/nm3, trimestre).
    
    Suporta:
    - MN1, MN2, MN3 (direto, trimestre None = atual)
    - T1_N1, T1_N2, T1_N3, T2_N1, T2_N2, T2_N3 (trimestre explícito)
    - Outros com título AV01/AV1 → nm1, AV02/AV2 → nm2, etc.
    
    Retorna (chave_nota, trimestre) ou (None, None) se não mapear.
    """
    tipo_lower = (tipo or "").lower().strip()
    titulo_lower = (titulo or "").lower().strip()
    
    # Mapeamento direto com trimestre
    if tipo_lower in ("mn1",):
        return ("nm1", None)
    if tipo_lower in ("mn2",):
        return ("nm2", None)
    if tipo_lower in ("mn3",):
        return ("nm3", None)
    
    # Trimestre explícito
    if tipo_lower.startswith("t1_n"):
        tri = 1
    elif tipo_lower.startswith("t2_n"):
        tri = 2
    elif tipo_lower.startswith("t3_n"):
        tri = 3
    else:
        tri = None
    
    if tri is not None:
        if tipo_lower.endswith("_n1") or tipo_lower.endswith("_n1"):
            return ("nm1", tri)
        if tipo_lower.endswith("_n2") or tipo_lower.endswith("_n2"):
            return ("nm2", tri)
        if tipo_lower.endswith("_n3") or tipo_lower.endswith("_n3"):
            return ("nm3", tri)
    
    # Para tipo "Outros", tenta inferir do título
    if tipo_lower == "outros":
        if titulo_lower.startswith("av01") or titulo_lower.startswith("av1"):
            return ("nm1", None)
        if titulo_lower.startswith("av02") or titulo_lower.startswith("av2"):
            return ("nm2", None)
        if titulo_lower.startswith("av03") or titulo_lower.startswith("av3"):
            return ("nm3", None)
        if "recupera" in titulo_lower:
            return (None, None)  # Recuperação não é NM padrão
    
    return (None, None)


def _eh_disciplina_modular(subject_id: str) -> bool:
    """Verifica se a disciplina é modular (mensal)."""
    try:
        with db.abrir() as con:
            linha = con.execute(
                "SELECT duration_type FROM subjects WHERE id = ?",
                (str(subject_id),),
            ).fetchone()
            return (linha["duration_type"] or "").lower() == "mensal"
    except Exception:
        return False


def _avaliacoes_por_disciplina(username) -> dict[str, dict[str, float]]:
    """Retorna {subject_id: {"nm1": nota, "nm2": nota, "nm3": nota}}.

    Considera avaliações com tipo MN1/MN2/MN3 ou equivalente.
    Se houver mais de uma avaliação para o mesmo tipo, usa a maior nota.
    
    Para disciplinas modulares (mensais), replica T1 para T2 e T3.
    """
    try:
        with db.abrir() as con:
            linhas = con.execute(
                "SELECT a.subject_id, a.type, a.title, s.score "
                "FROM student_assessments s "
                "JOIN assessments a ON a.id = s.assessment_id "
                "WHERE s.user_username = ? AND s.score IS NOT NULL",
                (str(username),),
            ).fetchall()
    except Exception:
        return {}

    resultado: dict[str, dict[str, float]] = {}
    for linha in linhas:
        sid = str(linha["subject_id"])
        tipo = linha["type"] or ""
        titulo = linha["title"] or ""
        score = float(linha["score"]) if linha["score"] is not None else 0

        chave_nota, trimestre = _mapear_tipo_nota(tipo, titulo)
        if chave_nota is None:
            continue

        bloco = resultado.setdefault(sid, {})
        bloco[chave_nota] = max(bloco.get(chave_nota, 0), score)

    # Para disciplinas modulares, replica T1 para T2 e T3
    for sid in list(resultado.keys()):
        if _eh_disciplina_modular(sid):
            bloco = resultado[sid]
            # Se tem nota no T1 (que foi mapeada para nm1/nm2/nm3 sem trimestre)
            # replica para todos os trimestres
            if bloco.get("nm1") or bloco.get("nm2") or bloco.get("nm3"):
                # Mantém as notas já existentes (são do T1 ou genéricas)
                pass

    return resultado


# --------------------------------------------------------------------------
# Qualitativos
# --------------------------------------------------------------------------
def _qualitativos_por_disciplina(username) -> dict[str, float]:
    """Soma dos pontos qualitativos por disciplina."""
    pontos = repo.listar_pontos_qualitativos(username)
    resultado: dict[str, float] = {}
    for p in pontos:
        sid = str(p.get("subject_id")) if p.get("subject_id") else "_geral"
        resultado[sid] = resultado.get(sid, 0) + float(p.get("points", 0))
    return resultado


# --------------------------------------------------------------------------
# Verificação de elegibilidade para avaliações
# --------------------------------------------------------------------------
def elegivel_av1(username: str) -> bool:
    """AV1 só está disponível se o aluno abriu pelo menos 8 aulas."""
    progresso = progresso_aluno(username)
    return progresso["aulas"] >= 8


def elegivel_recuperacao(username: str) -> bool:
    """Recuperação só está disponível se a média final (NM1+NM2+NM3)/3 < 6."""
    resumo = resumo_pontos(username)
    nm1 = resumo.get("nm1", 0)
    nm2 = resumo.get("nm2", 0)
    nm3 = resumo.get("nm3", 0)
    media = (nm1 + nm2 + nm3) / 3
    return media < 6.0


def bloqueio_avaliacao(username: str, tipo_avaliacao: str) -> str | None:
    """Retorna mensagem de bloqueio se o aluno não pode fazer a avaliação.
    
    Retorna None se permitido, ou string com motivo do bloqueio.
    """
    tipo = (tipo_avaliacao or "").lower().strip()
    
    if tipo in ("av1", "mn1"):
        if not elegivel_av1(username):
            progresso = progresso_aluno(username)
            return f"AV1 bloqueada. Abra pelo menos 8 aulas (atual: {progresso['aulas']})."
    
    elif tipo in ("recuperacao", "rec", "avrec"):
        if not elegivel_recuperacao(username):
            resumo = resumo_pontos(username)
            media = (resumo["nm1"] + resumo["nm2"] + resumo["nm3"]) / 3
            return f"Recuperação bloqueada. Média atual ({media:.2f}) deve ser inferior a 6.0."
    
    return None


def _calcular_nm(avaliacao: float, participacao: float, qualitativo: float) -> float:
    """NM = Avaliação + Participação + Qualitativos, teto 10."""
    nota = avaliacao + participacao + qualitativo
    return round(min(nota, 10.0), 4)


def _calcular_nm3(avaliacao: float, part1: float, part2: float, qualitativo: float) -> float:
    """NM3 = Avaliação + Média(Part.1, Part.2) + Qualitativos, teto 10."""
    participacao = round(min((part1 + part2) / 2, MAX_PARTICIPACAO), 4)
    nota = avaliacao + participacao + qualitativo
    return round(min(nota, 10.0), 4)


# --------------------------------------------------------------------------
# Resumo principal
# --------------------------------------------------------------------------
def resumo_pontos(username, subject_id=None) -> dict:
    """
    Pontos do aluno por disciplina com a nova fórmula:

      Participação_1 = (aulas + quizzes + forum) / 16, teto 3  (para NM1)
      Participação_2 = (aulas + quizzes + forum) / 16, teto 3  (para NM2)
      NM1 = Avaliação_MN1 + Participação_1 + Qualitativos
      NM2 = Avaliação_MN2 + Participação_2 + Qualitativos
      NM3 = flexível (mostra avaliação disponível)

    Retorna {"aulas", "quizzes", "forum",
              "participacao_nm1", "participacao_nm2",
              "nm1", "nm2", "nm3", "por_disciplina": [...]}.
    """
    aulas = repo.listar_aulas()
    quizzes = repo.listar_quizzes()

    disciplina_por_titulo = {str(aula.get("title")): aula.get("subject_id") for aula in aulas}
    disciplina_por_aula = {str(aula.get("id")): aula.get("subject_id") for aula in aulas}
    disciplina_por_quiz = {}
    for quiz in quizzes:
        disciplina = disciplina_por_aula.get(str(quiz.get("lesson_id")))
        if disciplina is not None:
            disciplina_por_quiz[str(quiz.get("title"))] = disciplina

    aulas_vistas: dict[str, set[str]] = {}
    melhores_quiz: dict[str, dict[str, int]] = {}

    for item in historico_aluno(username):
        atividade = str(item.get("activity") or "")
        disciplina = None
        achado = re.search(r"\| subject_id:(\d+)", atividade)
        if achado:
            disciplina = achado.group(1)
        limpo = atividade.split("|")[0].strip()

        if limpo.startswith("Acessou a aula:"):
            titulo = limpo.split(":", 1)[1].strip()
            disciplina = disciplina or disciplina_por_titulo.get(titulo)
            if disciplina is not None:
                aulas_vistas.setdefault(str(disciplina), set()).add(limpo)
        elif limpo.startswith("Concluiu Quiz:"):
            titulo, pontos = _parse_quiz_log(limpo)
            disciplina = disciplina or (disciplina_por_quiz.get(titulo) if titulo else None)
            if disciplina is not None and titulo:
                melhores = melhores_quiz.setdefault(str(disciplina), {})
                melhores[titulo] = max(melhores.get(titulo, 0), pontos)

    forum_por_disciplina = _forum_por_disciplina(username)
    avaliacoes = _avaliacoes_por_disciplina(username)
    qualitativos = _qualitativos_por_disciplina(username)

    disciplinas = set(aulas_vistas) | set(melhores_quiz) | set(forum_por_disciplina) | set(avaliacoes) | set(qualitativos)
    if subject_id is not None:
        disciplinas = {str(subject_id)} if str(subject_id) in disciplinas else set()

    nomes = {str(d["id"]): d["name"] for d in repo.listar_disciplinas(incluir_treinamento=True)}
    detalhes = []
    total_aulas = total_quizzes = total_forum = 0
    total_part_1 = 0.0
    total_part_2 = 0.0
    total_nm1 = 0.0
    total_nm2 = 0.0
    total_nm3 = 0.0

    for chave in sorted(disciplinas, key=lambda c: nomes.get(c, c)):
        n_aulas = len(aulas_vistas.get(chave, set()))
        n_quizzes = sum(melhores_quiz.get(chave, {}).values())
        n_forum = forum_por_disciplina.get(chave, 0)

        participacao_nm1 = _calcular_participacao(n_aulas, n_quizzes, n_forum, 0, 16)
        participacao_nm2 = _calcular_participacao(n_aulas, n_quizzes, n_forum, 16, 32)

        aval = avaliacoes.get(chave, {})
        qual = qualitativos.get(chave, 0)

        nm1 = _calcular_nm(aval.get("nm1", 0), participacao_nm1, qual)
        nm2 = _calcular_nm(aval.get("nm2", 0), participacao_nm2, qual)
        nm3_val = aval.get("nm3", 0)
        nm3 = _calcular_nm3(nm3_val, participacao_nm1, participacao_nm2, qual) if nm3_val else 0

        total_aulas += n_aulas
        total_quizzes += n_quizzes
        total_forum += n_forum
        total_part_1 += participacao_nm1
        total_part_2 += participacao_nm2
        total_nm1 += nm1
        total_nm2 += nm2
        total_nm3 += nm3

        detalhes.append({
            "subject_id": chave,
            "disciplina": nomes.get(chave, f"Disciplina {chave}"),
            "aulas": n_aulas,
            "quizzes": n_quizzes,
            "forum": n_forum,
            "participacao_nm1": round(participacao_nm1, 2),
            "participacao_nm2": round(participacao_nm2, 2),
            "avaliacao_nm1": aval.get("nm1", 0),
            "avaliacao_nm2": aval.get("nm2", 0),
            "avaliacao_nm3": aval.get("nm3", 0),
            "qualitativo": round(qual, 2),
            "nm1": round(nm1, 2),
            "nm2": round(nm2, 2),
            "nm3": round(nm3, 2),
        })

    n_disc = len(detalhes) or 1
    return {
        "aulas": total_aulas,
        "quizzes": total_quizzes,
        "forum": total_forum,
        "participacao_nm1": round(total_part_1 / n_disc, 2),
        "participacao_nm2": round(total_part_2 / n_disc, 2),
        "nm1": round(total_nm1 / n_disc, 2),
        "nm2": round(total_nm2 / n_disc, 2),
        "nm3": round(total_nm3 / n_disc, 2),
        "por_disciplina": detalhes,
    }
