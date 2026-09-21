"""
Gerenciamento de turmas e disciplinas (CRUD).

Cria e gerencia as tabelas `classes`, `subjects`, `class_subjects` e
`student_enrollments` no SQLite, incluindo campos novos:
  - classes: tipo_turma ('normal'|'modular'), ano_letivo
  - subjects: carga_horaria (horas), duration_type ('anual'|'mensal'), status ('incompleta'|'completa'|'inativa')
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from core import db

# --------------------------------------------------------------------------
# Inicialização (adiciona colunas novas se faltarem)
# --------------------------------------------------------------------------
_MIGRACOES = [
    "ALTER TABLE classes ADD COLUMN tipo_turma TEXT DEFAULT 'normal'",
    "ALTER TABLE classes ADD COLUMN ano_letivo TEXT DEFAULT ''",
    "ALTER TABLE subjects ADD COLUMN carga_horaria INTEGER DEFAULT 0",
    "ALTER TABLE subjects ADD COLUMN duration_type TEXT DEFAULT 'anual'",
    "ALTER TABLE subjects ADD COLUMN status TEXT DEFAULT 'incompleta'",
]


def _ensure_columns() -> None:
    """Executa migrações silenciosas para colunas que podem não existir."""
    try:
        with db.abrir(somente_leitura=False) as con:
            for sql in _MIGRACOES:
                try:
                    con.execute(sql)
                except sqlite3.OperationalError:
                    pass  # coluna já existe
            con.commit()
    except Exception:
        pass


_ensure_columns()


# --------------------------------------------------------------------------
# Turmas
# --------------------------------------------------------------------------
def listar_turmas() -> list[dict]:
    """Lista todas as turmas com contagem de alunos."""
    with db.abrir() as con:
        linhas = con.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM student_enrollments e WHERE e.class_id = c.id) AS alunos
               FROM classes c ORDER BY c.name"""
        ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_turma(class_id) -> dict | None:
    with db.abrir() as con:
        linha = con.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM student_enrollments e WHERE e.class_id = c.id) AS alunos
               FROM classes c WHERE c.id = ?""",
            (str(class_id),),
        ).fetchone()
    return dict(linha) if linha else None


def criar_turma(name: str, code: str = "", tipo_turma: str = "normal",
                ano_letivo: str = "") -> int | None:
    """Cria uma turma e retorna o ID (ou None em caso de erro)."""
    if not name or not name.strip():
        return None
    try:
        with db.abrir(somente_leitura=False) as con:
            cur = con.execute(
                "INSERT INTO classes (name, code, tipo_turma, ano_letivo) VALUES (?, ?, ?, ?)",
                (name.strip(), code.strip(), tipo_turma, ano_letivo),
            )
            con.commit()
            return cur.lastrowid
    except Exception:
        return None


def atualizar_turma(class_id, *, name: str = None, code: str = None,
                    tipo_turma: str = None, ano_letivo: str = None) -> bool:
    campos: list[str] = []
    valores: list = []
    if name is not None:
        campos.append("name = ?")
        valores.append(name.strip())
    if code is not None:
        campos.append("code = ?")
        valores.append(code.strip())
    if tipo_turma is not None:
        campos.append("tipo_turma = ?")
        valores.append(tipo_turma)
    if ano_letivo is not None:
        campos.append("ano_letivo = ?")
        valores.append(ano_letivo)
    if not campos:
        return False
    valores.append(class_id)
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(f"UPDATE classes SET {', '.join(campos)} WHERE id = ?", valores)
            con.commit()
        return True
    except Exception:
        return False


def remover_turma(class_id) -> bool:
    """Remove a turma e seus vínculos (disciplinas e matrículas)."""
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute("DELETE FROM class_subjects WHERE class_id = ?", (class_id,))
            con.execute("DELETE FROM student_enrollments WHERE class_id = ?", (class_id,))
            con.execute("DELETE FROM classes WHERE id = ?", (class_id,))
            con.commit()
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Disciplinas
# --------------------------------------------------------------------------
def listar_disciplinas() -> list[dict]:
    return [dict(l) for l in db.abrir().__enter__().execute(
        "SELECT * FROM subjects ORDER BY name"
    ).fetchall()] if False else _ler_disciplinas()


def _ler_disciplinas() -> list[dict]:
    with db.abrir() as con:
        linhas = con.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    return [dict(linha) for linha in linhas]


def obter_disciplina(subject_id) -> dict | None:
    with db.abrir() as con:
        linha = con.execute("SELECT * FROM subjects WHERE id = ?", (str(subject_id),)).fetchone()
    return dict(linha) if linha else None


def criar_disciplina(name: str, tipo: str = "regular", carga_horaria: int = 0,
                     duration_type: str = "anual", status: str = "incompleta") -> int | None:
    """Cria uma disciplina.
    
    Status: 'incompleta' (padrão), 'completa', 'inativa'
    """
    if not name or not name.strip():
        return None
    try:
        with db.abrir(somente_leitura=False) as con:
            cur = con.execute(
                "INSERT INTO subjects (name, type, carga_horaria, duration_type, status) VALUES (?, ?, ?, ?, ?)",
                (name.strip(), tipo, carga_horaria, duration_type, status),
            )
            con.commit()
            return cur.lastrowid
    except Exception:
        return None


def atualizar_disciplina(subject_id, *, name: str = None, tipo: str = None,
                         carga_horaria: int = None, duration_type: str = None,
                         status: str = None) -> bool:
    """Atualiza uma disciplina.
    
    Status: 'incompleta', 'completa', 'inativa'
    """
    campos: list[str] = []
    valores: list = []
    if name is not None:
        campos.append("name = ?")
        valores.append(name.strip())
    if tipo is not None:
        campos.append("type = ?")
        valores.append(tipo)
    if carga_horaria is not None:
        campos.append("carga_horaria = ?")
        valores.append(carga_horaria)
    if duration_type is not None:
        campos.append("duration_type = ?")
        valores.append(duration_type)
    if status is not None:
        campos.append("status = ?")
        valores.append(status)
    if not campos:
        return False
    valores.append(subject_id)
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(f"UPDATE subjects SET {', '.join(campos)} WHERE id = ?", valores)
            con.commit()
        return True
    except Exception:
        return False


def alternar_status_disciplina(subject_id) -> str | None:
    """Alterna o status da disciplina: incompleta -> completa -> inativa -> incompleta
    
    Retorna o novo status ou None em caso de erro.
    """
    try:
        with db.abrir() as con:
            linha = con.execute("SELECT status FROM subjects WHERE id = ?", (str(subject_id),)).fetchone()
            if not linha:
                return None
            atual = (linha["status"] or "incompleta").lower()
            
            if atual == "incompleta":
                novo = "completa"
            elif atual == "completa":
                novo = "inativa"
            else:
                novo = "incompleta"
            
            with db.abrir(somente_leitura=False) as con:
                con.execute("UPDATE subjects SET status = ? WHERE id = ?", (novo, str(subject_id)))
                con.commit()
            return novo
    except Exception:
        return None


def remover_disciplina(subject_id) -> bool:
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute("DELETE FROM class_subjects WHERE subject_id = ?", (subject_id,))
            con.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
            con.commit()
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Vínculos turma ↔ disciplina
# --------------------------------------------------------------------------
def listar_disciplinas_da_turma(class_id) -> list[dict]:
    with db.abrir() as con:
        linhas = con.execute(
            """SELECT s.* FROM subjects s
               JOIN class_subjects cs ON cs.subject_id = s.id
               WHERE cs.class_id = ? ORDER BY s.name""",
            (str(class_id),),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def vincular_disciplina(class_id, subject_id) -> bool:
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                "INSERT OR IGNORE INTO class_subjects (class_id, subject_id) VALUES (?, ?)",
                (class_id, subject_id),
            )
            con.commit()
        return True
    except Exception:
        return False


def desvincular_disciplina(class_id, subject_id) -> bool:
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                "DELETE FROM class_subjects WHERE class_id = ? AND subject_id = ?",
                (class_id, subject_id),
            )
            con.commit()
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Matrículas
# --------------------------------------------------------------------------
def contar_alunos(class_id) -> int:
    with db.abrir() as con:
        resultado = con.execute(
            "SELECT COUNT(*) FROM student_enrollments WHERE class_id = ?", (class_id,)
        ).fetchone()
    return resultado[0] if resultado else 0


def matricular_aluno(username: str, class_id) -> bool:
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute(
                "INSERT OR REPLACE INTO student_enrollments (user_username, class_id) VALUES (?, ?)",
                (username, class_id),
            )
            con.commit()
        return True
    except Exception:
        return False


def desmatricular_aluno(username: str) -> bool:
    try:
        with db.abrir(somente_leitura=False) as con:
            con.execute("DELETE FROM student_enrollments WHERE user_username = ?", (username,))
            con.commit()
        return True
    except Exception:
        return False


def listar_alunos_sem_turma() -> list[dict]:
    """Lista alunos que não estão matriculados em nenhuma turma."""
    with db.abrir() as con:
        linhas = con.execute(
            """SELECT u.* FROM app_users u
               LEFT JOIN student_enrollments e ON e.user_username = u.username
               WHERE e.user_username IS NULL
               AND u.role = 'student'
               ORDER BY u.name"""
        ).fetchall()
    return [dict(linha) for linha in linhas]
