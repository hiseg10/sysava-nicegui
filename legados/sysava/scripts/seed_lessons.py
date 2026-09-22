# scripts/seed_lessons.py
import os
import sys
import re
from dotenv import load_dotenv

# Garante que a saída do console suporte UTF-8 no Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
# Adiciona o diretório raiz ao path para importar os serviços
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def process_quiz_content(lesson_id: int, quiz_content: str, lesson_title: str):
    """Parseia o conteúdo de um quiz e o insere no banco de dados."""
    from legados.sysava.services import database as db

    # Tenta extrair um título para o Quiz
    quiz_title_match = re.search(r'^#+\s*(.*)', quiz_content, re.MULTILINE)
    quiz_title = quiz_title_match.group(1).strip() if quiz_title_match else f"Quiz: {lesson_title}"

    quiz_data, error = db.create_quiz(lesson_id, quiz_title)
    if error or not quiz_data:
        print(f"      -> ❌ Erro ao criar quiz: {error}")
        return
    
    quiz_id = quiz_data[0]['id']
    print(f"      -> 📝 Quiz '{quiz_title}' criado.")
    print(f"      -> Processando conteúdo do quiz...")

    lines = quiz_content.split('\n')
    
    questions_buffer = []
    
    current_question = None
    current_options = []
    current_correct_index = -1
    current_question_number = None
    
    parsing_gabarito = False
    
    def flush_current_question():
        nonlocal current_question, current_options, current_correct_index, current_question_number
        if current_question and current_options:
            questions_buffer.append({
                'question_text': current_question,
                'options': current_options,
                'correct_option_index': current_correct_index,
                'number': current_question_number
            })
            status = "✅" if current_correct_index != -1 else "⏳"
            print(f"        {status} Questão {current_question_number} identificada (aguardando gabarito/salvamento)...")
        
        current_question = None
        current_options = []
        current_correct_index = -1
        current_question_number = None

    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Remove caracteres de citação (blockquotes) comuns em markdown
        clean_line = re.sub(r'^>\s*', '', line)
        
        # Detecta início da seção de Gabarito (ex: "**✅ Gabarito:**" ou "## Gabarito")
        if re.search(r'(\*\*|##).*Gabarito', clean_line, re.IGNORECASE):
            print(f"      -> 🔑 Seção de Gabarito encontrada.")
            flush_current_question() # Salva a última questão pendente
            parsing_gabarito = True
            continue

        if parsing_gabarito:
            # Encontra todas as ocorrências de "1-c", "2.b", "3 c", etc. na linha
            all_answers = re.findall(r'(\d+)\s*[\-\.\)]\s*([a-eA-E])', clean_line)
            if all_answers:
                for q_num, ans_char in all_answers:
                    ans_idx = ord(ans_char.lower()) - ord('a')
                    
                    # Atualiza a questão correspondente no buffer
                    found = False
                    for q in questions_buffer:
                        if q['number'] == q_num:
                            q['correct_option_index'] = ans_idx
                            print(f"          -> Gabarito aplicado: Questão {q_num} = {ans_char.upper()} (Opção {ans_idx+1})")
                            found = True
                            break
                    if not found:
                        print(f"          ⚠️  Gabarito para questão {q_num} não encontrado no buffer.")
            continue

        question_regex_str = r'^(?:###\s*)?[\*]*(\d+)[\*]*[\.\)\-]\s*(.*)'

        # Ignora linhas de título markdown dentro do conteúdo
        if clean_line.startswith('#') and not re.match(question_regex_str, clean_line):
            continue

        # 1. Tenta identificar Gabarito/Resposta (ex: "**Resposta: (B)**")
        # Isso geralmente vem DEPOIS das opções, então atualizamos o índice se possível
        answer_match = re.search(r'(?:Resposta|Gabarito|Correct|Solução).*?([a-eA-E])', clean_line, re.IGNORECASE)
        if answer_match and current_options:
            correct_char = answer_match.group(1).upper()
            idx = ord(correct_char) - ord('A')
            if 0 <= idx < len(current_options):
                current_correct_index = idx
                print(f"          -> Gabarito identificado na linha: {correct_char} (Opção {idx+1})")
            continue

        # Verifica se é o início de uma nova pergunta (ex: "1. Pergunta", "1) Pergunta", "**1.** Pergunta")
        # Aceita formatação markdown (negrito/itálico) no número
        question_match = re.match(question_regex_str, clean_line)
        
        if question_match:
            flush_current_question()
            
            current_question_number = question_match.group(1)
            current_question = question_match.group(2)
            current_options = []
            current_correct_index = -1
            continue
            
        # Verifica se é uma opção. Agora aceita:
        # - [x], - [ ], [x], [ ], (x), ( ), com ou sem espaço dentro
        checkbox_match = re.match(r'^[-*+]?\s*[\[\(]\s*([xX\s]?)\s*[\]\)]\s*(.*)', clean_line)
        if checkbox_match:
            is_correct = checkbox_match.group(1).strip().lower() == 'x'
            opt_text = checkbox_match.group(2).strip()
            
            if is_correct:
                current_correct_index = len(current_options)
            
            current_options.append(opt_text)
            continue

        # NOVO: Tenta identificar Opção Letra com asterisco e parenteses (ex: "* (A) Texto")
        star_letter_paren_match = re.match(r'^\*\s+\(([a-eA-E])\)\s+(.*)', clean_line)
        if star_letter_paren_match:
            opt_text = star_letter_paren_match.group(2).strip()
            current_options.append(opt_text)
            continue

        # 4. Tenta identificar Opção Letra (ex: "a) Texto", "A. Texto", "**a)** Texto")
        letter_match = re.match(r'^[-*+]?\s*(?:\*\*)?([a-eA-E])(?:\*\*)?[\.\)]\s+(.*)', clean_line)
        if letter_match:
            opt_text = letter_match.group(2).strip()
            current_options.append(opt_text)
            continue
            
        # Continuação do texto da pergunta (se ainda não tiver opções)
        if current_question is not None and not current_options:
            if current_question == "":
                current_question = clean_line
            else:
                current_question += " " + clean_line
            
    # Salva a última pergunta se não estivermos no modo gabarito
    if not parsing_gabarito:
        flush_current_question()

    # Persiste as questões no banco
    print(f"      -> Salvando {len(questions_buffer)} questões no banco...")
    for q in questions_buffer:
        if q['correct_option_index'] == -1:
             print(f"        ⚠️  Questão {q['number']} ignorada (sem resposta correta identificada).")
             print(f"            (Dica: Use '[x]', adicione 'Resposta: X' ou uma seção '**✅ Gabarito:**')")
             continue
             
        _, q_error = db.create_quiz_question(quiz_id, q['question_text'], q['options'], q['correct_option_index'])
        if q_error:
             print(f"        ❌ Erro ao salvar questão {q['number']}: {q_error}")
        else:
             print(f"        ✅ Questão {q['number']} salva com sucesso.")

def run_lesson_seeder():
    # Configuração do ambiente
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=env_path)

    class MockSecrets(dict):
        def __getitem__(self, key):
            return os.environ.get(key)

    import streamlit as st
    st.secrets = MockSecrets()

    from legados.sysava.services import database as db

    if not db.is_db_connected():
        print("ERRO: Conexão com o banco falhou. Verifique o arquivo .env")
        return

    # O caminho base agora aponta para a pasta de Turmas
    base_path = os.path.join(project_root, 'data', 'Turmas')
    print(f"Iniciando importação de aulas em lote a partir de: {base_path}")

    if not os.path.exists(base_path):
        print(f"AVISO: Diretório '{base_path}' não encontrado. Nenhuma aula para importar.")
        return

    total_lessons = 0

    # Carrega todos os treinamentos existentes para verificação
    all_subjects_db = db.get_subjects()
    training_subjects_map = {s['name']: s['id'] for s in all_subjects_db if s.get('type') == 'training'}

    # Usa os.walk para percorrer toda a árvore de diretórios
    for root, dirs, files in os.walk(base_path):
        # Só nos interessam as pastas que contêm arquivos .md
        md_files = [f for f in files if f.lower().endswith(".md")]
        if not md_files:
            continue

        # Calcula o caminho relativo para entender a estrutura
        try:
            relative_path = os.path.relpath(root, base_path)
            path_parts = relative_path.split(os.sep)
        except ValueError:
            continue
        # --- NOVA LÓGICA PARA TREINAMENTOS ---
        # Estrutura esperada: {nome_do_treinamento}\{semana} (2 partes)
        if len(path_parts) == 2 and path_parts[0] in training_subjects_map:
            training_name, week_folder = path_parts
            subject_id = training_subjects_map[training_name]

            print(f"\n🚀 Encontrado Treinamento: '{training_name}' -> Semana '{week_folder}'")

            # Processa os arquivos .md dentro da pasta da semana do treinamento
            for lesson_file in sorted(md_files):
                lesson_path = os.path.join(root, lesson_file)
                
                # O log de aulas processadas para treinamentos pode ser um único arquivo na pasta do treinamento
                training_log_file = os.path.join(base_path, training_name, 'logs.txt')
                processed_lessons_training = set()
                if os.path.exists(training_log_file):
                    with open(training_log_file, 'r', encoding='utf-8') as f:
                        processed_lessons_training = set(line.strip() for line in f if line.strip())

                log_key = f"{training_name} :: {lesson_file}"
                if log_key in processed_lessons_training:
                    print(f"    ⏭️  Aula '{lesson_file}' já consta no logs.txt. Pulando.")
                    continue

                with open(lesson_path, 'r', encoding='utf-8') as f:
                    full_content = f.read()

                # Extrai título, descrição e quiz (lógica similar à de aulas normais)
                lesson_title_from_h1 = re.search(r'^#\s+(.*)', full_content, re.MULTILINE)
                lesson_title = lesson_title_from_h1.group(1).strip() if lesson_title_from_h1 else lesson_file[:-3].replace('_', ' ').capitalize()
                
                quiz_match = re.search(r'(?:^|\n)(#+.*Quiz.*)', full_content, re.IGNORECASE)
                lesson_content = full_content[:quiz_match.start(1)].strip() if quiz_match else full_content
                quiz_content = full_content[quiz_match.start(1):].strip() if quiz_match else ""

                # Insere a aula no banco, associada ao ID do treinamento
                lesson_id = db.upsert_lesson(lesson_title, subject_id, lesson_content, "")
                if lesson_id:
                    print(f"    ✅ Aula '{lesson_title}' importada para o treinamento '{training_name}'.")
                    total_lessons += 1

                    with open(training_log_file, 'a', encoding='utf-8') as f:
                        f.write(f"{log_key}\n")

                    if quiz_content:
                        process_quiz_content(lesson_id, quiz_content, lesson_title)

        # --- LÓGICA ANTIGA PARA TURMAS REGULARES ---
        # A estrutura esperada é: {turma}\{disciplina}\{semana} (3 partes)
        elif len(path_parts) == 3:
            dir1, dir2, week_folder = path_parts

            # --- LÓGICA ADICIONAL PARA TREINAMENTOS EM FORMATO DE TURMA ---
            # Se o nome da primeira pasta (turma) for um treinamento, usamos ele.
            if dir1 in training_subjects_map:
                print(f"\n🚀 Encontrado Treinamento '{dir1}' em formato de turma.")
                subject_id = training_subjects_map[dir1]
                subject_name = dir1 # Usamos o nome do treinamento para o log
                class_name = dir1
            else:
                # Comportamento padrão para turmas regulares
                class_name, subject_name, week_folder = path_parts

            # Define o caminho do log na pasta da turma e carrega aulas já processadas
            class_dir = os.path.join(base_path, class_name)
            log_file = os.path.join(class_dir, 'logs.txt')
            processed_lessons = set()
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    processed_lessons = set(line.strip() for line in f if line.strip())

            if week_folder.upper().startswith('S'):
                print(f"\n Encontrado: Turma '{class_name}' -> Disciplina '{subject_name}' -> Semana '{week_folder}'")

                # Se não for um treinamento, busca a disciplina regular pelo nome
                if len(path_parts) == 3 and path_parts[0] not in training_subjects_map: # Check if it's a regular subject
                    subject_data = db.get_subject_by_name(subject_name)
                    if not subject_data:
                        print(f"  ⚠️  Disciplina '{subject_name}' não encontrada no banco. Verifique se o nome da pasta corresponde ao nome no Escola.txt.")
                        continue
                    
                    subject_id = subject_data['id']
                # If it's a training in a 3-part path, subject_id is already set from training_subjects_map
                elif len(path_parts) == 3 and path_parts[0] in training_subjects_map:
                    subject_id = training_subjects_map[path_parts[0]]
                else: # Fallback for other cases, should ideally not happen with current logic
                    print(f"  ⚠️  Não foi possível determinar a disciplina para '{subject_name}'. Pulando.")
                    continue

                # Processa os arquivos .md dentro da pasta da semana
                for lesson_file in sorted(md_files):
                    lesson_title = lesson_file[:-3].replace('_', ' ').capitalize()
                    lesson_path = os.path.join(root, lesson_file)

                    # Verifica se a aula já foi processada (evita duplicação)
                    log_key = f"{subject_name} :: {lesson_title}"
                    if log_key in processed_lessons:
                        print(f"    ⏭️  Aula '{lesson_title}' já consta no logs.txt. Pulando.")
                        continue

                    with open(lesson_path, 'r', encoding='utf-8') as f:
                        full_content = f.read()
                    
                    # Separar conteúdo da aula e do quiz

                    # 1. Tenta encontrar o início do Quiz por qualquer cabeçalho (#) contendo a palavra "Quiz"
                    quiz_match = re.search(r'(?:^|\n)(#+.*Quiz.*)', full_content, re.IGNORECASE)

                    # 1. Tenta encontrar o início do Quiz pelo cabeçalho específico "## 📝 Quiz"
                    quiz_match = re.search(r'(?:^|\n)(##\s*📝\s*Quiz)', full_content, re.IGNORECASE)

                    
                    if quiz_match:
                        split_index = quiz_match.start(1)
                        lesson_content = full_content[:split_index].strip()
                        quiz_content = full_content[split_index:].strip()
                    else:
                        # 2. Fallback: Separador '---'
                        parts = re.split(r'\n\s*-{3,}\s*\n', full_content)
                        if len(parts) > 1:
                            lesson_content = "\n---\n".join(parts[:-1])
                            quiz_content = parts[-1].strip()
                        else:
                            lesson_content = full_content
                            quiz_content = ""

                    lines = lesson_content.splitlines()
                    
                    video_url = ""
                    description_lines = []
                    title_found = False
                    lesson_objective = ""
                    
                    for line in lines:
                        stripped = line.strip()
                        
                        # Procura URL de vídeo (primeira ocorrência de http)
                        if stripped.startswith("http") and not video_url:
                            video_url = stripped
                            continue
                        
                        # Procura o Título da Aula (primeira ocorrência de # ou ##)
                        if not title_found and stripped.startswith("#"):
                            clean_title = stripped.lstrip("#").strip()
                            if clean_title:
                                lesson_title = clean_title
                                title_found = True
                                continue
                        
                        # Tenta capturar o objetivo da aula (ex: "Objetivo: Aprender Python")
                        if not lesson_objective and re.match(r'^[\*#]*Objetivos?.*:', stripped, re.IGNORECASE):
                            lesson_objective = re.sub(r'^[\*#]*Objetivos?.*:\s*', '', stripped, flags=re.IGNORECASE).strip()
                        
                        description_lines.append(line)
                    
                    description = "\n".join(description_lines).strip()
                    if not description:
                        description = "Sem descrição"
                    
                    lesson_id = db.upsert_lesson(lesson_title, subject_id, description, video_url)
                    if lesson_id:
                        print(f"    ✅ Aula '{lesson_title}' importada/atualizada.")
                        total_lessons += 1

                        # Registra no log para não processar novamente
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"{log_key}\n")

                        # 1. Criar post inicial no fórum para a aula
                        if lesson_objective:
                            clean_obj = lesson_objective.rstrip('.')
                            forum_message = f"Conforme o objetivo desta aula ({clean_obj}), comente o que achou do tema em questão?"
                        else:
                            forum_message = f"Qual foi o seu maior aprendizado nesta aula? Compartilhe suas dúvidas e reflexões sobre o tema '{lesson_title}'!"
                        
                        _, error = db.add_forum_post(user_name="SysAva Bot", message=forum_message, lesson_id=lesson_id)
                        if not error:
                            print(f"      -> 💬 Post de fórum criado.")
                        else:
                            print(f"      -> ⚠️  Não foi possível criar post no fórum: {error}")

                        # 2. Processar e popular o quiz, se existir
                        if quiz_content:
                            process_quiz_content(lesson_id, quiz_content, lesson_title)
        else:
            # Diagnóstico para pastas ignoradas
            if len(path_parts) < 2: # Changed from 3 to 2 to catch training folders
                print(f"  ⚠️  Ignorando pasta '{relative_path}': Estrutura muito rasa (esperado: Turma/Disciplina/Semana ou Treinamento/Semana).")

    print(f"\nProcesso concluído. Total de aulas importadas: {total_lessons}")

if __name__ == "__main__":
    run_lesson_seeder()