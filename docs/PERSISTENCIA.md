# Persistência de Dados — SysAVA NiceGUI

> **Nota:** Este documento descreve a arquitetura LEGADA. Para a nova
> arquitetura enxuta, ver `docs/ARQUITETURA_NOVA.md`.

---

## Visão Geral da Arquitetura

```mermaid
graph TB
    subgraph "Nuvem"
        SB[(Supabase<br/>PostgreSQL)]
    end

    subgraph "Servidor Local"
        SYNC[core/sync.py<br/>Sincronização]
        DB[(escola_ativa.db<br/>SQLite Cache)]
    end

    subgraph "Aplicação NiceGUI"
        REPO[core/repositories.py<br/>Acesso Read-Only]
        AUTH[core/auth.py<br/>Autenticação]
        SCORES[core/scores.py<br/>Cálculo de Notas]
        UI[ui/*.py<br/>Interface]
    end

    SB -->|Pull incremental| SYNC
    SYNC -->|Upsert não-destrutivo| DB
    DB --> REPO
    DB --> AUTH
    DB --> SCORES
    REPO --> UI
    AUTH --> UI
    SCORES --> UI
```

---

## Fluxo de Dados

### 1. Sincronização Supabase → SQLite

```mermaid
sequenceDiagram
    participant U as Usuário
    participant UI as ui/sync.py
    participant SYNC as core/sync.py
    participant DB as SQLite
    participant SB as Supabase

    U->>UI: Clica "Sincronizar"
    UI->>SYNC: sincronizar(modo="incremental")
    SYNC->>SB: Baixa tabelas (paginado, 1000 linhas)
    SB-->>SYNC: Dados JSON
    SYNC->>DB: Backup (backups/backup_*.db)
    SYNC->>DB: Upsert por tabela
    Note over SYNC,DB: Chave: PK → Índice UNIQUE → Heurística
    SYNC-->>UI: Progresso em tempo real
    UI-->>U: Log e estatísticas
```

### 2. Acesso aos Dados (Leitura)

```mermaid
graph LR
    subgraph "Requisição"
        REQ[Requisição HTTP]
        AUTH{Autenticado?}
    end

    subgraph "Camada de Dados"
        REPO[repositories.py]
        DB[(SQLite)]
    end

    subgraph "Camada de Negócios"
        SCORES[scores.py]
        ATT[attendance.py]
        ASSESS[assessments.py]
    end

    subgraph "Apresentação"
        UI[ui/*.py]
    end

    REQ --> AUTH
    AUTH -->|Sim| REPO
    AUTH -->|Não| LOGIN[Login]
    REPO --> DB
    REPO --> SCORES
    REPO --> ATT
    REPO --> ASSESS
    SCORES --> UI
    ATT --> UI
    ASSESS --> UI
```

---

## Modelo de Dados (Entidades Principais)

```mermaid
erDiagram
    USERS {
        string username PK
        string name
        string ra
        string role
        boolean is_active
    }

    CLASSES {
        int id PK
        string name
        string code
        string tipo_turma
        string ano_letivo
        int school_id
    }

    SUBJECTS {
        int id PK
        string name
        string type
        int carga_horaria
        string duration_type
        string status
    }

    LESSONS {
        int id PK
        int subject_id FK
        string title
        string description
        string full_content
    }

    STUDENT_ENROLLMENTS {
        int id PK
        string user_username FK
        int class_id FK
    }

    CLASS_SUBJECTS {
        int id PK
        int class_id FK
        int subject_id FK
    }

    STUDENT_ASSESSMENTS {
        int id PK
        string user_username FK
        int assessment_id FK
        float score
        string status
    }

    ASSESSMENTS {
        int id PK
        int subject_id FK
        string type
        string title
    }

    ATTENDANCE {
        int id PK
        string class_name
        string student_name
        boolean is_present
        string status
        string date
    }

    USERS ||--o{ STUDENT_ENROLLMENTS : "matriculado em"
    CLASSES ||--o{ STUDENT_ENROLLMENTS : "turma"
    CLASSES ||--o{ CLASS_SUBJECTS : "disciplinas"
    SUBJECTS ||--o{ CLASS_SUBJECTS : "turmas"
    SUBJECTS ||--o{ LESSONS : "aulas"
    SUBJECTS ||--o{ ASSESSMENTS : "avaliações"
    USERS ||--o{ STUDENT_ASSESSMENTS : "submissões"
    ASSESSMENTS ||--o{ STUDENT_ASSESSMENTS : "notas"
}
```

---

## Tabelas do Banco de Dados (Novo Schema)

### Tabelas Essenciais (17)

| Tabela | Descrição | Sincronizada |
|--------|-----------|--------------|
| `users` | Usuários (alunos, professores, admin) | ✅ |
| `classes` | Turmas | ✅ |
| `subjects` | Disciplinas | ✅ |
| `class_subjects` | Turma ↔ Disciplina | ✅ |
| `student_enrollments` | Matrículas | ✅ |
| `lessons` | Aulas | ✅ |
| `quizzes` | Quizzes | ✅ |
| `quiz_questions` | Questões dos quizzes | ✅ |
| `assessments` | Avaliações | ✅ |
| `assessment_questions` | Questões das avaliações | ✅ |
| `student_assessments` | Submissões de avaliações | ✅ |
| `student_assessment_answers` | Respostas | ✅ |
| `attendance` | Frequência | ✅ |
| `forum_posts` | Posts do fórum | ✅ |
| `weekly_schedule` | Grade semanal | ✅ |
| `qualitative_points` | Pontos qualitativos | ✅ |
| `student_grades` | Notas calculadas | ✅ |

### Tabelas Eliminadas

| Tabela | Motivo |
|--------|--------|
| `historico_aulas` | Derivado de `user_history` |
| `master_config` | Mover para configuração local |
| `schedules` | Substituído por `weekly_schedule` |
| `schools` | Fundido em `classes.school_id` |
| `user_profiles` | Vazio, não essencial |
| `user_reminders` | Vazio, não essencial |
| `settings` | Configuração local, não AVA |
| `planejamento` | 0 registros |

---

## Fluxo de Notas (Scoring)

### Fórmula de Cálculo

```mermaid
graph TD
    subgraph "Entrada"
        H[user_history] --> A[Aulas Únicas]
        H --> Q[Quizzes Únicos]
        FP[forum_posts] --> F[Posts Únicos]
        SA[student_assessments] --> AV[Avaliações]
        QP[qualitative_points] --> QT[Qualitativos]
    end

    subgraph "Processamento"
        A --> PART[Participação]
        Q --> PART
        F --> PART
        PART --> P1["Part.1 (teto 3)"]
        PART --> P2["Part.2 (teto 3)"]
        P1 --> AVG["Média (para NM3)"]
        P2 --> AVG

        AV --> NM1["NM1 = Av.NM1 + Part.1 + Quali."]
        AV --> NM2["NM2 = Av.NM2 + Part.2 + Quali."]
        AV --> NM3["NM3 = Av.NM3 + Média(Part.) + Quali."]
    end

    subgraph "Saída"
        NM1 --> RES[Resumo por Disciplina]
        NM2 --> RES
        NM3 --> RES
    end
```

---

## Sincronização vs Escrita Local

```mermaid
graph TB
    subgraph "Dados Sincronizados (Supabase → SQLite)"
        direction LR
        SB1[users]
        SB2[classes]
        SB3[subjects]
        SB4[lessons]
        SB5[student_assessments]
        SB6[attendance]
    end

    subgraph "Dados Locais (apenas SQLite)"
        direction LR
        L1[student_grades]
        L2[qualitative_points]
    end

    subgraph "Fluxo"
        SYNC[Sincronização Diária] --> SB1
        SYNC --> SB2
        SYNC --> SB3
        SYNC --> SB4
        SYNC --> SB5
        SYNC --> SB6

        LOCAL[Escrita Local] --> L1
        LOCAL --> L2
    end
```

---

## Segurança e Sessão

```mermaid
sequenceDiagram
    participant U as Usuário
    participant UI as NiceGUI
    participant AUTH as auth.py
    participant DB as SQLite

    U->>UI: Login (username + senha)
    UI->>AUTH: autenticar(username, senha)
    AUTH->>DB: SELECT * FROM app_users
    DB-->>AUTH: Usuário
    AUTH->>AUTH: bcrypt.checkpw()

    alt Credenciais válidas
        AUTH-->>UI: Sucesso
        UI->>UI: app.storage.user = {username, role}
        UI-->>U: Redireciona para home
    else Credenciais inválidas
        AUTH-->>UI: Falha
        UI-->>U: Erro de login
    end

    Note over U,UI: Sessão persistente via STORAGE_SECRET env
```

---

## Resumo

| Componente | Responsabilidade | Arquivo Principal |
|------------|------------------|-------------------|
| **Persistência** | Conexão e operações SQL | `core/db.py` |
| **Repositório** | Consultas read-only | `core/repositories.py` |
| **Sincronização** | Pull Supabase → SQLite | `core/sync.py` |
| **Autenticação** | Login, sessão, papéis | `core/auth.py` |
| **Notas** | Cálculo de NM1/NM2/NM3 | `core/scores.py` |
| **Turmas** | CRUD turmas/disciplinas | `core/turmas.py` |
| **Interface** | Páginas web | `ui/*.py` |

Para a nova arquitetura enxuta, ver `docs/ARQUITETURA_NOVA.md`.
