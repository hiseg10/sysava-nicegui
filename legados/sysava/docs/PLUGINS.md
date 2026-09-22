# 🔌 Guia de Plugins do SysAva

Este documento descreve os plugins disponíveis na **Central de Plugins**, suas funcionalidades, regras de negócio e integrações. Os plugins estão localizados em `data/repo/plugins/`.

---

## 🎯 Gestor de Atividades Diárias (`daily_activities.py`)
Este plugin é o coração do engajamento diário em sala de aula.

-   **Objetivo:** Vincular tarefas práticas às aulas teóricas e atribuir pontuação imediata.
-   **Funcionalidades Principais:**
    -   **Scanner de Aulas:** Varre as disciplinas e identifica o número da aula (ex: Aula 05).
    -   **Integração EduBot:** Publica automaticamente a descrição da atividade no Fórum da aula selecionada.
    -   **Regra do Teto (Cap 6.0):** Pontua o aluno garantindo que a soma do **Escore do Sistema** (engajamento) + **Pontos Qualitativos** não ultrapasse **6.0 pontos** por bloco de 20 aulas (Bloco 1: Aulas 1-20; Bloco 2: Aulas 21-40).
    -   **Lançamento Rápido:** Tabela estilo planilha para pontuar a turma toda de uma vez.

## 📊 Gerenciador de Notas e Scores (`student_scores.py`)
Ferramenta para o fechamento bimestral e acompanhamento acadêmico.

-   **Objetivo:** Centralizar todas as notas e gerar relatórios visuais.
-   **Funcionalidades Principais:**
    -   **Quadro de Notas Completo:** Gestão de colunas NM1, NM2, NM3, Média Automática e Nota Final.
    -   **Lançamento de Conceitos:** Campo para atribuir menções (A, B, C...).
    -   **Histórico Qualitativo:** Registra todos os pontos extras ganhos pelo aluno com data e motivo.
    -   **Exportação PNG:** Gera uma imagem oficial com cabeçalho da escola e nome do professor para compartilhamento.

## 🗓️ Mapa de Grade Semanal (`grade_semanal.py`)
Organizador visual do tempo e horários.

-   **Objetivo:** Visualizar a intersecção de horários entre diferentes turmas.
-   **Funcionalidades Principais:**
    -   **Grade Unificada:** Mostra o "encaixe" das aulas da Turma A e Turma B em uma única linha do tempo.
    -   **Cores Distintivas:** Identificação visual rápida (Azul para Turma A, Verde para Turma B).
    -   **Destaque de Intervalos:** Faixas compactas para lanche e almoço.
    -   **Snapshot para PNG:** Exportação de alta qualidade (200 DPI) para impressão ou postagem em murais.

## 📝 Diário de Frequência (`student_attendance.py`)
Controle de presença simplificado.

-   **Objetivo:** Realizar a chamada diária de forma ágil.
-   **Funcionalidades Principais:**
    -   **Edição em Lote:** Usa o `st.data_editor` para marcar Presente/Falta/Atraso rapidamente.
    -   **Relatório Acumulado:** Calcula automaticamente a porcentagem de frequência e total de faltas de cada aluno desde o início dos registros.
    -   **Persistência Local:** Salva os dados em JSON, permitindo consulta de datas passadas.

## 📅 Agenda e Kanban (`agenda.py`)
Painel de controle diário para o professor e alunos.

-   **Objetivo:** Gerenciar o status das aulas do dia e tarefas pendentes.
-   **Funcionalidades Principais:**
    -   **Status de Aula:** Marcar aulas como Concluídas (Verde), Pendentes (Laranja) ou Normal (Cinza).
    -   **Kanban Integrado:** Quadro de "Pendente", "Em Andamento" e "Finalizado" para gestão de projetos ou estudos.
    -   **Sincronização:** Baseado na `grade_horaria.json`.

---

## 🛠️ Plugins de Manutenção e Auditoria

### 🔍 Radar de Fricção (`friction_radar.py`)
-   Analisa a saúde pedagógica das disciplinas.
-   Identifica aulas sem quiz, descrições muito curtas ou baixo engajamento de comentários no fórum.

### 💾 Auditoria e Backup (`audit_backup.py`)
-   Conta registros em todas as tabelas do Supabase.
-   Cria um clone completo dos dados em um arquivo SQLite local (`.db`) por segurança.

### 🚨 Relatório de Foco (`focus_report.py`)
-   Lista eventos onde alunos saíram da aba do navegador durante a realização de provas.

---

## ⚙️ Como os Plugins Funcionam

1.  **Hibridismo:** Muitos plugins funcionam tanto via interface visual (Streamlit) quanto via terminal (CLI) para tarefas automatizadas.
2.  **Armazenamento:** Dados sensíveis e estruturais ficam no **Supabase**. Dados de plugins (frequência, horários, notas manuais) são persistidos em arquivos **JSON** locais na pasta do plugin para garantir performance e simplicidade.
3.  **Integração:** O arquivo `views/plugins.py` faz a ponte, carregando dinamicamente o código de cada arquivo `.py` quando o usuário clica na aba correspondente.

---
*Documentação atualizada em: 08/05/2026*