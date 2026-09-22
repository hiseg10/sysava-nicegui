import os, sys, json
from pathlib import Path
from dotenv import dotenv_values

env_file = Path(__file__).resolve().parent.parent / ".env"
valores = dotenv_values(str(env_file))
URL = os.environ.get("SUPABASE_URL") or valores.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or valores.get("SUPABASE_SERVICE_ROLE_KEY")

from supabase import create_client
import sqlite3

client = create_client(URL, KEY)

LEGACY_DB = Path(__file__).resolve().parent.parent / "data" / "escola_ativa.db"
con = sqlite3.connect(str(LEGACY_DB))
con.row_factory = sqlite3.Row
cur = con.cursor()

LEGACY_MAP = {
    "users": "users", "classes": "classes", "subjects": "subjects",
    "class_subjects": "class_subjects", "student_enrollments": "student_enrollments",
    "lessons": "lessons", "quizzes": "quizzes", "quiz_questions": "quiz_questions",
    "assessments": "assessments", "assessment_questions": "assessment_questions",
    "student_assessments": "student_assessments",
    "student_assessment_answers": "student_assessment_answers",
    "attendance": "attendance", "forum_posts": "forum_posts",
    "weekly_schedule": "weekly_schedule", "user_history": "user_history",
}

def load_ids(table):
    try:
        return set(str(r[0]) for r in cur.execute(f"SELECT id FROM {table}").fetchall())
    except:
        return set()

def load_values(table, col):
    try:
        return set(str(r[0]) for r in cur.execute(f"SELECT {col} FROM {table}").fetchall())
    except:
        return set()

def safe_print(s):
    try:
        print(s)
    except (UnicodeEncodeError, UnicodeDecodeError):
        print(s.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))

def migrate(table, columns, batch_size=50, fk_checks=None, on_conflict=None):
    legacy = LEGACY_MAP.get(table, table)
    all_rows = [dict(r) for r in cur.execute(f"SELECT * FROM {legacy}").fetchall()]
    if not all_rows:
        print(f"  [SKIP] {table} vazio")
        return
    if fk_checks:
        valid_rows = []
        for row in all_rows:
            valid = True
            for fk_check in fk_checks:
                fk_col, ref_table = fk_check[0], fk_check[1]
                ref_col = fk_check[2] if len(fk_check) > 2 else "id"
                val = str(row.get(fk_col, ""))
                if val:
                    if ref_col == "id":
                        if val not in load_ids(ref_table):
                            valid = False
                            break
                    else:
                        if val not in load_values(ref_table, ref_col):
                            valid = False
                            break
            if valid:
                valid_rows.append(row)
        all_rows = valid_rows

    total = len(all_rows)
    if not total:
        print(f"  [SKIP] {table} todos orfaos")
        return

    ok = 0
    for i in range(0, total, batch_size):
        batch = all_rows[i:i+batch_size]
        data_list = [{c: row.get(c) for c in columns} for row in batch]
        try:
            if on_conflict:
                client.table(table).upsert(data_list, on_conflict=on_conflict).execute()
            else:
                client.table(table).upsert(data_list).execute()
            ok += len(batch)
            print(f"    progress {ok}/{total}")
        except Exception as e:
            print(f"  [ERRO batch {i}] {e}")
            for row in batch:
                try:
                    data = {c: row.get(c) for c in columns}
                    if on_conflict:
                        client.table(table).upsert(data, on_conflict=on_conflict).execute()
                    else:
                        client.table(table).upsert(data).execute()
                    ok += 1
                except Exception:
                    pass
    print(f"  [OK] {table}: {ok}/{total}")

print("Iniciando migracao (batch 50, com FKs)...\n")

print("[users]")
migrate("users", ["username", "name", "ra", "role", "is_active", "password_hash"])

print("[classes]")
migrate("classes", ["id", "name", "code", "official_name", "school_id", "tipo_turma", "ano_letivo", "is_active"])

print("[subjects]")
migrate("subjects", ["id", "name", "type", "aliases", "group_type", "carga_horaria", "duration_type", "lessons_per_week", "max_hours", "status", "folder_name", "is_active"])

print("[class_subjects]")
migrate("class_subjects", ["id", "class_id", "subject_id", "is_active"],
        fk_checks=[("class_id", "classes"), ("subject_id", "subjects")])

print("[student_enrollments]")
migrate("student_enrollments", ["class_id", "user_username"],
        fk_checks=[("class_id", "classes")],
        on_conflict="class_id,user_username")

print("[lessons]")
migrate("lessons", ["id", "subject_id", "title", "description", "full_content", "objective", "resources", "video_url", "week", "status", "uuid"],
        fk_checks=[("subject_id", "subjects")])

print("[quizzes]")
migrate("quizzes", ["id", "lesson_id", "title"],
        fk_checks=[("lesson_id", "lessons")])

print("[quiz_questions]")
migrate("quiz_questions", ["id", "quiz_id", "question_text", "question_type", "options", "correct_option_index"],
        fk_checks=[("quiz_id", "quizzes")])

print("[assessments]")
migrate("assessments", ["id", "subject_id", "title", "type"],
        fk_checks=[("subject_id", "subjects")])

print("[assessment_questions]")
migrate("assessment_questions", ["id", "assessment_id", "question_text", "question_type", "options", "correct_option_index"],
        fk_checks=[("assessment_id", "assessments")])

print("[student_assessments]")
migrate("student_assessments", ["id", "assessment_id", "user_username", "score", "status", "submitted_at"],
        fk_checks=[("assessment_id", "assessments")])

print("[student_assessment_answers]")
migrate("student_assessment_answers", ["id", "submission_id", "question_id", "answer_text", "answer_link", "selected_option_index"],
        fk_checks=[("submission_id", "student_assessments"), ("question_id", "assessment_questions")])

print("[attendance]")
migrate("attendance", ["class_name", "subject_id", "student_name", "student_number", "is_present", "status", "class_id", "date", "professor_name"],
        fk_checks=[("subject_id", "subjects"), ("class_id", "classes")])

print("[forum_posts]")
migrate("forum_posts", ["lesson_id", "user_name", "message"],
        fk_checks=[("lesson_id", "lessons")])

print("[weekly_schedule]")
migrate("weekly_schedule", ["class_id", "class_name", "day_of_week", "time_slot", "subject_name", "professor_name"],
        fk_checks=[("class_id", "classes")],
        on_conflict="class_id,day_of_week,time_slot,subject_name")

print("[user_history]")
migrate("user_history", ["id", "username", "activity", "timestamp"])

con.close()
print("\nMigracao concluida!")
