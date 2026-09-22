import os
import glob
import re
from pypdf import PdfReader

class GerenciadorContextoAula:
    def __init__(self, base_data_path):
        """
        Inicializa o gerenciador.
        :param base_data_path: Caminho raiz para a pasta 'data' (ex: b:\\Dev\\SysAva\\data)
        """
        self.base_data_path = base_data_path

    def _rota_1_arquivo_txt(self, arquivo_lista_path, numero_aula):
        """
        ROTA 1: Busca o contexto baseando-se no arquivo lista de aulas.txt existente.
        """
        if not os.path.exists(arquivo_lista_path):
            return f"Erro: Arquivo de lista não encontrado em {arquivo_lista_path}"

        conteudo_encontrado = ""
        
        try:
            with open(arquivo_lista_path, 'r', encoding='utf-8') as f:
                for linha in f:
                    # Assume formato: Disciplina \t Aula XX (Data): Título – Objetivo: ...
                    if f"Aula {numero_aula:02d}" in linha or f"Aula {numero_aula}" in linha:
                        conteudo_encontrado = linha.strip()
                        break
            
            if conteudo_encontrado:
                return f"CONTEXTO DO CRONOGRAMA (ROTA 1):\n{conteudo_encontrado}"
            else:
                return f"Aviso: Aula {numero_aula} não encontrada no arquivo de lista."
        except Exception as e:
            return f"Erro ao ler arquivo txt: {str(e)}"

    def listar_arquivos_rota_2(self, turma, disciplina, semana):
        """
        Retorna uma lista de arquivos disponíveis e uma lista de sugeridos.
        """
        semana_str = f"S{int(semana):02d}"
        
        path_aula = os.path.join(
            self.base_data_path, 
            "Turmas", 
            turma, 
            disciplina, 
            semana_str, 
        )

        if not os.path.exists(path_aula):
            return None, f"Pasta não encontrada: {path_aula}"

        # Busca todos os arquivos relevantes
        todos_arquivos = []
        # Varre a pasta e subpastas (os.walk) para encontrar arquivos ignorando se estão em 'seductec' ou na raiz
        for root, dirs, files in os.walk(path_aula):
            for file in files:
                if file.lower().endswith(('.pdf', '.md', '.txt')):
                    todos_arquivos.append(os.path.join(root, file))
        
        if not todos_arquivos:
            return [], "Nenhum arquivo encontrado na pasta."

        # Lógica de sugestão (Regex)
        padrao = re.compile(rf'(?i)(aula|semana|s|texto|aprofundamento)?[\s_]*0?{int(semana)}(?!\d)')
        
        sugeridos = []
        for arq in todos_arquivos:
            # Se tiver apenas 1 arquivo, sugere ele. Se tiver regex match, sugere também.
            if len(todos_arquivos) == 1 or padrao.search(os.path.basename(arq)):
                sugeridos.append(arq)
        
        return {
            "todos": sorted(todos_arquivos),
            "sugeridos": sorted(sugeridos)
        }, None

    def _rota_2_pasta_arquivos(self, turma, disciplina, semana):
        """
        ROTA 2: Busca PDFs e Links na estrutura de pastas data/Turmas/...
        Estrutura esperada: data/Turmas/<turma>/<disciplina>/S<semana>/seductec/
        """
        # Formata semana para S01, S02, etc.
        semana_str = f"S{int(semana):02d}"
        
        # Monta o caminho relativo
        path_aula = os.path.join(
            self.base_data_path, 
            "Turmas", 
            turma, 
            disciplina, 
            semana_str, 
            "seductec"
        )

        if not os.path.exists(path_aula):
            return f"Aviso: Pasta da aula não encontrada: {path_aula}"

        texto_acumulado = [f"CONTEXTO DE ARQUIVOS (ROTA 2 - {semana_str}):\n"]

        # --- FILTRAGEM INTELIGENTE ---
        # Regex para buscar o número da aula, evitando submatches (ex: "1" em "10").
        # Busca por padrões como "Aula 1", "Aula_1", "S01", "texto_aula_1", etc.
        padrao = re.compile(rf'(?i)(aula|semana|s|texto|aprofundamento)?[\s_]*0?{int(semana)}(?!\d)')

        def selecionar_arquivos_relevantes(arquivos_encontrados):
            if len(arquivos_encontrados) <= 1:
                return arquivos_encontrados # Se só tem um ou nenhum, retorna o que achou
            
            arquivos_filtrados = []
            for arq in arquivos_encontrados:
                if padrao.search(os.path.basename(arq)):
                    arquivos_filtrados.append(arq)
            
            # Se achou arquivos específicos, retorna eles.
            # Se não, NÃO retorna todos. Retorna uma lista vazia para que a mensagem de "nenhum arquivo" seja mostrada.
            return arquivos_filtrados

        # 1. Busca e filtra PDFs
        todos_pdfs = glob.glob(os.path.join(path_aula, "*.pdf"))
        pdfs_selecionados = selecionar_arquivos_relevantes(todos_pdfs)

        # Adiciona uma mensagem se múltiplos arquivos foram encontrados mas nenhum foi selecionado
        if len(todos_pdfs) > 1 and not pdfs_selecionados:
            nomes_pdfs = [os.path.basename(p) for p in todos_pdfs]
            texto_acumulado.append(f"--- Aviso: Múltiplos PDFs encontrados, mas nenhum corresponde à Aula {semana}. Arquivos ignorados: {', '.join(nomes_pdfs)} ---\n")

        for pdf_file in pdfs_selecionados:
            try:
                reader = PdfReader(pdf_file)
                texto_pdf = ""
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        texto_pdf += extracted + "\n"
                
                texto_acumulado.append(f"--- Conteúdo do PDF ({os.path.basename(pdf_file)}) ---\n{texto_pdf}\n")
            except Exception as e:
                texto_acumulado.append(f"Erro ao ler PDF {os.path.basename(pdf_file)}: {e}\n")

        # 2. Busca e filtra Links/Markdown/Txt
        todos_textos = glob.glob(os.path.join(path_aula, "*.md")) + glob.glob(os.path.join(path_aula, "*.txt"))
        mds = selecionar_arquivos_relevantes(todos_textos)

        for md_file in mds:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    texto_acumulado.append(f"--- Conteúdo Extra/Links ({os.path.basename(md_file)}) ---\n{f.read()}\n")
            except Exception as e:
                 texto_acumulado.append(f"Erro ao ler arquivo de texto {os.path.basename(md_file)}: {e}\n")

        if len(texto_acumulado) == 1: # Só tem o cabeçalho
            return "Aviso: Nenhum arquivo PDF ou de texto encontrado na pasta da semana."
            
        return "\n".join(texto_acumulado)

    def ler_arquivos_especificos(self, lista_caminhos):
        """
        Lê o conteúdo de uma lista exata de arquivos fornecida.
        """
        texto_acumulado = []
        
        for arquivo in lista_caminhos:
            _, ext = os.path.splitext(arquivo)
            ext = ext.lower()
            nome_base = os.path.basename(arquivo)

            try:
                if ext == '.pdf':
                    reader = PdfReader(arquivo)
                    texto_pdf = ""
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            texto_pdf += extracted + "\n"
                    texto_acumulado.append(f"--- Conteúdo PDF ({nome_base}) ---\n{texto_pdf}\n")
                
                elif ext in ['.md', '.txt']:
                    with open(arquivo, 'r', encoding='utf-8') as f:
                        texto_acumulado.append(f"--- Conteúdo Texto ({nome_base}) ---\n{f.read()}\n")
                
            except Exception as e:
                texto_acumulado.append(f"Erro ao ler {nome_base}: {e}\n")
        
        if not texto_acumulado:
            return ""
        return "\n".join(texto_acumulado)

    def obter_contexto_geracao(self, usar_arquivos=False, **kwargs):
        """
        Função Principal (Fachada) para decidir qual rota usar.
        
        :param usar_arquivos: Booleano. Se True, usa Rota 2. Se False, usa Rota 1.
        :param kwargs: Argumentos variáveis dependendo da rota.
            - Rota 1 requer: 'arquivo_lista_path', 'numero_aula'
            - Rota 2 requer: 'turma', 'disciplina', 'semana'
        """
        if usar_arquivos:
            # Validação simples
            if not all(k in kwargs for k in ('turma', 'disciplina', 'semana')):
                return "Erro: Rota 2 exige 'turma', 'disciplina' e 'semana'."
            
            return self._rota_2_pasta_arquivos(
                kwargs['turma'], 
                kwargs['disciplina'], 
                kwargs['semana']
            )
        else:
            if not all(k in kwargs for k in ('arquivo_lista_path', 'numero_aula')):
                return "Erro: Rota 1 exige 'arquivo_lista_path' e 'numero_aula'."
                
            return self._rota_1_arquivo_txt(kwargs['arquivo_lista_path'], kwargs['numero_aula'])