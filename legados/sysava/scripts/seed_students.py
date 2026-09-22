# scripts/seed_students.py
import os
import sys
from dotenv import load_dotenv

# Garante que a saída do console suporte UTF-8 no Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
# Adiciona o diretório raiz ao path para importar os serviços
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def run_student_seeder():
    # Configuração do ambiente (igual ao seed_data.py)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=env_path)

    class MockSecrets(dict):
        def __getitem__(self, key):
            return os.environ.get(key)

    import streamlit as st
    st.secrets = MockSecrets()

    from legados.sysava.services import database as db
    from legados.sysava.services import auth

    if not db.is_db_connected():
        print("ERRO: Conexão com o banco falhou. Verifique o arquivo .env")
        return

    print("Iniciando importação de alunos...")

    # Caminho base onde estão as pastas das turmas
    base_path = os.path.join(project_root, 'data', 'Turmas')

    # Percorre todas as pastas e arquivos
    for root, dirs, files in os.walk(base_path):
        for file in files:
            # Identifica arquivos que são códigos de turma (ex: 307297.txt)
            if file.endswith(".txt") and file[:-4].isdigit():
                class_code = file[:-4]
                file_path = os.path.join(root, file)
                
                print(f"\n📂 Processando turma {class_code}...")
                
                # Verifica se a turma existe no banco
                class_data = db.get_class_by_code(class_code)
                if not class_data:
                    print(f"  ⚠️ Turma {class_code} não encontrada no banco. Execute o seed_data.py primeiro.")
                    continue
                
                class_id = class_data['id']

                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [l.strip() for l in f if l.strip()]

                # O arquivo tem pares de linhas: Nome e depois RA
                count = 0
                for i in range(0, len(lines), 2):
                    if i+1 >= len(lines): break
                    
                    name = lines[i]
                    ra_line = lines[i+1]
                    
                    if "Código RA:" in ra_line:
                        ra = ra_line.split("Código RA:")[1].strip()
                        
                        # Senha inicial será o próprio RA
                        hashed_pw = auth.hash_password(ra)
                        
                        # Cria o usuário e matricula
                        user_res, user_err = db.upsert_user(username=ra, hashed_password=hashed_pw, name=name, ra=ra)
                        if user_err:
                            print(f"  ❌ Erro ao criar usuário {name}: {user_err}")
                            continue
                            
                        _, enroll_err = db.enroll_student_in_class(username=ra, class_id=class_id) # Use enroll_student_in_class
                        if enroll_err:
                            print(f"  ❌ Erro ao matricular {name}: {enroll_err}")
                        else:
                            count += 1
                            print(f"  ✅ {name} ({ra})")
                
                print(f"  -> Total importado na turma: {count}")

if __name__ == "__main__":
    run_student_seeder()