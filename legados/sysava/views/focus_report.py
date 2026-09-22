"""
Relatório de Perda de Foco em Avaliações

Este plugin analisa o histórico de todos os usuários em busca de registros
que indiquem que um aluno saiu da tela durante uma avaliação.

Ele agrupa os resultados por aluno e avaliação, mostrando quantas vezes
a perda de foco foi detectada.
"""

import os
import sys
from collections import defaultdict

# --- Configuração de Path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    from legados.sysava.services import database as db
except ImportError as e:
    print(f"Erro de importação: {e}")
    sys.exit(1)


def generate_focus_report():
    """Busca e exibe o relatório de perda de foco."""
    print("\n--- INICIANDO ANÁLISE DE PERDA DE FOCO ---")

    history = db.get_all_history(limit=5000) # Aumenta o limite para pegar mais dados
    focus_loss_events = defaultdict(int)

    for event in history:
        activity = event.get('activity', '')
        if "Perdeu o foco durante a avaliação" in activity:
            username = event.get('username')
            # Extrai o nome da avaliação do log
            assessment_name = activity.split(":")[-1].strip()
            key = (username, assessment_name)
            focus_loss_events[key] += 1

    if not focus_loss_events:
        print("\n✅ Nenhuma ocorrência de perda de foco encontrada nos registros recentes.")
    else:
        print("\n🚨 Relatório de Perda de Foco Detectada:\n")
        for (username, assessment), count in sorted(focus_loss_events.items()):
            print(f"- Aluno: {username:<20} | Avaliação: {assessment:<40} | Tentativas de Saída: {count}")

    print("\n--- ANÁLISE CONCLUÍDA ---")

def main():
    print("="*50)
    print("PLUGIN RELATÓRIO DE FOCO EM AVALIAÇÕES")
    print("="*50)

    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path): load_dotenv(dotenv_path=env_path)
    if not db.is_db_connected(): print("\n❌ ERRO: Não foi possível conectar ao banco de dados."); return
    generate_focus_report()

if __name__ == "__main__":
    main()