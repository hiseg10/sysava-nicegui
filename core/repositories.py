"""
Camada de acesso a dados do SysAVA (SQLite / escola_ativa.db).

Cada função abre e fecha sua própria conexão (somente leitura) usando
`core.db.abrir`. Assim não há conexão compartilhada entre threads, o que é
seguro para o servidor do NiceGUI.
"""

from __future__ import annotations

import sqlite3
from core import db


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _consultar(sql: str, parametros=()) -> list[dict]:
    """Executa um SELECT e devolve uma lista de dicionários."""
    try:
        with db.abrir() as con:
            cursor = con.execute(sql, parametros)
            if cursor.description is None:
                return []
            return [dict(linha) for linha in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


def _consultar_um(sql: str, parametros=()) -> dict | None:
    """Executa um SELECT e devolve o primeiro registro (ou None)."""
    linhas = _consultar(sql, parametros)
    return linhas[0] if linhas else None


# --------------------------------------------------------------------------
# Disciplinas
# --------------------------------------------------------------------------
def _coluna_existe(tabela: str, coluna: str) -> bool:
    """Verifica se uma coluna existe na tabela."""
    try:
        with db.abrir() as con:
            colunas = [r[1] for r in con.execute(f"PRAGMA table_info({tabela})").fetchall()]
            return coluna in colunas
    except Exception:
        return False


def listar_disciplinas(incluir_treinamento: bool = False, apenas_ativas: bool = False) -> list[dict]:
    """Lista as disciplinas, opcionalmente incluindo as do tipo 'training'.
    
    Se apenas_ativas=True, exclui disciplinas inativas e completas.
    Se a coluna 'status' não existir, ignora o filtro de status.
    """
    condicoes = []
    if not incluir_treinamento:
        condicoes.append("COALESCE(type, '') <> 'training'")
    if apenas_ativas and _coluna_existe("subjects", "status"):
        condicoes.append("COALESCE(status, 'incompleta') = 'incompleta'")
    
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    return _consultar(f"SELECT * FROM subjects {where} ORDER BY name")


def obter_disciplina(subject_id) -> dict | None:
    return _consultar_um("SELECT * FROM subjects WHERE id = ?", (str(subject_id),))


# --------------------------------------------------------------------------
# Aulas
# --------------------------------------------------------------------------
def listar_aulas(subject_id=None) -> list[dict]:
    """Lista as aulas de uma disciplina (ou todas, se subject_id for None)."""
    if subject_id is None:
        return _consultar("SELECT * FROM lessons ORDER BY id")
    return _consultar(
        "SELECT * FROM lessons WHERE subject_id = ? ORDER BY id", (str(subject_id),)
    )


def obter_aula(lesson_id) -> dict | None:
    return _consultar_um("SELECT * FROM lessons WHERE id = ?", (str(lesson_id),))


# --------------------------------------------------------------------------
# Quizzes
# --------------------------------------------------------------------------
def listar_quizzes() -> list[dict]:
    return _consultar("SELECT * FROM quizzes ORDER BY id")


def obter_quiz_da_aula(lesson_id) -> dict | None:
    return _consultar_um(
        "SELECT * FROM quizzes WHERE lesson_id = ? LIMIT 1", (str(lesson_id),)
    )


def mapa_quizzes_por_aula() -> dict[str, dict]:
    """Mapa {lesson_id: quiz} em uma única consulta (evita N+1)."""
    mapa: dict[str, dict] = {}
    for quiz in listar_quizzes():
        chave = str(quiz.get("lesson_id"))
        mapa.setdefault(chave, quiz)
    return mapa


# --------------------------------------------------------------------------
# Fórum
# --------------------------------------------------------------------------
def listar_posts_forum(lesson_id=None) -> list[dict]:
    if lesson_id is None:
        return _consultar("SELECT * FROM forum_posts ORDER BY id")
    return _consultar(
        "SELECT * FROM forum_posts WHERE lesson_id = ? ORDER BY id", (str(lesson_id),)
    )


def contagem_posts_por_aula() -> dict[str, int]:
    """Mapa {lesson_id: quantidade_de_posts} em uma única consulta."""
    linhas = _consultar(
        "SELECT lesson_id, COUNT(*) AS total FROM forum_posts "
        "WHERE lesson_id IS NOT NULL GROUP BY lesson_id"
    )
    return {str(linha["lesson_id"]): linha["total"] for linha in linhas}


# --------------------------------------------------------------------------
# Turmas, alunos e matrículas
# --------------------------------------------------------------------------
def listar_turmas() -> list[dict]:
    return _consultar("SELECT * FROM classes ORDER BY name")


def listar_disciplinas_da_turma(class_id, apenas_ativas: bool = False) -> list[dict]:
    """Lista disciplinas vinculadas a uma turma.
    
    Se apenas_ativas=True, exclui disciplinas inativas e completas.
    Se a coluna 'status' não existir, ignora o filtro de status.
    """
    condicoes = ["cs.class_id = ?"]
    parametros = [str(class_id)]
    
    if apenas_ativas and _coluna_existe("subjects", "status"):
        condicoes.append("COALESCE(s.status, 'incompleta') = 'incompleta'")
    
    where = " AND ".join(condicoes)
    return _consultar(
        "SELECT s.* FROM subjects s "
        "JOIN class_subjects cs ON cs.subject_id = s.id "
        f"WHERE {where} ORDER BY s.name",
        tuple(parametros),
    )


def listar_alunos_da_turma(class_id) -> list[dict]:
    return _consultar(
        "SELECT u.* FROM app_users u "
        "JOIN student_enrollments e ON e.user_username = u.username "
        "WHERE e.class_id = ? ORDER BY u.name",
        (str(class_id),),
    )


def listar_matriculas() -> list[dict]:
    return _consultar("SELECT * FROM student_enrollments")


def obter_aluno(username) -> dict | None:
    return _consultar_um("SELECT * FROM app_users WHERE username = ?", (str(username),))


def contexto_aluno(username) -> dict:
    """Reúne turma, disciplinas, notas e frequência de um aluno."""
    aluno = obter_aluno(username) or {}
    nome = aluno.get("name")

    class_id = next(
        (
            matricula["class_id"]
            for matricula in listar_matriculas()
            if str(matricula.get("user_username")) == str(username)
        ),
        None,
    )
    turma = None
    if class_id is not None:
        turma = next(
            (item for item in listar_turmas() if str(item.get("id")) == str(class_id)), None
        )

    turma_nome = (turma or {}).get("name")
    disciplinas = listar_disciplinas_da_turma(class_id) if class_id is not None else []

    notas: list[dict] = []
    frequencia: list[dict] = []
    if turma_nome and nome:
        notas = [
            item
            for item in listar_notas(class_name=turma_nome)
            if str(item.get("student_name")) == str(nome)
        ]
        frequencia = [
            item
            for item in listar_frequencia(class_name=turma_nome)
            if str(item.get("student_name")) == str(nome)
        ]

    presencas = sum(
        1 for item in frequencia if str(item.get("is_present")).strip() in {"1", "true", "t"}
    )
    return {
        "aluno": aluno,
        "turma": turma,
        "disciplinas": disciplinas,
        "notas": notas,
        "frequencia": frequencia,
        "presencas": presencas,
        "faltas": len(frequencia) - presencas,
    }


# --------------------------------------------------------------------------
# Horários e histórico de aulas
# --------------------------------------------------------------------------
def listar_horarios(class_id=None) -> list[dict]:
    if class_id is None:
        return _consultar("SELECT * FROM weekly_schedule ORDER BY time_slot")
    return _consultar(
        "SELECT * FROM weekly_schedule WHERE class_id = ? ORDER BY time_slot",
        (str(class_id),),
    )


def listar_historico_aulas(turma_id=None, disciplina_id=None) -> list[dict]:
    condicoes, parametros = [], []
    if turma_id is not None:
        condicoes.append("turma_id = ?")
        parametros.append(str(turma_id))
    if disciplina_id is not None:
        condicoes.append("disciplina_id = ?")
        parametros.append(str(disciplina_id))
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    return _consultar(
        f"SELECT * FROM historico_aulas {where} ORDER BY data_aula", tuple(parametros)
    )


# --------------------------------------------------------------------------
# Planejamento
# --------------------------------------------------------------------------
def listar_planejamentos(turma_id=None, disciplina_id=None) -> list[dict]:
    condicoes, parametros = [], []
    if turma_id is not None:
        condicoes.append("turma_id = ?")
        parametros.append(str(turma_id))
    if disciplina_id is not None:
        condicoes.append("disciplina_id = ?")
        parametros.append(str(disciplina_id))
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    return _consultar(
        f"SELECT * FROM planejamento {where} ORDER BY id", tuple(parametros)
    )


# --------------------------------------------------------------------------
# Frequência e notas
# --------------------------------------------------------------------------
def listar_frequencia(class_name=None, subject_id=None) -> list[dict]:
    condicoes, parametros = [], []
    if class_name is not None:
        condicoes.append("class_name = ?")
        parametros.append(str(class_name))
    if subject_id is not None:
        condicoes.append("subject_id = ?")
        parametros.append(str(subject_id))
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    return _consultar(
        f"SELECT * FROM attendance {where} ORDER BY date, student_name", tuple(parametros)
    )


def listar_notas(class_name=None, subject=None, trimester=None) -> list[dict]:
    condicoes, parametros = [], []
    if class_name is not None:
        condicoes.append("class_name = ?")
        parametros.append(str(class_name))
    if subject is not None:
        condicoes.append("subject = ?")
        parametros.append(str(subject))
    if trimester is not None:
        condicoes.append("trimester = ?")
        parametros.append(int(trimester))
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    # Dual: legado Streamlit usa student_name; NiceGUI usa user_username.
    colunas = _colunas_tabela("student_grades")
    if "student_name" in colunas:
        ordenar = "student_name"
    elif "user_username" in colunas:
        ordenar = "user_username"
    else:
        ordenar = "id"
    linhas = _consultar(
        f"SELECT * FROM student_grades {where} ORDER BY {ordenar}", tuple(parametros)
    )
    return linhas


def _colunas_tabela(tabela: str) -> set[str]:
    try:
        with db.abrir() as con:
            return {
                linha[1]
                for linha in con.execute(f'PRAGMA table_info("{tabela}")').fetchall()
            }
    except Exception:
        return set()


def listar_pontos_qualitativos(user_username=None) -> list[dict]:
    if user_username is None:
        return _consultar("SELECT * FROM qualitative_points ORDER BY date")
    return _consultar(
        "SELECT * FROM qualitative_points WHERE user_username = ? ORDER BY date",
        (str(user_username),),
    )


# --------------------------------------------------------------------------
# Configurações
# --------------------------------------------------------------------------
def listar_settings() -> list[dict]:
    return _consultar("SELECT * FROM settings ORDER BY chave")


def obter_setting(chave: str, padrao=None):
    registro = _consultar_um("SELECT valor FROM settings WHERE chave = ?", (chave,))
    return registro["valor"] if registro else padrao


# --------------------------------------------------------------------------
# Visão geral
# --------------------------------------------------------------------------
def contagens_gerais() -> dict[str, int]:
    """Contagem de registros das principais tabelas (para dashboards)."""
    tabelas = [
        "app_users", "classes", "subjects", "lessons", "quizzes", "quiz_questions",
        "assessments", "assessment_questions", "attendance", "student_enrollments",
        "student_grades", "qualitative_points", "forum_posts",
        "weekly_schedule",
    ]
    contagens: dict[str, int] = {}
    try:
        with db.abrir() as con:
            for tabela in tabelas:
                try:
                    contagens[tabela] = con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
                except Exception:
                    contagens[tabela] = 0
    except sqlite3.OperationalError:
        for tabela in tabelas:
            contagens[tabela] = 0
    return contagens
