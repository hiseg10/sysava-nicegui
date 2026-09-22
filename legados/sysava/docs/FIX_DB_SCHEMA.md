# 🔧 Correção do Esquema do Banco de Dados

O erro `Could not find the 'subject_id' column` indica que a tabela `lessons` no seu banco de dados está desatualizada (foi criada antes de adicionarmos o suporte a disciplinas).

Para corrigir, execute o seguinte comando SQL no **Supabase SQL Editor**:

```sql
-- 1. Adiciona a coluna subject_id na tabela lessons
ALTER TABLE lessons ADD COLUMN IF NOT EXISTS subject_id bigint references subjects(id);

-- 2. Remove a constraint antiga se existir (para evitar conflitos)
ALTER TABLE lessons DROP CONSTRAINT IF EXISTS lessons_subject_id_title_key;

-- 3. Adiciona a constraint de unicidade composta (necessária para o upsert funcionar)
ALTER TABLE lessons ADD CONSTRAINT lessons_subject_id_title_key UNIQUE (subject_id, title);

-- 4. Recarrega o cache do esquema para garantir que a API detecte a mudança
NOTIFY pgrst, 'reload schema';
```