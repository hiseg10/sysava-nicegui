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

DATA_DIR = os.path.join(ROOT_DIR, 'data', 'Turmas')
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'credentials.json')
ENV_PATH = os.path.join(ROOT_DIR, '.env')

# Carrega variáveis de ambiente
load_dotenv(ENV_PATH)

def setup_gemini():
    """
    Configura o cliente do Gemini.
    Tenta usar a API KEY do .env primeiro (recomendado para scripts).
    Se não houver, tenta ler o credentials.json para fluxo OAuth (mais complexo para scripts headless).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        print("🔑 Usando GEMINI_API_KEY encontrada no .env")
        genai.configure(api_key=api_key)
        return True
    
    # Fallback: Tenta ler o credentials.json apenas para validar existência, 
    # mas para scripts de geração, a API Key é mandatória pela simplicidade da lib genai.
    if os.path.exists(CREDENTIALS_PATH):
        print(f"📂 Arquivo credentials.json encontrado em: {CREDENTIALS_PATH}")
        try:
            with open(CREDENTIALS_PATH, 'r') as f:
                creds = json.load(f)
                project_id = creds.get('installed', {}).get('project_id')
                print(f"ℹ️  Projeto identificado: {project_id}")
                print("⚠️  Para este script rodar de forma autônoma, por favor adicione 'GEMINI_API_KEY=sua_chave' no arquivo .env")
                print("   Você pode gerar uma chave em: https://aistudio.google.com/app/apikey")
                return False
        except Exception as e:
            print(f"❌ Erro ao ler credentials.json: {e}")
            return False
    else:
        print("❌ Nenhuma credencial encontrada (nem .env, nem credentials.json).")
        return False

def generate_content_with_fallback(prompt, model_names=["gemini-3.1-flash-lite-preview",
                                                        "gemini-2.5-flash", 
                                                        "gemini-2.5-pro", 
                                                        "gemini-2.0-flash",
                                                        "gemini-2.5-flash-lite",
                                                        "gemini-flash-latest", 
                                                        "gemini-3-flash-preview"]):
    """Tenta gerar conteúdo usando uma lista de modelos em sequência."""
    while True:
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return response
            except Exception as e:
                if "429" in str(e):
                    print(f"   ⏳ Cota excedida (429) com '{model_name}'. Aguardando 60s antes de tentar o próximo modelo...")
                    time.sleep(60)
                else:
                    print(f"   ⚠️  Erro com '{model_name}': {e}")
                continue
        
        print("\n   ❌ Todos os modelos falharam com a chave atual.")
        new_key = input("   🔑 Insira uma NOVA API KEY temporária para continuar (ou Enter para pular): ").strip()
        
        if new_key:
            print("   🔄 Reconfigurando API e tentando novamente...")
            genai.configure(api_key=new_key)
        else:
            return None

def parse_cronograma_with_ai(cronograma_text):
    """
    Usa o Gemini para ler o texto do cronograma e estruturar os dados.
    Retorna uma lista de dicionários: [{'week': 1, 'lesson': 1, 'topic': '...'}, ...]
    """
    prompt = f"""
    Analise o seguinte texto de um cronograma de aulas.
    Extraia a estrutura de aulas.
    Regra de inferência de Semanas: Geralmente as disciplinas possuem blocos de 8 ou 10 aulas por semana.
    Se as semanas não estiverem explicitamente numeradas no texto, deduza a semana (week) baseando-se nessa contagem sequencial (ex: aulas 1-8 ou 1-10 são semana 1).
    Retorne APENAS um JSON (sem markdown, sem aspas triplas) com o seguinte formato para cada aula identificada:
    [
        {{
            "week": int, (número da semana, ex: 1)
            "lesson_number": int, (número sequencial da aula, ex: 1)
            "topic": "string" (título ou tema da aula)
        }}
    ]

    Texto do Cronograma:
    {cronograma_text}
    """
    
    # Tenta flash primeiro (mais rápido/estável), depois pro, depois legado
    response = generate_content_with_fallback(prompt)
    
    if not response:
        print("   ❌ Falha: Nenhum modelo disponível conseguiu processar o cronograma.")
        return []

    try:
        text_resp = response.text.strip()
        # Limpeza básica caso o modelo retorne markdown ```json ... ```
        if text_resp.startswith("```"):
            text_resp = re.sub(r"^```json|^```", "", text_resp).strip()
            text_resp = re.sub(r"```$", "", text_resp).strip()
        
        return json.loads(text_resp)
    except Exception as e:
        print(f"   ❌ Erro ao processar resposta JSON: {e}")
        return []

def generate_lesson_content(subject, class_name, topic, lesson_num):
    """
    Gera o conteúdo da aula em Markdown usando o Gemini.
    """
    prompt = f"""
    Atue como o Professor Helio Lima do CETI PROFESSOR RALDIR CAVALCANTE BASTOS.
    Crie o conteúdo de uma aula em formato Markdown seguindo ESTRITAMENTE o modelo abaixo.

    Variáveis:
    - Número da Aula: {lesson_num}
    - Tema: {topic}
    - Turma: {class_name}
    - Disciplina: {subject}

    Modelo de Saída (Markdown):
    # 🎨 Aula {lesson_num}: {topic}

    **🏫 Escola:** CETI PROFESSOR RALDIR CAVALCANTE BASTOS  
    **👨‍🏫 Professor:** Helio Lima  
    **🎓 Turma:** {class_name}
    **📚 Componente:** {subject}  

    ---

    ## 📑 Sumário
    1. 🏁 Introdução
    2. 🎯 Objetivos
    3. 💡 Conteúdo
    4. 📖 Glossário
    5. 🛠️ Atividade Prática
    6. 📝 Quiz

    ---

    ## 🏁 Introdução
    (Breve introdução ao tema)

    ## 🎯 Objetivos
    (Liste 3 objetivos claros)
    
    ## 💡 Conteúdo
    (Explicação detalhada, didática, com exemplos práticos ou de código se for programação)
    
    ## 📖 Glossário
    (Definição de termos chave)

    ## 🛠️ Atividade Prática
    (Exercícios ou exemplos práticos)
    
    ## 📝 Quiz de Fixação
    (Crie 4 perguntas de múltipla escolha, 4 alternativas. Para cada pergunta, marque a resposta correta com um [x] e as incorretas com [ ]. Exemplo: - [x] Opção correta)
    
    ## Gabarito Comentado
    (Breve explicação da resposta correta)
    """
    
    response = generate_content_with_fallback(prompt)
    
    if response:
        return response.text
    
    return None

def main():
    print("🤖 Iniciando Gerador de Aulas via Gemini IA...")
    
    if not setup_gemini():
        return

    # Varre a estrutura de pastas
    # Esperado: data/Turmas/{Turma}/{Disciplina}/Cronograma*.md
    search_pattern = os.path.join(DATA_DIR, "**", "Cronograma*.md")
    cronogramas = glob.glob(search_pattern, recursive=True)
    
    print(f"📂 Encontrados {len(cronogramas)} arquivos de cronograma.")

    for crono_path in cronogramas:
        path_obj = Path(crono_path)
        # Estrutura: .../Turmas/{Turma}/{Disciplina}/Cronograma.md
        try:
            subject_dir = path_obj.parent
            subject_name = subject_dir.name
            class_name = subject_dir.parent.name
            
            print(f"\n🎓 Processando: Turma {class_name} | Disciplina {subject_name}")
            print(f"   📄 Lendo: {path_obj.name}")
            
            with open(crono_path, 'r', encoding='utf-8') as f:
                crono_text = f.read()
            
            # 1. Interpretar o Cronograma
            print("   🧠 Interpretando cronograma com Gemini...")
            lessons_plan = parse_cronograma_with_ai(crono_text)
            
            if not lessons_plan:
                print("   ⚠️  Não foi possível extrair aulas deste cronograma.")
                continue
                
            print(f"   📋 Plano identificado: {len(lessons_plan)} aulas.")
            
            # 2. Verificar e Gerar Aulas Faltantes
            for lesson in lessons_plan:
                week_num = lesson.get('week')
                lesson_num = lesson.get('lesson_number')
                topic = lesson.get('topic')
                
                if not week_num or not lesson_num:
                    continue
                
                # Formata nomes de pasta e arquivo
                week_folder_name = f"S{int(week_num):02d}"
                
                week_dir_path = os.path.join(subject_dir, week_folder_name)
                
                # Cria pasta da semana se não existir
                if not os.path.exists(week_dir_path):
                    os.makedirs(week_dir_path)
                    print(f"   📁 Pasta criada: {week_folder_name}")
                
                # Verifica se a aula já existe (com busca flexível de nomes)
                lesson_num_int = int(lesson_num)
                existing_files = os.listdir(week_dir_path)
                
                # Regex: Aula + (espaço/underscore opcional) + (0 opcional) + numero + (fim ou separador)
                pattern = re.compile(rf"^Aula[\s_]*0?{lesson_num_int}(?:[\s_.-].*)?\.md$", re.IGNORECASE)
                
                found_file = None
                for fname in existing_files:
                    if pattern.match(fname):
                        found_file = fname
                        break
                
                if found_file:
                    print(f"   ✅ Existe: {week_folder_name}/{found_file}")
                    continue

                # Se não existe, define o nome padrão para criar
                lesson_file_name = f"Aula_{lesson_num_int:02d}.md"
                lesson_file_path = os.path.join(week_dir_path, lesson_file_name)

                print(f"   ⚙️  Gerando: {week_folder_name}/{lesson_file_name} - Tema: {topic}")
                
                content = generate_lesson_content(subject_name, class_name, topic, lesson_num)
                
                if content:
                    with open(lesson_file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"      💾 Salvo com sucesso.")
                    
                    # Delay para respeitar rate limits do Gemini (Free Tier)
                    time.sleep(4) 
                else:
                    print("      ❌ Falha na geração.")

        except Exception as e:
            print(f"❌ Erro crítico ao processar {crono_path}: {e}")

    print("\n🏁 Processo finalizado.")

if __name__ == "__main__":
    main()