# 🚀 Sugestões de Melhoria - Projeto SysAva

Este documento consolida o planejamento de evolução técnica e visual da plataforma para transformá-la em uma aplicação de nível profissional.

## 1. Tema Visual e Experiência do Usuário (UI/UX)

- **Design "Modern Slate":** Substituir o visual padrão por um tema escuro customizado com gradientes (`linear-gradient(135deg, #1e1e2f 0%, #121212 100%)`).
- **Estilo de Cards:** Envolver as seções principais em containers com bordas arredondadas, sombras sutis e bordas destacadas ao passar o mouse (*hover*).
- **Feedback Progressivo:** Utilizar o componente `st.status` do Streamlit para detalhar as sub-etapas da geração por IA (ex: "Lendo material base...", "Consultando Gemini...", "Formatando Markdown...").
- **Inputs Refinados:** Melhorar a visibilidade de campos de texto e áreas de código com cores de fundo que contrastem melhor com o novo tema.

## 2. Padrão de Arquitetura (Clean Code)

- **Tipagem Estática (Typing):** Implementar `TypedDict` ou modelos `Pydantic` no arquivo `services/database.py` para evitar erros de tipo `Any` ou `Unknown` no Pylance e garantir contratos de dados claros.
- **Centralização de Estado:** Criar um serviço `services/state_manager.py` para gerenciar todas as chaves do `st.session_state`, evitando o uso de strings soltas espalhadas pelas visualizações.
- **Tratamento de Erros Robusto:** Envolver as chamadas do Supabase em blocos `try/except` mais granulares, retornando objetos de erro padronizados.

## 3. Gerador de Aulas (UX Progressiva)

- **Stepper de Fluxo:** Implementar um indicador visual de etapas (1. Contexto -> 2. Geração AI -> 3. Integração) para guiar o professor no processo de criação.
- **Prompt Registry:** Externalizar os prompts da IA (hoje fixos no código) para arquivos de configuração `.yaml` ou `.json`. Isso permite ajustar a "persona" do professor sem alterar o código-fonte.
- **Truncamento Inteligente:** Implementar limites de caracteres automáticos dependendo do modelo escolhido (Local vs Nuvem) para evitar erros de janela de contexto.

## 4. Documentação e Manutenibilidade

- **Auto-Documentação:** Adicionar Docstrings no padrão Google ou NumPy em todas as funções da camada de serviços.
- **Logs de Auditoria:** Expandir o sistema de auditoria para incluir logs de tentativas de saída de tela em avaliações com mais detalhes técnicos.
- **Testes de Unidade:** Iniciar a implementação de testes para as funções críticas de cálculo de score e parser de quizzes.

---
*Documento gerado para auxiliar no roadmap de desenvolvimento do SysAva.*