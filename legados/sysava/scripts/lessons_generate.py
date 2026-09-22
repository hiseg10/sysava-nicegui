import os
import json
import time
import glob
import re
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google_auth_oauthlib.flow import InstalledAppFlow
import warnings

# import google.generativeai as genai # Descomente e configure se for usar a lib oficial
from legados.sysava.scripts.contexto_aulas import GerenciadorContextoAula


# Suprime avisos de depreciação do pacote google.generativeai para limpar o console
warnings.simplefilter(action='ignore', category=FutureWarning)

# --- CONFIGURAÇÃO ---
current_dir = os.path.dirname(os.path.abspath(__file__))
# Verifica se a pasta 'data' existe no diretório atual (caso o script esteja na raiz)
if os.path.exists(os.path.join(current_dir, 'data')):
    ROOT_DIR = current_dir
else:
    # Caso contrário, assume que está em uma subpasta (ex: scripts/) e sobe um nível
    ROOT_DIR = os.path.abspath(os.path.join(current_dir, '..'))

    
# Configurações de Diretório
# Assume que este script está em b:\Dev\SysAva\scripts
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
DATA_DIR = os.path.join(BASE_DIR, "data", "Turmas")
REPO_DIR = os.path.join(DATA_DIR, "repo")
ENV_PATH = os.path.join(ROOT_DIR, '.env')
# Carrega variáveis de ambiente
load_dotenv(ENV_PATH)


class GeradorAulaGemini:
    def __init__(self, api_key=None):
        """
        Inicializa o gerador de aulas.
        :param api_key: Chave de API do Google Gemini (opcional para teste de prompt).
        """
        self.contexto_mgr = GerenciadorContextoAula(DATA_DIR)
        self.api_key = api_key
        
        # Configuração da API (Exemplo)
        # if self.api_key:
        #     genai.configure(api_key=self.api_key)
        #     self.model = genai.GenerativeModel('gemini-1.5-flash')

    def _carregar_competencias_curriculo(self, disciplina):
        """
        Tenta carregar as competências e habilidades do arquivo curriculo_db.json.
        """
        path_json = os.path.join(REPO_DIR, "ementas_cronogramas", "curriculo_db.json")
        dados_disciplina = {}

        if os.path.exists(path_json):
            try:
                with open(path_json, 'r', encoding='utf-8') as f:
                    db = json.load(f)
                    # Busca em todos os segmentos (BASICO, EPT, etc.)
                    term_busca = disciplina.upper()
                    for segmento, conteudos in db.items():
                        if term_busca in conteudos:
                            dados_disciplina = conteudos[term_busca]
                            break
            except Exception as e:
                print(f"[Aviso] Erro ao ler banco de currículo: {e}")
        
        return dados_disciplina

    def gerar_prompt_aula(self, turma, disciplina, semana, usar_arquivos=True):
        """
        Gera o prompt final para o LLM, decidindo a rota de contexto.
        """
        # 1. Obtenção do Contexto (Rota 1 ou Rota 2)
        if usar_arquivos:
            # ROTA 2: Busca automática na pasta data/Turmas/...
            print(f">>> Gerando via ROTA 2 (Arquivos) para {turma} - {disciplina} - Semana {semana}")
            contexto_str = self.contexto_mgr.obter_contexto_geracao(
                usar_arquivos=True,
                turma=turma,
                disciplina=disciplina,
                semana=semana
            )
        else:
            # ROTA 1: Busca no arquivo de lista (Cronograma)
            # Tenta inferir o caminho do txt: data/repo/<Disciplina>/lista de aulas.txt
            print(f">>> Gerando via ROTA 1 (Cronograma) para {disciplina} - Aula {semana}")
            
            # Ajuste de caminho: Assume que o nome da pasta da disciplina pode ter acentos (ex: Computação)
            # Se o input for "Computacao", isso pode requerer um mapeamento ou input exato.
            caminho_lista = os.path.join(REPO_DIR, disciplina, "lista de aulas.txt")
            
            if not os.path.exists(caminho_lista):
                # Tentativa de fallback para nome capitalizado se não achar
                caminho_lista = os.path.join(REPO_DIR, disciplina.capitalize(), "lista de aulas.txt")

            contexto_str = self.contexto_mgr.obter_contexto_geracao(
                usar_arquivos=False,
                arquivo_lista_path=caminho_lista,
                numero_aula=semana
            )

        # 2. Dados do Currículo
        info_curriculo = self._carregar_competencias_curriculo(disciplina)
        texto_curriculo = ""
        if info_curriculo:
            habilidades = ", ".join(info_curriculo.get('habilidades', []))
            texto_curriculo = (
                f"REFERÊNCIA CURRICULAR:\n"
                f"Competência: {info_curriculo.get('competencia', '')}\n"
                f"Habilidades: {habilidades}\n"
            )

        # 3. Montagem do Prompt
        prompt = f"""
Você é um professor assistente experiente. Crie um plano de aula completo seguindo os dados abaixo.

DADOS GERAIS:
Turma: {turma}
Disciplina: {disciplina}
Semana/Aula: {semana}

{texto_curriculo}

CONTEXTO / CONTEÚDO BASE:
{contexto_str}

---

SOLICITAÇÃO:
Com base no contexto fornecido (seja um tópico do cronograma ou textos de apoio extraídos de arquivos), elabore:
1. **Objetivos de Aprendizagem** (Verbos de ação).
2. **Introdução Teórica** (Explicação clara do tema).
3. **Atividade Prática** (Passo a passo ou roteiro de exercícios).
4. **Recursos Didáticos Necessários**.
5. **Método de Avaliação**.

Se houver links de vídeos no contexto, sugira como integrá-los à aula.
"""
        return prompt
