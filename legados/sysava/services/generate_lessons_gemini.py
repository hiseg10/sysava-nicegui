import os
import json
from legados.sysava.services import database as db
from dotenv import load_dotenv
from legados.sysava.services.contexto_aulas import GerenciadorContextoAula

# Configurações de Diretório
# Assume que este script está em b:\Dev\SysAva\services
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tenta localizar a pasta data, seja rodando do services ou da raiz
if os.path.exists(os.path.join(BASE_DIR, "data")):
    DATA_DIR = os.path.join(BASE_DIR, "data")
else:
    # Fallback caso a estrutura seja diferente
    DATA_DIR = os.path.join(os.getcwd(), "data")

REPO_DIR = os.path.join(DATA_DIR, "repo")
ENV_PATH = os.path.join(BASE_DIR, '.env')

# Carrega variáveis de ambiente
load_dotenv(ENV_PATH)

class GeradorAulaGemini:
    def __init__(self, api_key=None):
        """
        Inicializa o gerador de aulas.
        :param api_key: Chave de API (opcional, pois o serviço de IA lida com isso na interface).
        """
        self.contexto_mgr = GerenciadorContextoAula(DATA_DIR)
        self.api_key = api_key

    def obter_nome_escola(self):
        """
        Busca o nome da escola, priorizando o banco de dados e usando o arquivo
        Escola.txt como fallback.
        """
        # 1. Tenta buscar do banco de dados primeiro
        school_data = db.get_school()
        if school_data and school_data.get('name'):
            return school_data['name']

        # 2. Fallback para o arquivo Escola.txt se não encontrar no banco
        path_escola = os.path.join(DATA_DIR, "Turmas", "Escola.txt")
        if os.path.exists(path_escola):
            try:
                with open(path_escola, 'r', encoding='utf-8') as f:
                    return f.readline().strip()
            except Exception as e:
                print(f"[Aviso] Erro ao ler Escola.txt: {e}")
        return "Escola Técnica Estadual" # Valor padrão final

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

    def listar_arquivos_aula(self, turma, disciplina, semana):
        """
        Retorna estrutura com arquivos 'todos' e 'sugeridos'.
        """
        resultado, erro = self.contexto_mgr.listar_arquivos_rota_2(turma, disciplina, semana)
        if erro:
            return None, erro
        return resultado, None

    def processar_arquivos_selecionados(self, lista_arquivos):
        """
        Lê o conteúdo dos arquivos escolhidos.
        """
        return self.contexto_mgr.ler_arquivos_especificos(lista_arquivos)

    def obter_contexto_aula(self, turma, disciplina, semana, numero_aula=None, usar_arquivos=True):
        """
        Obtém o contexto da aula (Rota 1 ou Rota 2).
        """
        if numero_aula is None:
            numero_aula = semana

        if usar_arquivos:
            # ROTA 2: Busca automática na pasta data/Turmas/...
            print(f">>> [DEBUG] Gerando via ROTA 2 (Arquivos) para {turma} - {disciplina} - Semana {semana}")
            contexto_str = self.contexto_mgr.obter_contexto_geracao(
                usar_arquivos=True,
                turma=turma,
                disciplina=disciplina,
                semana=semana
            )
        else:
            # ROTA 1: Busca no arquivo de lista (Cronograma)

            print(f">>> [DEBUG] Gerando via ROTA 1 (Cronograma) para {disciplina} - Aula {numero_aula}")
            
            semana_str = f"S{int(semana):02d}"
            
            # Tenta encontrar o arquivo .txt (cronograma) em diversas vias possíveis
            opcoes_caminho = [
                # Nova recomendação: Caminho específico da semana (Turmas ou Repo)
                os.path.join(DATA_DIR, "Turmas", turma, disciplina, semana_str, "lista de aulas.txt"),
                os.path.join(REPO_DIR, turma, disciplina, semana_str, "lista de aulas.txt"),
                # Caminho padrão por Disciplina (com e sem turma)
                os.path.join(REPO_DIR, turma, disciplina, "lista de aulas.txt"),
                os.path.join(REPO_DIR, disciplina, "lista de aulas.txt"),
                os.path.join(REPO_DIR, disciplina.capitalize(), "lista de aulas.txt")
            ]
            
            caminho_lista = None
            for opt in opcoes_caminho:
                if os.path.exists(opt):
                    caminho_lista = opt
                    print(f"    🔎 Arquivo de cronograma encontrado em: {opt}")
                    break
            
            if not caminho_lista:
                # Fallback final: se nada foi encontrado, usa o primeiro da lista para o erro ser informativo
                caminho_lista = opcoes_caminho[0]
            contexto_str = self.contexto_mgr.obter_contexto_geracao(
                usar_arquivos=False,
                arquivo_lista_path=caminho_lista,
                numero_aula=numero_aula
            )
        return contexto_str

    def gerar_prompt_aula(self, turma, disciplina, semana, contexto_str: str, school_name: str = "Escola Técnica Estadual", professor_name: str = "Professor(a) Assistente", numero_aula: int = None, titulo_personalizado: str = None):
        """
        Gera o prompt final para o LLM a partir de um contexto já fornecido,
        usando o template estruturado que gera um plano de aula completo com quiz.
        """
        if numero_aula is None:
            numero_aula = semana

        # Instrução para a IA inferir o tópico ou usar o personalizado
        if titulo_personalizado:
            topic_instruction = f"TEMA DEFINIDO: {titulo_personalizado}"
        else:
            topic_instruction = "Inferir o TEMA principal a partir do CONTEÚDO BASE fornecido."

        # 2. Dados do Currículo
        info_curriculo = self._carregar_competencias_curriculo(disciplina)
        texto_curriculo = ""
        if info_curriculo:
            habilidades = ", ".join(info_curriculo.get('habilidades', []))
            texto_curriculo = (
                f"REFERÊNCIA CURRICULAR (Use para guiar os objetivos):\n"
                f"Competência: {info_curriculo.get('competencia', '')}\n"
                f"Habilidades: {habilidades}\n"
            )

        # 3. Adaptação de Nível Pedagógico (Ex: 9º ano vs Ensino Médio/Técnico)
        nivel_pedagogico = "Ensino Médio/Técnico"
        instrucao_nivel = "Pode usar termos técnicos padrão e referências em inglês, mas sempre com breve explicação."
        
        if "9ano" in turma.lower() or "9º" in turma:
            nivel_pedagogico = "Ensino Fundamental (9º Ano)"
            instrucao_nivel = (
                "IMPORTANTE: Alunos com pouco contato com inglês. EVITE termos em inglês sem tradução. "
                "Sempre que usar um termo técnico (ex: 'Array', 'Loop'), coloque a tradução ou um apelido em português ao lado. "
                "Use uma didática muito simples, focada em conceitos básicos e analogias lúdicas."
            )

        # 4. Montagem do Prompt
        prompt = f"""
Atue como um Professor Assistente de {disciplina}, especialista em criação de materiais didáticos para o {nivel_pedagogico}.
Público-Alvo: {nivel_pedagogico} de escola pública ({turma}).
{instrucao_nivel}
Use uma linguagem acessível, motivadora, com muitas analogias do cotidiano e cultura pop.

Crie o conteúdo de uma aula em formato Markdown seguindo ESTRITAMENTE o modelo abaixo.

DADOS DA AULA:
- Semana: {semana}
- Número da Aula: {numero_aula}
- Tema: {topic_instruction}
- Turma: {turma}
- Disciplina: {disciplina}

{texto_curriculo}

CONTEÚDO BASE (Material de apoio obrigatório):
---
{contexto_str}
---

DIRETRIZES DE ESTILO E RIQUEZA VISUAL:
1. Emojis: Use abundantemente para tornar a leitura amigável.
2. Formatação: Use negrito para termos chave, tabelas se houver comparações, e blocos de código formatados.
3. ILUSTRAÇÕES: Sempre que um conceito for complexo, inclua uma imagem usando o formato: `![Descrição Detalhada](https://source.unsplash.com/1600x900/?keyword)`. Escolha keywords em inglês que façam sentido com o tema (ex: 'robot', 'code', 'nature').
4. LINKS REAIS (EXTRAÇÃO OBRIGATÓRIA): O CONTEÚDO BASE abaixo contém links e referências reais (YouTube, sites, etc). Sua missão é LOCALIZAR esses links no texto e copiá-los EXATAMENTE como estão para a seção de Recursos. Se você for um modelo local (sem internet), NÃO INVENTE URLs; use apenas as que encontrar no material de apoio. Se não houver links no material, sugira "Termos de Busca" precisos para o YouTube.

Modelo de Saída (Siga este formato):
# Aula {numero_aula}: {titulo_personalizado if titulo_personalizado else "[TEMA INFERIDO]"}

**🏫 Escola:** {school_name}
**👨‍🏫 Professor:** {professor_name}
**🎓 Turma:** {turma}
**📚 Componente:** {disciplina}

---

## 📑 Sumário
1. 🏁 Introdução
2. 🎯 Objetivos
3. 💡 Conteúdo (com ilustrações)
4. 📖 Glossário
5. 🛠️ Atividade Prática
6. 🧰 Recursos e Links Reais (Copiados do contexto)
7. 📝 Quiz

---

## 🎯 Objetivos de Aprendizagem
(Liste 3 objetivos claros e mensuráveis)

## 💡 Conteúdo
(Explicação didática. Insira pelo menos 2 ilustrações usando o padrão Unsplash mencionado acima para quebrar o texto e facilitar o entendimento.)

## 📖 Glossário
(Definição de termos chave.)

## 🛠️ Atividade Prática
(Um desafio prático ou exercício de reflexão baseado no conteúdo.)

---

## 🧰 Recursos e Links Reais
(Liste ferramentas, softwares e principalmente LINKS DE VÍDEOS OU ARTIGOS encontrados no CONTEÚDO BASE. Se não encontrar links reais, sugira termos de busca específicos para o YouTube.)

---

## 📝 Quiz: {titulo_personalizado if titulo_personalizado else "[TEMA]"}

(Crie 3 perguntas de múltipla escolha com 4 alternativas cada. Marque a resposta correta com um [x] e as incorretas com [ ].)
---
### ✅ Gabarito
(Liste o gabarito de forma simples. Ex: 1. C, 2. A, 3. B)
"""
        return prompt