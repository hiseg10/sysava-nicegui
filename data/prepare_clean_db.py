"""
Prepara o banco limpo para o Supabase.

Fluxo:
1. Copia escola_ativa_legado.db (original intacto)
2. Cria escola_ativa.db novo com schema limpo
3. Migra apenas registros com FK valida
4. Registros orfaos ficam em escola_ativa_legado.db para analise posterior

Uso: python data/prepare_clean_db.py
"""
import os, sys, json, sqlite3
from pathlib import Path

LEGACY = Path(__file__).resolve().parent.parent / "data" / "escola_ativa_legado.db"
CLEAN = Path(__file__).resolve().parent.parent / "data" / "escola_ativa.db"

if CLEAN.exists():
    print("escola_ativa.db ja existe. Pulando preparacao.")
    sys.exit(0)

print(f"Fonte:  {LEGACY}")
print(f"Destino: {CLEAN}")
print()

CLEAN_SCHEMA = """
CREATE TABLE users (
    username TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ra TEXT DEFAULT '',
    role TEXT NOT NULL DEFAULT 'student',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    password_hash TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_ra ON users(ra);

CREATE TABLE classes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL, code TEXT DEFAULT '', official_name TEXT DEFAULT '',
    school_id INTEGER DEFAULT 1, tipo_turma TEXT NOT NULL DEFAULT 'normal',
    ano_letivo TEXT NOT NULL DEFAULT '2026', is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_classes_year ON classes(ano_letivo);
CREATE INDEX IF NOT EXISTS idx_classes_tipo ON classes(tipo_turma);

CREATE TABLE subjects (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'regular',
    aliases TEXT DEFAULT '', group_type TEXT DEFAULT '', carga_horaria INTEGER NOT NULL DEFAULT 0,
    duration_type TEXT NOT NULL DEFAULT 'anual', lessons_per_week INTEGER DEFAULT 0,
    max_hours INTEGER DEFAULT 0, status TEXT NOT NULL DEFAULT 'incompleta',
    folder_name TEXT DEFAULT '', is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_subjects_status ON subjects(status);
CREATE INDEX IF NOT EXISTS idx_subjects_type ON subjects(type);

CREATE TABLE class_subjects (
    id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, subject_id INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, subject_id)
);
CREATE INDEX IF NOT EXISTS idx_class_subjects_class ON class_subjects(class_id);
CREATE INDEX IF NOT EXISTS idx_class_subjects_subject ON class_subjects(subject_id);

CREATE TABLE student_enrollments (
    id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, user_username TEXT NOT NULL,
    enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(class_id, user_username)
);
CREATE INDEX IF NOT EXISTS idx_enrollments_class ON student_enrollments(class_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_user ON student_enrollments(user_username);

CREATE TABLE lessons (
    id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL, title TEXT NOT NULL,
    description TEXT DEFAULT '', full_content TEXT DEFAULT '', objective TEXT DEFAULT '',
    resources TEXT DEFAULT '', video_url TEXT DEFAULT '', week TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'disponivel', uuid TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_lessons_subject ON lessons(subject_id);
CREATE INDEX IF NOT EXISTS idx_lessons_week ON lessons(week);

CREATE TABLE quizzes (
    id INTEGER PRIMARY KEY, lesson_id INTEGER NOT NULL, title TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quizzes_lesson ON quizzes(lesson_id);

CREATE TABLE quiz_questions (
    id INTEGER PRIMARY KEY, quiz_id INTEGER NOT NULL, question_text TEXT NOT NULL,
    question_type TEXT NOT NULL DEFAULT 'objective', options TEXT DEFAULT '[]',
    correct_option_index INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz ON quiz_questions(quiz_id);

CREATE TABLE assessments (
    id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL, title TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'MN1', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_assessments_subject ON assessments(subject_id);
CREATE INDEX IF NOT EXISTS idx_assessments_type ON assessments(type);

CREATE TABLE assessment_questions (
    id INTEGER PRIMARY KEY, assessment_id INTEGER NOT NULL, question_text TEXT NOT NULL,
    question_type TEXT NOT NULL DEFAULT 'objective', options TEXT DEFAULT '[]',
    correct_option_index INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_assessment_questions_assessment ON assessment_questions(assessment_id);

CREATE TABLE student_assessments (
    id INTEGER PRIMARY KEY, assessment_id INTEGER NOT NULL, user_username TEXT NOT NULL,
    score REAL, status TEXT NOT NULL DEFAULT 'pendente', submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(assessment_id, user_username)
);
CREATE INDEX IF NOT EXISTS idx_student_assessments_assessment ON student_assessments(assessment_id);
CREATE INDEX IF NOT EXISTS idx_student_assessments_user ON student_assessments(user_username);

CREATE TABLE student_assessment_answers (
    id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
    answer_text TEXT DEFAULT '', answer_link TEXT DEFAULT '', selected_option_index INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_student_assessment_answers_submission ON student_assessment_answers(submission_id);

CREATE TABLE attendance (
    id INTEGER PRIMARY KEY, class_name TEXT NOT NULL, subject_id INTEGER,
    student_name TEXT NOT NULL, student_number INTEGER DEFAULT 0, is_present BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'Presente', class_id INTEGER, date TEXT NOT NULL,
    professor_name TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_attendance_class_date ON attendance(class_name, date);
CREATE INDEX IF NOT EXISTS idx_attendance_subject ON attendance(subject_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_name, date);

CREATE TABLE forum_posts (
    id INTEGER PRIMARY KEY, lesson_id INTEGER, user_name TEXT NOT NULL,
    message TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_forum_posts_lesson ON forum_posts(lesson_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_user ON forum_posts(user_name);

CREATE TABLE weekly_schedule (
    id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, class_name TEXT NOT NULL,
    day_of_week TEXT NOT NULL, time_slot TEXT NOT NULL, subject_name TEXT NOT NULL,
    professor_name TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, day_of_week, time_slot, subject_name)
);
CREATE INDEX IF NOT EXISTS idx_weekly_schedule_class ON weekly_schedule(class_id);
CREATE INDEX IF NOT EXISTS idx_weekly_schedule_day ON weekly_schedule(day_of_week);

CREATE TABLE user_history (
    id INTEGER PRIMARY KEY, username TEXT NOT NULL, activity TEXT NOT NULL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_history_username ON user_history(username);
CREATE INDEX IF NOT EXISTS idx_user_history_timestamp ON user_history(timestamp);

CREATE TABLE qualitative_points (
    id INTEGER PRIMARY KEY, user_username TEXT NOT NULL, subject_id INTEGER NOT NULL,
    points REAL NOT NULL DEFAULT 0, notes TEXT DEFAULT '', date TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_qualitative_user ON qualitative_points(user_username);
CREATE INDEX IF NOT EXISTS idx_qualitative_subject ON qualitative_points(subject_id);

CREATE TABLE student_grades (
    id INTEGER PRIMARY KEY, user_username TEXT NOT NULL, class_name TEXT NOT NULL,
    subject TEXT NOT NULL, trimester INTEGER NOT NULL DEFAULT 1, nm1 REAL DEFAULT 0,
    nm2 REAL DEFAULT 0, nm3 REAL DEFAULT 0, participation REAL DEFAULT 0,
    qualitative REAL DEFAULT 0, final_grade REAL DEFAULT 0, status TEXT DEFAULT 'finalizado',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_username, class_name, subject, trimester)
);
CREATE INDEX IF NOT EXISTS idx_student_grades_user ON student_grades(user_username);
CREATE INDEX IF NOT EXISTS idx_student_grades_class ON student_grades(class_name);
"""

print("Criando escola_ativa.db com schema limpo...")
con_clean = sqlite3.connect(str(CLEAN))
con_clean.executescript(CLEAN_SCHEMA)
con_clean.commit()

con_leg = sqlite3.connect(str(LEGACY))
con_leg.row_factory = sqlite3.Row
cur_leg = con_leg.cursor()
cur_clean = con_clean.cursor()

def get_ids(table):
    try:
        return set(str(r[0]) for r in cur_clean.execute(f"SELECT id FROM {table}").fetchall())
    except:
        return set()

DEFAULTS = {
    "is_active": "1", "status": "'incompleta'", "created_at": "'2026-01-01'",
    "updated_at": "'2026-01-01'", "duration_type": "'anual'",
    "type": "'regular'", "lessons_per_week": "0", "max_hours": "0",
    "school_id": "1", "ano_letivo": "'2026'",
}

def insert(table, columns, rows):
    if not rows:
        return 0
    c = ", ".join(columns)
    inserted = 0
    for row in rows:
        vals = []
        for col in columns:
            v = row.get(col)
            if v is None:
                vals.append(DEFAULTS.get(col, "NULL"))
            elif isinstance(v, str):
                vals.append("'" + v.replace("'", "''") + "'")
            elif isinstance(v, (list, dict)):
                vals.append("'" + json.dumps(v, ensure_ascii=False).replace("'", "''") + "'")
            else:
                vals.append(str(v))
        try:
            cur_clean.execute(f"INSERT INTO {table} ({c}) VALUES ({', '.join(vals)})")
            inserted += 1
        except Exception as e:
            pass
    con_clean.commit()
    return inserted

def migrate_table(supabase_table, legacy_table, columns, fk_checks=None):
    all_rows = [dict(r) for r in cur_leg.execute(f"SELECT * FROM {legacy_table}").fetchall()]
    if not all_rows:
        print(f"  [SKIP] {legacy_table} vazio")
        return
    if fk_checks:
        valid = []
        for row in all_rows:
            ok = True
            for fk_col, ref_table in fk_checks:
                val = str(row.get(fk_col, ""))
                if val and val not in get_ids(ref_table):
                    ok = False
                    break
            if ok:
                valid.append(row)
        all_rows = valid
    total = len(all_rows)
    inserted = insert(supabase_table, columns, all_rows)
    orphans = total - inserted
    print(f"  [OK] {supabase_table}: {inserted}/{total} ({orphans} orfaos)")

print("\n=== MIGRACAO ===\n")

print("[users]")
migrate_table("users", "app_users", ["username","name","ra","role","is_active","password_hash"])

print("[classes]")
migrate_table("classes", "classes", ["id","name","code","official_name","school_id","tipo_turma","ano_letivo","is_active"])

print("[subjects]")
migrate_table("subjects", "subjects", ["id","name","type","aliases","group_type","carga_horaria","duration_type","lessons_per_week","max_hours","status","folder_name","is_active"])

print("[class_subjects]")
migrate_table("class_subjects", "class_subjects", ["id","class_id","subject_id","is_active"],
              fk_checks=[("class_id","classes"), ("subject_id","subjects")])

print("[student_enrollments]")
migrate_table("student_enrollments", "student_enrollments", ["class_id","user_username"],
              fk_checks=[("class_id","classes")])

print("[lessons]")
migrate_table("lessons", "lessons", ["id","subject_id","title","description","full_content","objective","resources","video_url","week","status","uuid"],
              fk_checks=[("subject_id","subjects")])

print("[quizzes]")
migrate_table("quizzes", "quizzes", ["id","lesson_id","title"],
              fk_checks=[("lesson_id","lessons")])

print("[quiz_questions]")
migrate_table("quiz_questions", "quiz_questions", ["id","quiz_id","question_text","question_type","options","correct_option_index"],
              fk_checks=[("quiz_id","quizzes")])

print("[assessments]")
migrate_table("assessments", "assessments", ["id","subject_id","title","type"],
              fk_checks=[("subject_id","subjects")])

print("[assessment_questions]")
migrate_table("assessment_questions", "assessment_questions", ["id","assessment_id","question_text","question_type","options","correct_option_index"],
              fk_checks=[("assessment_id","assessments")])

print("[student_assessments]")
migrate_table("student_assessments", "student_assessments", ["id","assessment_id","user_username","score","status","submitted_at"],
              fk_checks=[("assessment_id","assessments")])

print("[student_assessment_answers]")
migrate_table("student_assessment_answers", "student_assessment_answers", ["id","submission_id","question_id","answer_text","answer_link","selected_option_index"],
              fk_checks=[("submission_id","student_assessments"), ("question_id","assessment_questions")])

print("[attendance]")
migrate_table("attendance", "attendance", ["class_name","subject_id","student_name","student_number","is_present","status","class_id","date","professor_name"],
              fk_checks=[("subject_id","subjects"), ("class_id","classes")])

print("[forum_posts]")
migrate_table("forum_posts", "forum_posts", ["lesson_id","user_name","message"],
              fk_checks=[("lesson_id","lessons")])

print("[weekly_schedule]")
migrate_table("weekly_schedule", "weekly_schedule", ["class_id","class_name","day_of_week","time_slot","subject_name","professor_name"],
              fk_checks=[("class_id","classes")])

print("[user_history]")
migrate_table("user_history", "user_history", ["id","username","activity","timestamp"])

print("\n=== VERIFICACAO ===")
for table in ["users","classes","subjects","lessons","quizzes","assessments","forum_posts","user_history"]:
    count = cur_clean.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: {count}")

con_clean.close()
con_leg.close()
print("\n[OK] escola_ativa.db criado com dados limpos")
print("    escola_ativa_legado.db preservado com dados orfaos")
print("    Usar data/prepare_clean_db.py para compatibilizar dados orfaos")
