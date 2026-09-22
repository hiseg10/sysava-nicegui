# 🧅 Arquitetura da Aplicação (Modo Cebola)

Este documento descreve a arquitetura em camadas do SysAva, inspirada em princípios como a "Onion Architecture", para garantir o isolamento de responsabilidades e a manutenibilidade do código.

## 1. Ponto de Entrada e Carregamento (`app.py`)

O `app.py` funciona como o "bootloader" e roteador principal do sistema.

- **Responsabilidade:**
  - Gerenciar o estado da sessão do usuário (`st.session_state`), verificando se ele está logado.
  - Renderizar o menu de navegação na barra lateral.
  - Atuar como um roteador, chamando a função `show_page()` da view correspondente à página selecionada pelo usuário.

## 2. Camada de Apresentação (UI) - `views/`

- **Responsabilidade:** Controlar toda a interface do usuário (UI).
- **Descrição:** Cada arquivo `.py` nesta pasta representa uma página da aplicação (ex: `aulas.py`, `admin.py`). Eles são responsáveis por desenhar os componentes visuais (botões, tabelas, formulários) e chamar a camada de serviços para executar ações. **Esta camada não deve conter lógica de acesso direto ao banco de dados.**
- **Páginas Notáveis:**
  - `admin.py`: Contém a lógica para as abas de gerenciamento de usuários, aulas, avaliações, e o poderoso **Gerador de Aulas com IA**.
  - `plugins.py`: Página especial que serve como um hub para funcionalidades extras, divididas em plugins nativos e externos.

## 3. Camada de Serviços (Lógica de Negócios) - `services/`

- **Responsabilidade:** Orquestrar a lógica de negócios e atuar como intermediária entre a UI e os dados.
- **Descrição:**
  - `database.py`: **Camada de Acesso a Dados (DAL)**. Este é o único arquivo que pode se comunicar com o Supabase. Ele abstrai todas as queries SQL em funções Python claras (ex: `get_user()`, `create_lesson()`). Se o banco de dados fosse trocado, apenas este arquivo precisaria ser modificado.
  - `auth.py`: Contém a lógica de autenticação, como criptografar e verificar senhas.
  - `ai_generation.py`: Gerencia a interação com a API do Google Gemini, construindo os prompts para geração de aulas e análise de cronogramas.
  - `quiz_parser.py`: Contém a lógica para analisar o conteúdo Markdown de um quiz e extrair perguntas, opções e gabarito.

## 4. Ferramentas e Scripts Auxiliares - `scripts/`

- **Responsabilidade:** Fornecer ferramentas de linha de comando para tarefas de automação e manutenção.
- **Descrição:**
  - `seed_lessons.py`: Um poderoso script para **importar aulas em lote**. Ele varre a pasta `data/Turmas/`, lê arquivos `.md`, separa o conteúdo da aula do quiz, e popula o banco de dados, incluindo a criação de posts iniciais no fórum. Ele é compatível tanto com disciplinas regulares quanto com **Treinamentos**.

## 5. Estrutura de Dados Locais - `data/`

- **Responsabilidade:** Armazenar arquivos locais que servem como fonte de dados para a aplicação.
- **Descrição:**
  - `data/Turmas/`: Contém os materiais de aula em Markdown para serem importados pelo `seed_lessons.py`. A estrutura `Turma/Disciplina/Semana/` é fundamental para a organização.
  - `data/repo/`: Funciona como um repositório de conhecimento para a IA e para os plugins.
    - `plugins/`: Contém os scripts Python dos **Plugins Externos**.
    - `ebooks/`: Armazena os arquivos PDF para o **Leitor de E-books**.
    - Outras pastas aqui servem de contexto para o `ai_generation.py` criar aulas mais precisas.

## 6. Sistema de Plugins

A extensibilidade do SysAva é garantida por um sistema de plugins de dois tipos:

- **Plugins Nativos (`views/plugins.py`):** São funcionalidades que requerem uma interface de usuário interativa, como o Leitor de PDF. São implementados diretamente na página de plugins.
- **Plugins Externos (`data/repo/plugins/`):** São scripts Python independentes que rodam em "modo puro" para tarefas de backend. A página de plugins apenas os lista e executa, exibindo a saída do console. Exemplos incluem `audit_backup.py` e `friction_radar.py`.

## Fluxo de Geração de Aula com IA

1.  **Usuário (Professor)** acessa a aba "Gerador de Aulas" em `views/admin.py`.
2.  Ele insere um cronograma e a API Key.
3.  A UI chama a função `parse_cronograma()` em `services/ai_generation.py`.
4.  `ai_generation.py` envia o prompt para a API do Gemini e recebe a estrutura de aulas em JSON.
5.  A UI exibe o plano de aulas. Ao clicar em "Iniciar Geração", um loop é iniciado.
6.  Para cada aula, a UI chama `generate_lesson_markdown()` em `ai_generation.py`.
7.  `ai_generation.py` busca contexto na pasta `data/repo/` e monta um prompt detalhado para o Gemini.
8.  O Gemini retorna o conteúdo completo da aula em Markdown.
9.  A UI chama `quiz_parser.py` para separar o conteúdo da aula do conteúdo do quiz.
10. Finalmente, a UI chama as funções `upsert_lesson()` e `create_quiz_question()` em `services/database.py` para salvar tudo no banco de dados.
