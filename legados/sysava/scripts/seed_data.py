# scripts/seed_data.py
import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório raiz ao path para que possamos importar os serviços
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def run_seeder():
    """
    Função principal que carrega o ambiente e executa o seeder.
    """
    # O script espera que o arquivo .env esteja na pasta raiz (um nível acima de 'scripts')
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=env_path)

    # Este é um hack para fazer o `services/database.py` (que usa st.secrets)
    # funcionar fora de um app Streamlit.
    class MockSecrets(dict):
        def __getitem__(self, key):
            # Tenta obter do ambiente, se não existir, retorna None
            return os.environ.get(key)

    import streamlit as st
    st.secrets = MockSecrets()

    # Agora que o ambiente está configurado, podemos importar o módulo de banco de dados
    from legados.sysava.services import database as db

    if not db.is_db_connected():
        print("ERRO: Conexão com o banco de dados falhou.")
        print("Verifique se você criou um arquivo .env na raiz do projeto com SUPABASE_URL e SUPABASE_KEY.")
        return

    # Verificação básica da URL
    url = os.environ.get("SUPABASE_URL", "")
    if not url.startswith("http"):
        print(f"ERRO: A URL do Supabase no .env parece inválida: '{url}'")
        return

    print("Iniciando o processo de seeding do banco de dados...")

    # Caminho para o arquivo de dados
    file_to_parse = os.path.join(project_root, 'data', 'Turmas', 'Escola.txt')

    with open(file_to_parse, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    # 1. Processar a Escola
    school_name = lines[0]
    # Assume que a segunda linha é algo como "GRE:00021ª"
    school_gre = lines[1].split(':')[1].strip() if ':' in lines[1] else lines[1]
    print(f"Processando escola: {school_name}")
    school_id = db.upsert_school(name=school_name, gre=school_gre)
    if not school_id:
        print("ERRO: Falha ao criar a escola. Abortando.")
        return

    # 2. Processar Turmas e Disciplinas
    i = 2
    while i < len(lines):
        # Uma linha de turma é aquela que é seguida por uma linha de "Código da Turma"
        if (i + 1 < len(lines)) and lines[i+1].startswith("Código da Turma:"):
            class_name = lines[i]
            class_code = lines[i+1].split(":")[1].strip()
            
            print(f"  - Processando turma: {class_name} ({class_code})")
            class_id = db.upsert_class(name=class_name, code=class_code, school_id=school_id)
            
            if not class_id:
                print(f"    ERRO: Falha ao criar a turma {class_name}.")
                i += 1
                continue

            # As disciplinas começam duas linhas após o nome da turma
            j = i + 2
            while j < len(lines):
                # É uma disciplina se a próxima linha NÃO for um código de turma
                if (j + 1 >= len(lines)) or not lines[j+1].startswith("Código da Turma:"):
                    subject_name = lines[j]
                    print(f"    - Vinculando disciplina: {subject_name}")
                    subject_id = db.upsert_subject(name=subject_name)
                    if subject_id:
                        db.link_subject_to_class(class_id=class_id, subject_id=subject_id)
                    j += 1
                else:
                    break # Fim das disciplinas desta turma
            i = j # Pula o ponteiro principal para o final do bloco processado
        else:
            i += 1 # Linha não é o início de um bloco de turma, avança

    print("\nSeeding concluído com sucesso!")

if __name__ == "__main__":
    run_seeder()