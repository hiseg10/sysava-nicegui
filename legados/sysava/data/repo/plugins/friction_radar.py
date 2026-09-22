"""
Radar de Fricção do Curso

Este plugin analisa a estrutura dos cursos (disciplinas e aulas) em busca de
pontos de "fricção" que podem indicar dificuldades de aprendizagem ou baixo
engajamento.

Ele verifica:
1.  **Aulas sem Quiz:** Aulas que não possuem um quiz de fixação associado.
2.  **Aulas com Baixo Engajamento no Fórum:** Aulas com pouca ou nenhuma interação no fórum.
3.  **Aulas com Conteúdo Mínimo:** Aulas cujo texto descritivo é muito curto.
"""

import os
import sys

# --- Configuração de Path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    from legados.sysava.services import database as db
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("Certifique-se de que as dependências como 'python-dotenv' e 'supabase' estão instaladas no ambiente virtual.")
    sys.exit(1)


def analyze_course_friction():
    """
    Executa a análise em todas as disciplinas e aulas, imprimindo um relatório de fricção.
    """
    print("\n--- INICIANDO ANÁLISE DE FRICÇÃO DOS CURSOS ---")

    all_subjects = db.get_subjects()
    if not all_subjects:
        print("Nenhuma disciplina encontrada para analisar.")
        return

    total_issues = 0

    for subject in all_subjects:
        # Ignora disciplinas do tipo 'training' por enquanto
        if subject.get('type') == 'training':
            continue

        print(f"\n🔎 Analisando Disciplina: '{subject['name']}'")
        lessons = db.get_lessons_for_subject(subject['id'])
        
        if not lessons:
            print("   - Nenhuma aula encontrada nesta disciplina.")
            continue

        subject_issues_found = False
        for lesson in lessons:
            lesson_issues = []

            # 1. Verifica se a aula tem quiz
            quiz = db.get_quiz_for_lesson(lesson['id'])
            if not quiz:
                lesson_issues.append("Aula sem quiz de fixação.")

            # 2. Verifica engajamento no fórum (considera o post do bot)
            forum_posts = db.get_forum_posts(lesson_id=lesson['id'])
            if len(forum_posts) <= 1:
                lesson_issues.append("Baixo engajamento no fórum (0 ou 1 post).")

            # 3. Verifica se o conteúdo é muito curto
            description = lesson.get('description', '')
            if not description or len(description) < 200:
                lesson_issues.append(f"Conteúdo muito curto ({len(description)} caracteres).")

            if lesson_issues:
                subject_issues_found = True
                total_issues += len(lesson_issues)
                print(f"  - ⚠️  Aula: '{lesson['title']}'")
                for issue in lesson_issues:
                    print(f"    - {issue}")
        
        if not subject_issues_found:
            print("   - ✅ Nenhum ponto de fricção óbvio encontrado.")

    print("\n--- ANÁLISE CONCLUÍDA ---")
    print(f"Total de problemas potenciais identificados: {total_issues}")


def main():
    """Função principal que executa o plugin."""
    print("="*50)
    print("PLUGIN RADAR DE FRICÇÃO DO SYSAVA")
    print("="*50)

    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
    
    if not db.is_db_connected():
        print("\n❌ ERRO: Não foi possível conectar ao banco de dados.")
        return

    analyze_course_friction()

if __name__ == "__main__":
    main()