---
title: Documentação do Plugin de Frequência (student_attendance.py)
description: Guia completo sobre as funcionalidades do plugin de registro de presença do SysAva, incluindo sincronização com banco, backups e exportação.
---

# 📅 Plugin de Frequência (`student_attendance.py`)

Este documento detalha as funcionalidades do plugin `student_attendance.py`, responsável pelo registro diário de presença dos alunos por turma e disciplina no SysAva. Os dados são salvos localmente em JSON e sincronizados com o Supabase.

## 🚀 Visão Geral

O plugin gerencia a chamada diária de alunos, permitindo ao professor registrar presença, falta ou atraso para cada aluno. Os registros são persistidos em duas camadas: um arquivo JSON local (`student_attendance.json`) e a tabela `attendance` no Supabase, garantindo disponibilidade mesmo offline.

## ✨ Principais Funcionalidades

### 1. Seleção de Turma, Disciplina e Data

- **Sidebar**: Turma e disciplina são selecionadas na barra lateral.
- **Filtro por Disciplinas Ativas**: Apenas disciplinas com `is_active = true` são exibidas.
- **Data Flexível**: O professor pode selecionar qualquer data para registrar ou corrigir uma chamada passada.

### 2. Carregamento de Dados (3 Fontes)

O plugin mescla dados de três fontes para montar a chamada:

| Fonte | Descrição | Prioridade |
|---|---|---|
| **Supabase (`attendance`)** | Registros sincronizados do banco cloud | Alta |
| **Backups Locais (`data/frequencia/`)** | Arquivos JSON de backup de chamadas anteriores | Média |
| **JSON Principal (`student_attendance.json`)** | Cache local do plugin | Base |

> **Regra de Merge**: Dados já existentes no JSON principal não são sobrescritos por backups ou dados do banco.

### 3. Interface de Chamada (Data Editor)

- Tabela compacta com colunas: `Nº`, `Nome`, `Status`.
- O campo **Status** é um dropdown com 3 opções: `Presente`, `Falta`, `Atraso`.
- Todos os alunos iniciam como `Presente` por padrão.
- A tabela é editável diretamente na interface (inline editing).

### 4. Persistência e Sincronização

Ao clicar em **"Salvar Chamada do Dia"**, ocorre:

1. **JSON Local**: O arquivo `student_attendance.json` é atualizado com a estrutura:
   ```
   { class_id: { subject_id: { "YYYY-MM-DD": { username: "Presente"|"Falta"|"Atraso" } } } }
   ```

2. **Supabase (Tabela `attendance`)**: Um upsert é realizado com `on_conflict="student_name, class_name, subject_id, date"`. Cada registro contém:
   - `student_name`, `student_number`, `is_present` (boolean)
   - `class_name`, `subject_id`, `subject_name`
   - `date`, `professor_name`

> **Importante**: A constraint UNIQUE da tabela `attendance` é `(student_name, class_name, subject_id, date)`. O campo `subject_id` é obrigatório para que o upsert funcione corretamente.

### 5. Resumo Diário

Após a chamada, um painel de métricas exibe:
- Total de **Presenças**
- Total de **Faltas**
- Total de **Atrasos**

### 6. Relatório Acumulado de Frequência

Uma tabela ordenada por número de faltas exibe para cada aluno:
- Presenças, Faltas, Atrasos
- **% de Frequência** = `(Presenças + Atrasos) / Total de Dias × 100`

### 7. Exportação CSV

Duas opções de download:

| Botão | Conteúdo |
|---|---|
| **Resumo da Disciplina** | Tabela de frequência (%) da disciplina selecionada |
| **Histórico Geral (Turma)** | Log detalhado de todas as chamadas (todas as disciplinas e datas) |

## 🗂️ Estrutura de Dados

### JSON Local (`student_attendance.json`)

```json
{
  "12": {
    "45": {
      "2025-09-08": {
        "aluno1_username": "Presente",
        "aluno2_username": "Falta",
        "aluno3_username": "Atraso"
      },
      "2025-09-05": { ... }
    }
  }
}
```

- **Chave raiz**: `class_id` (string)
- **Segundo nível**: `subject_id` (string)
- **Terceiro nível**: Data no formato ISO (`YYYY-MM-DD`)
- **Folha**: `{ username: status }`

### Tabela Supabase (`attendance`)

| Coluna | Tipo | Descrição |
|---|---|---|
| `student_name` | TEXT | Nome completo do aluno |
| `student_number` | INT | Número de ordem na lista |
| `is_present` | BOOLEAN | `true` = Presente/Atraso, `false` = Falta |
| `class_name` | TEXT | Nome da turma |
| `subject_id` | BIGINT | ID da disciplina (FK para `subjects`) |
| `subject_name` | TEXT | Nome da disciplina |
| `date` | TEXT | Data no formato `YYYY-MM-DD` |
| `professor_name` | TEXT | Nome do professor logado |

**Constraint UNIQUE**: `(student_name, class_name, subject_id, date)`

## 🔄 Integração com Outros Plugins

| Plugin | Relação | Direção |
|---|---|---|
| `student_scores.py` | Lê `student_attendance.json` para calcular bônus de frequência | Leitura |
| `gerar_planos_txt.py` | Lê tabela `attendance` para pré-preencher lista de presença | Leitura |
| `student_scores.py` | Exibe estatísticas de frequência no quadro de notas | Leitura |

## 🛠️ Como Usar

1. Acesse **Plugins → Diário de Frequência** no SysAva.
2. Na sidebar, selecione a **Turma** e a **Disciplina**.
3. Defina a **Data** da chamada.
4. Na tabela, altere o status de cada aluno (Presente / Falta / Atraso).
5. Clique em **"Salvar Chamada do Dia"**.
6. Opcionalmente, baixe os relatórios em CSV.

## ⚠️ Notas Importantes

- **Backups Legados**: O plugin suporta dois formatos de backup na pasta `data/frequencia/`: formato lista (legado) e formato dicionário (atual).
- **Dados Offline**: Se o Supabase estiver indisponível, os dados são salvos apenas no JSON local. A sincronização ocorrerá na próxima tentativa.
- **Fallback Silencioso**: Erros de conexão com o banco são tratados silenciosamente para não interromper o fluxo do professor.
