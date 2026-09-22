"""
Auditoria e Backup do Banco de Dados

Este plugin realiza duas funções principais:
1.  **Auditoria Rápida:** Conta o número de registros nas tabelas principais (usuários, turmas, aulas, etc.) e imprime um resumo.
2.  **Backup em SQLite:** Extrai os dados de todas as tabelas importantes e os salva em um arquivo de banco de dados SQLite local (`.db`).

O arquivo de backup é nomeado com a data atual e salvo nesta mesma pasta de plugins.
"""

import os
import sys
import sqlite3
import json
import requests
from datetime import datetime

# --- Configuração de Path ---
# URL da sua API local rodando na porta 8000
API_URL = "http://127.0.0.1:8000"

# Adiciona o diretório raiz do projeto ao sys.path para que possamos importar os serviços.
# O script está em 'data/repo/plugins', subimos 4 níveis para chegar na raiz 'SysAva'.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    from legados.sysava.services import database as db
except ImportError as e:
    print(f"Erro de importação: {e}")
    print("Certifique-se de que as dependências como 'python-dotenv' e 'supabase' estão instaladas no ambiente virtual.")
    sys.exit(1)


def sync_local_to_supabase():
    """Puxa dados da API local e envia para o Supabase (Cloud)."""
    print("\n--- SINCRONIZANDO AUTOMAÇÃO: LOCAL -> SUPABASE ---")
    
    # Carrega mapeamentos de IDs para garantir a integridade referencial na nuvem
    try:
        all_classes = {} # Mapeia nomes/códigos para o 'code' (iSeduc ID)
        for c in db.get_classes():
            class_code = c.get('code')
            if class_code:
                for field in ['official_name', 'portal_name', 'name', 'code']:
                    val = c.get(field)
                    if val:
                        all_classes[str(val).strip().upper()] = class_code

        all_subjects = {s['name'].strip().upper(): s['id'] for s in db.get_subjects()}
    except Exception as e:
        print(f"     ⚠️ Falha ao carregar mapeamentos de IDs: {e}")
        all_classes, all_subjects = {}, {}

    # 1. Sincronizar Histórico de Aulas
    try:
        print("  -> Sincronizando 'historico_aulas'...")
        resp = requests.get(f"{API_URL}/historico")
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                item.pop('id', None)
                
                # Normalização para garantir o batimento com o mapa de IDs da nuvem
                t_name = item.get('turma', '').strip().upper()
                d_name = item.get('disciplina', '').strip().upper()
                
                # Injeção de IDs caso os campos venham vazios da API local (baseado no nome)
                resolved_code = all_classes.get(t_name)
                if resolved_code and not item.get('turma_id'):
                    item['turma_id'] = resolved_code
                
                if not item.get('disciplina_id') and d_name:
                    item['disciplina_id'] = all_subjects.get(d_name)

                # Ajustado para usar turma_id e disciplina_id no conflito, 
                # pois agora existe a UNIQUE CONSTRAINT no Supabase.
                db.supabase.table("historico_aulas").upsert(
                    item, 
                    on_conflict="data_aula,horario,turma_id,disciplina_id"
                ).execute()
            print(f"     ✅ {len(data)} registros de histórico sincronizados.")
    except Exception as e:
        print(f"     ⚠️ Falha ao sincronizar histórico: {e}")

    # 2. Sincronizar Planejamento
    try:
        print("  -> Sincronizando 'planejamento'...")
        resp = requests.get(f"{API_URL}/planejamento/pendente")
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                item.pop('id', None)

                t_name = item.get('turma', '').strip().upper()
                d_name = item.get('disciplina', '').strip().upper()
                
                resolved_code = all_classes.get(t_name)
                if resolved_code and not item.get('turma_id'):
                    item['turma_id'] = resolved_code
                
                if not item.get('disciplina_id') and d_name:
                    item['disciplina_id'] = all_subjects.get(d_name)

                # Atualizado para bater com a restrição UNIQUE da sua API:
                # data_planejada, horario, turma_id, disciplina_id
                db.supabase.table("planejamento").upsert(
                    item, on_conflict="data_planejada,horario,turma_id,disciplina_id"
                ).execute()
            print(f"     ✅ {len(data)} registros de planejamento sincronizados.")
    except Exception as e:
        print(f"     ⚠️ Falha ao sincronizar planejamento: {e}")

    # 3. Sincronizar Master Config (SQLite -> Cloud)
    try:
        print("  -> Sincronizando 'master_config'...")
        resp = requests.get(f"{API_URL}/config/all")
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                # item é {"key": "...", "value": "..."}
                # Se o valor for string, tentamos converter para JSON para o campo JSONB do Supabase
                val = item['value']
                if isinstance(val, str):
                    try: val = json.loads(val)
                    except: pass
                db.supabase.table("master_config").upsert({"key": item['key'], "value": val}).execute()
            print(f"     ✅ {len(data)} chaves de configuração sincronizadas.")
    except Exception as e:
        print(f"     ⚠️ Falha ao sincronizar configurações: {e}")

def repair_cloud_ids():
    """Busca registros no Supabase com FKs nulas e tenta corrigi-los usando os nomes."""
    print("\n--- REPARANDO INTEGRIDADE DAS CHAVES NO SUPABASE ---")
    try:
        all_classes = {}
        for c in db.get_classes():
            class_code = c.get('code')
            if class_code:
                for field in ['official_name', 'portal_name', 'name', 'code']:
                    val = c.get(field)
                    if val:
                        all_classes[str(val).strip().upper()] = class_code
                    
        all_subjects = {s['name'].strip().upper(): s['id'] for s in db.get_subjects()}
        
        for table in ["historico_aulas", "planejamento"]:
            print(f"  -> Verificando inconsistências em '{table}'...")
            # Busca registros onde pelo menos um ID está faltando
            res = db.supabase.table(table).select("*").or_("turma_id.is.null,disciplina_id.is.null").execute()
            
            repaired = 0
            for row in res.data:
                updates = {}
                t_name = row.get('turma', '').strip().upper()
                d_name = row.get('disciplina', '').strip().upper()

                resolved_code = all_classes.get(t_name)
                if resolved_code and not row.get('turma_id'):
                    updates['turma_id'] = resolved_code
                
                if not row.get('disciplina_id') and d_name:
                    updates['disciplina_id'] = all_subjects.get(d_name)

                if updates:
                    db.supabase.table(table).update(updates).eq("id", row['id']).execute()
                    repaired += 1
            if repaired > 0: print(f"     ✅ {repaired} registros órfãos reparados em '{table}'.")
    except Exception as e:
        print(f"     ⚠️ Falha no reparo de integridade: {e}")

def run_audit():
    """Realiza uma contagem de registros nas tabelas principais."""
    print("\n--- INICIANDO AUDITORIA RÁPIDA ---")

    # Mapeamento de tabelas para labels amigáveis (As 12 tabelas principais)
    audit_targets = {
        "app_users": "Usuários",
        "classes": "Turmas",
        "subjects": "Disciplinas",
        "lessons": "Aulas",
        "quizzes": "Quizzes",
        "quiz_questions": "Questões de Quiz",
        "assessments": "Avaliações (Provas)",
        "assessment_questions": "Questões de Prova",
        "attendance": "Registros de Frequência",
        "weekly_schedule": "Grade Horária",
        "student_enrollments": "Matrículas",
        "class_subjects": "Vínculos Turma/Disc",
        "historico_aulas": "Histórico de Automação (Robô)",
        "planejamento": "Fila de Planejamento",
        "master_config": "Espelhamento de Configurações"
    }
    
    results = {}

    for table, label in audit_targets.items():
        try:
            res = db.supabase.table(table).select("*", count='exact').execute()
            print(f"✅ {label}: {res.count}")
            results[table] = {"label": label, "count": res.count, "status": "ok"}
        except Exception:
            print(f"⚠️ {label}: Tabela ainda não existe no Supabase.")
            results[table] = {"label": label, "count": 0, "status": "missing"}

    # Salva o resumo para a API ler
    report_path = os.path.join(os.path.dirname(__file__), "audit_summary.json")
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
            
        print(f"--- AUDITORIA CONCLUÍDA ({len(audit_targets)} tabelas) ---\n")

    except Exception as e:
        print(f"❌ Erro durante a auditoria: {e}")


def run_backup():
    """Cria um backup do banco de dados em um arquivo SQLite."""
    print("\n--- INICIANDO BACKUP PARA SQLITE ---")

    # Tabelas a serem backupeadas
    TABLES_TO_BACKUP = [
        'app_users', 'classes', 'subjects', 'lessons', 'quizzes', 'quiz_questions',
        'assessments', 'assessment_questions', 'attendance', 'weekly_schedule',
        'student_enrollments', 'class_subjects', 'historico_aulas', 
        'planejamento', 'master_config'
    ]

    # Nome do arquivo de backup
    date_str = datetime.now().strftime("%Y-%m-%d")
    backup_filename = f"backup_SysAva_{date_str}.db"
    backup_filepath = os.path.join(os.path.dirname(__file__), backup_filename)

    try:
        # Conecta ao banco de dados SQLite (cria se não existir)
        conn = sqlite3.connect(backup_filepath)
        cursor = conn.cursor()
        print(f"💾 Arquivo de backup será salvo em: {backup_filepath}")

        for table_name in TABLES_TO_BACKUP:
            try:
                print(f"  -> Processando tabela: '{table_name}'...")
                
                # 1. Busca dados com paginação (O Supabase limita em 1000 por requisição)
                data = []
                start = 0
                page_size = 1000
                
                while True:
                    response = db.supabase.table(table_name).select("*")\
                        .range(start, start + page_size - 1).execute()
                    
                    page_data = response.data
                    if not page_data:
                        break
                    
                    data.extend(page_data)
                    if len(page_data) < page_size:
                        break
                    start += page_size

                if not data:
                    print(f"     - Tabela '{table_name}' está vazia. Pulando.")
                    continue

                # 2. Cria a tabela no SQLite
                columns = data[0].keys()
                
                # Dropamos a tabela antes de criar para garantir que o esquema no SQLite 
                # acompanhe as mudanças no Supabase (como a nova coluna 'class_id').
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join([f'{col} TEXT' for col in columns])})"
                cursor.execute(create_table_sql)

                # 4. Insere os dados
                placeholders = ', '.join(['?'] * len(columns))
                insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

                rows_to_insert = []
                for row in data:
                    # Converte listas/dicionários para string JSON para compatibilidade com SQLite
                    values = [str(v) if isinstance(v, (dict, list)) else v for v in row.values()]
                    rows_to_insert.append(tuple(values))
                
                cursor.executemany(insert_sql, rows_to_insert)
                print(f"     - {len(rows_to_insert)} registros salvos.")
            except Exception as e:
                print(f"     - ⚠️ Pulando tabela '{table_name}': Não encontrada na nuvem ou erro de acesso.")

        # Salva as alterações e fecha a conexão
        conn.commit()
        conn.close()

        print("\n✅ BACKUP CONCLUÍDO COM SUCESSO!")

    except Exception as e:
        print(f"❌ Erro durante o backup: {e}")


def main():
    """Função principal que executa o plugin."""
    print("="*50)
    print("PLUGIN DE AUDITORIA E BACKUP DO SYSAVA")
    print("="*50)

    # Carrega as variáveis de ambiente do arquivo .env na raiz do projeto
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        print("Arquivo .env carregado.")
    
    # Inicializa a conexão com o banco
    if not db.is_db_connected():
        print("\n❌ ERRO: Não foi possível conectar ao banco de dados.")
        print("Verifique se as variáveis SUPABASE_URL e SUPABASE_KEY estão no arquivo .env na raiz do projeto.")
        return

    print("\nConexão com o banco de dados estabelecida com sucesso.")
    
    # Primeiro, envia os dados locais da automação para a nuvem
    sync_local_to_supabase()
    
    # Repara registros órfãos que já estão no Supabase mas sem ID vinculado
    repair_cloud_ids()
    
    # Depois realiza a auditoria e o backup normal
    run_audit()
    run_backup()

if __name__ == "__main__":
    main()