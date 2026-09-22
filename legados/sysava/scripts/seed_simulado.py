# scripts/seed_simulado.py
import os
import sys
import re
from dotenv import load_dotenv

# Adiciona o diretório raiz ao path para importar os serviços e scripts parentes
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importa a função madura do seed_lessons
try:
    from legados.sysava.scripts.seed_lessons import process_quiz_content
except ImportError as e:
    print(f"ERRO: A importação segura de 'process_quiz_content' falhou: {e}")
    sys.exit(1)

def run_simulado_seeder():
    """
    Função dedicada exclusivamente a popular o Simulado Final (45 Questões) no banco Supabase
    sem inferir ou danificar a varredura normal de aulos do seeder padrão.
    """
    # Configuração do ambiente e variáveis
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=env_path)

    # Injeção das credenciais localmente, similar ao tratamento streamlit
    class MockSecrets(dict):
        def __getitem__(self, key):
            return os.environ.get(key)

    import streamlit as st
    st.secrets = MockSecrets()

    # Importa o módulo de banco de dados do projeto
    from legados.sysava.services import database as db

    if not db.is_db_connected():
        print("ERRO CRÍTICO: Conexão com o banco de dados falhou. Cheque a .env!")
        return

    # Mapeia diretamente o arquivo do simulado recém-criado/revisado
    simulado_path = os.path.join(project_root, 'data', 'repo', 'Olimpíada', 'Revisão Hackathon', 'Simulado_01.md')
    
    if not os.path.exists(simulado_path):
        print(f"ERRO: Arquivo base do Simulado não foi encontrado no caminho: {simulado_path}")
        return

    print("🚀 Iniciando injeção modular do Simulado Final (45 Questões) ...")

    with open(simulado_path, 'r', encoding='utf-8') as f:
        full_content = f.read()

    # 1. Selecionar Turma
    classes = db.get_classes()
    if not classes:
        print("ERRO: Nenhuma turma cadastrada no banco Supabase!")
        return

    print("\n--- SELEÇÃO DE TURMA ---")
    for i, cls in enumerate(classes):
        print(f"[{i + 1}] {cls['name']} (ID: {cls['id']})")

    try:
        class_choice = int(input("\nSelecione o número da Turma: ")) - 1
        if class_choice < 0 or class_choice >= len(classes):
            raise ValueError
        selected_class = classes[class_choice]
    except (ValueError, IndexError):
        print("Opção inválida. Operação abortada.")
        return

    # 2. Selecionar Disciplina da Turma
    subjects = db.get_subjects_for_class(selected_class['id'])
    if not subjects:
        print(f"ERRO: Nenhuma disciplina vinculada à turma '{selected_class['name']}'!")
        return

    print(f"\n--- SELEÇÃO DE DISCIPLINA (Turma: {selected_class['name']}) ---")
    for i, sub in enumerate(subjects):
        print(f"[{i + 1}] {sub['name']} (ID: {sub['id']})")

    try:
        sub_choice = int(input("\nSelecione o número da Disciplina: ")) - 1
        if sub_choice < 0 or sub_choice >= len(subjects):
            raise ValueError
        target_subject = subjects[sub_choice]
        target_subject_id = target_subject['id']
        print(f"\n📍 Alocando simulado em: {selected_class['name']} -> {target_subject['name']}")
    except (ValueError, IndexError):
        print("Opção inválida. Operação abortada.")
        return

    # Cria ou Atualiza a Aula-Mãe que vai receber o simulado na Tabela de Aulas
    lesson_title = "Simulado Final Integrado: Do Piauí Para o Mundo"
    lesson_content = "Este é o simulador definitivo contendo 45 questões de gabarito para a maratona Hackathon, abordando as Regras do Edital, Plataforma AVA Cefet, TI Verde, Fundamentos de Lógica, Python, C e Inglês Técnico Moderno."
    video_url = ""

    lesson_id = db.upsert_lesson(lesson_title, target_subject_id, lesson_content, video_url)
    
    if not lesson_id:
        print("ERRO: Falha na criação física da Aula-Mãe do Simulado.")
        return
        
    print(f"✅ 'Aula' criada e atracada com sucesso no Supabase (ID: {lesson_id}).")
    
    # Preparo do conteúdo via injeção sintética de cabeçalho do quiz para a Regex original engolir macio
    print("⏳ Realizando extração algorítmica de perguntas, gabaritos e formatação de arrays...")
    
    quiz_ready_content = f"## 📝 Quiz: {lesson_title}\n\n" + full_content
    
    # Repassa toda a carga processual para o módulo estável sem inventar a roda
    process_quiz_content(lesson_id, quiz_ready_content, lesson_title)
    
    print("\n🎉 POPULAÇÃO CONCLUÍDA: Simulado no ar com total proteção à estabilidade do projeto original!")

if __name__ == "__main__":
    run_simulado_seeder()
