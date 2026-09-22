import os
import glob
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

        # 1. Busca PDF (aula em pdf.pdf ou similar)
        pdfs = glob.glob(os.path.join(path_aula, "*.pdf"))
        for pdf_file in pdfs:
            try:
                reader = PdfReader(pdf_file)
                texto_pdf = ""
                for page in reader.pages:
                    texto_pdf += page.extract_text() + "\n"
                
                texto_acumulado.append(f"--- Conteúdo do PDF ({os.path.basename(pdf_file)}) ---\n{texto_pdf}\n")
            except Exception as e:
                texto_acumulado.append(f"Erro ao ler PDF {os.path.basename(pdf_file)}: {e}\n")

        # 2. Busca Links/Markdown (links...md)
        mds = glob.glob(os.path.join(path_aula, "*link*.md"))  # Pega qualquer md que tenha 'link' no nome
        # Se não achar específico, pega todos .md ou .txt
        if not mds:
            mds = glob.glob(os.path.join(path_aula, "*.txt")) + glob.glob(os.path.join(path_aula, "*.md"))

        for md_file in mds:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    texto_acumulado.append(f"--- Conteúdo Extra/Links ({os.path.basename(md_file)}) ---\n{f.read()}\n")
            except Exception as e:
                 texto_acumulado.append(f"Erro ao ler arquivo de texto {os.path.basename(md_file)}: {e}\n")

        if len(texto_acumulado) == 1: # Só tem o cabeçalho
            return "Aviso: Nenhum arquivo PDF ou de texto encontrado na pasta da semana."
            
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