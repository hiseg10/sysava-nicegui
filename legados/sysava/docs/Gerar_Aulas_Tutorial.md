# 🎓 Tutorial: Gerador de Planos de Aula com IA

Este documento serve como guia para utilização do **Gerador de Aulas Híbrido**, uma ferramenta desenvolvida em Python e Streamlit que utiliza Inteligência Artificial (Google Gemini) para criar planos de aula detalhados a partir de seus arquivos e cronogramas.

---

## 🚀 Como Iniciar

Para abrir o sistema, execute o seguinte comando no terminal, dentro da pasta do projeto:

```bash
streamlit run views/Gerador_de_Aulas.py
```

O navegador abrirá automaticamente com a interface da ferramenta.

---

## 🛠️ Passo a Passo de Utilização

A interface é dividida em duas partes principais: a **Barra Lateral (Esquerda)** para configurações e a **Área Principal (Direita)** para geração e visualização.

### 1. Configuração (Barra Lateral)

Antes de gerar a aula, você precisa definir o contexto na barra lateral:

1.  **Fonte de Contexto:**
    *   **📂 Arquivos da Pasta (Rota 2):** Ideal se você já tem materiais (PDFs, textos) organizados nas pastas das semanas. O sistema lerá esses arquivos para basear a aula.
    *   **📝 Lista de Cronograma (Rota 1):** Ideal para planejar com base apenas no tema definido no arquivo `lista de aulas.txt`, sem materiais de apoio específicos.

2.  **Seleção de Turma e Disciplina:**
    *   O sistema lista automaticamente as pastas encontradas em `data/Turmas`.
    *   Selecione a **Turma** e, em seguida, a **Disciplina**.

3.  **Semana / Nº Aula:**
    *   Defina o número da semana ou aula (ex: 1, 2, 3...).
    *   *Nota:* Na "Rota 2", o sistema buscará arquivos na pasta correspondente (ex: `.../S01/seductec`).

### 2. Buscando Contexto (Botão 1)

Na área principal, siga a ordem dos botões:

*   Clique em **"1. Buscar Contexto"**.
*   O sistema irá varrer os arquivos ou o cronograma conforme sua configuração.
*   **Verifique:** Uma caixa de texto chamada "🔍 Contexto Encontrado" aparecerá. Leia para garantir que o sistema encontrou o conteúdo correto antes de pedir para a IA trabalhar.

### 3. Gerando a Aula (Botão 2)

Com o contexto carregado:

*   Clique em **"2. Gerar Plano de Aula com IA"**.
*   Aguarde alguns segundos enquanto o modelo Gemini processa as informações.
*   O sistema combina suas instruções, o contexto encontrado e técnicas de engenharia de prompt para criar a aula.

---

## 📄 Visualização e Exportação

Após a geração, o resultado aparecerá na aba **"📄 Plano de Aula"** à direita.

*   **Leitura:** O plano vem formatado em Markdown, com introdução, objetivos, desenvolvimento e atividades.
*   **Download:** Clique no botão **"💾 Baixar Plano (.md)"** para salvar o arquivo no seu computador. O nome do arquivo seguirá o padrão `Aula_XX_NomeDisciplina.md`.

### Aba de Debug
Existe uma aba chamada **"🔍 Contexto (Debug)"**. Ela serve para desenvolvedores ou curiosos verem exatamente qual **Prompt** foi enviado para a IA. Isso é útil para entender por que a IA gerou determinada resposta.

---

## 📂 Estrutura de Pastas Esperada

Para que a "Rota 2" funcione corretamente, seus arquivos devem estar organizados da seguinte forma:

```text
data/
 └── Turmas/
      └── [Nome da Turma]/
           └── [Nome da Disciplina]/
                └── S[Número da Semana com 2 dígitos]/
                     └── seductec/
                          └── [Seus arquivos aqui]
```

*Exemplo:* `data/Turmas/3 Ano Regular/Inteligencia Artificial/S01/seductec/artigo_intro.pdf`