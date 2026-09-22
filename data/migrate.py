"""
Migra dados do escola_ativa.db para o Supabase via API.
Uso: python data/migrate.py
Requer: SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env
"""
import os, sys, json
from pathlib import Path
from dotenv import dotenv_values

env_file = Path(__file__).resolve().parent.parent / ".env"
valores = dotenv_values(str(env_file))
URL = os.environ.get("SUPABASE_URL") or valores.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or valores.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or valores.get("SUPABASE_KEY")

if not URL or not KEY:
    print("ERRO: Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

from supabase import create_client
import sqlite3

client = create_client(URL, KEY)
LEGACY_DB = Path(__file__).resolve().parent.parent / "data" / "escola_ativa.db"
con = sqlite3.connect(str(LEGACY_DB))
con.row_factory = sqlite3.Row
cur = con.cursor()

LEGACY_MAP = {
    "users": "app_users", "classes": "classes", "subjects": "subjects",
    "class_subjects": "class_subjects", "student_enrollments": "student_enrollments",
    "lessons": "lessons", "quizzes": "quizzes", "quiz_questions": "quiz_questions",
    "assessments": "assessments", "assessment_questions": "assessment_questions",
    "student_assessments": "student_assessments",
    "student_assessment_answers": "student_assessment_answers",
    "attendance": "attendance", "forum_posts": "forum_posts",
    "weekly_schedule": "weekly_schedule",
}

def g(row, key, default=""):
    try:
        v = row[key]
        return v if v is not None else default
    except (KeyError, TypeError):
        return default

def escape(val):
    if val is None: return "NULL"
    if isinstance(val, str): return "'" + val.replace("'", "''") + "'"
    if isinstance(val, (int, float)): return str(val)
    if isinstance(val, (list, dict)):
        return "'" + json.dumps(val, ensure_ascii=False).replace("'", "''") + "'"
    return str(val)

def insert(table, rows, cols):
    if not rows: return
    c = ", ".join(cols)
    for r in rows:
        v = ", ".join(escape(r.get(c2, "")) for c2 in cols)
        resp = client.table(table).upsert({"id": r.get("id"), **{c2: r.get(c2) for c2 in cols if c2 != "id"}}).execute()

def migrate(table, columns, batch_size=100):
    legacy = LEGACY_MAP.get(table, table)
    rows = [dict(r) for r in cur.execute(f"SELECT * FROM {legacy}").fetchall()]
    if not rows:
        print(f"  [SKIP] {table} vazio")
        return
    total = len(rows)
    ok = 0
    for i in range(0, total, batch_size):
        for row in rows[i:i+batch_size]:
            try:
                data = {c: row.get(c) for c in columns}
                client.table(table).upsert(data).execute()
                ok += 1
            except Exception as e:
                pass
    print(f"  [OK] {table}: {ok}/{total}")

print("Iniciando migracao...")

print("\n[users]")
migrate("users", ["username", "name", "ra", "role", "is_active", "password_hash"])

print("\n[classes]")
migrate("classes", ["id", "name", "code", "official_name", "school_id", "tipo_turma", "ano_letivo", "is_active"])

print("\n[subjects]")
migrate("subjects", ["id", "name", "type", "aliases", "group_type", "carga_horaria", "duration_type", "lessons_per_week", "max_hours", "status", "folder_name", "is_active"])

print("\n[class_subjects]")
migrate("class_subjects", ["id", "class_id", "subject_id", "is_active"])

print("\n[student_enrollments]")
migrate("student_enrollments", ["class_id", "user_username"])

print("\n[lessons]")
migrate("lessons", ["id", "subject_id", "title", "description", "full_content", "objective", "resources", "video_url", "week", "status", "uuid"])

print("\n[quizzes]")
migrate("quizzes", ["id", "lesson_id", "title"])

print("\n[quiz_questions] (JSON)")
migrate("quiz_questions", ["id", "quiz_id", "question_text", "question_type", "options", "correct_option_index"])

print("\n[assessments]")
migrate("assessments", ["id", "subject_id", "title", "type"])

print("\n[assessment_questions] (JSON)")
migrate("assessment_questions", ["id", "assessment_id", "question_text", "question_type", "options", "correct_option_index"])

print("\n[student_assessments]")
migrate("student_assessments", ["id", "assessment_id", "user_username", "score", "status", "submitted_at"])

print("\n[student_assessment_answers]")
migrate("student_assessment_answers", ["id", "submission_id", "question_id", "answer_text", "answer_link", "selected_option_index"])

print("\n[attendance]")
migrate("attendance", ["class_name", "subject_id", "student_name", "student_number", "is_present", "status", "class_id", "date", "professor_name"])

print("\n[forum_posts]")
migrate("forum_posts", ["lesson_id", "user_name", "message"])

print("\n[weekly_schedule]")
migrate("weekly_schedule", ["class_id", "class_name", "day_of_week", "time_slot", "subject_name", "professor_name"])

print("\n[user_history] - mantido no SQLite local")

con.close()
print("\nMigracao concluida!")
