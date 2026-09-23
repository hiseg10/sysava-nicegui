-- =============================================================================
-- PATCH: Supabase PRINCIPAL do SysAVA NiceGUI
-- O NiceGUI passou a usar `app_users` (herdeiro). O principal ainda tem `users`.
-- Idempotente — rodar no SQL Editor do projeto principal.
-- =============================================================================

-- 1. Renomear users -> app_users (se ainda existir como users)
DO $$
BEGIN
    IF to_regclass('public.users') IS NOT NULL
       AND to_regclass('public.app_users') IS NULL THEN
        ALTER TABLE public.users RENAME TO app_users;
    END IF;
END $$;

-- 2. Colunas de transição (Streamlit / login dual)
ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS password TEXT DEFAULT '';
ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS password_hash TEXT DEFAULT '';

-- 3. Tabelas de push que o principal ainda não tinha
CREATE TABLE IF NOT EXISTS public.user_profiles (
    username      TEXT PRIMARY KEY,
    bio           TEXT DEFAULT '',
    avatar_url    TEXT DEFAULT '',
    notificacoes  JSONB,
    idioma        TEXT DEFAULT 'pt-BR',
    prefs         JSONB,
    atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

-- (student_grades / qualitative_points / attendance.status|class_id
--  já existem no principal — verificado via OpenAPI.)

-- 4. Grants / RLS no mesmo padrão do legado
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename IN ('app_users', 'user_profiles')
    LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', r.tablename);
    END LOOP;
END $$;

GRANT ALL ON public.app_users TO anon, authenticated, service_role;
GRANT ALL ON public.user_profiles TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;

NOTIFY pgrst, 'reload schema';
