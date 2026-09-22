# Arquitetura de Persistência SysAVA NiceGUI

## Visão Geral

```
┌─────────────────────────────────────────────────────────┐
│                    SUPABASE (Fonte de Verdade)           │
│  17 tabelas normalizadas com RLS                         │
│  PostgreSQL + Row Level Security                         │
│  ~10MB de dados (dentro do limite gratuito)              │
└──────────────────────┬──────────────────────────────────┘
                       │ Sync periódico (incremental)
                       │ POSTGREST / REST API
                       ▼
┌─────────────────────────────────────────────────────────┐
│                SQLITE (Cache Local)                      │
│  escola_ativa.db — apenas leitura para a UI              │
│  17 tabelas espelhadas                                   │
│  Zero dependência de arquivos JSON/MD/TXT                │
└──────────────────────┬──────────────────────────────────┘
                       │ Query
                       ▼
┌─────────────────────────────────────────────────────────┐
│              NICEGUI (Aplicação Web)                     │
│  core/* → Repositório → SQLite                         │
│  ui/* → Interface                                      │
└─────────────────────────────────────────────────────────┘
```

## Princípios

| Princípio | Detalhe |
|-----------|---------|
| **Supabase = Fonte de Verdade** | Todos os dados vivem no Supabase |
| **SQLite = Cache Local** | Apenas leitura, para performance offline |
| **Zero Arquivos de Dados** | Sem `.json`, `.md`, `.txt` para dados |
| **Sync Incremental** | Só baixa o que mudou desde o último sync |
| **RLS Ativo** | Cada usuário só vê seus próprios dados |

## 18 Tabelas do Novo Schema

### Entidades Principais
| # | Tabela | Descrição | Registros (local) |
|---|--------|-----------|-------------------|
| 1 | `users` | Usuários (alunos, professores, admin) | 46 |
| 2 | `classes` | Turmas + escola | 2 |
| 3 | `subjects` | Disciplinas | 16 |
| 4 | `class_subjects` | Turma ↔ Disciplina | 28 |
| 5 | `student_enrollments` | Matrículas | 42 |
| 6 | `lessons` | Aulas | 357 |
| 7 | `quizzes` | Quizzes | 338 |
| 8 | `quiz_questions` | Questões dos quizzes | 973 |
| 9 | `assessments` | Avaliações (MN1, MN2, MN3) | 15 |
| 10 | `assessment_questions` | Questões das avaliações | 135 |
| 11 | `student_assessments` | Submissões e notas | 388 |
| 12 | `student_assessment_answers` | Respostas | 3,167 |
| 13 | `attendance` | Frequência | 488 |
| 14 | `forum_posts` | Posts do fórum | 3,626 |
| 15 | `weekly_schedule` | Grade semanal | 22 |
| 16 | `user_history` | Histórico de atividades | 13,547 |
| 17 | `qualitative_points` | Pontos qualitativos | (local) |
| 18 | `student_grades` | Notas calculadas | (local) |

### Tabelas Eliminadas (14 → 18)
| Tabela Removida | Motivo |
|-----------------|--------|
| `historico_aulas` | Derivado de `user_history` |
| `master_config` | Mover para `settings` do Supabase |
| `schedules` | Substituído por `weekly_schedule` |
| `schools` | Fundido em `classes.school_id` |
| `user_profiles` | Vazio (0 registros), não essencial |
| `user_reminders` | Vazio (0 registros), não essencial |
| `settings` | Configuração local, não AVA |
| `planejamento` | 0 registros, não essencial |
| `sqlite_sequence` | Sistema, não dados |

## Fluxo de Sincronização

```
┌──────────┐    Push/Pull    ┌──────────┐
│ Supabase │◄──────────────►│  core/   │
│          │                │ sync.py  │
└──────────┘                └────┬─────┘
                                 │
                    SQLite upsert não-destrutivo
                                 │
                                 ▼
                        ┌──────────────┐
                        │ escola_ativa │
                        │    .db       │
                        └──────┬───────┘
                               │
                          Query local
                               │
                               ▼
                        ┌──────────────┐
                        │  NiceGUI UI  │
                        └──────────────┘
```

### Sincronização Supabase → SQLite
1. `core/sync.py` faz pull via PostgREST
2. Para cada tabela: backup → upsert não-destrutivo
3. Mantém chaves locais, atualiza apenas se houve mudança
4. Atualiza `sync_state.json` (temporário, pode migrar para Supabase)

### Escrita Local → Supabase
1. Notas atualizadas em `student_assessments` → push para Supabase
2. Frequência salva em `attendance` → push para Supabase
3. Fórum posts → push para Supabase
4. Tudo em background thread (não bloqueia UI)

## Gerenciamento de Limites do Supabase

### Estimativa de Uso Mensal
| Origem | Estimativa |
|--------|------------|
| Database (PostgreSQL) | ~15MB (dentro do free 500MB) |
| Auth (usuários) | ~10KB |
| Storage (se usado) | ~0KB |
| Edge Functions (se usado) | ~0KB |
| **Total mensal estimado** | **~20MB** (muito abaixo de 5GB) |

### Controle de Crescimento
- `forum_posts` é a tabela maior (~3,669 registros, cresce com uso)
- `student_assessment_answers` (~3,583 registros)
- `quiz_questions` (~973 registros)
- **Recomendação**: Fazer cleanup de `user_history` (13,547 registros) — pode ser arquivado ou mantido apenas no SQLite
- **Tabela `lessons` tem `full_content` e `description` grandes** — considerar compressão ou armazenar em Supabase Storage se ultrapassar 1MB por aula

### Limite 5GB mensais - Estratégia
| Ação | Economia |
|------|----------|
| Remover `user_history` do Supabase (13K+ registros) | ~5MB/mês |
| Remover `historico_aulas` (1K registros) | ~1MB/mês |
| Não syncronizar `master_config` (5KB) | ~0.01MB/mês |
| Usar `text` em vez de `jsonb` para options | Menos overhead |
| **Economia total** | **~6MB/mês ≈ economia de 99%** |

## Variáveis de Ambiente (Render)

```env
# Obrigatórias
SUPABASE_URL=https://SEU-PROJETO.supabase.co
SUPABASE_KEY=sua-chave-service_role
STORAGE_SECRET=gerado-automaticamente-pelo-Render
PORT=8080

# Opcionais
SYSAVA_DB_PATH=/data/escola_ativa.db
SYSAVA_ENV_FILE=/caminho/para/.env
```

### Configuração no Render
1. **Web Service** → conectar GitHub repo
2. **Environment** → adicionar variáveis acima
3. **Volumes** → criar volume para `/data` (persistência SQLite)
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `python main.py`

## Estrutura de Arquivos (Pós-Limpeza)

```
sysava-nicegui/
├── core/
│   ├── auth.py              # Autenticação (SQLite local)
│   ├── assessments.py       # Avaliações e submissões
│   ├── attendance.py        # Frequência
│   ├── conteudo.py          # Conteúdo de aulas
│   ├── db.py                # Conexão SQLite
│   ├── friction.py          # Radar de atrito
│   ├── logs.py              # Logging
│   ├── parsing.py           # Parse de valores
│   ├── repositories.py      # Acesso read-only
│   ├── scores.py            # Cálculo de notas
│   ├── settings.py          # Configurações
│   ├── state.py             # Estado compartilhado
│   ├── sync.py              # Sync Supabase ↔ SQLite
│   ├── turmas.py            # CRUD de turmas/disciplinas
│   ├── user_profile.py      # Perfis (local apenas)
│   └── __init__.py
├── ui/                      # Interface NiceGUI
├── data/
│   ├── escola_ativa.db      # Único arquivo de dados
│   └── logs/                # Logs rotativos
├── docs/
│   ├── schema_supabase.sql  # Schema do Supabase
│   ├── ARQUITETURA_NOVA.md  # Este documento
│   └── ROADMAP_NICEGUI.md   # Roadmap existente
├── main.py                  # Ponto de entrada
├── render.yaml              # Config Render
├── requirements.txt         # Dependências
└── .env                     # Credenciais Supabase
```

## Comparativo: Antes vs Depois

| Aspecto | Antes (Legado) | Depois (Limpo) |
|---------|----------------|----------------|
| **Tabelas no Supabase** | 21 | 17 |
| **Tabelas eliminadas** | — | 4 |
| **Arquivos de dados** | 7+ (JSON, TXT, config) | 1 (SQLite) |
| **Esquema de nota** | JSON/MD/TXT | Tabela `student_grades` |
| **Escola** | Tabela `schools` separada | `classes.school_id` |
| **Histórico de aulas** | Tabela `historico_aulas` | Derivado de `user_history` |
| **Configurações** | `master_config`, `settings` | Local ou Supabase settings |
| **RLS** | Não configurado | Ativo em todas as tabelas |
| **Dependência de .env** | Formato quebrado | Formato correto `KEY=VALUE` |
| **Limite mensal Supabase** | ~24MB estimado | ~18MB estimado |

## Migração

### Passo 1: Criar novo schema no Supabase
```bash
# Executar o schema SQL no SQL Editor do Supabase
psql "postgresql://.../postgres" -f docs/schema_supabase.sql
```

### Passo 2: Migrar dados das tabelas legadas
```sql
-- Exemplo: migrar app_users → users
INSERT INTO users (username, name, ra, role, is_active, password_hash)
SELECT username, name, ra, role, is_active, password FROM app_users;
```

### Passo 3: Atualizar código
- Remover referências a tabelas eliminadas
- Atualizar `core/repositories.py` com novas tabelas
- Corrigir queries de `core/sync.py`

### Passo 4: Limpar arquivos
- Remover `data/storage_secret.txt` → usar `STORAGE_SECRET` env
- Remover `data/db_config.json` → usar `SYSAVA_DB_PATH` env
- Remover `data/sync_state.json` → opcional, pode migrar para DB
- Remover `data/push_sync_state.json`
- Limpar `.env` (formato correto)
- Limpar `backups/` antigos

### Passo 5: Deploy no Render
1. Push para GitHub
2. Render detecta `render.yaml`
3. Adicionar variáveis de ambiente
4. Criar volume persistente para `/data`
5. Reiniciar serviço
