"""
Mecanismo de recuperação de dados perdidos na limpeza com FKs.

A limpeza anterior descartou (ou corrompeu) 4 grupos de dados por bugs
no prepare_clean_db.py. Este script recupera tudo do legado e grava no
escola_ativa.db:

1. quiz_questions (973) — o legado não tem a coluna `question_type`,
   exigida (NOT NULL) pelo schema limpo. Recupera com default 'objective'.
2. student_assessments (45) — alunos refizeram provas. O UNIQUE
   (assessment_id, user_username) mantém uma submissão por prova; guarda a
   submissão MAIS RECENTE (maior id) e corrige as notas no banco limpo.
3. attendance (488) — subject_id era NULL e o filtro de FK descartava
   NULLs indevidamente. Recupera com subject_id NULL + class_id mapeado.
4. weekly_schedule (22) — class_id usa o código antigo (309197/314114),
   não o id novo (1/2). Remapeia via classes.code/nome.

Uso: python data/recover_orphans.py
Idempotente: pode rodar várias vezes sem duplicar.
"""
import sqlite3
from pathlib import Path

LEGACY = Path(__file__).resolve().parent / "escola_ativa_legado.db"
CLEAN = Path(__file__).resolve().parent / "escola_ativa.db"


def _q(v) -> str:
    """Escapa uma string para SQL."""
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def conectar():
    con_leg = sqlite3.connect(str(LEGACY))
    con_leg.row_factory = sqlite3.Row
    con_clean = sqlite3.connect(str(CLEAN))
    con_clean.row_factory = sqlite3.Row
    return con_leg, con_clean


def contar(cur, tabela) -> int:
    try:
        return cur.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    except Exception:
        return -1


def mapa_classes(cur_clean):
    """Mapa code->id e sufixo de nome -> id das turmas limpas."""
    por_code = {}
    por_sufixo = {}
    for r in cur_clean.execute("SELECT id, code, name FROM classes").fetchall():
        cid, code, nome = r["id"], r["code"], r["name"]
        por_code[str(code)] = cid
        # Extrai o marcador de turma (ex.: "I-A", "I-B", "Turma I-A")
        partes = str(nome).split("Turma")
        if len(partes) > 1:
            sufixo = partes[-1].strip().split("(")[0].strip()
            por_sufixo[sufixo] = cid
        elif "I-A" in str(nome):
            por_sufixo["I-A"] = cid
        elif "I-B" in str(nome):
            por_sufixo["I-B"] = cid
    return por_code, por_sufixo


def resolver_class_id(valor, class_name, por_code, por_sufixo):
    """Devolve o id novo da turma a partir de code ou nome."""
    if valor is not None:
        cid = por_code.get(str(valor))
        if cid:
            return cid
    if class_name:
        for sufixo, cid in por_sufixo.items():
            if sufixo and sufixo in str(class_name):
                return cid
    return None


# --------------------------------------------------------------------------
# 1. quiz_questions
# --------------------------------------------------------------------------
def recuperar_quiz_questions(cur_leg, cur_clean):
    total = contar(cur_leg, "quiz_questions")
    ja = contar(cur_clean, "quiz_questions")
    if ja >= total:
        print(f"[quiz_questions] já completo ({ja}/{total}) — pulando.")
        return ja
    # ids já existentes (não duplicar)
    existentes = set(r[0] for r in cur_clean.execute("SELECT id FROM quiz_questions").fetchall())
    quiz_ids = set(r[0] for r in cur_clean.execute("SELECT id FROM quizzes").fetchall())
    inseridos = 0
    for r in cur_leg.execute("SELECT * FROM quiz_questions").fetchall():
        row = dict(r)
        if row["id"] in existentes:
            continue
        if row.get("quiz_id") not in quiz_ids:
            continue  # quiz não existe no limpo (não deveria ocorrer)
        cur_clean.execute(
            "INSERT INTO quiz_questions (id, quiz_id, question_text, question_type, options, correct_option_index) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                row["id"], row["quiz_id"], row["question_text"],
                "objective", row.get("options") or "[]",
                row.get("correct_option_index", 0),
            ),
        )
        inseridos += 1
    cur_clean.connection.commit()
    print(f"[quiz_questions] +{inseridos} recuperados (total agora {contar(cur_clean, 'quiz_questions')}/{total}).")
    return inseridos


# --------------------------------------------------------------------------
# 2. student_assessments (manter submissão mais recente) + respostas
# --------------------------------------------------------------------------
def recuperar_student_assessments(cur_leg, cur_clean):
    # Vencedores: maior id por (assessment_id, user_username)
    vencedores = cur_leg.execute("""
        SELECT MAX(id) AS wid FROM student_assessments
        GROUP BY assessment_id, user_username
    """).fetchall()
    winner_ids = set(r["wid"] for r in vencedores)

    total_sa = len(winner_ids)
    # Reconstruir do zero para garantir notas corretas
    cur_clean.execute("DELETE FROM student_assessment_answers")
    cur_clean.execute("DELETE FROM student_assessments")

    inseridos_sa = 0
    for r in cur_leg.execute("SELECT * FROM student_assessments").fetchall():
        if r["id"] not in winner_ids:
            continue
        cur_clean.execute(
            "INSERT INTO student_assessments (id, assessment_id, user_username, score, status, submitted_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (r["id"], r["assessment_id"], r["user_username"], r["score"], r["status"], r["submitted_at"]),
        )
        inseridos_sa += 1

    # Respostas dos vencedores
    inseridos_ans = 0
    for r in cur_leg.execute("SELECT * FROM student_assessment_answers").fetchall():
        if r["submission_id"] not in winner_ids:
            continue
        cur_clean.execute(
            "INSERT INTO student_assessment_answers (id, submission_id, question_id, answer_text, answer_link, selected_option_index) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (r["id"], r["submission_id"], r["question_id"], dict(r).get("answer_text") or "", dict(r).get("answer_link") or "", dict(r).get("selected_option_index")),
        )
        inseridos_ans += 1
    cur_clean.connection.commit()
    print(f"[student_assessments] {inseridos_sa} submissões (mais recentes) reconstruídas.")
    print(f"[student_assessment_answers] {inseridos_ans} respostas reconstruídas.")
    return inseridos_sa, inseridos_ans


# --------------------------------------------------------------------------
# 3. attendance
# --------------------------------------------------------------------------
def recuperar_attendance(cur_leg, cur_clean, por_code, por_sufixo):
    total = contar(cur_leg, "attendance")
    ja = contar(cur_clean, "attendance")
    if ja >= total:
        print(f"[attendance] já completo ({ja}/{total}) — pulando.")
        return ja
    existentes = set(r[0] for r in cur_clean.execute("SELECT id FROM attendance").fetchall())
    inseridos = 0
    for r in cur_leg.execute("SELECT * FROM attendance").fetchall():
        if r["id"] in existentes:
            continue
        class_id = resolver_class_id(None, dict(r).get("class_name"), por_code, por_sufixo)
        status = "Presente" if dict(r).get("is_present") else "Ausente"
        cur_clean.execute(
            "INSERT INTO attendance (id, class_name, subject_id, student_name, student_number, is_present, status, class_id, date, professor_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (r["id"], r["class_name"], dict(r).get("subject_id"), r["student_name"],
             dict(r).get("student_number", 0), dict(r).get("is_present", 1), status,
             class_id, r["date"], dict(r).get("professor_name") or ""),
        )
        inseridos += 1
    cur_clean.connection.commit()
    print(f"[attendance] +{inseridos} recuperados (total agora {contar(cur_clean, 'attendance')}/{total}).")
    return inseridos


# --------------------------------------------------------------------------
# 4. weekly_schedule
# --------------------------------------------------------------------------
def recuperar_weekly_schedule(cur_leg, cur_clean, por_code, por_sufixo):
    total = contar(cur_leg, "weekly_schedule")
    ja = contar(cur_clean, "weekly_schedule")
    if ja >= total:
        print(f"[weekly_schedule] já completo ({ja}/{total}) — pulando.")
        return ja
    existentes = set(r[0] for r in cur_clean.execute("SELECT id FROM weekly_schedule").fetchall())
    inseridos = 0
    for r in cur_leg.execute("SELECT * FROM weekly_schedule").fetchall():
        if r["id"] in existentes:
            continue
        class_id = resolver_class_id(dict(r).get("class_id"), dict(r).get("class_name"), por_code, por_sufixo)
        if class_id is None:
            print(f"  [aviso] weekly_schedule id={r['id']} sem turma resolvida (class_id={dict(r).get('class_id')}, name={dict(r).get('class_name')}).")
            continue
        cur_clean.execute(
            "INSERT INTO weekly_schedule (id, class_id, class_name, day_of_week, time_slot, subject_name, professor_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (r["id"], class_id, r["class_name"], r["day_of_week"], r["time_slot"], r["subject_name"], dict(r).get("professor_name") or ""),
        )
        inseridos += 1
    cur_clean.connection.commit()
    print(f"[weekly_schedule] +{inseridos} recuperados (total agora {contar(cur_clean, 'weekly_schedule')}/{total}).")
    return inseridos


def main():
    con_leg, con_clean = conectar()
    cur_leg = con_leg.cursor()
    cur_clean = con_clean.cursor()
    por_code, por_sufixo = mapa_classes(cur_clean)

    print("=== RECUPERACAO DE DADOS ===\n")

    r1 = recuperar_quiz_questions(cur_leg, cur_clean)
    r2 = recuperar_student_assessments(cur_leg, cur_clean)
    r3 = recuperar_attendance(cur_leg, cur_clean, por_code, por_sufixo)
    r4 = recuperar_weekly_schedule(cur_leg, cur_clean, por_code, por_sufixo)

    print("\n=== RESUMO ===")
    for tabela in ["quiz_questions", "student_assessments", "student_assessment_answers", "attendance", "weekly_schedule"]:
        print(f"  {tabela}: {contar(cur_clean, tabela)}")

    con_leg.close()
    con_clean.close()
    print("\n[OK] Recuperacao concluida. Rode python data/migrate.py para enviar ao Supabase.")


if __name__ == "__main__":
    main()
