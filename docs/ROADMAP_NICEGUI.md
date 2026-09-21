# Roadmap — sysava-nicegui

Objetivo: substituir o **SysAVA Streamlit** (lento e com tráfego acima de
5 GB/mês) por um app **NiceGUI** rápido, usando o `escola_ativa.db` local como
**cache** dos dados do Supabase, e publicá-lo para os alunos.

Base: `D:\Local\Dev\sysava-nicegui` · venv: `.venv\Scripts\python.exe` · porta 8080

---

## 1. Estado atual (o que já existe)

### Infraestrutura
- [x] Ambiente: `.venv` (Python 3.13) + `requirements.txt` (`nicegui==3.17.0`) + `run.bat`
- [x] `main.py` com rotas `/`, `/dashboard`, `/manage-turmas`, `/frequencia`
- [x] `core/db.py` — conexão SQLite + `data/db_config.json` + `SYSAVA_DB_PATH`
- [x] `core/repositories.py` — acesso a dados (disciplinas, aulas, quizzes, fórum, turmas, alunos, horários, histórico, planejamento, frequência, notas, settings)
- [x] `ui/layout.py` — navegação compartilhada (`inicio_pagina`)

### Páginas
- [x] Página **Banco de Dados** (`ui/database.py`) — testar/conectar/trocar o `.db`, listar tabelas, colunas e pré-visualizar registros
- [x] Página **Radar de Atrito** (`ui/friction.py` + `core/friction.py`) — porte do `friction_radar.py`, com filtros e export CSV
- [x] Página **Sincronização** (`ui/sync.py` + `core/sync.py`) — Supabase → SQLite (ver Fase 1)
- [x] **Login** (`ui/login.py` + `core/auth.py` + `ui/security.py`) — sessão, papéis e layout responsivo (ver Fase 2)
- [x] Página **Frequência** (`ui/frequencia.py` + `core/attendance.py`) — chamada diária, resumo e CSV (ver Fase 3)
- [x] Página **Aulas** (`ui/aulas.py` + `core/conteudo.py`) — turma/disciplina, agrupamento, detalhe, quiz e export Markdown
- [x] Página **Pontos** (`ui/pontos.py` + `core/scores.py`) — aulas + quizzes + fórum por disciplina
- [x] Página **Provas** (`ui/provas.py` + `core/assessments.py`) — questões/gabarito, submissões, notas e export
- [x] Página **Configuração** (`ui/config.py` + `core/settings.py`) — `settings` editável + `master_config` (leitura)

### Novas Funcionalidades (implementadas)
- [x] **Menu Flutuante de Acesso Rápido** (`ui/layout.py`) — FAB para consultar RA, notas e pontos por turma
- [x] **Dark Mode** — Toggle de tema claro/escuro com persistência
- [x] **Sistema de Notas NM1/NM2/NM3** (`core/scores.py`) — Fórmula: Avaliação + Participação + Qualitativos
- [x] **Participação por Disciplina** — (aulas + quizzes + forum) / 16, teto 3 pontos
- [x] **Mapeamento de Tipos de Avaliação** — MN1/MN2/MN3, T1_N1/T2_N1, Outros
- [x] **Diferenciação Modular vs Anual** — Disciplinas mensais replicam T1 para T2/T3
- [x] **Status de Disciplinas** — incompleta/completa/inativa com toggle
- [x] **Bloqueio de Avaliações** — AV1 requer 8+ aulas, Recuperação requer média < 6
- [x] **Gerenciar Turmas** (`ui/manage_turmas.py`) — CRUD completo com disciplinas e vínculos
- [x] **Perfil do Usuário** (`ui/perfil.py`) — Informações pessoais, notas, configurações
- [x] **Filtro de Disciplinas Inativas** — Exclui completas/inativas dos fluxos ativos

Banco local: `D:\Florestan\Apps\SysAva\data\escola_ativa.db` (7,2 MB, 31 tabelas com dados)

---

## 2. Plugins a portar (estudo já feito)

| Plugin legado | O que faz | Porte | Valor |
|---|---|---|---|
| `student_scores.py` (70 KB) | Planilha de notas, importação de avaliações, composição (engaj. + qualit. + bônus), replicação de trimestre, painel do aluno, export PNG/HTML | Muito alta | Muito alto |
| `gerar_planos_txt.py` (66 KB) | Planos de aula `.txt`: diagnóstico → planejamento → individual/lote, smart-fill, cadência semanal, presença | Alta | Muito alto |
| `grade_semanal.py` | Grade de horários, edição, export PNG/CSV | Média | Médio-alto |
| `student_attendance.py` | Chamada diária, merge de 3 fontes, upsert, relatórios, CSV | Média | Alto |
| `audit_backup.py` | Sync Supabase + auditoria + backup `.db` | Baixa-média | Alto |
| `agenda.py` | Linha do tempo de aulas + status + Kanban | Média | Alto |
| `daily_activities.py` | Atividade do dia → fórum (EduBot) + pontos qualitativos (teto 6,0) | Média | Alto |
| `friction_radar.py` | Aulas sem quiz, fórum fraco, conteúdo curto | **Feito** | Médio |

Tabelas do `escola_ativa.db` que já cobrem esses plugins: `lessons`
(`full_content`, `objective`, `resources`), `planejamento`, `historico_aulas`,
`weekly_schedule`, `turma_disciplina_config` + `discipline_aliases`,
`attendance`, `student_grades`, `qualitative_points`, `assessments`,
`assessment_questions`, `settings`, `master_config`.

> Nota: `forum_posts` está vazia neste banco, então o critério "fórum fraco" do
> Radar acusa todas as 304 aulas. Isso é esperado até a sincronização popular a
> tabela.

---

## 3. Fase 1 — Sincronização Supabase → SQLite (cache)

O Supabase é a base de acesso dos alunos (notas, provas, aulas, frequência),
atualizada diariamente. O `escola_ativa.db` deve virar cache local.

- [x] `core/sync.py`: portar a lógica de `sysava\data\repo\plugins\audit_backup.py` sem depender de Streamlit
- [x] Cliente Supabase via `.env` (sem expor chave em log/tela) — `SUPABASE_URL`/`SUPABASE_KEY` ou `SYSAVA_ENV_FILE`; só host e chave mascarada aparecem
- [x] Sync **incremental** por `updated_at`/`created_at` + opção de **full**
- [x] **Backup automático** antes de sincronizar (`backups/backup_SysAva_YYYY-MM-DD_HHMMSS.db`)
- [x] Auditoria de contagens: diff local × nuvem, tabela por tabela
- [x] Página **Sincronização** (`ui/sync.py`): botão, progresso em tempo real, último sync, contagens, log e "dry-run"
- [x] Tratamento de falha/retomada (idempotente, transação por tabela, watermark só avança em sucesso)
- [x] Agendamento (diário) ou botão manual — switch + horário em `data/sync_config.json`

**Decisão:** para o **cache (pull Supabase → SQLite)** o caminho é o **Supabase
direto** (PostgREST), sem depender do FastAPI local. O push local → nuvem
(automação/planejamento) continua fora do escopo deste app por enquanto.

**Upsert não-destrutivo:** grava por chave (PK local → índice UNIQUE → heurística),
adiciona colunas novas vindas da nuvem, cria tabelas ausentes, compara valores
(registros inalterados não são reescritos) e ignora conflitos de constraint
(`INSERT OR IGNORE`), reportando quantos foram ignorados.

---

## 4. Fase 2 — Autenticação e base do app

Hoje o NiceGUI **não tem login**. Necessário para migrar alunos com segurança.

- [x] Login por **RA/usuário + senha** (senhas já são `bcrypt` em `app_users`) — `core/auth.py` (aceita `username` ou `ra`, bloqueia `status` inativo)
- [x] Sessão via `ui.run(storage_secret=...)` + `app.storage.user` — segredo em `data/storage_secret.txt` (ou `SYSAVA_STORAGE_SECRET`)
- [x] Papéis: `admin`, `teacher`, `student` (`app_users.role`)
- [x] Middleware/guard por rota (negar `/radar`, `/database`, etc. para aluno) — `ui/security.py` (`MiddlewareAutenticacao`)
- [x] Página inicial por papel (home do aluno × painel do professor) — `/` redireciona; `/aluno` × `/dashboard`
- [x] Log de atividades (`user_history`) — login, logout e erros
- [x] Layout responsivo/mobile (alunos vão acessar pelo celular) — cabeçalho + menu lateral (`ui/layout.py`)
  - Desktop: links agrupados em menus suspensos (**Ensino** / **Gestão** / **Sistema**) para não estourar a largura
  - Mobile: menu lateral com seções; classes responsivas do Quasar (`gt-sm` / `lt-md`); item atual destacado; marca leva ao início do papel
- [x] Tratamento global de erros + logging em arquivo — `core/logs.py` (`data/logs/sysava.log`), `app.on_page_exception`/`on_exception`

---

## 5. Fase 3 — Plugins (ordem sugerida)

- [x] **Aulas** (`views/aulas.py`) — lista por turma/disciplina, agrupamento, detalhe, quiz e export
  - `core/conteudo.py` + `ui/aulas.py`; aluno vê a própria turma e o acesso é logado em `user_history`
- [x] **Pontos do aluno** (`get_student_score`) — `core/scores.py` + `ui/pontos.py`
  - pontos = (aulas + quizzes + fórum) / 32; staff escolhe turma/aluno, aluno vê o próprio
- [x] **Provas** (`views/avaliacoes.py`) — `core/assessments.py` + `ui/provas.py`
  - questões com gabarito, submissões, lançamento de nota e export (MD) da prova
- [x] **Configuração** — `core/settings.py` + `ui/config.py` (settings editável, master_config)
- [x] **Frequência** (`student_attendance`) — tabela editável, resumo, CSV
  - `core/attendance.py` + `ui/frequencia.py`; chave `(student_name, class_name, subject_id, date)`
  - Status Presente/Falta/Atraso em coluna local `status` (a nuvem só tem `is_present`)
  - Resumo diário, relatório acumulado (% freq = (presenças+atrasos)/total) e 2 CSVs
  - **Caveat:** o app grava no SQLite local; um sync posterior pode sobrescrever `is_present`
    de linhas já existentes na nuvem até existir o push local → Supabase (Fase 4)
- [ ] **Grade Semanal** (`grade_semanal`) — tabela + export (sem matplotlib: gerar HTML/CSV)
- [ ] **Agenda** (`agenda.py`) + Kanban de tarefas
- [ ] **Atividades diárias** (`daily_activities`) — lançamento de pontos
- [ ] **Fórum** — posts por aula (base do engajamento)
- [ ] **Notas** (`student_scores`) — planilha, composição, replicação, export
- [ ] **Planos de aula** (`gerar_planos_txt`) — diagnóstico/planejamento/lote
- [ ] **Auditoria/Manutenção** (ex-`audit_backup`) como página

---

## 6. Fase 4 — Publicar online e migrar os alunos

### 6.1 Opções de hospedagem

1. **VPS + NiceGUI (recomendado)** — `ui.run(host='0.0.0.0', port=8080, reload=False, storage_secret=...)`
   atrás de **Caddy** (HTTPS automático) ou Nginx. Docker + systemd para subir sozinho.
2. **Cloudflare Tunnel** — expõe o app local sem abrir portas; ótimo para começar e testar com poucos alunos.
3. **Desktop (NiceGUI `native=True`)** — cada professor roda local, sem tráfego de hospedagem; sincroniza com o Supabase. Ótimo para o professor, não para o aluno.
4. **Streamlit Community Cloud** — é o cenário atual; tem limites e é lento, não resolveria.

### 6.2 Por que o Streamlit estoura 5 GB/mês

Pontos prováveis (o porte deve evitar todos):

- **Re-run completo do script** a cada interação → o Streamlit reenvia o diff da página inteira por WebSocket.
- **PNG embutido em base64** (`student_scores`, `grade_semanal` geram imagens com matplotlib a cada render) → payload enorme e repetido.
- **Tabelas grandes** (`st.data_editor` de turmas inteiras) reenviadas a cada interação.
- Chamadas ao Supabase a cada re-run, sem cache local.

### 6.3 Estratégias de redução de tráfego (obrigatórias no NiceGUI)

- [ ] Ler do **SQLite local**; Supabase só no sync diário (corta egress de banco)
- [ ] Exportar PNG/PDF **sob demanda** (`ui.download`), nunca renderizar imagem inline repetidamente
- [ ] **Paginação** em todas as tabelas (ex.: 15–25 linhas por página)
- [ ] Compressão **gzip/brotli** no proxy reverso + cache de assets estáticos
- [ ] Evitar reenvio de payloads grandes no WebSocket: consultar sob demanda, não pré-carregar tudo
- [ ] Preferir tabelas HTML/JSON enxutas a imagens
- [ ] Medir: log de bytes por rota no proxy (Caddy/Nginx) e alerta de consumo

### 6.4 Deploy

- [ ] `Dockerfile` + `docker-compose` (app + Caddy)
- [ ] Variáveis de ambiente: `SYSAVA_DB_PATH`, credenciais Supabase, `storage_secret`
- [ ] Domínio + HTTPS + backup diário do `escola_ativa.db`
- [ ] Healthcheck (`GET /` → 200) e reinício automático
- [ ] Migração: avisar alunos, manter o Streamlit no ar em paralelo por um período
- [ ] Monitorar tráfego e comparar com o baseline de 5 GB/mês

---

## 7. Riscos e decisões pendentes

- **Caminho do sync (pull):** decidido — **Supabase direto** via PostgREST. O push
  local → nuvem segue pendente (FastAPI local × endpoint próprio).
- **Escrita no `escola_ativa.db`:** resolvido em `core/sync.py` (upsert
  não-destrutivo, transação por tabela, backup antes de gravar).
- **`normalizar_para_matching` ausente**: `student_scores.py` importa essa função de `services.contexto_aulas`, que não existe — quebra o import no legado.
- **Funções de serviço ausentes no legado**: `get_subject_raiz`, `get_subject_by_id`, `get_lessons_for_subject_full`, `get_all_students` (usadas por `gerar_planos_txt.py`).
- **Aliases mãe×filha**: `turma_disciplina_config(aliases_id, aliases_name)` + `discipline_aliases` — regra central dos planos de aula.
- **`forum_posts` vazia** no banco local.
- **`matplotlib`/`pandas`**: evitar no NiceGUI (peso e tráfego).

---

## 8. Definição de pronto (por tarefa)

1. Segue a arquitetura: lógica em `core/`, página fina em `ui/`, rota em `layout.LINKS`.
2. Consultas conferidas contra o schema real (`PRAGMA table_info`), somente leitura por padrão.
3. `py_compile` limpo e rotas respondendo **HTTP 200** com o venv do projeto.
4. Verificação de UI feita com a skill `browser-automation` (console sem erros).
5. Checkbox deste roadmap marcado.
