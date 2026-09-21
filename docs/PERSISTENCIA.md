# Persistência de Dados — SysAVA NiceGUI

Este documento descreve como os dados são armazenados, sincronizados e
accessados no SysAVA, incluindo o fluxo completo desde o Supabase até
a interface do usuário.

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
    APP_USERS {
        string username PK
        string name
        string ra
        string role
        string status
        string password_hash
    }
    
    CLASSES {
        int id PK
        string name
        string code
        string tipo_turma
        string ano_letivo
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
    
    USER_HISTORY {
        int id PK
        string username FK
        string activity
        timestamp timestamp
    }
    
    QUALITATIVE_POINTS {
        int id PK
        string user_username FK
        int subject_id FK
        float points
        string notes
    }
    
    APP_USERS ||--o{ STUDENT_ENROLLMENTS : "matriculado em"
    CLASSES ||--o{ STUDENT_ENROLLMENTS : "turma"
    CLASSES ||--o{ CLASS_SUBJECTS : "disciplinas"
    SUBJECTS ||--o{ CLASS_SUBJECTS : "turmas"
    SUBJECTS ||--o{ LESSONS : "aulas"
    SUBJECTS ||--o{ ASSESSMENTS : "avaliações"
    APP_USERS ||--o{ STUDENT_ASSESSMENTS : "submissões"
    ASSESSMENTS ||--o{ STUDENT_ASSESSMENTS : "notas"
    APP_USERS ||--o{ USER_HISTORY : "atividades"
    APP_USERS ||--o{ QUALITATIVE_POINTS : "pontos"
    SUBJECTS ||--o{ QUALITATIVE_POINTS : "disciplina"
```

---

## Tabelas do Banco de Dados

### Tabelas Principais

| Tabela | Descrição | Sincronizada |
|--------|-----------|--------------|
| `app_users` | Usuários (alunos, professores, admin) | ✅ |
| `classes` | Turmas | ✅ |
| `subjects` | Disciplinas | ✅ |
| `lessons` | Aulas | ✅ |
| `quizzes` | Quizzes | ✅ |
| `quiz_questions` | Questões dos quizzes | ✅ |
| `assessments` | Avaliações (MN1, MN2, etc.) | ✅ |
| `assessment_questions` | Questões das avaliações | ✅ |
| `student_enrollments` | Matrículas | ✅ |
| `student_assessments` | Submissões de avaliações | ✅ |
| `attendance` | Frequência | ✅ |
| `forum_posts` | Posts do fórum | ✅ |
| `user_history` | Histórico de atividades | ✅ |

### Tabelas Locais (não sincronizadas)

| Tabela | Descrição |
|--------|-----------|
| `student_grades` | Notas calculadas (local) |
| `qualitative_points` | Pontos qualitativos |
| `settings` | Configurações do sistema |
| `master_config` | Configuração mestre |
| `user_profiles` | Perfis de usuários |
| `user_reminders` | Lembretes |

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

### Detalhamento por Disciplina

```mermaid
graph LR
    subgraph "Disciplina: PROGRAMAÇÃO"
        subgraph "Aluno: João"
            AULAS["Aulas: 8/10"]
            QUIZ["Quizzes: 5/8"]
            FORUM["Fórum: 3 posts"]
            
            AULAS --> PART計算
            QUIZ --> PART計算
            FORUM --> PART計算
            
            PART计算 --> PART["Part = 16/16 = 1.0<br/>(teto 3)"]
            
            PART --> NM1["NM1 = 8.0 + 1.0 + 0.5 = 9.5"]
            PART --> NM2["NM2 = 7.0 + 1.0 + 0.5 = 8.5"]
            PART --> NM3["NM3 = 6.0 + 1.0 + 0.5 = 7.5"]
        end
    end
```

---

## Mapeamento de Tipos de Avaliação

```mermaid
graph TD
    subgraph "Tipos no Banco"
        T1[MN1]
        T2[MN2]
        T3[MN3]
        T4[T1_N1]
        T5[T2_N1]
        T6[Outros]
    end
    
    subgraph "Mapeamento"
        T1 --> NM1["NM1"]
        T2 --> NM2["NM2"]
        T3 --> NM3["NM3"]
        T4 --> NM1
        T5 --> NM1
        T6 --> TITLE{Análise do Título}
        TITLE -->|"AV01/AV1"| NM1
        TITLE -->|"AV02/AV2"| NM2
        TITLE -->|"Recuperação"| IGN[Ignorado]
    end
```

---

## Status de Disciplinas

```mermaid
stateDiagram-v2
    [*] --> Incompleta
    
    Incompleta --> Completa : Carga horária fechada
    Completa --> Inativa : Ocultar dos fluxos
    Inativa --> Incompleta : Reabrir
    
    note right of Incompleta
        Pode receber:
        - Aulas
        - Notas
        - Pontos
        - Frequência
    end note
    
    note right of Completa
        Não pode:
        - Criar aulas
        - Lançar notas
        - Registrar pontos
        
        Visível em:
        - Consultas
        - Relatórios
    end note
    
    note right of Inativa
        Oculta de:
        - Seletores de disciplina
        - Fluxos de criação
        
        Visível em:
        - Gerenciamento
        - Consultas estatísticas
    end note
```

---

## Sincronização vs Escrita Local

```mermaid
graph TB
    subgraph "Dados Sincronizados (Supabase → SQLite)"
        direction LR
        SB1[app_users]
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
        L3[settings]
        L4[user_profiles]
        L5[user_history]
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
        LOCAL --> L3
        LOCAL --> L4
        LOCAL --> L5
    end
```

---

## Upsert Não-Destrutivo

O processo de sincronização usa upsert não-destrutivo:

```mermaid
graph TD
    START[Início] --> CHECK{Existe tabela?}
    
    CHECK -->|Não| CREATE[Criar tabela]
    CREATE --> INSERT[Inserir linhas]
    
    CHECK -->|Sim| COLS{Colunas novas?}
    COLS -->|Sim| ALTER[Adicionar colunas]
    COLS -->|Não| KEY[Determinar chave]
    ALTER --> KEY
    
    KEY --> EXIST{Registros existentes?}
    EXIST -->|Não| INSERT
    EXIST -->|Sim| COMPARE{Valores iguais?}
    
    COMPARE -->|Sim| SKIP[Pular (inalterado)]
    COMPARE -->|Não| UPDATE[Atualizar registro]
    
    INSERT --> LOG[Log de operação]
    UPDATE --> LOG
    SKIP --> LOG
    LOG --> END[Fim]
```

**Chave de upsert:** PK → Índice UNIQUE → Heurística

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
    
    Note over U,UI: Sessão persistente via storage_secret
```

---

## Estrutura de Arquivos

```
sysava-nicegui/
├── core/                    # Camada de dados e negócios
│   ├── auth.py              # Autenticação e sessão
│   ├── assessments.py       # Avaliações e submissões
│   ├── attendance.py        # Frequência
│   ├── conteudo.py          # Conteúdo de aulas
│   ├── db.py                # Conexão SQLite
│   ├── friction.py          # Radar de atrito
│   ├── logs.py              # Logging
│   ├── repositories.py      # Acesso read-only aos dados
│   ├── scores.py            # Cálculo de notas
│   ├── settings.py          # Configurações
│   ├── sync.py              # Sincronização Supabase
│   ├── turmas.py            # CRUD de turmas/disciplinas
│   └── user_profile.py      # Perfis de usuários
│
├── ui/                      # Camada de apresentação
│   ├── aulas.py             # Página de aulas
│   ├── config.py            # Configurações
│   ├── database.py          # Gerenciamento do banco
│   ├── frequencia.py        # Frequência
│   ├── friction.py          # Radar de atrito
│   ├── layout.py            # Layout compartilhado
│   ├── login.py             # Login
│   ├── manage_turmas.py     # Gerenciar turmas
│   ├── pontos.py            # Pontos do aluno
│   ├── perfil.py            # Perfil do usuário
│   ├── provas.py            # Provas e avaliações
│   ├── quiz.py              # Quizzes
│   └── sync.py              # Sincronização
│
├── data/
│   └── escola_ativa.db      # Banco SQLite local
│
└── main.py                  # Ponto de entrada
```

---

## Diagrama de Dependências

```mermaid
graph TD
    MAIN[main.py] --> AUTH[core/auth.py]
    MAIN --> SYNC[core/sync.py]
    MAIN --> REPO[core/repositories.py]
    
    UI_AULAS[ui/aulas.py] --> REPO
    UI_AULAS --> AUTH
    UI_PONTOS[ui/pontos.py] --> REPO
    UI_PONTOS --> SCORES[core/scores.py]
    UI_PROVAS[ui/provas.py] --> REPO
    UI_PROVAS --> ASSESS[core/assessments.py]
    UI_LAYOUT[ui/layout.py] --> REPO
    UI_LAYOUT --> SCORES
    
    SCORES --> REPO
    SCORES --> DB[core/db.py]
    ASSESS --> DB
    ATT[core/attendance.py] --> DB
    
    DB --> SQLITE[(escola_ativa.db)]
    SYNC --> DB
    SYNC --> SUPABASE[(Supabase)]
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
