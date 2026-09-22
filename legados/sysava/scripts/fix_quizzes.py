import os
import re
import sys
from dotenv import load_dotenv
from supabase import create_client

def fix_quiz_titles():
    """
    Script para padronizar os títulos dos Quizzes no banco de dados.
    Padrão alvo: ## 📝 Quiz de Fixação: Aula XX - {disciplina}
    """
    
    # Carrega variáveis de ambiente do arquivo .env na raiz do projeto
    # Assume que o script está em /scripts e o .env em /
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    dotenv_path = os.path.join(root_dir, '.env')
    load_dotenv(dotenv_path)
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        print("❌ Erro: Credenciais do Supabase (SUPABASE_URL, SUPABASE_KEY) não encontradas no arquivo .env")
        print(f"   Caminho tentado: {dotenv_path}")
        return

    print("🔌 Conectando ao Supabase...")
    try:
        supabase = create_client(url, key)
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return

    print("📥 Buscando dados de Quizzes, Aulas e Disciplinas...")
    try:
        quizzes_resp = supabase.table("quizzes").select("*").execute()
        lessons_resp = supabase.table("lessons").select("*").execute()
        subjects_resp = supabase.table("subjects").select("*").execute()
        
        quizzes = quizzes_resp.data
        lessons = lessons_resp.data
        subjects = subjects_resp.data
    except Exception as e:
        print(f"❌ Erro ao buscar dados: {e}")
        return

    # Mapas para busca rápida
    lessons_map = {l['id']: l for l in lessons}
    subjects_map = {s['id']: s for s in subjects}

    print(f"🔍 Analisando {len(quizzes)} quizzes...")
    updated_count = 0

    for quiz in quizzes:
        lesson_id = quiz.get('lesson_id')
        if not lesson_id or lesson_id not in lessons_map:
            continue

        lesson = lessons_map[lesson_id]
        subject_id = lesson.get('subject_id')
        subject_name = subjects_map[subject_id]['name'] if subject_id in subjects_map else "Geral"
        
        lesson_title = lesson.get('title', '')

        # Tenta extrair "Aula XX" do título da aula
        match = re.search(r"(Aula\s*\d+)", lesson_title, re.IGNORECASE)
        
        if match:
            aula_part = match.group(1).title() # Ex: Aula 01
        else:
            # Se não encontrar "Aula XX", usa o título da aula (limitado a 30 chars)
            aula_part = lesson_title[:30] + "..." if len(lesson_title) > 30 else lesson_title

        # Constrói o novo título no padrão solicitado
        new_title = f"## 📝 Quiz de Fixação: {aula_part} - {subject_name}"

        if quiz['title'] != new_title:
            try:
                supabase.table("quizzes").update({"title": new_title}).eq("id", quiz['id']).execute()
                print(f"✅ [ID {quiz['id']}] Renomeado:\n   De:   {quiz['title']}\n   Para: {new_title}")
                updated_count += 1
            except Exception as e:
                print(f"❌ Erro ao atualizar quiz {quiz['id']}: {e}")
        
    print(f"\n🏁 Processo concluído! {updated_count} quizzes foram padronizados.")

def fix_local_md_files():
    """
    Varre a pasta data/Turmas e atualiza os cabeçalhos dos quizzes nos arquivos .md locais.
    """
    print("\n📂 Iniciando atualização dos arquivos locais (.md)...")
    
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    base_path = os.path.join(root_dir, 'data', 'Turmas')
    
    if not os.path.exists(base_path):
        print(f"❌ Diretório não encontrado: {base_path}")
        return

    count = 0
    
    for root, dirs, files in os.walk(base_path):
        md_files = [f for f in files if f.lower().endswith(".md")]
        if not md_files:
            continue
            
        # Tenta deduzir a disciplina pelo caminho (Turma/Disciplina/Semana)
        try:
            relative_path = os.path.relpath(root, base_path)
            path_parts = relative_path.split(os.sep)
        except ValueError:
            continue
            
        # Espera-se estrutura: Turma / Disciplina / Semana
        subject_name = path_parts[1] if len(path_parts) >= 2 else "Geral"

        for file in md_files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Busca título da aula (primeiro H1 ou nome do arquivo)
                h1_match = re.search(r'^#\s+(.*)', content, re.MULTILINE)
                lesson_title = h1_match.group(1).strip() if h1_match else file[:-3].replace('_', ' ')
                
                # Extrai "Aula XX" ou usa fallback
                match_aula = re.search(r"(Aula\s*\d+)", lesson_title, re.IGNORECASE)
                aula_part = match_aula.group(1).title() if match_aula else (lesson_title[:30] + "..." if len(lesson_title) > 30 else lesson_title)
                
                new_header = f"## 📝 Quiz de Fixação: {aula_part} - {subject_name}"
                
                # Substitui a linha do cabeçalho do Quiz (## ... Quiz ...)
                # Usa regex para encontrar qualquer variação de header de quiz
                new_content, subs = re.subn(r'^##\s*.*Quiz.*$', new_header, content, flags=re.MULTILINE | re.IGNORECASE)
                
                if subs > 0 and content != new_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"   ✏️ [Arquivo] Atualizado: {file}")
                    count += 1
            except Exception as e:
                print(f"❌ Erro ao processar arquivo {file}: {e}")

    print(f"✅ Atualização de arquivos concluída. {count} arquivos modificados.")

if __name__ == "__main__":
    fix_quiz_titles()
    fix_local_md_files()