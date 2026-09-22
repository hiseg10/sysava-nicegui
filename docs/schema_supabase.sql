-- ============================================================
-- SYSAVA - Schema Supabase (Fonte de Verdade)
-- Banco de dados enxuto e normalizado para AVA
-- ============================================================
-- Este schema substitui as 21 tabelas legadas por 17 tabelas
-- normalizadas. Remove: historico_aulas, master_config, schedules,
-- schools, user_profiles, user_reminders, settings, planejamento.
-- ============================================================

-- ---------------------------------------------------------
-- 1. users (substitui app_users)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    username    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    ra          TEXT DEFAULT '',
    role        TEXT NOT NULL DEFAULT 'student',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    password_hash TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_ra ON users(ra);

-- ---------------------------------------------------------
-- 2. classes (substitui classes + schools)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS classes (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    code        TEXT DEFAULT '',
    official_name TEXT DEFAULT '',
    school_id   INTEGER DEFAULT 1,
    tipo_turma  TEXT NOT NULL DEFAULT 'normal',
    ano_letivo  TEXT NOT NULL DEFAULT '2026',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_classes_year ON classes(ano_letivo);
CREATE INDEX IF NOT EXISTS idx_classes_tipo ON classes(tipo_turma);

-- ---------------------------------------------------------
-- 3. subjects (substitui subjects)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS subjects (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'regular',
    aliases         TEXT DEFAULT '',
    group_type      TEXT DEFAULT '',
    carga_horaria   INTEGER NOT NULL DEFAULT 0,
    duration_type   TEXT NOT NULL DEFAULT 'anual',
    lessons_per_week INTEGER DEFAULT 0,
    max_hours       INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'incompleta',
    folder_name     TEXT DEFAULT '',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_subjects_status ON subjects(status);
CREATE INDEX IF NOT EXISTS idx_subjects_type ON subjects(type);

-- ---------------------------------------------------------
-- 4. class_subjects (junction: turma ↔ disciplina)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS class_subjects (
    id          SERIAL PRIMARY KEY,
    class_id    INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, subject_id)
);

CREATE INDEX IF NOT EXISTS idx_class_subjects_class ON class_subjects(class_id);
CREATE INDEX IF NOT EXISTS idx_class_subjects_subject ON class_subjects(subject_id);

-- ---------------------------------------------------------
-- 5. student_enrollments (matrículas)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_enrollments (
    id              SERIAL PRIMARY KEY,
    class_id        INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    user_username   TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    enrolled_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, user_username)
);

CREATE INDEX IF NOT EXISTS idx_enrollments_class ON student_enrollments(class_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_user ON student_enrollments(user_username);

-- ---------------------------------------------------------
-- 6. lessons (aulas)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS lessons (
    id          SERIAL PRIMARY KEY,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT DEFAULT '',
    full_content TEXT DEFAULT '',
    objective   TEXT DEFAULT '',
    resources   TEXT DEFAULT '',
    video_url   TEXT DEFAULT '',
    week        TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'disponivel',
    uuid        TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lessons_subject ON lessons(subject_id);
CREATE INDEX IF NOT EXISTS idx_lessons_week ON lessons(week);

-- ---------------------------------------------------------
-- 7. quizzes (quizzes)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS quizzes (
    id          SERIAL PRIMARY KEY,
    lesson_id   INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quizzes_lesson ON quizzes(lesson_id);

-- ---------------------------------------------------------
-- 8. quiz_questions (questões dos quizzes)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS quiz_questions (
    id                  SERIAL PRIMARY KEY,
    quiz_id             INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_text       TEXT NOT NULL,
    question_type       TEXT NOT NULL DEFAULT 'objective',
    options             TEXT DEFAULT '[]',
    correct_option_index INTEGER DEFAULT 0,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz ON quiz_questions(quiz_id);

-- ---------------------------------------------------------
-- 9. assessments (avaliações/provas)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessments (
    id          SERIAL PRIMARY KEY,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'MN1',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assessments_subject ON assessments(subject_id);
CREATE INDEX IF NOT EXISTS idx_assessments_type ON assessments(type);

-- ---------------------------------------------------------
-- 10. assessment_questions (questões das avaliações)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS assessment_questions (
    id                      SERIAL PRIMARY KEY,
    assessment_id           INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_text           TEXT NOT NULL,
    question_type           TEXT NOT NULL DEFAULT 'objective',
    options                 TEXT DEFAULT '[]',
    correct_option_index    INTEGER DEFAULT 0,
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assessment_questions_assessment ON assessment_questions(assessment_id);

-- ---------------------------------------------------------
-- 11. student_assessments (submissões e notas)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_assessments (
    id              SERIAL PRIMARY KEY,
    assessment_id   INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    user_username   TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    score           REAL,
    status          TEXT NOT NULL DEFAULT 'pendente',
    submitted_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(assessment_id, user_username)
);

CREATE INDEX IF NOT EXISTS idx_student_assessments_assessment ON student_assessments(assessment_id);
CREATE INDEX IF NOT EXISTS idx_student_assessments_user ON student_assessments(user_username);

-- ---------------------------------------------------------
-- 12. student_assessment_answers (respostas das avaliações)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_assessment_answers (
    id                  SERIAL PRIMARY KEY,
    submission_id       INTEGER NOT NULL REFERENCES student_assessments(id) ON DELETE CASCADE,
    question_id         INTEGER NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    answer_text         TEXT DEFAULT '',
    answer_link         TEXT DEFAULT '',
    selected_option_index INTEGER,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_student_assessment_answers_submission ON student_assessment_answers(submission_id);

-- ---------------------------------------------------------
-- 13. attendance (frequência)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance (
    id              SERIAL PRIMARY KEY,
    class_name      TEXT NOT NULL,
    subject_id      INTEGER REFERENCES subjects(id),
    student_name    TEXT NOT NULL,
    student_number  INTEGER DEFAULT 0,
    is_present      BOOLEAN NOT NULL DEFAULT TRUE,
    status          TEXT NOT NULL DEFAULT 'Presente',
    class_id        INTEGER REFERENCES classes(id),
    date            TEXT NOT NULL,
    professor_name  TEXT DEFAULT '',
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attendance_class_date ON attendance(class_name, date);
CREATE INDEX IF NOT EXISTS idx_attendance_subject ON attendance(subject_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_name, date);

-- ---------------------------------------------------------
-- 14. forum_posts (fórum)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS forum_posts (
    id          SERIAL PRIMARY KEY,
    lesson_id   INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    user_name   TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    message     TEXT NOT NULL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forum_posts_lesson ON forum_posts(lesson_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_user ON forum_posts(user_name);

-- ---------------------------------------------------------
-- 15. weekly_schedule (grade semanal)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS weekly_schedule (
    id          SERIAL PRIMARY KEY,
    class_id    INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    class_name  TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    time_slot   TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    professor_name TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, day_of_week, time_slot, subject_name)
);

CREATE INDEX IF NOT EXISTS idx_weekly_schedule_class ON weekly_schedule(class_id);
CREATE INDEX IF NOT EXISTS idx_weekly_schedule_day ON weekly_schedule(day_of_week);

-- ---------------------------------------------------------
-- 16. qualitative_points (pontos qualitativos)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS qualitative_points (
    id          SERIAL PRIMARY KEY,
    user_username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    points      REAL NOT NULL DEFAULT 0,
    notes       TEXT DEFAULT '',
    date        TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_qualitative_user ON qualitative_points(user_username);
CREATE INDEX IF NOT EXISTS idx_qualitative_subject ON qualitative_points(subject_id);

-- ---------------------------------------------------------
-- 17. student_grades (notas calculadas)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_grades (
    id              SERIAL PRIMARY KEY,
    user_username   TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    class_name      TEXT NOT NULL,
    subject         TEXT NOT NULL,
    trimester       INTEGER NOT NULL DEFAULT 1,
    nm1             REAL DEFAULT 0,
    nm2             REAL DEFAULT 0,
    nm3             REAL DEFAULT 0,
    participation   REAL DEFAULT 0,
    qualitative     REAL DEFAULT 0,
    final_grade     REAL DEFAULT 0,
    status          TEXT DEFAULT 'finalizado',
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_username, class_name, subject, trimester)
);

CREATE INDEX IF NOT EXISTS idx_student_grades_user ON student_grades(user_username);
CREATE INDEX IF NOT EXISTS idx_student_grades_class ON student_grades(class_name);

-- ============================================================
-- VIEWS ÚTEIS (opcional)
-- ============================================================

-- Visão resumida de notas por aluno
CREATE OR REPLACE VIEW v_student_grades_summary AS
SELECT
    user_username,
    class_name,
    subject,
    nm1, nm2, nm3,
    COALESCE(nm1, 0) + COALESCE(nm2, 0) + COALESCE(nm3, 0) AS total_notas,
    participation,
    qualitative,
    final_grade,
    status
FROM student_grades;

-- Visão de frequência por turma/disciplina
CREATE OR REPLACE VIEW v_attendance_summary AS
SELECT
    class_name,
    subject_id,
    student_name,
    COUNT(*) AS total_chamadas,
    SUM(CASE WHEN is_present THEN 1 ELSE 0 END) AS presencas,
    SUM(CASE WHEN status = 'Falta' THEN 1 ELSE 0 END) AS faltas,
    ROUND(100.0 * SUM(CASE WHEN is_present OR status = 'Atraso' THEN 1 ELSE 0 END) / COUNT(*), 1) AS percentual_frequencia
FROM attendance
GROUP BY class_name, subject_id, student_name;

-- ============================================================
-- RLS (Row Level Security) - Supabase
-- ============================================================
-- Habilitar RLS em todas as tabelas para segurança
-- Executar no painel do Supabase ou via SQL:
--
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE class_subjects ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE student_enrollments ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE lessons ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE quizzes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE assessment_questions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE student_assessments ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE student_assessment_answers ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE forum_posts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE weekly_schedule ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE qualitative_points ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE student_grades ENABLE ROW LEVEL SECURITY;
--
-- Políticas sugeridas:
-- Alunos: SELECT em tudo (próprios dados)
-- Professores: SELECT/INSERT/UPDATE em dados da turma
-- Admin: Tudo (SELECT/INSERT/UPDATE/DELETE em tudo)
-- ============================================================
