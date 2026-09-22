import re
from legados.sysava.services import database as db

def split_lesson_and_quiz(full_content: str):
    """
    Separa o conteúdo da aula do conteúdo do quiz.
    Retorna (lesson_content, quiz_content)
    """
    # 1. Tenta encontrar o início do Quiz pelo cabeçalho específico "## 📝 Quiz"
    # O template do Gemini usa "## 📝 Quiz" ou "## 📝 Quiz de Fixação"
    quiz_match = re.search(r'(?:^|\n)(##\s*📝\s*Quiz)', full_content, re.IGNORECASE)
    
    if quiz_match:
        split_index = quiz_match.start(1)
        lesson_content = full_content[:split_index].strip()
        quiz_content = full_content[split_index:].strip()
        return lesson_content, quiz_content
    
    return full_content, None

def process_quiz_content(lesson_id: int, quiz_content: str, lesson_title: str):
    """Parseia o conteúdo de um quiz e o insere no banco de dados."""
    
    # Tenta extrair um título para o Quiz
    quiz_title_match = re.search(r'^#+\s*(.*)', quiz_content, re.MULTILINE)
    quiz_title = quiz_title_match.group(1).strip() if quiz_title_match else f"Quiz: {lesson_title}"

    # Cria o Quiz no banco
    quiz_data, error = db.create_quiz(lesson_id, quiz_title)
    if error or not quiz_data:
        return False, f"Erro ao criar quiz: {error}"
    
    quiz_id = quiz_data[0]['id']
    
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
        
        current_question = None
        current_options = []
        current_correct_index = -1
        current_question_number = None

    for line in lines:
        line = line.strip()
        if not line: continue
        
        clean_line = re.sub(r'^>\s*', '', line)
        
        # Detecta início da seção de Gabarito
        if re.search(r'(\*\*|##).*Gabarito', clean_line, re.IGNORECASE):
            flush_current_question()
            parsing_gabarito = True
            continue

        if parsing_gabarito:
            # Parse gabarito lines like "1-c", "2.b"
            all_answers = re.findall(r'(\d+)\s*[\-\.\)]\s*([a-eA-E])', clean_line)
            if all_answers:
                for q_num, ans_char in all_answers:
                    ans_idx = ord(ans_char.lower()) - ord('a')
                    for q in questions_buffer:
                        if q['number'] == q_num:
                            q['correct_option_index'] = ans_idx
                            break
            continue

        question_regex_str = r'^(?:###\s*)?[\*]*(\d+)[\*]*[\.\)\-]\s*(.*)'

        # Ignora títulos
        if clean_line.startswith('#') and not re.match(question_regex_str, clean_line):
            continue

        # Identifica resposta na linha (ex: Resposta: B)
        answer_match = re.search(r'(?:Resposta|Gabarito|Correct|Solução).*?([a-eA-E])', clean_line, re.IGNORECASE)
        if answer_match and current_options:
            correct_char = answer_match.group(1).upper()
            idx = ord(correct_char) - ord('A')
            if 0 <= idx < len(current_options):
                current_correct_index = idx
            continue

        # Nova pergunta
        question_match = re.match(question_regex_str, clean_line)
        if question_match:
            flush_current_question()
            current_question_number = question_match.group(1)
            current_question = question_match.group(2)
            current_options = []
            current_correct_index = -1
            continue
            
        # Opção checkbox [x]
        checkbox_match = re.match(r'^[-*+]?\s*[\[\(]\s*([xX\s]?)\s*[\]\)]\s*(.*)', clean_line)
        if checkbox_match:
            is_correct = checkbox_match.group(1).strip().lower() == 'x'
            opt_text = checkbox_match.group(2).strip()
            if is_correct:
                current_correct_index = len(current_options)
            current_options.append(opt_text)
            continue

        # Opção letra a)
        letter_match = re.match(r'^[-*+]?\s*(?:\*\*)?([a-eA-E])(?:\*\*)?[\.\)]\s+(.*)', clean_line)
        if letter_match:
            opt_text = letter_match.group(2).strip()
            current_options.append(opt_text)
            continue
            
        # Continuação da pergunta
        if current_question is not None and not current_options:
            if current_question == "":
                current_question = clean_line
            else:
                current_question += " " + clean_line
            
    if not parsing_gabarito:
        flush_current_question()

    saved_count = 0
    for q in questions_buffer:
        if q['correct_option_index'] == -1:
             continue
             
        _, q_error = db.create_quiz_question(quiz_id, q['question_text'], q['options'], q['correct_option_index'])
        if not q_error:
             saved_count += 1
             
    return True, f"Quiz criado com {saved_count} questões."