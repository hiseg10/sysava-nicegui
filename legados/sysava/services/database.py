# services/database.py
from supabase import create_client, Client
import streamlit as st
import httpx
import os
import re

@st.cache_resource
def init_connection():
    """Inicializa e armazena em cache a conexão com o Supabase."""
    try:
        # Tenta pegar de secrets (Streamlit Cloud/Local) ou variáveis de ambiente (Session/Docker)
        supabase_url = st.secrets.get("SUPABASE_URL") if "SUPABASE_URL" in st.secrets else os.environ.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_KEY") if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")
        
        if supabase_url and supabase_key:
            return create_client(supabase_url, supabase_key)
        return None
    except Exception as e:
        print(f"Erro na conexão com Supabase: {e}")
        return None

supabase = init_connection()

def is_db_connected():
    """Verifica se a conexão com o banco de dados foi estabelecida."""
    return supabase is not None

def check_db_structure():
    """Verifica se a estrutura básica do banco (tabela app_users) existe."""
    if not is_db_connected():
        return False
    try:
        # head=True faz uma requisição leve apenas para verificar a existência da tabela
        supabase.table("app_users").select("username", head=True).execute()
        return True
    except Exception:
        return False

# --- Funções de Usuário ---
def get_user(username: str):
    if not is_db_connected(): return None
    response = supabase.table("app_users").select("username, password, name, role").eq("username", username).execute()
    return response.data[0] if response.data else None

def get_all_users():
    if not is_db_connected(): return []
    try:
        response = supabase.table("app_users").select("*").execute()
        return response.data
    except Exception as e:
        print(f"❌ DEBUG: Erro em get_all_users: {e}")
        return []

def create_user(username: str, hashed_password: str, name: str, ra: str, role: str = 'student'):
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("app_users").insert({
            "username": username, "password": hashed_password, "name": name, "ra": ra, "role": role
        }).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def delete_user(username: str):
    """Remove um usuário do banco de dados."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("app_users").delete().eq("username", username).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

# --- Funções de Histórico do Usuário ---
def add_user_history(username: str, activity: str):
    """Adiciona uma entrada ao histórico do usuário."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("user_history").insert({
            "username": username, "activity": activity
        }).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def get_user_history(username: str):
    """Busca o histórico de um usuário."""
    if not is_db_connected(): return []
    try:
        response = supabase.table("user_history").select("*").eq("username", username).order("timestamp", desc=True).execute()
        return response.data
    except Exception as e:
        return []

def get_all_history(limit: int = 200):
    """Busca o histórico global de atividades (para relatórios)."""
    if not is_db_connected(): return []
    try:
        response = supabase.table("user_history").select("*").order("timestamp", desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        return []

def upsert_user(username: str, hashed_password: str, name: str, ra: str):
    """Cria ou atualiza um usuário (útil para scripts de importação em massa)."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("app_users").upsert({
            "username": username, "password": hashed_password, "name": name, "ra": ra, "role": "student"
        }).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

# --- Funções de Score e Pontuação ---
def get_user_forum_lessons_by_subject(user_name: str):
    """
    Conta a participação do usuário no fórum por disciplina.
    Retorna um dicionário {subject_id: count_de_aulas_unicas_com_post}.
    """
    if not is_db_connected(): return {}
    try:
        # 1. Pega todos os posts do usuário que estão em um fórum de aula
        res = supabase.table("forum_posts").select("lesson_id").eq("user_name", user_name).not_.is_("lesson_id", "null").execute()
        if not res.data: return {}
        
        # 2. Pega os IDs únicos das aulas onde o usuário postou
        lesson_ids = list({r['lesson_id'] for r in res.data})
        
        # 3. Busca a qual disciplina cada uma dessas aulas pertence
        lessons_res = supabase.table("lessons").select("id, subject_id").in_("id", lesson_ids).execute()
        if not lessons_res.data: return {}
        
        # 4. Conta quantas aulas únicas por disciplina
        subject_counts = {}
        for lesson in lessons_res.data:
            sid = lesson['subject_id']
            subject_counts[sid] = subject_counts.get(sid, 0) + 1
        return subject_counts
    except Exception:
        return {}

def get_student_score(username: str, filter_subject_id: int = None):
    """Calcula o score detalhado do aluno, considerando apenas a melhor tentativa de cada quiz."""
    if not is_db_connected(): return {"quiz": 0, "lesson": 0, "forum": 0, "total": 0}

    # Estrutura: {subject_id: {quiz_title: max_points}}
    best_quiz_scores_by_subject = {}
    viewed_lessons_by_subject = {} # {subject_id: set_of_lesson_activities}
    
    history = get_user_history(username)

    # --- Mapas auxiliares para fallback em logs antigos ---
    all_lessons = get_lessons()
    lesson_title_map = {l['title']: l['subject_id'] for l in all_lessons}
    try:
        all_quizzes = supabase.table("quizzes").select("title, lesson_id").execute().data or []
        lesson_id_map = {l['id']: l['subject_id'] for l in all_lessons}
        quiz_title_map = {q['title']: lesson_id_map.get(q['lesson_id']) for q in all_quizzes if q.get('lesson_id') in lesson_id_map}
    except Exception:
        quiz_title_map = {}

    for h in history:
        act = h.get('activity', '')
        subject_id = None
        
        # 1. Tenta extrair subject_id dos logs novos
        match_sid = re.search(r'\| subject_id:(\d+)', act)
        if match_sid:
            subject_id = int(match_sid.group(1))
        
        clean_act = act.split('|')[0].strip()

        # 2. Fallback para logs antigos
        if not subject_id:
            if clean_act.startswith("Acessou a aula:"):
                title = clean_act.replace("Acessou a aula:", "").strip()
                subject_id = lesson_title_map.get(title)
            elif clean_act.startswith("Concluiu Quiz:"):
                try:
                    title_part = clean_act.replace("Concluiu Quiz:", "").strip()
                    title = title_part.rsplit('(', 1)[0].strip()
                    subject_id = quiz_title_map.get(title)
                except:
                    pass

        if not subject_id: continue

        # Contabiliza Aulas (únicas por título)
        if clean_act.startswith("Acessou a aula:"):
            if subject_id not in viewed_lessons_by_subject:
                viewed_lessons_by_subject[subject_id] = set()
            viewed_lessons_by_subject[subject_id].add(clean_act)
            
        # Contabiliza Quizzes (apenas a melhor nota de cada quiz)
        elif clean_act.startswith("Concluiu Quiz:"):
            try:
                title_part = clean_act.replace("Concluiu Quiz:", "").strip()
                quiz_name = title_part.rsplit('(', 1)[0].strip()
                score_part = title_part.rsplit('(', 1)[-1].split(')')[0]
                
                if '/' in score_part:
                    points = int(score_part.split('/')[0])
                    
                    if subject_id not in best_quiz_scores_by_subject:
                        best_quiz_scores_by_subject[subject_id] = {}
                    
                    # Guarda apenas a maior pontuação para este quiz específico
                    current_best = best_quiz_scores_by_subject[subject_id].get(quiz_name, 0)
                    if points > current_best:
                        best_quiz_scores_by_subject[subject_id][quiz_name] = points
            except:
                pass
    user_data = get_user(username)
    forum_points_by_subject = {}
    if user_data and user_data.get('name'):
        forum_points_by_subject = get_user_forum_lessons_by_subject(user_data['name'])

    # 3. Consolida e calcula o score final
    enrollment = get_user_enrollment(username)
    class_name = ""
    if enrollment:
        classes = get_classes()
        class_info = next((c for c in classes if c['id'] == enrollment['class_id']), None)
        if class_info:
            class_name = class_info.get('name', '').lower()
            replacements = {'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c', 'º': '', 'ª': ''}
            for k, v in replacements.items():
                class_name = class_name.replace(k, v)
            class_name = re.sub(r'[-\s]+', '', class_name)

    all_subjects = {s['id']: s['name'] for s in get_subjects()}
    workload_3ds = { "ATIVIDADES INTEGRADORAS - INTELIGÊNCIA ARTIFICIAL": 40, "TESTE DE SISTEMAS E SEGURANÇA DE DADOS": 80, "INTELIGÊNCIA ARTIFICIAL APLICADA A AUTOMAÇÃO": 80, "INTERNET DAS COISAS - IOT": 80, "ORIENTAÇÃO PROFISSIONAL E EMPREENDEDORISMO": 40, "PROJETO INTEGRADOR": 120 }

    total_score, total_quiz_points, total_lesson_points, total_forum_points = 0, 0, 0, 0
    all_subject_ids = set(best_quiz_scores_by_subject.keys()) | set(viewed_lessons_by_subject.keys()) | set(forum_points_by_subject.keys())

    if filter_subject_id:
        all_subject_ids = {sid for sid in all_subject_ids if sid == filter_subject_id}

    for sid in all_subject_ids:
        l_points = len(viewed_lessons_by_subject.get(sid, set()))
        
        # Soma as melhores notas de cada quiz desta disciplina
        q_points = sum(best_quiz_scores_by_subject.get(sid, {}).values())
        
        f_points = forum_points_by_subject.get(sid, 0)
        raw_subject_score = l_points + q_points + f_points
        
        total_lesson_points += l_points
        total_quiz_points += q_points
        total_forum_points += f_points

        final_subject_score = raw_subject_score
        is_3ano_ds = ("3ano" in class_name or "3serie" in class_name) and ("ds" in class_name or "sis" in class_name or "des" in class_name)
        
        if is_3ano_ds:
            subject_name = all_subjects.get(sid, "").upper().strip()
            workload = workload_3ds.get(subject_name, 40)
            divisor = (workload / 40.0) * 32.0
            if divisor > 0:
                final_subject_score = raw_subject_score / divisor
        else:
            final_subject_score = raw_subject_score / 32.0
            
        total_score += final_subject_score

    return {
        "quiz": total_quiz_points,
        "lesson": total_lesson_points,
        "forum": total_forum_points,
        "total": round(total_score, 2)
    }

# --- Funções do Fórum ---
def get_forum_posts(lesson_id: int = None):
    if not is_db_connected(): return []
    try:
        query = supabase.table("forum_posts").select("*").order("created_at", desc=True)
        if lesson_id:
            query = query.eq("lesson_id", lesson_id)
        # Se lesson_id for None, não aplica o filtro de 'null', permitindo ver todo o histórico no Fórum Geral
        response = query.execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar posts do fórum: {e}")
        return []

def add_forum_post(user_name: str, message: str, lesson_id: int = None):
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        post_data = {"user_name": user_name, "message": message}
        if lesson_id:
            post_data['lesson_id'] = lesson_id
        response = supabase.table("forum_posts").insert(post_data).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def delete_forum_post(post_id: int):
    if not is_db_connected(): return None, "Banco de dados não conectado"
    response, error = supabase.table("forum_posts").delete().eq("id", post_id).execute()
    return response, error

# --- Funções da Estrutura Acadêmica ---

def get_school():
    if not is_db_connected(): return None
    try:
        response = supabase.table("schools").select("*").limit(1).execute()
        return response.data[0] if response.data else None
    except Exception:
        return None

def upsert_school(name: str, gre: str):
    """Insere ou atualiza uma escola. Retorna o ID da escola."""
    if not is_db_connected(): return None
    try:
        res = supabase.table("schools").select("id").eq("name", name).execute()
        if res.data:
            return res.data[0]['id']
        res = supabase.table("schools").insert({"name": name, "gre": gre}).execute()
        return res.data[0]['id']
    except Exception as e:
        print(f"Erro ao acessar tabela 'schools': {e}")
        return None

def upsert_class(name: str, code: str, school_id: int):
    """Insere ou atualiza uma turma. Retorna o ID da turma."""
    if not is_db_connected(): return None
    res = supabase.table("classes").select("id").eq("code", code).execute()
    if res.data:
        return res.data[0]['id']
    res = supabase.table("classes").insert({"name": name, "code": code, "school_id": school_id}).execute()
    return res.data[0]['id']

def get_classes():
    """Busca todas as turmas cadastradas."""
    if not is_db_connected(): return []
    try:
        response = supabase.table("classes").select("*").order("name").execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar turmas: {e}")
        return []

def get_class_by_code(code: str):
    if not is_db_connected(): return None
    res = supabase.table("classes").select("id").eq("code", code).execute()
    return res.data[0] if res.data else None

def upsert_subject(name: str, type: str = 'regular'):
    """Insere ou atualiza uma disciplina. Retorna o ID da disciplina."""
    if not is_db_connected(): return None
    res = supabase.table("subjects").select("id").eq("name", name).eq("type", type).execute()
    if res.data:
        return res.data[0]['id']
    res = supabase.table("subjects").insert({"name": name, "type": type}).execute()
    return res.data[0]['id']

def link_subject_to_class(class_id: int, subject_id: int):
    """Associa uma disciplina a uma turma, ignorando se já existir."""
    if not is_db_connected(): return
    res = supabase.table("class_subjects").select("*").eq("class_id", class_id).eq("subject_id", subject_id).execute()
    if not res.data:
        supabase.table("class_subjects").insert({"class_id": class_id, "subject_id": subject_id}).execute()

def get_subjects():
    """Busca todas as disciplinas."""
    if not is_db_connected(): return []
    try:
        response = supabase.table("subjects").select("*").execute()
        return response.data
    except Exception:
        return []

def enroll_student(username: str, class_id: int):
    """Matricula um aluno em uma turma."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("student_enrollments").upsert({
            "user_username": username, "class_id": class_id
        }).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def get_subject_by_name(name: str):
    if not is_db_connected(): return None
    # Tenta busca exata
    res = supabase.table("subjects").select("id").eq("name", name).execute()
    if res.data:
        return res.data[0]
    # Tenta busca case-insensitive (ignora maiúsculas/minúsculas)
    res = supabase.table("subjects").select("id").ilike("name", name).execute()
    return res.data[0] if res.data else None

def get_user_enrollment(username: str):
    """Busca a matrícula (turma) de um usuário."""
    if not is_db_connected(): return None
    try:
        response = supabase.table("student_enrollments").select("class_id").eq("user_username", username).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Erro ao buscar matrícula do usuário '{username}': {e}")
        return None

def get_subjects_for_class(class_id: int):
    """Busca todas as disciplinas associadas a uma turma."""
    if not is_db_connected(): return []
    try:
        # 1. Buscar os subject_ids da tabela de junção
        response = supabase.table("class_subjects").select("subject_id").eq("class_id", class_id).execute()
        if not response.data:
            return []
        
        subject_ids = [item['subject_id'] for item in response.data]
        subjects_response = supabase.table("subjects").select("*").in_("id", subject_ids).order("name").execute()
        return subjects_response.data
    except Exception as e:
        print(f"Erro ao buscar disciplinas da turma {class_id}: {e}")
        return []

def enroll_student_in_class(username: str, class_id: int):
    if not is_db_connected(): return None, "Offline"
    try:
        supabase.table("student_enrollments").delete().eq("user_username", username).execute()
        response = supabase.table("student_enrollments").insert({"user_username": username, "class_id": class_id}).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def get_students_by_class(class_id: int):
    """Busca todos os alunos matriculados em uma turma específica."""
    if not is_db_connected(): return []
    try:
        enrollments_res = supabase.table("student_enrollments").select("user_username").eq("class_id", class_id).execute()
        if not enrollments_res.data: return []
        usernames = [e['user_username'] for e in enrollments_res.data]
        users_res = supabase.table("app_users").select("*").in_("username", usernames).execute()
        return users_res.data
    except Exception as e:
        print(f"Erro ao buscar alunos da turma {class_id}: {e}")
        return []

def get_classes_for_subject(subject_id: int):
    if not is_db_connected(): return []
    try:
        response = supabase.table("class_subjects").select("class_id").eq("subject_id", subject_id).execute()
        return [item['class_id'] for item in response.data] if response.data else []
    except Exception:
        return []

def unenroll_student(username: str):
    if not is_db_connected(): return None, "Offline"
    return supabase.table("student_enrollments").delete().eq("user_username", username).execute()

def get_unassigned_students():
    all_students = [u for u in get_all_users() if u.get('role') == 'student']
    all_enrollments = supabase.table("student_enrollments").select("user_username").execute().data or []
    enrolled_usernames = {e['user_username'] for e in all_enrollments}
    return [s for s in all_students if s['username'] not in enrolled_usernames]

def update_training_links(subject_id: int, new_class_ids: list):
    if not is_db_connected(): return
    try:
        supabase.table("class_subjects").delete().eq("subject_id", subject_id).execute()
        if new_class_ids:
            links_to_insert = [{"subject_id": subject_id, "class_id": cid} for cid in new_class_ids]
            supabase.table("class_subjects").insert(links_to_insert).execute()
    except Exception as e:
        print(f"Erro ao atualizar vínculos do treinamento: {e}")

# --- Funções de Aulas e Conteúdo ---
def get_lessons():
    if not is_db_connected(): return []
    try:
        response = supabase.table("lessons").select("*").order("id").execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar aulas: {e}")
        return []

def get_lessons_for_subject(subject_id: int):
    if not is_db_connected(): return []
    try:
        response = supabase.table("lessons").select("*").eq("subject_id", subject_id).order("id").execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar aulas da disciplina {subject_id}: {e}")
        return []

def get_lesson_by_id(lesson_id: int):
    if not is_db_connected(): return None
    try:
        response = supabase.table("lessons").select("*").eq("id", lesson_id).execute()
        return response.data[0] if response.data else None
    except Exception:
        return None

def get_quiz_for_lesson(lesson_id: int):
    if not is_db_connected(): return None
    try:
        response = supabase.table("quizzes").select("id, title").eq("lesson_id", lesson_id).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Erro ao buscar quiz da aula {lesson_id}: {e}")
        return None

def get_quizzes_for_subject(subject_id: int):
    if not is_db_connected(): return []
    try:
        lessons_res = supabase.table("lessons").select("id").eq("subject_id", subject_id).execute()
        lesson_ids = [l['id'] for l in lessons_res.data]
        if not lesson_ids: return []
        quizzes_res = supabase.table("quizzes").select("id, title, lesson_id").in_("lesson_id", lesson_ids).execute()
        return quizzes_res.data
    except Exception as e:
        print(f"Erro ao buscar quizzes da disciplina {subject_id}: {e}")
        return []

def get_quiz_by_id(quiz_id: int):
    if not is_db_connected(): return None
    try:
        response = supabase.table("quizzes").select("*").eq("id", quiz_id).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Erro ao buscar quiz por ID {quiz_id}: {e}")
        return None

def get_quiz_questions(quiz_id: int):
    if not is_db_connected(): return []
    try:
        response = supabase.table("quiz_questions").select("*").eq("quiz_id", quiz_id).execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar questões do quiz {quiz_id}: {e}")
        return []

def create_lesson(title: str, subject_id: int, description: str, video_url: str):
    """Cria uma nova aula no banco."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("lessons").insert({
            "title": title, "subject_id": subject_id, "description": description, "video_url": video_url
        }).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def upsert_lesson(title: str, subject_id: int, description: str, video_url: str):
    """Cria ou atualiza uma aula. Retorna o ID da aula."""
    if not is_db_connected(): return None
    try:
        lesson_data = {
            "title": title,
            "subject_id": subject_id,
            "description": description,
            "video_url": video_url
        }
        # on_conflict usa as colunas com a constraint UNIQUE para fazer o upsert
        response = supabase.table("lessons").upsert(lesson_data, on_conflict="subject_id,title").execute()
        return response.data[0]['id']
    except Exception as e:
        print(f"Erro ao fazer upsert da aula '{title}': {e}")
        return None

def delete_lesson(lesson_id: int):
    """Remove uma aula do banco de dados."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        # Remove dependências manualmente para evitar erro de Foreign Key (caso falte CASCADE)
        supabase.table("forum_posts").delete().eq("lesson_id", lesson_id).execute()
        
        quizzes_res = supabase.table("quizzes").select("id").eq("lesson_id", lesson_id).execute()
        if quizzes_res.data:
            quiz_ids = [q['id'] for q in quizzes_res.data]
            if quiz_ids:
                supabase.table("quiz_questions").delete().in_("quiz_id", quiz_ids).execute()
                supabase.table("quizzes").delete().in_("id", quiz_ids).execute()
        response = supabase.table("lessons").delete().eq("id", lesson_id).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def create_quiz(lesson_id: int, title: str):
    """Cria um novo quiz associado a uma aula."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("quizzes").insert({"lesson_id": lesson_id, "title": title}).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def create_quiz_question(quiz_id: int, question_text: str, options: list, correct_index: int):
    """Cria uma nova questão para um quiz."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("quiz_questions").insert({
            "quiz_id": quiz_id, "question_text": question_text, "options": options, "correct_option_index": correct_index
        }).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def delete_quiz_question(question_id: int):
    """Remove uma questão de quiz do banco de dados."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("quiz_questions").delete().eq("id", question_id).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def get_all_quiz_questions():
    if not is_db_connected(): return []
    try:
        response = supabase.table('quiz_questions').select('*').execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Erro ao buscar todas as questões de quiz: {e}")
        return []

def update_quiz_question_options(question_id: int, new_options: list):
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("quiz_questions").update({"options": new_options}).eq("id", question_id).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def update_quiz_question_correct_index(question_id: int, correct_index: int):
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("quiz_questions").update({"correct_option_index": correct_index}).eq("id", question_id).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

# --- Funções de Avaliações (MN1, MN2, MN3, RM) ---

def get_assessments_by_subject(subject_id: int):
    """Busca todas as avaliações de uma disciplina."""
    if not is_db_connected(): return []
    try:
        response = supabase.table("assessments").select("*").eq("subject_id", subject_id).order("type").execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar avaliações: {e}")
        return []

def create_assessment(subject_id: int, type: str, title: str):
    """Cria uma nova avaliação (MN1, MN2, MN3, RM)."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("assessments").insert({
            "subject_id": subject_id, "type": type, "title": title
        }).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def get_assessment_questions(assessment_id: int):
    """Busca as questões de uma avaliação."""
    if not is_db_connected(): return []
    try:
        response = supabase.table("assessment_questions").select("*").eq("assessment_id", assessment_id).order("id").execute()
        return response.data
    except Exception:
        return []

def create_assessment_question(assessment_id: int, question_text: str, question_type: str, options: list, correct_index: int):
    """Cria uma questão para avaliação (Objetiva ou Subjetiva)."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        data = {
            "assessment_id": assessment_id,
            "question_text": question_text,
            "question_type": question_type, # 'objective' ou 'subjective'
            "options": options,
            "correct_option_index": correct_index
        }

        response = supabase.table("assessment_questions").insert(data).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def delete_assessment_question(question_id: int):
    """Remove uma questão de avaliação do banco de dados."""
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("assessment_questions").delete().eq("id", question_id).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def get_all_assessments():
    if not is_db_connected(): return []
    try:
        response = supabase.table("assessments").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        return []

def get_all_assessment_questions():
    if not is_db_connected(): return []
    try:
        response = supabase.table("assessment_questions").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        return []

def update_assessment_question_options(question_id: int, new_options: list):
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("assessment_questions").update({"options": new_options}).eq("id", question_id).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def update_assessment_question_correct_index(question_id: int, correct_index: int):
    if not is_db_connected(): return None, "Banco de dados não conectado"
    try:
        response = supabase.table("assessment_questions").update({"correct_option_index": correct_index}).eq("id", question_id).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def get_all_quiz_questions_for_subject(subject_id: int, assessment_type: str = None, workload: int = 40, scope_mode: str = 'auto', start_lesson: int = None, end_lesson: int = None):
    """Busca questões de quizzes filtradas pelo tipo de avaliação (MN1, MN2, etc)."""
    if not is_db_connected(): return []
    try:
        lessons_res = supabase.table("lessons").select("id, title").eq("subject_id", subject_id).order("id").execute()
        all_lessons = lessons_res.data
        
        if not all_lessons: return []

        target_lessons = []
        if scope_mode == 'manual' and start_lesson is not None and end_lesson is not None:
            for lesson in all_lessons:
                title = lesson.get('title', '')
                match = re.search(r'Aula\s*(\d+)', title, re.IGNORECASE)
                if match:
                    lesson_num = int(match.group(1))
                    if start_lesson <= lesson_num <= end_lesson:
                        target_lessons.append(lesson)
        else:
            lessons_per_week = 10 if workload == 80 else 8
            mn1_limit = lessons_per_week * 2
            mn2_start = mn1_limit
            mn2_limit = mn2_start + (lessons_per_week * 2)
            if assessment_type == 'MN1':
                target_lessons = all_lessons[:mn1_limit]
            elif assessment_type == 'MN2':
                target_lessons = all_lessons[mn2_start:mn2_limit]
            else:
                target_lessons = all_lessons

        if not target_lessons: target_lessons = all_lessons
        if not target_lessons: return []
        lesson_ids = [l['id'] for l in target_lessons]
        quizzes_res = supabase.table("quizzes").select("id").in_("lesson_id", lesson_ids).execute()
        quiz_ids = [q['id'] for q in quizzes_res.data] if quizzes_res.data else []
        if not quiz_ids: return []
        questions_res = supabase.table("quiz_questions").select("*").in_("quiz_id", quiz_ids).execute()
        return questions_res.data
    except Exception as e:
        print(f"Erro ao buscar banco de questões: {e}")
        return []

# --- Funções de Submissão e Controle de Avaliações ---
def get_user_progress_stats(username: str):
    if not is_db_connected(): return {"lessons": 0, "quizzes": 0, "forum": 0}
    history = get_user_history(username)
    unique_lessons = set()
    unique_quizzes = set()
    forum_posts = 0
    for item in history:
        act = item.get('activity', '')
        if act.startswith("Acessou a aula:"):
            unique_lessons.add(act)
        elif act.startswith("Concluiu Quiz:"):
            unique_quizzes.add(act.split('(')[0].strip())
        elif "mensagem no fórum" in act:
            forum_posts += 1
    return {"lessons": len(unique_lessons), "quizzes": len(unique_quizzes), "forum": forum_posts}

def get_student_submission(username: str, assessment_id: int):
    """Verifica se o aluno já realizou a avaliação."""
    if not is_db_connected(): return None
    try:
        res = supabase.table("student_assessments").select("*").eq("user_username", username).eq("assessment_id", assessment_id).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None

def get_student_submissions(username: str, assessment_id: int):
    if not is_db_connected(): return []
    try:
        res = supabase.table("student_assessments").select("*").eq("user_username", username).eq("assessment_id", assessment_id).order("submitted_at", desc=True).execute()
        return res.data
    except Exception as e:
        print(f"Erro ao buscar submissões do aluno: {e}")
        return []

def submit_assessment(username: str, assessment_id: int, answers: list, final_score: float = None):
    """
    Salva a submissão da prova.
    answers: lista de dicts {'question_id': int, 'type': str, 'value': ...}
    """
    if not is_db_connected(): return None, "Offline"
    try:
        # 1. Criar a submissão pai
        sub_res = supabase.table("student_assessments").insert({
            "user_username": username,
            "assessment_id": assessment_id,
            "status": "submitted",
            "score": final_score # Adiciona a nota final aqui
        }).execute()
        
        if not sub_res.data:
            return None, "Erro ao criar registro de submissão."
            
        submission_id = sub_res.data[0]['id']
        
        # 2. Inserir as respostas
        answers_data = []
        for ans in answers:
            entry = {
                "submission_id": submission_id,
                "question_id": ans['question_id'],
                "selected_option_index": ans.get('value'), # Para objetivas
                "answer_text": ans.get('text'),            # Para subjetivas
                "answer_link": ans.get('link')             # Para subjetivas
            }
            answers_data.append(entry)
            
        supabase.table("student_assessment_answers").insert(answers_data).execute()
        return True, None
    except Exception as e:
        return None, str(e)

def simulate_student_activities(username: str):
    """Simula a conclusão de todas as aulas e quizzes para um usuário."""
    if not is_db_connected(): return None, "Offline"
    try:
        lessons = get_lessons()
        if not lessons:
            return None, "Nenhuma aula encontrada para simular."
        history_entries = []
        # Simula acesso a todas as aulas e quizzes
        for lesson in lessons:
            history_entries.append({"username": username, "activity": f"Acessou a aula: {lesson['title']}"})
            quiz = get_quiz_for_lesson(lesson['id'])
            if quiz:
                history_entries.append({"username": username, "activity": f"Concluiu Quiz: {quiz['title']} (2/2)"})
        # Simula 15 posts no fórum para garantir liberação
        for _ in range(15):
            history_entries.append({"username": username, "activity": "Enviou mensagem no fórum"})

        supabase.table("user_history").insert(history_entries).execute()
        return True, None
    except Exception as e:
        return None, str(e)

def reset_student_data(username: str):
    """Zera o histórico, submissões e respostas de avaliações de um aluno."""
    if not is_db_connected(): return None, "Offline"
    try:
        supabase.table("user_history").delete().eq("username", username).execute()

        submissions_res = supabase.table("student_assessments").select("id").eq("user_username", username).execute()
        if submissions_res.data:
            submission_ids = [s['id'] for s in submissions_res.data]
            supabase.table("student_assessment_answers").delete().in_("submission_id", submission_ids).execute()
            supabase.table("student_assessments").delete().in_("id", submission_ids).execute()
        return True, None
    except Exception as e:
        return None, str(e)

def get_assessment_submissions_with_users(assessment_id: int):
    if not is_db_connected(): return []
    try:
        # Supabase permite join na query se as chaves estrangeiras estiverem certas
        # Sintaxe: tabela!fk(colunas)
        response = supabase.table("student_assessments")\
            .select("*, app_users!inner(name, ra)")\
            .eq("assessment_id", assessment_id)\
            .execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar submissões: {e}")
        return []

def get_submission_answers(submission_id: int):
    """Busca as respostas de uma submissão específica."""
    if not is_db_connected(): return []
    try:
        response = supabase.table("student_assessment_answers").select("*").eq("submission_id", submission_id).execute()
        return response.data
    except Exception:
        return []

def update_submission_score(submission_id: int, new_score: float):
    """Atualiza a nota final de uma submissão."""
    if not is_db_connected(): return None, "Offline"
    try:
        response = supabase.table("student_assessments").update({"score": new_score}).eq("id", submission_id).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

# --- Funções de Cronogramas (Gerador de Aulas) ---
def create_schedule(subject_id: int, content: str):
    """Salva um texto de cronograma para uma disciplina."""
    if not is_db_connected(): return None, "Offline"
    try:
        response = supabase.table("schedules").insert({"subject_id": subject_id, "content": content}).execute()
        return response.data, None
    except Exception as e:
        return None, str(e)

def get_latest_schedule(subject_id: int):
    """Busca o último cronograma salvo para a disciplina."""
    if not is_db_connected(): return None
    try:
        response = supabase.table("schedules").select("content").eq("subject_id", subject_id).order("created_at", desc=True).limit(1).execute()
        return response.data[0]['content'] if response.data else None
    except Exception:
        return None

def import_school_structure(text: str):
    """Processa um texto no formato Escola.txt e popula o banco."""
    if not is_db_connected(): return False, "Banco de dados não conectado"
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) < 2:
        return False, "Formato inválido. Mínimo necessário: Nome da Escola e GRE."

    logs = []
    try:
        # 1. Processar a Escola
        school_name = lines[0]
        school_gre = lines[1].split(':')[1].strip() if ':' in lines[1] else lines[1]
        
        school_id = upsert_school(name=school_name, gre=school_gre)
        if not school_id:
            return False, "Falha ao criar/atualizar escola."
        logs.append(f"✅ Escola processada: {school_name}")

        # 2. Processar Turmas e Disciplinas
        i = 2
        while i < len(lines):
            if (i + 1 < len(lines)) and lines[i+1].startswith("Código da Turma:"):
                class_name = lines[i]
                class_code = lines[i+1].split(":")[1].strip()
                class_id = upsert_class(name=class_name, code=class_code, school_id=school_id)
                if class_id:
                    logs.append(f"  🏫 Turma: {class_name}")
                    j = i + 2
                    while j < len(lines):
                        if (j + 1 >= len(lines)) or not lines[j+1].startswith("Código da Turma:"):
                            subject_name = lines[j]
                            subject_id = upsert_subject(name=subject_name)
                            if subject_id:
                                link_subject_to_class(class_id=class_id, subject_id=subject_id)
                                logs.append(f"    📘 Disciplina: {subject_name}")
                            j += 1
                        else: break
                    i = j
                else: i += 1
            else: i += 1
        return True, "\n".join(logs)
    except Exception as e:
        return False, str(e)
