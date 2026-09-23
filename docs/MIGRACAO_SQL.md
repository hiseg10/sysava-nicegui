-- ============================================================
-- MIGRAÇÃO: Schema Legado → Schema Limpo
-- Executar no SQL Editor do Supabase
-- ============================================================

-- ---------------------------------------------------------
-- FASE 1: Criar novas tabelas
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_users (
    username    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    ra          TEXT DEFAULT '',
    role        TEXT NOT NULL DEFAULT 'student',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    password_hash TEXT DEFAULT '',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classes (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    code            TEXT DEFAULT '',
    official_name   TEXT DEFAULT '',
    school_id       INTEGER DEFAULT 1,
    tipo_turma      TEXT NOT NULL DEFAULT 'normal',
    ano_letivo      TEXT NOT NULL DEFAULT '2026',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS class_subjects (
    id          SERIAL PRIMARY KEY,
    class_id    INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, subject_id)
);

CREATE TABLE IF NOT EXISTS student_enrollments (
    id              SERIAL PRIMARY KEY,
    class_id        INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    user_username   TEXT NOT NULL REFERENCES app_users(username) ON DELETE CASCADE,
    enrolled_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, user_username)
);

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

CREATE TABLE IF NOT EXISTS quizzes (
    id          SERIAL PRIMARY KEY,
    lesson_id   INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id                  SERIAL PRIMARY KEY,
    quiz_id             INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_text       TEXT NOT NULL,
    question_type       TEXT NOT NULL DEFAULT 'objective',
    options             TEXT DEFAULT '[]',
    correct_option_index INTEGER DEFAULT 0,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessments (
    id          SERIAL PRIMARY KEY,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'MN1',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessment_questions (
    id                      SERIAL PRIMARY KEY,
    assessment_id           INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_text           TEXT NOT NULL,
    question_type           TEXT NOT NULL DEFAULT 'objective',
    options                 TEXT DEFAULT '[]',
    correct_option_index    INTEGER DEFAULT 0,
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_assessments (
    id              SERIAL PRIMARY KEY,
    assessment_id   INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    user_username   TEXT NOT NULL REFERENCES app_users(username) ON DELETE CASCADE,
    score           REAL,
    status          TEXT NOT NULL DEFAULT 'pendente',
    submitted_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(assessment_id, user_username)
);

CREATE TABLE IF NOT EXISTS student_assessment_answers (
    id                  SERIAL PRIMARY KEY,
    submission_id       INTEGER NOT NULL REFERENCES student_assessments(id) ON DELETE CASCADE,
    question_id         INTEGER NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    answer_text         TEXT DEFAULT '',
    answer_link         TEXT DEFAULT '',
    selected_option_index INTEGER,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS forum_posts (
    id          SERIAL PRIMARY KEY,
    lesson_id   INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    user_name   TEXT NOT NULL,
    message     TEXT NOT NULL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS qualitative_points (
    id          SERIAL PRIMARY KEY,
    user_username TEXT NOT NULL REFERENCES app_users(username) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    points      REAL NOT NULL DEFAULT 0,
    notes       TEXT DEFAULT '',
    date        TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_grades (
    id              SERIAL PRIMARY KEY,
    user_username   TEXT NOT NULL REFERENCES app_users(username) ON DELETE CASCADE,
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

-- ============================================================
-- FASE 2: Migrar dados das tabelas legadas
-- ============================================================

-- Migrar users
INSERT INTO app_users (username, name, ra, role, is_active, password_hash)
SELECT username, name, ra, role, is_active, password
FROM app_users
ON CONFLICT(username) DO NOTHING;

-- Migrar classes (com school_id)
INSERT INTO classes (id, name, code, official_name, school_id, tipo_turma, ano_letivo, is_active)
SELECT id, name, code, official_name, school_id, COALESCE(tipo_turma, 'normal'), COALESCE(ano_letivo, '2026'), TRUE
FROM classes_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar subjects
INSERT INTO subjects (id, name, type, aliases, group_type, carga_horaria, duration_type, lessons_per_week, max_hours, status, folder_name, is_active)
SELECT id, name, COALESCE(type, 'regular'), COALESCE(aliases, ''), COALESCE(group_type, ''), carga_horaria, COALESCE(duration_type, 'anual'), lessons_per_week, max_hours, COALESCE(status, 'incompleta'), folder_name, TRUE
FROM subjects_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar class_subjects
INSERT INTO class_subjects (class_id, subject_id, is_active)
SELECT class_id, subject_id, TRUE
FROM class_subjects_legacy
ON CONFLICT(class_id, subject_id) DO NOTHING;

-- Migrar student_enrollments
INSERT INTO student_enrollments (class_id, user_username, enrolled_at)
SELECT class_id, user_username, CURRENT_TIMESTAMP
FROM student_enrollments_legacy
ON CONFLICT(class_id, user_username) DO NOTHING;

-- Migrar lessons
INSERT INTO lessons (id, subject_id, title, description, full_content, objective, resources, video_url, week, status, uuid)
SELECT id, subject_id, title, description, full_content, objective, resources, video_url, week, status, uuid
FROM lessons_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar quizzes
INSERT INTO quizzes (id, lesson_id, title)
SELECT id, lesson_id, title
FROM quizzes_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar quiz_questions
INSERT INTO quiz_questions (id, quiz_id, question_text, question_type, options, correct_option_index)
SELECT id, quiz_id, question_text, question_type, options, correct_option_index
FROM quiz_questions_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar assessments
INSERT INTO assessments (id, subject_id, title, type)
SELECT id, subject_id, title, type
FROM assessments_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar assessment_questions
INSERT INTO assessment_questions (id, assessment_id, question_text, question_type, options, correct_option_index)
SELECT id, assessment_id, question_text, question_type, options, correct_option_index
FROM assessment_questions_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar student_assessments
INSERT INTO student_assessments (id, assessment_id, user_username, score, status, submitted_at)
SELECT id, assessment_id, user_username, score, status, submitted_at
FROM student_assessments_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar student_assessment_answers
INSERT INTO student_assessment_answers (id, submission_id, question_id, answer_text, answer_link, selected_option_index)
SELECT id, submission_id, question_id, answer_text, answer_link, selected_option_index
FROM student_assessment_answers_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar attendance (com status)
INSERT INTO attendance (class_name, subject_id, student_name, student_number, is_present, status, date, professor_name)
SELECT class_name, subject_id, student_name, student_number, is_present, status, date, professor_name
FROM attendance_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar forum_posts
INSERT INTO forum_posts (id, lesson_id, user_name, message, created_at)
SELECT id, lesson_id, user_name, message, created_at
FROM forum_posts_legacy
ON CONFLICT(id) DO NOTHING;

-- Migrar weekly_schedule
INSERT INTO weekly_schedule (id, class_id, class_name, day_of_week, time_slot, subject_name, professor_name)
SELECT id, class_id, class_name, day_of_week, time_slot, subject_name, professor_name
FROM weekly_schedule_legacy
ON CONFLICT(id) DO NOTHING;

-- Criar qualitative_points e student_grades a partir de dados locais (se existirem)
-- Nota: Estas tabelas não existem no Supabase legado, precisam ser criadas pela primeira vez
-- e populadas com dados calculados

-- ============================================================
-- FASE 3: Ativar RLS
-- ============================================================

ALTER TABLE app_users ENABLE ROW LEVEL SECURITY;
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

-- ============================================================
-- FASE 4: Criar políticas RLS
-- ============================================================

-- Todos os usuários podem ler seus próprios dados
CREATE POLICY "Usuarios leem proprios dados" ON users
    FOR SELECT USING (auth.uid() = username);

-- Alunos podem ver turmas que estão matriculados
CREATE POLICY "Alunos veem turmas matriculadas" ON classes
    FOR SELECT USING (
        id IN (SELECT class_id FROM student_enrollments WHERE user_username = auth.uid())
    );

-- Todos podem ler disciplinas ativas
CREATE POLICY "Todos leem disciplinas" ON subjects
    FOR SELECT USING (is_active = TRUE);

-- Professores e admin podem gerenciar tudo (simplificado)
CREATE POLICY "Admin gerencia tudo" ON classes
    FOR ALL USING (
        auth.jwt() ->> 'role' = 'admin'
    );

-- ============================================================
-- FASE 5: Remover tabelas legadas (opcional - fazer após confirmar)
-- ============================================================
-- Executar APENAS após confirmar que tudo funciona:
--
-- DROP TABLE IF EXISTS app_users CASCADE;
-- DROP TABLE IF EXISTS classes_legacy CASCADE;
-- DROP TABLE IF EXISTS subjects_legacy CASCADE;
-- DROP TABLE IF EXISTS class_subjects_legacy CASCADE;
-- DROP TABLE IF EXISTS student_enrollments_legacy CASCADE;
-- DROP TABLE IF EXISTS lessons_legacy CASCADE;
-- DROP TABLE IF EXISTS quizzes_legacy CASCADE;
-- DROP TABLE IF EXISTS quiz_questions_legacy CASCADE;
-- DROP TABLE IF EXISTS assessments_legacy CASCADE;
-- DROP TABLE IF EXISTS assessment_questions_legacy CASCADE;
-- DROP TABLE IF EXISTS student_assessments_legacy CASCADE;
-- DROP TABLE IF EXISTS student_assessment_answers_legacy CASCADE;
-- DROP TABLE IF EXISTS attendance_legacy CASCADE;
-- DROP TABLE IF EXISTS forum_posts_legacy CASCADE;
-- DROP TABLE IF EXISTS weekly_schedule_legacy CASCADE;
-- DROP TABLE IF EXISTS historico_aulas CASCADE;
-- DROP TABLE IF EXISTS master_config CASCADE;
-- DROP TABLE IF EXISTS schedules CASCADE;
-- DROP TABLE IF EXISTS schools CASCADE;
-- DROP TABLE IF EXISTS user_profiles CASCADE;
-- DROP TABLE IF EXISTS user_reminders CASCADE;
-- DROP TABLE IF EXISTS settings CASCADE;
-- DROP TABLE IF EXISTS planejamento CASCADE;
-- DROP TABLE IF EXISTS sqlite_sequence CASCADE;
-- ============================================================
