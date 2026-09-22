# Documentação de Funcionalidades Avançadas

Este documento detalha o funcionamento de recursos avançados do SysAva, como a página de Plugins e a gestão de Treinamentos (disciplinas flutuantes).

## 🧩 Página de Plugins

A página de "Plugins", acessível no menu lateral para **Administradores** e **Professores**, é um centro para estender as funcionalidades do SysAva. Ela é dividida em duas seções principais:

### 1. Plugins Nativos

Esta aba contém funcionalidades interativas que já vêm integradas à interface do SysAva.

#### 📚 Leitor de E-books (PDF)
- **O que faz:** Permite visualizar arquivos PDF diretamente na plataforma.
- **Como usar:** O sistema busca automaticamente por arquivos `.pdf` nos seguintes locais:
  - `data/repo/ebooks/` (para e-books gerais)
  - `data/Turmas/` (em qualquer subpasta, permitindo associar PDFs a turmas ou disciplinas específicas)
- **Requisito:** A biblioteca `streamlit-pdf-viewer` precisa estar instalada (`pip install streamlit-pdf-viewer`).

#### 🎓 Gerador de Certificados
- **O que faz:** Apresenta uma interface de exemplo para a geração de certificados de conclusão para os alunos.

### 2. Plugins Externos

Esta aba permite executar scripts Python (`.py`) para realizar tarefas de backend, como manutenção, relatórios e análises.

- **Localização:** Os scripts devem ser colocados na pasta `data/repo/plugins/`.
- **Execução:** A interface lista os scripts encontrados. Ao clicar em "Executar", o script é rodado em um processo separado e sua saída (qualquer `print`) é exibida na tela.
- **⚠️ Segurança:** Execute apenas scripts de fontes confiáveis, pois eles têm acesso ao ambiente do servidor e ao banco de dados.

#### Exemplos de Plugins Externos:
- **`audit_backup.py`**: Realiza uma contagem de registros nas tabelas principais e cria um backup do banco de dados em um arquivo SQLite na mesma pasta.
- **`friction_radar.py`**: Analisa as disciplinas em busca de "pontos de fricção" (aulas sem quiz, baixo engajamento, etc.) e gera um relatório.
- **`focus_report.py`**: Gera um relatório de todas as vezes que os alunos saíram da tela durante uma avaliação.
- **`student_scores.py`**: Permite gerenciar as notas gerais dos alunos e adicionar pontos qualitativos diários.

---

## 🚀 Treinamentos (Disciplinas Flutuantes)

O recurso de "Treinamentos" permite criar disciplinas especiais que não pertencem a uma única turma, mas podem ser vinculadas a várias delas. É ideal para preparatórios, olimpíadas, nivelamento e revisões.

### Como Funciona

1.  **Criação:**
    - Vá para a página **Admin** e acesse a aba **"🚀 Treinamentos"**.
    - Use o formulário "Criar Novo Treinamento/Olimpíada" para criar a disciplina flutuante. No banco de dados, ela será uma `subject` com `type = 'training'`.

2.  **Vínculo com Turmas:**
    - Após criar o treinamento, selecione-o na lista.
    - Use a caixa de seleção múltipla para escolher todas as turmas que devem ter acesso a este treinamento.
    - Os alunos das turmas vinculadas verão o treinamento em sua lista de disciplinas.

3.  **Adicionar Aulas:**
    Existem duas maneiras de popular as aulas de um treinamento:

    - **Via Interface:** Na mesma aba "Treinamentos", use o formulário "Adicionar Nova Aula" para criar aulas individualmente.

    - **Em Lote (com `seed_lessons.py`):** Para adicionar muitas aulas de uma vez, você pode usar o script de importação. Para que ele reconheça o treinamento, siga a estrutura de pastas abaixo:

      ```
      data/
      └── Turmas/
          └── Nome Exato do Treinamento/
              ├── Nome Exato do Treinamento/  (Repita o nome aqui)
              │   └── S01/
              │       ├── aula_01.md
              │       └── aula_02.md
              └── logs.txt
      ```

      **Por que a pasta é repetida?**
      Essa estrutura `Treinamento/Treinamento/Semana` foi projetada para ser compatível com a ferramenta **"🤖 Gerador de Aulas"**, que espera o formato `Turma/Disciplina/Semana`. Dessa forma, você pode usar o gerador de aulas com IA para criar o conteúdo do seu treinamento de forma automatizada. O script `seed_lessons.py` foi ajustado para entender essa estrutura e importar as aulas para a disciplina flutuante correta.
