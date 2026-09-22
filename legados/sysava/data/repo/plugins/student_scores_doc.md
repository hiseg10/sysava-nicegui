---
title: Documentação do Plugin de Notas e Pontos Qualitativos (student_scores.py)
description: Guia completo sobre as funcionalidades do plugin de gerenciamento de notas do SysAva, incluindo cálculo de engajamento, composição de notas e exportação visual.
---

# 📊 Plugin de Notas e Pontos Qualitativos (`student_scores.py`)

Este documento detalha as funcionalidades do plugin `student_scores.py`, responsável pelo gerenciamento completo das notas dos alunos no SysAva. O plugin combina dados de avaliações do banco, score de engajamento, pontos qualitativos e frequência para compor as notas finais.

## 🚀 Visão Geral

O plugin atua como um painel central de notas, permitindo ao professor:
- Visualizar e editar o quadro de notas da turma em formato planilha.
- Importar notas de avaliações reais (provas/AVs) do banco de dados.
- Compor notas automaticamente usando engajamento + qualitativo + frequência.
- Replicar notas entre trimestres (para disciplinas mensais/modulares).
- Exportar relatórios coloridos em PNG e HTML para apresentação em sala.

## ✨ Principais Funcionalidades

### 1. Seleção de Turma, Disciplina e Período

- **Sidebar**: Turma e disciplina são selecionadas na barra lateral.
- **Filtro por Disciplinas Ativas**: Apenas disciplinas com `is_active = true` são exibidas.
- **Visão Geral**: Opção "Visão Geral (Todas)" mostra dados agregados de todas as disciplinas.
- **Filtro por Trimestre**: Rádio para alternar entre 1º, 2º, 3º Trimestre ou Visão Geral.

### 2. Quadro de Notas (Planilha Editável)

Tabela interativa com as seguintes colunas:

| Coluna | Descrição | Editável? |
|---|---|---|
| `Nome` | Nome do aluno | ❌ |
| `Engaj.` | Score de engajamento do sistema | ❌ |
| `N1 (T1/T2/T3)` | Nota 1 de cada trimestre | ✅ |
| `N2 (T1/T2/T3)` | Nota 2 de cada trimestre | ✅ |
| `N3 (T1/T2/T3)` | Nota 3 de cada trimestre | ✅ |
| `Média` | Média aritmética das notas do período | ❌ |
| `Nota Final` | Nota final manual (se necessário) | ✅ |
| `Conceito` | Conceito (A, B, C...) | ✅ |
| `Qualitativo` | Pontos qualitativos acumulados | ❌ |

### 3. Formação das Notas (Lógica)

A nota de cada aluno é composta por múltiplas fontes, com a seguinte prioridade:

```
NM1 = Avaliação MN1 (banco) > Outros (banco) > Manual (JSON)
NM2 = Avaliação MN2 (banco) > Outros (banco) > Manual (JSON)
NM3 = Avaliação MN3 (banco) > Manual (JSON)
```

**Média por Trimestre**: `Média = (N1 + N2 + N3) ÷ 3`

**Média Visão Geral**: `Média = (Média_T1 + Média_T2 + Média_T3) ÷ 3`

### 4. Assistente de Lançamento e Composição

#### Aba 1: Importar Avaliação (Provas/AVs)

- Lista todas as avaliações cadastradas para a disciplina (MN1, MN2, MN3, Outros).
- Permite selecionar: Avaliação → Trimestre → Coluna de Destino (N1, N2 ou N3).
- Importa as notas das submissões dos alunos diretamente do banco.
- Opção de substituir notas já existentes ou apenas preencher zeradas.

#### Aba 2: Compor Nota (Engajamento + Qualitativo)

Permite formar uma nota (recomendado: N3) somando componentes:

| Componente | Descrição | Obrigatório? |
|---|---|---|
| **Score de Engajamento** | Pontuação automática do sistema (aulas + quizzes + fórum) | Opcional |
| **Pontos Qualitativos** | Lançamentos manuais do professor (participação, projetos) | Opcional |
| **Bônus por Frequência** | Proporcional à % de presença | Opcional |
| **Bônus Extra** | Valor manual (+0 a +5) | Opcional |

**Regra de Bônus Extra**: O bônus só é concedido se o aluno tiver `Engajamento ≥ 1.0`.

**Regras de Frequência**:
- **Proporcional**: `Bônus = Bônus_Max × (% Freq / 100)`
- **Por Faixa**: 100% = Máximo, ≥85% = 80%, ≥75% = 50%
- **Exclusivo 100%**: Apenas alunos com 100% de presença recebem o bônus

**Teto Máximo**: A nota composta não pode ultrapassar o teto definido (padrão: 10.0).

#### Aba 3: Replicar Disciplina Mensal

- Copia as notas N1, N2 e N3 de um trimestre de origem para outros trimestres.
- Útil para disciplinas mensais/modulares onde as notas do período são as mesmas em todos os trimestres.

### 5. Botão "Replicar N1, N2 e N3 para Outros Trimestres"

Função rápida que copia as notas do 1º Trimestre para o 2º e 3º, atualizando tanto a estrutura por disciplina quanto os campos `overall_nmX` do JSON.

### 6. Painel Individual do Aluno

Ao selecionar um aluno na lista, exibe:
- **Média Final**, **Score de Engajamento**, **Pontos Qualitativos** (métricas).
- Formulário para **adicionar pontos qualitativos** (pontos + motivo).
- **Histórico** de pontos qualitativos registrados (filtrado pela disciplina).

### 7. Exportação Visual

#### PNG Colorido (Matplotlib)
- Gera imagem 200 DPI com tabela estilizada.
- Cores por nível: 🟢 ≥ 6.0 (Aprovado), 🟡 4.0–5.9 (Alerta), 🔴 < 4.0 (Abaixo da Média).
- Cabeçalho institucional com escola, turma, disciplina, período e professor.

#### HTML Interativo
- Relatório completo com tabela colorida + explicação de critérios de avaliação.
- Ideial para projeção em sala ou impressão (`Ctrl + P`).
- Inclui legenda e composição das notas (N1, N2, N3, Média).

## 🗂️ Estrutura de Dados

### JSON Local (`student_scores.json`)

```json
{
  "students_data": {
    "aluno_username": {
      "name": "Nome do Aluno",
      "overall_score": 7.5,
      "overall_grade": "A",
      "overall_nm1": 8.0,
      "overall_nm2": 7.0,
      "overall_nm3": 7.5,
      "overall_nm4": 8.0,
      "...": "...",
      "subjects": {
        "45": {
          "score": 7.5,
          "grade": "A",
          "T1": { "N1": 8.0, "N2": 7.0, "N3": 7.5 },
          "T2": { "N1": 8.0, "N2": 7.0, "N3": 7.5 },
          "T3": { "N1": 8.0, "N2": 7.0, "N3": 7.5 }
        }
      },
      "daily_qualitative_points": [
        {
          "date": "2025-09-08",
          "points": 1.5,
          "notes": "Participação em aula",
          "subject_id": 45
        }
      ]
    }
  }
}
```

### Estrutura `daily_qualitative_points`

| Campo | Tipo | Descrição |
|---|---|---|
| `date` | TEXT | Data do lançamento (`YYYY-MM-DD`) |
| `points` | FLOAT | Pontos adicionados (0.0 a 5.0) |
| `notes` | TEXT | Motivo/atividade |
| `subject_id` | INT | ID da disciplina (opcional) |
| `lesson_id` | INT | ID da aula (opcional, para resolução via `lesson_sub_map`) |

## 🔄 Integração com Outros Plugins

| Plugin | Relação | Direção |
|---|---|---|
| `student_attendance.py` | Grava dados em `student_attendance.json` | Escrita (indireta) |
| `student_scores.py` | Lê `student_attendance.json` para bônus de frequência | Leitura |
| `database.py` | Consulta `assessments`, `student_assessments`, `lessons`, `subjects` | Leitura |
| `contexto_aulas.py` | Usa `normalizar_para_matching` para resolver disciplinas equivalentes | Leitura |

## 📊 Fontes de Dados

| Fonte | Dados Obtidos |
|---|---|
| `database.get_student_score()` | Score de engajamento (aulas + quizzes + fórum) |
| `database.get_assessments_by_subject()` | Avaliações cadastradas (MN1, MN2, MN3) |
| `database.get_assessment_submissions_with_users()` | Notas das submissões dos alunos |
| `student_attendance.json` | Histórico de frequência (presenças/faltas) |
| `student_scores.json` | Notas manuais e pontos qualitativos |
| `database.get_lessons()` | Mapa aula→disciplina (para resolver qualitativos) |

## 🛠️ Como Usar

1. Acesse **Plugins → Gerenciador de Notas** no SysAva.
2. Na sidebar, selecione a **Turma** e a **Disciplina**.
3. Escolha o **Trimestre** para filtrar as colunas visíveis.
4. **Edite diretamente** na planilha as notas que desejar.
5. Clique em **"Salvar Alterações da Turma"**.
6. Para compor nota automática, use o **Assistente de Lançamento** (expander abaixo da planilha).
7. Para exportar, use a seção **"Exportar Relatório Colorido"** no final da página.

## ⚠️ Notas Importantes

- **Cache**: O plugin usa `@st.cache_data` com TTL de 10 minutos para scores e 5 minutos para o JSON. O cache é limpo ao salvar.
- **Retrocompatibilidade**: A estrutura JSON suporta tanto o formato antigo (`nm1`, `nm2`) quanto o novo aninhado (`T1.N1`, `T1.N2`). Leitura prioriza o novo.
- **Replicação Mensal**: Disciplinas modulares (40h) devem ter as notas replicadas para todos os trimestres usando o botão dedicado.
- **Bônus de Frequência**: Requer que o plugin `student_attendance.py` tenha registrado a frequência para calcular a % de presença.
- **Matplotlib Opcional**: A exportação PNG requer a biblioteca `matplotlib`. Se não instalada, apenas o HTML é disponibilizado.
