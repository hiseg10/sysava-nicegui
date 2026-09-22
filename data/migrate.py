"""
Migra dados do escola_ativa.db para o Supabase via API.
Uso: python data/migrate.py
Requer: SUPABASE_URL e SUPABASE_KEY no .env
"""
import os, sys
from pathlib import Path
from dotenv import dotenv_values

# Carrega credenciais
env_file = Path(__file__).resolve().parent.parent / ".env"
valores = dotenv_values(str(env_file))
URL = os.environ.get("SUPABASE_URL") or valores.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY") or valores.get("SUPABASE_KEY")

if not URL or not KEY:
    print("ERRO: Defina SUPABASE_URL e SUPABASE_KEY")
    sys.exit(1)

from supabase import create_client
import sqlite3
from pathlib import Path

client = create_client(URL, KEY)
LEGACY_DB = Path(__file__).resolve().parent.parent / "data" / "escola_ativa.db"
con = sqlite3.connect(str(LEGACY_DB))
con.row_factory = sqlite3.Row
cur = con.cursor()


def migrate(table: str, columns: list, batch_size: int = 100):
    """Lê do SQLite e faz upsert no Supabase em batches."""
    rows = [dict(r) for r in cur.execute(f"SELECT * FROM {table}").fetchall()]
    if not rows:
        print(f"  [SKIP] {table} vazio")
        return
    total = len(rows)
    ok = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        try:
            for row in batch:
                data = {c: row.get(c) for c in columns}
                resp = client.table(table).upsert(data).execute()
                ok += 1
        except Exception as e:
            print(f"  [ERRO] {table} lote {i}: {e}")
    print(f"  [OK] {table}: {ok}/{total}")


def migrate_json(table: str, columns: list, json_cols: list, batch_size: int = 50):
    """Igual migrate() mas converte colunas JSON antes de enviar."""
    rows = [dict(r) for r in cur.execute(f"SELECT * FROM {table}").fetchall()]
    if not rows:
        print(f"  [SKIP] {table} vazio")
        return
    total = len(rows)
    ok = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        try:
            for row in batch:
                data = {c: row.get(c) for c in columns}
                for jc in json_cols:
                    if jc in data and isinstance(data[jc], str):
                        import json
                        try:
                            data[jc] = json.loads(data[jc])
                        except (json.JSONDecodeError, ValueError):
                            pass
                resp = client.table(table).upsert(data).execute()
                ok += 1
        except Exception as e:
            print(f"  [ERRO] {table} lote {i}: {e}")
    print(f"  [OK] {table}: {ok}/{total}")


# ========================================================
# Migrações por tabela
# ========================================================
print("Iniciando migracao...")

print("\n[users]")
migrate("users", ["username", "name", "ra", "role", "is_active", "password_hash"])

print("\n[classes]")
migrate("classes", ["id", "name", "code", "official_name", "school_id",
                     "tipo_turma", "ano_letivo", "is_active"])

print("\n[subjects]")
migrate("subjects", ["id", "name", "type", "aliases", "group_type", "carga_horaria",
                      "duration_type", "lessons_per_week", "max_hours", "status",
                      "folder_name", "is_active"])

print("\n[class_subjects]")
migrate("class_subjects", ["id", "class_id", "subject_id", "is_active"])

print("\n[student_enrollments]")
migrate("student_enrollments", ["class_id", "user_username"])

print("\n[lessons]")
migrate("lessons", ["id", "subject_id", "title", "description", "full_content",
                     "objective", "resources", "video_url", "week", "status",
                     "uuid"])

print("\n[quizzes]")
migrate("quizzes", ["id", "lesson_id", "title"])

print("\n[quiz_questions] (JSON)")
migrate_json("quiz_questions", ["id", "quiz_id", "question_text", "question_type",
                                 "options", "correct_option_index"],
              ["options"])

print("\n[assessments]")
migrate("assessments", ["id", "subject_id", "title", "type"])

print("\n[assessment_questions] (JSON)")
migrate_json("assessment_questions", ["id", "assessment_id", "question_text",
                                        "question_type", "options",
                                        "correct_option_index"],
              ["options"])

print("\n[student_assessments]")
migrate("student_assessments", ["id", "assessment_id", "user_username",
                                 "score", "status", "submitted_at"])

print("\n[student_assessment_answers] (JSON)")
migrate_json("student_assessment_answers", ["id", "submission_id", "question_id",
                                              "answer_text", "answer_link",
                                              "selected_option_index"],
              [])

print("\n[attendance]")
migrate("attendance", ["class_name", "subject_id", "student_name", "student_number",
                        "is_present", "status", "class_id", "date", "professor_name"])

print("\n[forum_posts]")
migrate("forum_posts", ["lesson_id", "user_name", "message"])

print("\n[weekly_schedule]")
migrate("weekly_schedule", ["class_id", "class_name", "day_of_week", "time_slot",
                             "subject_name", "professor_name"])

print("\n[user_history] (não sincronizado - local apenas)")
print("  [SKIP] user_history mantido no SQLite local")

con.close()
print("\nMigracao concluida!")
