# Tutorial de Build do SysAva com PyInstaller

Este tutorial explica o processo de criação de um executável standalone para o SysAva utilizando o PyInstaller, detalhando o uso e as possíveis alterações no arquivo `SysAva.spec`.

## 1. Preparação do Ambiente

Antes de iniciar o processo de build, certifique-se de que o ambiente Python está configurado corretamente. O script `setup.ps1` automatiza a criação de um ambiente virtual e a instalação das dependências necessárias.

1.  **Execução do script `setup.ps1`:**

    *   Abra o PowerShell como administrador.
    *   Navegue até o diretório raiz do projeto SysAva.
    *   Execute o script: `.\setup.ps1`

    Este script irá:

    *   Criar um ambiente virtual (se ainda não existir).
    *   Instalar ou atualizar as dependências listadas no arquivo `requirements.txt`.
    *   Executar o PyInstaller para gerar o executável.

## 2. Entendendo o arquivo `SysAva.spec`

O arquivo `SysAva.spec` é um script Python que contém as instruções para o PyInstaller construir o executável. Ele define quais arquivos devem ser incluídos, quais módulos devem ser "escondidos" e outras configurações importantes.

Aqui estão as seções mais importantes do arquivo `SysAva.spec`:

*   **`Analysis`:** Esta seção configura a análise do script principal (`app.py`) e define as dependências.
    *   `pathex`: Lista de caminhos onde o PyInstaller deve procurar por módulos.
    *   `binaries`: Lista de arquivos binários a serem incluídos.
    *   `datas`: Lista de arquivos de dados (como imagens, arquivos de configuração, etc.) a serem incluídos.
        *   Exemplo: `[('views', 'views'), ('services', 'services'), ('data', 'data'), ('.streamlit', '.streamlit')]` inclui os diretórios `views`, `services`, `data` e `.streamlit` no executável.
    *   `hiddenimports`: Lista de módulos que o PyInstaller pode não detectar automaticamente. É crucial adicionar módulos como `streamlit` e `streamlit.components.v1` aqui.
        *   Para incluir o executável do Streamlit, adicione uma entrada à lista `datas` na seção `Analysis`.
        *   Exemplo: `datas += [('.sysenv/Scripts/streamlit.exe', '.sysenv/Scripts')]`

    *   `hookspath`: Lista de caminhos para hooks personalizados do PyInstaller.
    *   `excludes`: Lista de módulos a serem excluídos.
    *   `noarchive`: Se `True`, os arquivos não são armazenados em um arquivo único, o que pode facilitar a depuração.
*   **`PYZ`:** Esta seção cria um arquivo zip contendo o código Python.
*   **`EXE`:** Esta seção cria o executável final.
    *   `name`: Nome do executável.
    *   `console`: Se `True`, uma janela de console será exibida quando o executável for executado. Se `False`, o executável será executado sem console.
*   **`COLLECT`:** Esta seção coleta todos os arquivos necessários em uma pasta.

## 3. Alterações Comuns no `SysAva.spec`

*   **Adicionar arquivos de dados:**

    Para incluir arquivos adicionais (por exemplo, arquivos JSON, CSV, etc.), adicione uma entrada à lista `datas` na seção `Analysis`.

    Exemplo: `datas += [('meus_arquivos', 'meus_arquivos')]`
*   **Adicionar imports ocultos:**

    Se o executável falhar ao iniciar devido a módulos não encontrados, adicione-os à lista `hiddenimports` na seção `Analysis`.

    Exemplo: `hiddenimports += ['meu_modulo_oculto']`
*   **Remover a janela do console:**

    Para criar um executável que não exiba uma janela de console, altere `console=True` para `console=False` na seção `EXE`.

## 4. Construindo o Executável

Após fazer as alterações necessárias no arquivo `SysAva.spec`, execute o seguinte comando no PowerShell:

```powershell
& "$venvDir\Scripts\pyinstaller.exe" SysAva.spec --noconfirm
```

O executável estará localizado na pasta `dist\SysAva`.