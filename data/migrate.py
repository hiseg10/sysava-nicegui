"""
Script de migração: escola_ativa.db (legado) → Supabase (novo schema).
Gera data/migrate.sql com INSERTs prontos para o SQL Editor do Supabase.
Uso: python data/migrate.py
"""
import sqlite3, json
from pathlib import Path

LEGACY_DB = Path(__file__).resolve().parent.parent / "data" / "escola_ativa.db"
OUTPUT_SQL = Path(__file__).resolve().parent / "migrate.sql"

con = sqlite3.connect(str(LEGACY_DB))
con.row_factory = sqlite3.Row
cur = con.cursor()
lines = []

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
    lines.append(f"-- {len(rows)} registros em {table}")
    c = ", ".join(cols)
    for r in rows:
        v = ", ".join(escape(r.get(c2, "")) for c2 in cols)
        lines.append(f"INSERT INTO {table} ({c}) VALUES ({v});")
    lines.append("")

# users
lines.append("-- ========================================================")
lines.append("-- users (de app_users)")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM app_users").fetchall()]
insert("users", rows, ["username","name","ra","role","is_active","password_hash","created_at","updated_at"])

# classes
lines.append("-- ========================================================")
lines.append("-- classes")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM classes").fetchall()]
insert("classes", rows, ["id","name","code","official_name","school_id","tipo_turma","ano_letivo","is_active","created_at","updated_at"])

# subjects
lines.append("-- ========================================================")
lines.append("-- subjects")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM subjects").fetchall()]
insert("subjects", rows, ["id","name","type","aliases","group_type","carga_horaria","duration_type","lessons_per_week","max_hours","status","folder_name","is_active","created_at","updated_at"])

# class_subjects
lines.append("-- ========================================================")
lines.append("-- class_subjects")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM class_subjects").fetchall()]
insert("class_subjects", rows, ["id","class_id","subject_id","is_active","created_at"])

# student_enrollments
lines.append("-- ========================================================")
lines.append("-- student_enrollments")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM student_enrollments").fetchall()]
insert("student_enrollments", rows, ["class_id","user_username","enrolled_at"])

# lessons
lines.append("-- ========================================================")
lines.append("-- lessons")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM lessons").fetchall()]
insert("lessons", rows, ["id","subject_id","title","description","full_content","objective","resources","video_url","week","status","uuid","created_at","updated_at"])

# quizzes
lines.append("-- ========================================================")
lines.append("-- quizzes")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM quizzes").fetchall()]
insert("quizzes", rows, ["id","lesson_id","title","created_at"])

# quiz_questions
lines.append("-- ========================================================")
lines.append("-- quiz_questions")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM quiz_questions").fetchall()]
insert("quiz_questions", rows, ["id","quiz_id","question_text","question_type","options","correct_option_index","created_at"])

# assessments
lines.append("-- ========================================================")
lines.append("-- assessments")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM assessments").fetchall()]
insert("assessments", rows, ["id","subject_id","title","type","created_at","updated_at"])

# assessment_questions
lines.append("-- ========================================================")
lines.append("-- assessment_questions")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM assessment_questions").fetchall()]
insert("assessment_questions", rows, ["id","assessment_id","question_text","question_type","options","correct_option_index","created_at"])

# student_assessments
lines.append("-- ========================================================")
lines.append("-- student_assessments")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM student_assessments").fetchall()]
insert("student_assessments", rows, ["id","assessment_id","user_username","score","status","submitted_at","created_at"])

# student_assessment_answers
lines.append("-- ========================================================")
lines.append("-- student_assessment_answers")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM student_assessment_answers").fetchall()]
insert("student_assessment_answers", rows, ["id","submission_id","question_id","answer_text","answer_link","selected_option_index","created_at"])

# attendance
lines.append("-- ========================================================")
lines.append("-- attendance")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM attendance").fetchall()]
insert("attendance", rows, ["class_name","subject_id","student_name","student_number","is_present","status","class_id","date","professor_name","created_at"])

# forum_posts
lines.append("-- ========================================================")
lines.append("-- forum_posts")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM forum_posts").fetchall()]
insert("forum_posts", rows, ["lesson_id","user_name","message","created_at"])

# weekly_schedule
lines.append("-- ========================================================")
lines.append("-- weekly_schedule")
lines.append("-- ========================================================")
rows = [dict(r) for r in cur.execute("SELECT * FROM weekly_schedule").fetchall()]
insert("weekly_schedule", rows, ["class_id","class_name","day_of_week","time_slot","subject_name","professor_name","created_at"])

# qualitative_points placeholder
lines.append("-- ========================================================")
lines.append("-- qualitative_points (novo - popul via sync)")
lines.append("-- ========================================================")
lines.append("")

# student_grades placeholder
lines.append("-- ========================================================")
lines.append("-- student_grades (novo - gerado via scores.py)")
lines.append("-- ========================================================")
lines.append("")

# RLS
lines.append("-- ========================================================")
lines.append("-- RLS")
lines.append("-- ========================================================")
lines.append("""
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE lessons ENABLE ROW LEVEL SECURITY;
ALTER TABLE quizzes ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_assessment_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE forum_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE weekly_schedule ENABLE ROW LEVEL SECURITY;
ALTER TABLE qualitative_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_grades ENABLE ROW LEVEL SECURITY;
""")

sql = "\n".join(lines)
OUTPUT_SQL.write_text(sql, encoding="utf-8")
print(f"OK {OUTPUT_SQL} gerado ({len(lines)} linhas)")
print("\nOrdem no Supabase SQL Editor:")
print("  1. schema_supabase.sql (cria tabelas)")
print("  2. migrate.sql (popula dados)")
con.close()
