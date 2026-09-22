"""
Plugin de Gerenciamento de Notas e Pontos Qualitativos (SysAva)

Este plugin permite que administradores e professores gerenciem as notas gerais
dos alunos e adicionem pontos qualitativos diários, salvando os dados em um
arquivo JSON local.

Uso: Acessível via menu 'Plugins' no painel administrativo do SysAva.
"""

import streamlit as st
import json
import os
import re
import sys
import pandas as pd
from datetime import datetime
from io import BytesIO
from legados.sysava.services.contexto_aulas import normalizar_para_matching

# Tenta importar Matplotlib para geração de PNG
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# --- Configurações de Caminho ---
PLUGIN_DIR = os.path.dirname(__file__)
SCORES_FILE = os.path.join(PLUGIN_DIR, "student_scores.json")
ATTENDANCE_FILE = os.path.join(PLUGIN_DIR, "student_attendance.json")

# Adiciona o diretório raiz do projeto ao sys.path para garantir que os módulos sejam encontrados.
# O script está em 'data/repo/plugins', então subimos 3 níveis para chegar à raiz.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def log_message(message, type="info"):
    """Exibe mensagens no Streamlit ou no Console dependendo do contexto."""
    try:
        if type == "error": st.error(message)
        elif type == "warning": st.warning(message)
        else: st.info(message)
    except:
        print(f"[{type.upper()}] {message}")

try:
    from legados.sysava.services import database as db
except ImportError:
    db = None
    log_message("Erro: Não foi possível importar o serviço de banco de dados.", "error")

@st.cache_data(ttl=600)
def load_json(file_path):
    """Carrega dados de um arquivo JSON. Retorna um dicionário vazio se o arquivo não existir ou estiver corrompido."""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            log_message(f"Arquivo '{file_path}' corrompido. Criando novo.", "warning")
            return {"students_data": {}}
        except Exception as e:
            log_message(f"Erro ao carregar JSON: {e}", "error")
            return {"students_data": {}}
    return {"students_data": {}}

@st.cache_data(ttl=300)
def get_cached_student_score(username, subject_id):
    """Wrapper para cachear a consulta de scores do banco de dados e evitar 431/timeouts."""
    if db:
        return db.get_student_score(username, filter_subject_id=subject_id)
    return {'total': 0.0}

def save_json(file_path, data):
    """Salva dados em um arquivo JSON."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log_message(f"Erro ao salvar JSON: {e}", "error")

def clean_col_label_for_export(col_name: str) -> str:
    """Higieniza e formata os cabeçalhos para o relatório exportado (sem emojis que quebram fontes)."""
    col_str = str(col_name).strip()
    col_str = re.sub(r'[\U00010000-\U0010ffff]', '', col_str).strip()
    col_str = re.sub(r'[^\w\s\(\)\.\-]', '', col_str).strip()
    mapping = {
        'NM1': 'N1 (T1)', 'NM2': 'N2 (T1)', 'NM3': 'N3 (T1)',
        'NM4': 'N1 (T2)', 'NM5': 'N2 (T2)', 'NM6': 'N3 (T2)',
        'NM7': 'N1 (T3)', 'NM8': 'N2 (T3)', 'NM9': 'N3 (T3)',
        'Engaj': 'Engaj.', 'Qualit': 'Qualitativo',
        'Final': 'Nota Final', 'Conc': 'Conceito',
        'Nome': 'Estudante'
    }
    for k, v in mapping.items():
        if k in col_str:
            return v
    return col_str

def create_scores_png(df, class_name, subject_name, school_name, prof_name, selected_trim="1º Trimestre"):
    """Gera uma imagem PNG colorida e diagramada para comentar as notas em sala de aula."""
    export_df = df.drop(columns=['Username']) if 'Username' in df.columns else df.copy()
    
    # Remove colunas de conceito e nota final manual
    cols_to_drop = [c for c in export_df.columns if any(k in c for k in ['Conc', 'Conceito', 'Final', '📝', '🎓'])]
    export_df = export_df.drop(columns=cols_to_drop, errors='ignore')

    # Filtra colunas de acordo com o trimestre selecionado
    if selected_trim == "1º Trimestre":
        active_nms = ['NM1', 'NM2', 'NM3', 'N1 (T1)', 'N2 (T1)', 'N3 (T1)']
    elif selected_trim == "2º Trimestre":
        active_nms = ['NM4', 'NM5', 'NM6', 'N1 (T2)', 'N2 (T2)', 'N3 (T2)']
    elif selected_trim == "3º Trimestre":
        active_nms = ['NM7', 'NM8', 'NM9', 'N1 (T3)', 'N2 (T3)', 'N3 (T3)']
    else:
        active_nms = [f'NM{i}' for i in range(1, 10)]

    keep_cols = []
    for c in export_df.columns:
        if c in ['Nome', 'Estudante', '🌐 Engaj.', 'Engaj.', 'Média', 'Média Final', '⭐ Qualit.', 'Qualitativo']:
            keep_cols.append(c)
        elif any(nm == c or nm in c for nm in active_nms):
            keep_cols.append(c)

    export_df = export_df[[c for c in keep_cols if c in export_df.columns]]
    export_df.columns = [clean_col_label_for_export(c) for c in export_df.columns]

    # Higieniza nome da escola
    clean_school = re.sub(r'^(?:(?:Escola|Institui[cç][aã]o|School)\s*:\s*)+', '', str(school_name), flags=re.IGNORECASE).strip()

    n_rows = len(export_df)
    fig_height = max(6.0, n_rows * 0.45 + 3.2)
    fig, ax = plt.subplots(figsize=(15, fig_height))
    ax.axis('off')

    # Cabeçalho Principal (Visual institucional limpo)
    plt.text(0.5, 0.97, clean_school, fontsize=16, fontweight='bold', color='#1a252f', ha='center', va='top', transform=fig.transFigure)
    plt.text(0.5, 0.93, f"Quadro de Notas — {class_name}", fontsize=13, fontweight='bold', color='#2c3e50', ha='center', va='top', transform=fig.transFigure)
    plt.text(0.5, 0.89, f"Disciplina: {subject_name} | Período: {selected_trim} | Professor: {prof_name}", fontsize=10, color='#555555', ha='center', va='top', transform=fig.transFigure)

    # Faixa de Legenda com Cores
    plt.text(
        0.5, 0.85, 
        "Legenda: [Verde: >= 6.0 (Aprovado/Bom)]  |  [Amarelo: 4.0 - 5.9 (Em Alerta)]  |  [Vermelho: < 4.0 (Abaixo da Media)]  |  [Azul: Engajamento & Qualitativo]",
        fontsize=8.5, ha='center', va='top', transform=fig.transFigure, style='italic', color='#333333'
    )

    the_table = ax.table(
        cellText=export_df.values, 
        colLabels=export_df.columns, 
        cellLoc='center', 
        loc='center',
        bbox=[0, 0, 1, 0.81]
    )

    the_table.auto_set_font_size(False)
    the_table.set_fontsize(8.5)
    the_table.scale(1.2, 1.6)

    # Estilização e Coloração das Células
    for (row, col), cell in the_table.get_celld().items():
        if row == 0:
            # Cabeçalho da Tabela
            cell.set_facecolor('#203a43')
            cell.get_text().set_color('#ffffff')
            cell.get_text().set_weight('bold')
        else:
            col_name = export_df.columns[col]
            val = export_df.iloc[row - 1, col]

            if col_name == 'Estudante':
                cell.set_facecolor('#ffffff' if row % 2 == 0 else '#fdfdfe')
                cell.get_text().set_horizontalalignment('left')
                cell.get_text().set_color('#111111')
            elif col_name in ['Engaj.', 'Qualitativo']:
                cell.set_facecolor('#e8f4f8') # Azul suave
                cell.get_text().set_color('#0c5460')
                cell.get_text().set_weight('bold')
            elif col_name == 'Conceito':
                conc = str(val).strip().upper()
                if conc in ['A', 'B']:
                    cell.set_facecolor('#d4edda')
                    cell.get_text().set_color('#155724')
                elif conc == 'C':
                    cell.set_facecolor('#fff3cd')
                    cell.get_text().set_color('#856404')
                elif conc in ['D', 'E']:
                    cell.set_facecolor('#f8d7da')
                    cell.get_text().set_color('#721c24')
                else:
                    cell.set_facecolor('#f8f9fa')
                cell.get_text().set_weight('bold')
            else:
                # Notas numéricas (N1, N2, N3, Média, Nota Final)
                try:
                    num_v = float(val)
                    if num_v >= 6.0:
                        cell.set_facecolor('#d4edda') # Verde suave
                        cell.get_text().set_color('#155724')
                        cell.get_text().set_weight('bold')
                    elif num_v >= 4.0:
                        cell.set_facecolor('#fff3cd') # Amarelo suave
                        cell.get_text().set_color('#856404')
                        cell.get_text().set_weight('bold')
                    elif num_v > 0.0:
                        cell.set_facecolor('#f8d7da') # Vermelho suave
                        cell.get_text().set_color('#721c24')
                        cell.get_text().set_weight('bold')
                    else:
                        cell.set_facecolor('#fdfdfe' if row % 2 == 0 else '#f8f9fa')
                        cell.get_text().set_color('#888888')
                except (ValueError, TypeError):
                    cell.set_facecolor('#ffffff')

    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=200)
    plt.close(fig)
    return buf.getvalue()

def generate_scores_html_report(df, class_name, subject_name, school_name, prof_name, selected_trim="1º Trimestre"):
    """Gera um relatório HTML interativo, colorido e com explicação de notas para apresentação em sala."""
    export_df = df.drop(columns=['Username']) if 'Username' in df.columns else df.copy()

    # Remove colunas de conceito e nota final manual (para visual limpo e focado)
    cols_to_drop = [c for c in export_df.columns if any(k in c for k in ['Conc', 'Conceito', 'Final', '📝', '🎓'])]
    export_df = export_df.drop(columns=cols_to_drop, errors='ignore')

    # Filtra colunas de acordo com o trimestre selecionado
    if selected_trim == "1º Trimestre":
        active_nms = ['NM1', 'NM2', 'NM3', 'N1 (T1)', 'N2 (T1)', 'N3 (T1)']
    elif selected_trim == "2º Trimestre":
        active_nms = ['NM4', 'NM5', 'NM6', 'N1 (T2)', 'N2 (T2)', 'N3 (T2)']
    elif selected_trim == "3º Trimestre":
        active_nms = ['NM7', 'NM8', 'NM9', 'N1 (T3)', 'N2 (T3)', 'N3 (T3)']
    else:
        active_nms = [f'NM{i}' for i in range(1, 10)]

    keep_cols = []
    for c in export_df.columns:
        if c in ['Nome', 'Estudante', '🌐 Engaj.', 'Engaj.', 'Média', 'Média Final', '⭐ Qualit.', 'Qualitativo']:
            keep_cols.append(c)
        elif any(nm == c or nm in c for nm in active_nms):
            keep_cols.append(c)

    export_df = export_df[[c for c in keep_cols if c in export_df.columns]]
    export_df.columns = [clean_col_label_for_export(c) for c in export_df.columns]

    # Higieniza nome da escola
    clean_school = re.sub(r'^(?:(?:Escola|Institui[cç][aã]o|School)\s*:\s*)+', '', str(school_name), flags=re.IGNORECASE).strip()

    rows_html = ""
    for _, row in export_df.iterrows():
        cells_html = ""
        for col_name in export_df.columns:
            val = row[col_name]
            cell_style = "padding: 9px 12px; border-bottom: 1px solid #e2e8f0; text-align: center;"
            
            if col_name == "Estudante":
                cell_style += " text-align: left; font-weight: 600; color: #1e293b;"
                cells_html += f'<td style="{cell_style}">{val}</td>'
            elif col_name in ["Engaj.", "Qualitativo"]:
                cell_style += " background-color: #f0fdf4; color: #166534; font-weight: 600;"
                cells_html += f'<td style="{cell_style}">{val}</td>'
            else:
                try:
                    num_v = float(val)
                    if num_v >= 6.0:
                        n_style = "background-color: #dcfce7; color: #166534; font-weight: bold;"
                    elif num_v >= 4.0:
                        n_style = "background-color: #fef9c3; color: #854d0e; font-weight: bold;"
                    elif num_v > 0.0:
                        n_style = "background-color: #fee2e2; color: #991b1b; font-weight: bold;"
                    else:
                        n_style = "color: #94a3b8;"
                    cells_html += f'<td style="{cell_style} {n_style}">{num_v:.2f}</td>'
                except (ValueError, TypeError):
                    cells_html += f'<td style="{cell_style}">{val}</td>'

        rows_html += f"<tr>{cells_html}</tr>"

    headers_html = "".join([f'<th style="padding: 11px 12px; background-color: #1e293b; color: white; text-align: center; font-size: 13px; font-weight: 600;">{c}</th>' for c in export_df.columns])

    html_content = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Quadro de Notas — {class_name}</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
        .card {{ background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.08); padding: 28px; max-width: 1200px; margin: auto; }}
        .header {{ text-align: center; margin-bottom: 18px; border-bottom: 2px solid #e2e8f0; padding-bottom: 16px; }}
        .header h1 {{ margin: 0; font-size: 20px; color: #0f172a; font-weight: bold; letter-spacing: -0.01em; }}
        .header h2 {{ margin: 6px 0 4px 0; font-size: 15px; color: #334155; }}
        .header p {{ margin: 4px 0; font-size: 13px; color: #64748b; }}
        .legend {{ display: flex; justify-content: center; gap: 20px; margin: 14px 0 4px 0; font-size: 12px; }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; font-weight: 500; }}
        .dot {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }}
        .explanation-box {{ margin-top: 26px; padding: 18px 22px; background: #f8fafc; border-radius: 10px; border: 1px solid #e2e8f0; border-left: 5px solid #3b82f6; font-size: 13px; color: #334155; line-height: 1.6; }}
        .explanation-title {{ margin: 0 0 10px 0; font-size: 14px; font-weight: bold; color: #0f172a; display: flex; align-items: center; gap: 8px; }}
        .explanation-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .card {{ box-shadow: none; padding: 0; max-width: 100%; border: none; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>{clean_school}</h1>
            <h2>Relatório de Notas — {class_name}</h2>
            <p><strong>Disciplina:</strong> {subject_name} &nbsp;|&nbsp; <strong>Período:</strong> {selected_trim} &nbsp;|&nbsp; <strong>Professor:</strong> {prof_name}</p>
            <div class="legend">
                <div class="legend-item"><span class="dot" style="background:#dcfce7; border: 1px solid #86efac;"></span> ≥ 6.0 (Aprovado)</div>
                <div class="legend-item"><span class="dot" style="background:#fef9c3; border: 1px solid #fde047;"></span> 4.0 a 5.9 (Em Alerta)</div>
                <div class="legend-item"><span class="dot" style="background:#fee2e2; border: 1px solid #fca5a5;"></span> &lt; 4.0 (Abaixo da Média)</div>
                <div class="legend-item"><span class="dot" style="background:#f0fdf4; border: 1px solid #bbf7d0;"></span> Engajamento &amp; Qualitativo</div>
            </div>
        </div>
        <table>
            <thead>
                <tr>{headers_html}</tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <div class="explanation-box">
            <div class="explanation-title">📘 Composição e Critérios de Formação das Notas</div>
            <div class="explanation-grid">
                <div>
                    <p style="margin: 3px 0;"><strong>📝 N1 e N2 (Avaliações Formativas):</strong> Notas obtidas nas avaliações e atividades teóricas/práticas realizadas no ambiente SysAva.</p>
                    <p style="margin: 3px 0;"><strong>🏆 N3 (Engajamento e Prática):</strong> Nota composta pela participação contínua: soma do <em>Score de Engajamento</em> (quizzes e fórum) + <em>Pontos Qualitativos</em> (atividades em sala) + <em>Bônus de Frequência</em>.</p>
                </div>
                <div>
                    <p style="margin: 3px 0;"><strong>📊 Média do Período:</strong> Média aritmética das notas lançadas no trimestre: <code>Média = (N1 + N2 + N3) ÷ 3</code>.</p>
                    <p style="margin: 3px 0;"><strong>🎯 Metas de Desempenho:</strong> <span style="color:#166534; font-weight:bold;">≥ 6.0</span> (Aprovado) &nbsp;|&nbsp; <span style="color:#854d0e; font-weight:bold;">4.0 a 5.9</span> (Alerta) &nbsp;|&nbsp; <span style="color:#991b1b; font-weight:bold;">&lt; 4.0</span> (Recuperação).</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html_content

def get_student_qualitative_points(student_json, selected_subject_id, selected_subject_name=None, lesson_sub_map=None, matching_subject_ids=None, all_subjects_mode=False):
    """Calcula os pontos qualitativos do aluno (atividades diárias + lançamentos manuais) com teto máximo de 6.0 pontos."""
    all_points = student_json.get("daily_qualitative_points", [])
    if not all_points:
        return 0.0

    if selected_subject_id is None or all_subjects_mode:
        return min(6.0, round(sum(float(p.get('points', 0)) for p in all_points), 2))

    sid_str = str(selected_subject_id)
    matching_ids = set(matching_subject_ids or [])
    matching_ids.add(selected_subject_id)
    matching_str_ids = {str(i) for i in matching_ids if i is not None}

    total_pts = 0.0
    for p in all_points:
        p_sid = p.get('subject_id')
        p_lid = p.get('lesson_id')
        pts = float(p.get('points', 0))

        # Se tem lesson_id mas não tem subject_id, resolve pelo mapa de aulas
        if p_sid is None and p_lid and lesson_sub_map and p_lid in lesson_sub_map:
            p_sid = lesson_sub_map[p_lid]

        # 1. Bate direto com a disciplina atual ou equivalentes
        if p_sid is not None and (p_sid in matching_ids or str(p_sid) in matching_str_ids):
            total_pts += pts
        # 2. Ponto sem disciplina vinculada (atribuído de forma geral)
        elif p_sid is None:
            total_pts += pts

    return min(6.0, round(total_pts, 2))

def get_student_attendance_stats(class_id, subject_id, students, matching_subject_ids=None):
    """Calcula a frequência (%) de cada aluno a partir dos registros do plugin de presença."""
    att_data = load_json(ATTENDANCE_FILE)
    class_key = str(class_id)
    subj_keys = [str(subject_id)] if subject_id is not None else []
    if matching_subject_ids:
        subj_keys.extend([str(sid) for sid in matching_subject_ids if sid is not None])

    class_history = att_data.get(class_key, {})
    
    # Coleta todas as datas registradas para as disciplinas correspondentes
    subject_history = {}
    for sk in subj_keys:
        if sk in class_history and isinstance(class_history[sk], dict):
            for dk, entries in class_history[sk].items():
                if isinstance(entries, dict):
                    if dk not in subject_history:
                        subject_history[dk] = {}
                    subject_history[dk].update(entries)

    stats = {}
    all_dates = list(subject_history.keys())
    
    for s in students:
        u = s['username']
        p_cnt = 0
        f_cnt = 0
        a_cnt = 0
        for dk in all_dates:
            stat = subject_history[dk].get(u)
            if stat == "Presente": p_cnt += 1
            elif stat == "Falta": f_cnt += 1
            elif stat == "Atraso": a_cnt += 1

        total_days = p_cnt + f_cnt + a_cnt
        freq_pct = round((p_cnt + a_cnt) / total_days * 100, 1) if total_days > 0 else 0.0
        stats[u] = {
            "presencas": p_cnt,
            "faltas": f_cnt,
            "atrasos": a_cnt,
            "total_aulas": total_days,
            "freq_pct": freq_pct
        }
        
    return stats

def run_cli_report():
    """Executa um relatório no terminal quando o plugin é chamado como script externo."""
    print("\n" + "="*50)
    print("📊 RELATÓRIO DE ESCORES E PONTOS QUALITATIVOS")
    print("="*50)
    
    data = load_json(SCORES_FILE)
    students = data.get("students_data", {})
    
    if not students:
        print("Nenhum dado de aluno encontrado no arquivo JSON.")
        return

    for username, info in students.items():
        score = info.get("overall_score", 0)
        grade = info.get("overall_grade", "N/A")
        q_points = len(info.get("daily_qualitative_points", []))
        print(f"Estudante: {info['name']} ({username})")
        print(f"  - Score: {score} | Grade: {grade}")
        print(f"  - Registros Qualitativos: {q_points}")
        print("-" * 30)
    print("="*50 + "\n")

def show_student_scores():
    """Renderiza a interface para gerenciar escores e pontos qualitativos dos alunos."""
    st.title("📊 Gerenciador de Notas e Pontos Qualitativos")

    if db is None:
        st.error("Serviço de banco de dados não disponível.")
        return

    # Busca informações da instituição e professor para os labels do PNG
    school_info = db.get_school()
    school_name = school_info.get('name', 'SysAva') if school_info else "SysAva"
    prof_name = st.session_state.get('usuario', 'Professor')

    # Carrega os dados existentes
    all_scores_data = load_json(SCORES_FILE)
    if "students_data" not in all_scores_data:
        all_scores_data["students_data"] = {}

    # --- SIDEBAR: Seleção de Turma e Disciplina ---
    with st.sidebar:
        st.header("Filtros")
        classes = db.get_classes()
        # Mapeia ID para objeto completo para facilitar exibição composta
        class_options = {c['name']: c['id'] for c in classes}
        # Cria um mapeamento de exibição: "Nome Amigável (Nome Oficial)"
        class_display = {c['name']: f"{c['name']} ({c.get('official_name', 'S/N Oficial')})" for c in classes}
        
        selected_class_name = st.selectbox(
            "Selecione a Turma", 
            ["-- Selecione --"] + list(class_options.keys()),
            format_func=lambda x: class_display.get(x, x)
        )

        selected_subject_id = None
        selected_subject_name = "Visão Geral"

        if selected_class_name != "-- Selecione --":
            class_id = class_options[selected_class_name]
            subjects = db.get_subjects_for_class(class_id)
            # Filtra apenas disciplinas ativas configuradas em Admin > Turmas
            subjects = [s for s in subjects if s.get('is_active', True)]
            
            subject_options = {"Visão Geral (Todas)": None}
            for s in subjects:
                s_name = s['name'].strip()
                if s_name not in subject_options:
                    subject_options[s_name] = s['id']

            selected_subject_name = st.selectbox("Selecione a Disciplina", list(subject_options.keys()))
            selected_subject_id = subject_options[selected_subject_name]
        else:
            st.info("Selecione uma turma para carregar o quadro de notas.")
            return

        st.divider()
        selected_trim_opt = st.radio(
            "Filtrar por Período",
            ["1º Trimestre", "2º Trimestre", "3º Trimestre", "Visão Geral"],
            index=0,
            horizontal=True,
            key="trim_selector"
        )
        st.session_state['selected_trimester'] = selected_trim_opt

    if selected_class_name == "-- Selecione --":
            st.info("Selecione uma turma para carregar o quadro de notas.")
            return

    # --- CARREGAMENTO DE ALUNOS ---
    students = db.get_students_by_class(class_id)
    if not students:
        st.warning(f"Nenhum aluno encontrado na turma {selected_class_name}.")
        return

    st.subheader(f"📋 Quadro de Notas: {selected_class_name}")
    st.caption(f"Disciplina: {selected_subject_name}")

    # --- CARREGAMENTO DE AVALIAÇÕES E MAPA DE AULAS DO BANCO ---
    asmt_lookup = {k: {} for k in ["MN1", "MN2", "MN3", "Outros1", "Outros2", "Outros3", "Outros4"]}
    lesson_sub_map = {}
    matching_subject_ids = {selected_subject_id} if selected_subject_id is not None else set()
    
    if db and db.is_db_connected():
        try:
            # Mapa de todas as aulas para suas disciplinas para resolução precisa de pontos de atividades
            lessons_db = db.supabase.table("lessons").select("id, subject_id").execute().data or []
            lesson_sub_map = {l['id']: l['subject_id'] for l in lessons_db}

            if selected_subject_name and selected_subject_name != "Visão Geral":
                norm_target = normalizar_para_matching(selected_subject_name)
                all_subjs = db.get_subjects()
                for s in all_subjs:
                    s_norm = normalizar_para_matching(s['name'])
                    if (s_norm in norm_target or norm_target in s_norm) and len(s_norm) > 3:
                        matching_subject_ids.add(s['id'])
        except Exception:
            pass

    if selected_subject_id is not None:
        try:
            assessments = db.get_assessments_by_subject(selected_subject_id)
            assessments = sorted(assessments, key=lambda x: x.get('created_at', x['id']))
            
            outros_found = 0
            for a in assessments:
                a_type = str(a.get('type', ''))
                target_key = None
                
                if a_type in ["MN1", "MN2", "MN3"]:
                    target_key = a_type
                elif a_type == "Outros":
                    outros_found += 1
                    target_key = f"Outros{outros_found}" if outros_found <= 4 else None
                
                if target_key and target_key in asmt_lookup:
                    subs = db.get_assessment_submissions_with_users(a['id'])
                    for s in subs:
                        user_info = s.get('app_users') or {}
                        u_name = user_info.get('username')
                        u_real_name = user_info.get('name')
                        u_score = s.get('score')
                        
                        if u_score is not None:
                            if u_name:
                                if u_name not in asmt_lookup[target_key] or u_score > asmt_lookup[target_key][u_name]:
                                    asmt_lookup[target_key][u_name] = u_score
                            if u_real_name:
                                if u_real_name not in asmt_lookup[target_key] or u_score > asmt_lookup[target_key][u_real_name]:
                                    asmt_lookup[target_key][u_real_name] = u_score
        except Exception:
            pass

    # Prepara a lista de dados para o Dataframe (Quadro da Turma)
    table_rows = []
    for s in students:
        username = s['username']
        
        # Inicializa aluno no JSON se não existir
        if username not in all_scores_data["students_data"]:
            all_scores_data["students_data"][username] = {
                "name": s['name'], "overall_score": 0, "overall_grade": None, "subjects": {}, "daily_qualitative_points": [],
                "overall_nm1": 0.0, "overall_nm2": 0.0, "overall_nm3": 0.0, "overall_outros1": 0.0, "overall_outros2": 0.0
            }

        student_json = all_scores_data["students_data"][username]
        if "subjects" not in student_json: student_json["subjects"] = {}
        if "daily_qualitative_points" not in student_json: student_json["daily_qualitative_points"] = []

        # Garante que as chaves de notas gerais existam para todos os alunos (correção de inconsistência)
        for key in ["overall_nm1", "overall_nm2", "overall_nm3", "overall_outros1", "overall_outros2"]:
            if key not in student_json:
                # Inicializa todas as 9 notas e as gerais
                student_json.update({f"overall_nm{i}": 0.0 for i in range(1, 10)})
        
        
        # Inicializa variáveis locais para evitar NameError
        nm1, nm2, nm3, nm4, nm5, nm6, nm7, nm8, nm9 = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        outros1, outros2 = 0.0, 0.0
        manual_score, manual_grade = 0.0, ""

        # Busca score calculado pelo sistema
        calc = get_cached_student_score(username, selected_subject_id)
        
        # Busca dados salvos manualmente
        if selected_subject_id is None:
            manual_score = student_json.get("overall_score", 0)
            manual_grade = student_json.get("overall_grade", "")
            nm1 = student_json.get("overall_nm1", 0.0)
            nm2 = student_json.get("overall_nm2", 0.0)
            nm3 = student_json.get("overall_nm3", 0.0)
            nm4 = student_json.get("overall_nm4", 0.0)
            nm5 = student_json.get("overall_nm5", 0.0)
            nm6 = student_json.get("overall_nm6", 0.0)
            nm7 = student_json.get("overall_nm7", 0.0)
            nm8 = student_json.get("overall_nm8", 0.0)
            nm9 = student_json.get("overall_nm9", 0.0)
            outros1 = student_json.get("overall_outros1", 0.0)
            outros2 = student_json.get("overall_outros2", 0.0)
        else:
            sid_str = str(selected_subject_id)
            if "subjects" not in student_json:
                student_json["subjects"] = {}
            
            if sid_str not in student_json["subjects"]:
                student_json["subjects"][sid_str] = {
                    "score": calc.get('total', 0.0), "grade": "",
                    "T1": {"N1": 0.0, "N2": 0.0, "N3": 0.0},
                    "T2": {"N1": 0.0, "N2": 0.0, "N3": 0.0},
                    "T3": {"N1": 0.0, "N2": 0.0, "N3": 0.0}
                }
            
            sub_data = student_json["subjects"].get(sid_str, {})
            manual_score = sub_data.get("score", 0)
            manual_grade = sub_data.get("grade", "")

            # Carrega as notas da estrutura aninhada
            t1_data = sub_data.get("T1", {})
            t2_data = sub_data.get("T2", {})
            t3_data = sub_data.get("T3", {})

            # Lógica de retrocompatibilidade: Tenta ler a nova estrutura aninhada.
            # Se falhar, lê a estrutura antiga (nm1, nm2, etc.) para não perder dados.
            nm1 = t1_data.get("N1", sub_data.get("nm1", 0.0))
            nm2 = t1_data.get("N2", sub_data.get("nm2", 0.0))
            nm3 = t1_data.get("N3", sub_data.get("nm3", 0.0))
            nm4 = t2_data.get("N1", sub_data.get("nm4", 0.0))
            nm5 = t2_data.get("N2", sub_data.get("nm5", 0.0))
            nm6 = t2_data.get("N3", sub_data.get("nm6", 0.0))
            nm7 = t3_data.get("N1", sub_data.get("nm7", 0.0))
            nm8 = t3_data.get("N2", sub_data.get("nm8", 0.0))
            nm9 = t3_data.get("N3", sub_data.get("nm9", 0.0))

        # --- LÓGICA DE FORMAÇÃO DE NOTAS (Simplificada) ---
        system_score = round(float(calc['total']), 2)

        # Busca bases de notas (Prioriza Avaliações Específicas > Outros > Manual)
        db_mn1 = asmt_lookup["MN1"].get(username, asmt_lookup["MN1"].get(s['name']))
        db_mn2 = asmt_lookup["MN2"].get(username, asmt_lookup["MN2"].get(s['name']))
        db_mn3 = asmt_lookup["MN3"].get(username, asmt_lookup["MN3"].get(s['name']))
        db_ot1 = asmt_lookup["Outros1"].get(username, asmt_lookup["Outros1"].get(s['name']))
        db_ot2 = asmt_lookup["Outros2"].get(username, asmt_lookup["Outros2"].get(s['name']))
        db_ot3 = asmt_lookup["Outros3"].get(username, asmt_lookup["Outros3"].get(s['name']))
        db_ot4 = asmt_lookup["Outros4"].get(username, asmt_lookup["Outros4"].get(s['name']))

        val_ot1 = db_ot1 if db_ot1 is not None else db_ot3
        base_nm1 = round(float(db_mn1 if db_mn1 is not None else (val_ot1 if val_ot1 is not None else nm1)), 2)
        
        val_ot2 = db_ot2 if db_ot2 is not None else db_ot4
        base_nm2 = round(float(db_mn2 if db_mn2 is not None else (val_ot2 if val_ot2 is not None else nm2)), 2)

        base_nm3 = round(float(db_mn3 if db_mn3 is not None else nm3), 2)
        
        # Calcula pontos qualitativos acumulados (atividades diárias + lançamentos manuais)
        qual_manual = get_student_qualitative_points(
            student_json=student_json,
            selected_subject_id=selected_subject_id,
            selected_subject_name=selected_subject_name,
            lesson_sub_map=lesson_sub_map,
            matching_subject_ids=matching_subject_ids
        )
        
        # Lógica simplificada: As notas são o que foi digitado ou o que veio do banco.
        f_nm1 = base_nm1
        f_nm2 = base_nm2
        f_nm3 = base_nm3
        
        # Lógica de Média por Trimestre
        t1_notes = [nm1, nm2, nm3]
        t2_notes = [nm4, nm5, nm6]
        t3_notes = [nm7, nm8, nm9]

        # Média estrita (N1 + N2 + N3) / 3 para cada trimestre
        media_t1 = round((float(nm1) + float(nm2) + float(nm3)) / 3.0, 2)
        media_t2 = round((float(nm4) + float(nm5) + float(nm6)) / 3.0, 2)
        media_t3 = round((float(nm7) + float(nm8) + float(nm9)) / 3.0, 2)

        # Média calculada para o período ativo
        current_trim_view = st.session_state.get('selected_trimester', "1º Trimestre")
        if current_trim_view == "1º Trimestre":
            media_exibida = media_t1
        elif current_trim_view == "2º Trimestre":
            media_exibida = media_t2
        elif current_trim_view == "3º Trimestre":
            media_exibida = media_t3
        else: # Visão Geral
            media_exibida = round((media_t1 + media_t2 + media_t3) / 3.0, 2)

        table_rows.append({
            "Username": username,
            "Nome": s['name'],
            "🌐 Engaj.": system_score,
            # T1
            "NM1": t1_notes[0],
            "NM2": t1_notes[1],
            "NM3": t1_notes[2],
            # T2
            "NM4": t2_notes[0],
            "NM5": t2_notes[1],
            "NM6": t2_notes[2],
            # T3
            "NM7": t3_notes[0],
            "NM8": t3_notes[1],
            "NM9": t3_notes[2],
            "Média": media_exibida,
            "📝 Final": float(manual_score) if manual_score is not None else 0.0,
            "🎓 Conc.": manual_grade if manual_grade is not None else "",
            "⭐ Qualit.": qual_manual,
        })

    df_scores = pd.DataFrame(table_rows)

    # --- EDITOR DE DADOS (PLANILHA) ---
    selected_trim = st.session_state.get('selected_trimester', "1º Trimestre")

    # Define quais colunas de nota devem ser visíveis
    visible_notes = []
    if selected_trim == "1º Trimestre":
        visible_notes = ["NM1", "NM2", "NM3"]
    elif selected_trim == "2º Trimestre":
        visible_notes = ["NM4", "NM5", "NM6"]
    elif selected_trim == "3º Trimestre":
        visible_notes = ["NM7", "NM8", "NM9"]
    else: # Visão Geral
        visible_notes = [f"NM{i}" for i in range(1, 10)]

    col_cfg = {
        "Username": None,
        "Nome": st.column_config.TextColumn("Estudante", width="large", disabled=True),
        "🌐 Engaj.": st.column_config.NumberColumn("Engaj.", help="Score do Sistema (influencia NM1, NM2 e NM3)", disabled=True, format="%.2f"),
        # T1
        "NM1": st.column_config.NumberColumn("N1 (T1)", help="Nota 1 do 1º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),
        "NM2": st.column_config.NumberColumn("N2 (T1)", help="Nota 2 do 1º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),
        "NM3": st.column_config.NumberColumn("N3 (T1)", help="Nota 3 do 1º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),
        # T2
        "NM4": st.column_config.NumberColumn("N1 (T2)", help="Nota 1 do 2º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),
        "NM5": st.column_config.NumberColumn("N2 (T2)", help="Nota 2 do 2º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),
        "NM6": st.column_config.NumberColumn("N3 (T2)", help="Nota 3 do 2º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),
        # T3
        "NM7": st.column_config.NumberColumn("N1 (T3)", help="Nota 1 do 3º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),
        "NM8": st.column_config.NumberColumn("N2 (T3)", help="Nota 2 do 3º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),
        "NM9": st.column_config.NumberColumn("N3 (T3)", help="Nota 3 do 3º Trimestre", min_value=0.0, max_value=10.0, format="%.2f"),

        "Média": st.column_config.NumberColumn("Média Final", disabled=True, format="%.2f"),
        "📝 Final": st.column_config.NumberColumn("Nota Final", help="Nota final manual, se necessário", min_value=0.0, step=0.1, format="%.2f"),
        "🎓 Conc.": st.column_config.TextColumn("Conceito", help="Ex: A, B, C..."),
        "⭐ Qualit.": st.column_config.NumberColumn("Qualitativo", help="Pontos qualitativos acumulados", disabled=True, format="%.1f"),
    }

    col_order = ["Nome", "🌐 Engaj."] + visible_notes + ["Média", "📝 Final", "🎓 Conc.", "⭐ Qualit."]

    edited_df = st.data_editor(
        df_scores,
        column_config=col_cfg,
        column_order=col_order,
        hide_index=True,
        use_container_width=True,
        key=f"ed_scr_{class_id}_{selected_trim.replace(' ', '_')}"
    )

    col_sv1, col_sv2 = st.columns([1, 1])
    with col_sv1:
        if st.button("💾 Salvar Alterações da Turma", type="primary", use_container_width=True):
            for _, row in edited_df.iterrows():
                uname = row['Username']
                s_json = all_scores_data["students_data"][uname]
                
                # Lógica de salvamento simplificada
                if selected_subject_id is None:
                    s_json["overall_score"] = row["📝 Final"]
                    s_json["overall_grade"] = row["🎓 Conc."]
                    for i in range(1, 10):
                        if f"NM{i}" in row:
                            s_json[f"overall_nm{i}"] = round(row[f"NM{i}"], 2)
                else:
                    sid_str = str(selected_subject_id)
                    if "subjects" not in s_json: s_json["subjects"] = {}
                    if sid_str not in s_json["subjects"]: s_json["subjects"][sid_str] = {}
                    
                    s_json["subjects"][sid_str]["score"] = row["📝 Final"]
                    s_json["subjects"][sid_str]["grade"] = row["🎓 Conc."]
                    
                    if "NM1" in row and "NM2" in row and "NM3" in row:
                        s_json["subjects"][sid_str]["T1"] = {"N1": round(row["NM1"], 2), "N2": round(row["NM2"], 2), "N3": round(row["NM3"], 2)}
                    if "NM4" in row and "NM5" in row and "NM6" in row:
                        s_json["subjects"][sid_str]["T2"] = {"N1": round(row["NM4"], 2), "N2": round(row["NM5"], 2), "N3": round(row["NM6"], 2)}
                    if "NM7" in row and "NM8" in row and "NM9" in row:
                        s_json["subjects"][sid_str]["T3"] = {"N1": round(row["NM7"], 2), "N2": round(row["NM8"], 2), "N3": round(row["NM9"], 2)}
            
            save_json(SCORES_FILE, all_scores_data)
            st.cache_data.clear() # Limpa o cache para mostrar os novos dados após salvar
            st.success("Quadro de notas atualizado!")
            st.rerun()

    with col_sv2:
        if st.button("🔄 Replicar N1, N2 e N3 para Outros Trimestres", type="secondary", use_container_width=True, help="Copia as notas N1, N2 e N3 do 1º Trimestre para o 2º e 3º Trimestres (Disciplinas Mensais/Modulares)"):
            sid_str = str(selected_subject_id) if selected_subject_id is not None else None
            rep_count = 0
            for _, row in edited_df.iterrows():
                uname = row['Username']
                s_json = all_scores_data["students_data"][uname]
                
                # Identifica notas de origem (prioriza T1 > T2 > T3)
                n1 = row.get("NM1") or s_json.get("overall_nm1", 0.0)
                n2 = row.get("NM2") or s_json.get("overall_nm2", 0.0)
                n3 = row.get("NM3") or s_json.get("overall_nm3", 0.0)

                if selected_subject_id is not None:
                    if "subjects" not in s_json: s_json["subjects"] = {}
                    if sid_str not in s_json["subjects"]: s_json["subjects"][sid_str] = {}
                    t1_d = s_json["subjects"][sid_str].get("T1", {})
                    if "NM1" in row: n1 = round(row["NM1"], 2)
                    elif "N1" in t1_d: n1 = t1_d["N1"]
                    if "NM2" in row: n2 = round(row["NM2"], 2)
                    elif "N2" in t1_d: n2 = t1_d["N2"]
                    if "NM3" in row: n3 = round(row["NM3"], 2)
                    elif "N3" in t1_d: n3 = t1_d["N3"]

                    s_json["subjects"][sid_str]["T1"] = {"N1": n1, "N2": n2, "N3": n3}
                    s_json["subjects"][sid_str]["T2"] = {"N1": n1, "N2": n2, "N3": n3}
                    s_json["subjects"][sid_str]["T3"] = {"N1": n1, "N2": n2, "N3": n3}
                
                # Espelho geral
                s_json["overall_nm1"], s_json["overall_nm4"], s_json["overall_nm7"] = n1, n1, n1
                s_json["overall_nm2"], s_json["overall_nm5"], s_json["overall_nm8"] = n2, n2, n2
                s_json["overall_nm3"], s_json["overall_nm6"], s_json["overall_nm9"] = n3, n3, n3
                rep_count += 1

            save_json(SCORES_FILE, all_scores_data)
            st.cache_data.clear()
            st.success(f"🎉 Notas N1 ({n1}), N2 ({n2}), N3 ({n3}) replicadas com sucesso para todos os trimestres de {rep_count} aluno(s)!")
            st.rerun()

    st.divider()

    # --- ASSISTENTE DE LANÇAMENTO E COMPOSIÇÃO DE NOTAS ---
    with st.expander("⚡ Assistente de Lançamento e Composição de Notas", expanded=False):
        if selected_subject_id is None:
            st.info("💡 Selecione uma disciplina específica no menu lateral para importar notas de avaliações ou compor notas por engajamento/qualitativo.")
        else:
            tab_asmt, tab_compose, tab_rep_trim = st.tabs([
                "📝 Importar Avaliação (Provas/AVs)",
                "🏆 Compor Nota (Engajamento + Qualitativo)",
                "🔄 Replicar Disciplina Mensal"
            ])

            # --- ABA 1: IMPORTAR AVALIAÇÃO DO BANCO ---
            with tab_asmt:
                st.markdown("##### 📥 Atribuir Notas de Avaliação Realizada a N1, N2 ou N3")
                st.caption("Escolha uma prova/avaliação realizada pelos alunos e lance as notas obtidas diretamente na coluna desejada.")

                available_asmts = []
                try:
                    raw_asmts = db.get_assessments_by_subject(selected_subject_id)
                    for a in raw_asmts:
                        subs = db.get_assessment_submissions_with_users(a['id'])
                        available_asmts.append({
                            'id': a['id'],
                            'title': a.get('title', f"Avaliação #{a['id']}"),
                            'type': a.get('type', 'Geral'),
                            'subs_count': len(subs),
                            'submissions': subs
                        })
                except Exception as e:
                    st.warning(f"Aviso ao consultar avaliações do banco: {e}")

                if not available_asmts:
                    st.info("Nenhuma avaliação cadastrada no sistema para esta disciplina.")
                else:
                    col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
                    with col_a1:
                        asmt_map = {f"[{a['type']}] {a['title']} ({a['subs_count']} submissões)": a for a in available_asmts}
                        sel_asmt_label = st.selectbox("1. Selecione a Avaliação:", list(asmt_map.keys()), key="sel_asmt_box")
                        sel_asmt = asmt_map[sel_asmt_label]

                    with col_a2:
                        sel_trim_a = st.selectbox("2. Trimestre:", ["1º Trimestre (T1)", "2º Trimestre (T2)", "3º Trimestre (T3)"], key="sel_trim_asmt")
                        trim_code_a = "T1" if "1º" in sel_trim_a else ("T2" if "2º" in sel_trim_a else "T3")

                    with col_a3:
                        sel_slot_a = st.selectbox("3. Coluna de Destino:", ["N1", "N2", "N3"], key="sel_slot_asmt")

                    slot_map_a = {
                        ("T1", "N1"): "NM1", ("T1", "N2"): "NM2", ("T1", "N3"): "NM3",
                        ("T2", "N1"): "NM4", ("T2", "N2"): "NM5", ("T2", "N3"): "NM6",
                        ("T3", "N1"): "NM7", ("T3", "N2"): "NM8", ("T3", "N3"): "NM9",
                    }
                    target_nm_a = slot_map_a.get((trim_code_a, sel_slot_a), "NM1")

                    col_btn_a, col_chk_a = st.columns([1, 2])
                    with col_chk_a:
                        overwrite_a = st.checkbox("Substituir notas que já tenham valor lançado", value=True, key="chk_overwrite_a")
                    with col_btn_a:
                        if st.button(f"📥 Aplicar Notas em {sel_slot_a} ({trim_code_a})", type="primary", use_container_width=True, key="btn_apply_asmt"):
                            subs = sel_asmt['submissions']
                            if not subs:
                                st.warning("Esta avaliação ainda não possui submissões registradas.")
                            else:
                                user_scores = {}
                                for s_sub in subs:
                                    u_info = s_sub.get('app_users') or {}
                                    u_uname = u_info.get('username')
                                    u_real = u_info.get('name')
                                    score_val = s_sub.get('score')
                                    if score_val is not None:
                                        if u_uname: user_scores[u_uname] = float(score_val)
                                        if u_real: user_scores[u_real] = float(score_val)

                                count_applied = 0
                                sid_str = str(selected_subject_id)
                                for st_obj in students:
                                    un = st_obj['username']
                                    rn = st_obj['name']
                                    s_val = user_scores.get(un, user_scores.get(rn))
                                    if s_val is not None:
                                        st_json = all_scores_data["students_data"].setdefault(un, {})
                                        st_json.setdefault("subjects", {}).setdefault(sid_str, {}).setdefault(trim_code_a, {})
                                        curr = st_json["subjects"][sid_str][trim_code_a].get(sel_slot_a, 0.0)
                                        if overwrite_a or curr == 0.0:
                                            st_json["subjects"][sid_str][trim_code_a][sel_slot_a] = round(s_val, 2)
                                            st_json[f"overall_{target_nm_a.lower()}"] = round(s_val, 2)
                                            count_applied += 1

                                save_json(SCORES_FILE, all_scores_data)
                                st.cache_data.clear()
                                st.success(f"✅ Notas da avaliação '{sel_asmt['title']}' aplicadas em {sel_slot_a} ({trim_code_a}) para {count_applied} aluno(s)!")
                                st.rerun()

            # --- ABA 2: COMPOR NOTA (ENGAJAMENTO + QUALITATIVO) ---
            with tab_compose:
                st.markdown("##### 🏆 Formar Nota com Engajamento + Pontos Qualitativos")
                st.caption("Some o Score de Engajamento aos Pontos Qualitativos para compor uma das notas (ex: N3).")
                st.info("📌 **Regra do Bônus Extra:** O bônus só é concedido a alunos que possuam **Engajamento ≥ 1.0** (que realizaram atividades nas aulas).")

                col_c1, col_c2, col_c3, col_c4 = st.columns([1, 1, 1, 1])
                with col_c1:
                    sel_trim_c = st.selectbox("1. Trimestre:", ["1º Trimestre (T1)", "2º Trimestre (T2)", "3º Trimestre (T3)"], key="sel_trim_comp")
                    trim_code_c = "T1" if "1º" in sel_trim_c else ("T2" if "2º" in sel_trim_c else "T3")
                with col_c2:
                    sel_slot_c = st.selectbox("2. Nota a Formar:", ["N3 (Recomendado)", "N1", "N2"], key="sel_slot_comp")
                    slot_code_c = "N3" if "N3" in sel_slot_c else ("N1" if "N1" in sel_slot_c else "N2")
                with col_c3:
                    bonus_manual = st.number_input("3. Bônus Extra (+):", min_value=0.0, max_value=5.0, value=0.0, step=0.5, key="bonus_manual_comp", help="Exige Engajamento >= 1.0 para ser aplicado.")
                with col_c4:
                    teto_nota = st.number_input("4. Teto Máximo:", min_value=1.0, max_value=10.0, value=10.0, step=0.5, key="teto_nota_comp")

                slot_map_c = {
                    ("T1", "N1"): "NM1", ("T1", "N2"): "NM2", ("T1", "N3"): "NM3",
                    ("T2", "N1"): "NM4", ("T2", "N2"): "NM5", ("T2", "N3"): "NM6",
                    ("T3", "N1"): "NM7", ("T3", "N2"): "NM8", ("T3", "N3"): "NM9",
                }
                target_nm_c = slot_map_c.get((trim_code_c, slot_code_c), "NM3")

                col_inc1, col_inc2, col_inc3 = st.columns(3)
                with col_inc1:
                    inc_engaj = st.checkbox("Somar Score de Engajamento", value=True, key="chk_engaj_comp")
                with col_inc2:
                    inc_qualit = st.checkbox("Somar Pontos Qualitativos", value=True, key="chk_qualit_comp")
                with col_inc3:
                    inc_freq = st.checkbox("Somar Bônus por Frequência", value=True, key="chk_freq_comp")

                if inc_freq:
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        bonus_max_freq = st.number_input(
                            "Bônus de Frequência (100% de Presença = Bônus Máximo):",
                            min_value=0.0, max_value=5.0, value=1.0, step=0.5, key="bonus_max_freq",
                            help="Alunos com 100% de presença recebem o bônus máximo. Demais recebem proporcional à frequência."
                        )
                    with col_f2:
                        regra_freq = st.selectbox(
                            "Cálculo da Frequência:",
                            ["Proporcional (% Freq × Bônus Máximo)", "Por Faixa (100%=Max, ≥85%=80%, ≥75%=50%)", "Exclusivo para 100% de Presença"],
                            key="regra_freq_comp"
                        )
                else:
                    bonus_max_freq = 0.0
                    regra_freq = "Proporcional (% Freq × Bônus Máximo)"

                # Busca histórico de frequência dos alunos da turma
                att_stats = get_student_attendance_stats(
                    class_id=class_id,
                    subject_id=selected_subject_id,
                    students=students,
                    matching_subject_ids=matching_subject_ids
                )

                # Prévia em tempo real para o professor
                preview_list = []
                for st_obj in students:
                    un = st_obj['username']
                    rn = st_obj['name']
                    st_json = all_scores_data["students_data"].get(un, {})

                    # Engajamento
                    calc_eng = get_cached_student_score(un, selected_subject_id)
                    raw_eng = float(calc_eng.get('total', 0.0))
                    eng_val = round(raw_eng, 2) if inc_engaj else 0.0

                    # Qualitativo (Atividades Diárias + Lançados)
                    if inc_qualit:
                        q_val = get_student_qualitative_points(
                            student_json=st_json,
                            selected_subject_id=selected_subject_id,
                            selected_subject_name=selected_subject_name,
                            lesson_sub_map=lesson_sub_map,
                            matching_subject_ids=matching_subject_ids
                        )
                    else:
                        q_val = 0.0

                    # Frequência (% Presença) e Bônus
                    att_info = att_stats.get(un, {})
                    freq_pct = att_info.get("freq_pct", 0.0)

                    if inc_freq and bonus_max_freq > 0.0:
                        if "Proporcional" in regra_freq:
                            bonus_freq = round(float(bonus_max_freq) * (freq_pct / 100.0), 2)
                        elif "Por Faixa" in regra_freq:
                            if freq_pct >= 100.0: bonus_freq = float(bonus_max_freq)
                            elif freq_pct >= 85.0: bonus_freq = round(float(bonus_max_freq) * 0.8, 2)
                            elif freq_pct >= 75.0: bonus_freq = round(float(bonus_max_freq) * 0.5, 2)
                            else: bonus_freq = 0.0
                        else: # Exclusivo para 100%
                            bonus_freq = float(bonus_max_freq) if freq_pct >= 100.0 else 0.0
                    else:
                        bonus_freq = 0.0

                    # Regra de Bônus Manual: só concede bônus se o aluno tiver pelo menos 1.0 ponto de Engajamento
                    aluno_elegivel_bonus = (raw_eng >= 1.0)
                    bonus_efetivo = float(bonus_manual) if aluno_elegivel_bonus else 0.0

                    # Se não marcou nada e o bônus for 0, a nota zera
                    if not inc_engaj and not inc_qualit and not inc_freq and float(bonus_manual) == 0.0:
                        nota_calc = 0.0
                    else:
                        nota_calc = min(float(teto_nota), round(eng_val + q_val + bonus_freq + bonus_efetivo, 2))

                    bonus_desc = f"+{bonus_efetivo:.1f}" if aluno_elegivel_bonus and bonus_manual > 0 else ("0.0 (Engaj < 1.0)" if bonus_manual > 0 else "0.0")
                    bonus_freq_desc = f"+{bonus_freq:.2f}" if bonus_freq > 0 else "0.00"

                    preview_list.append({
                        "Estudante": rn,
                        "% Freq.": f"{freq_pct:.1f}%",
                        "Bônus Freq.": bonus_freq_desc,
                        "Engajamento": eng_val,
                        "Qualitativo": q_val,
                        "Bônus Extra": bonus_desc,
                        f"Nota Formada ({slot_code_c})": nota_calc
                    })

                df_p = pd.DataFrame(preview_list)
                with st.expander("👀 Ver Prévia da Composição para Toda a Turma", expanded=False):
                    st.dataframe(df_p, hide_index=True, use_container_width=True)

                col_btn_apply, col_btn_reset = st.columns([2, 1])
                with col_btn_apply:
                    if st.button(f"✨ Formar e Salvar {slot_code_c} ({trim_code_c}) para Toda a Turma", type="primary", use_container_width=True, key="btn_apply_compose"):
                        sid_str = str(selected_subject_id)
                        for item in preview_list:
                            target_uname = None
                            for st_obj in students:
                                if st_obj['name'] == item['Estudante']:
                                    target_uname = st_obj['username']
                                    break
                            if target_uname:
                                v_nota = item[f"Nota Formada ({slot_code_c})"]
                                st_json = all_scores_data["students_data"].setdefault(target_uname, {})
                                st_json.setdefault("subjects", {}).setdefault(sid_str, {}).setdefault(trim_code_c, {})
                                st_json["subjects"][sid_str][trim_code_c][slot_code_c] = v_nota
                                st_json[f"overall_{target_nm_c.lower()}"] = v_nota

                        save_json(SCORES_FILE, all_scores_data)
                        st.cache_data.clear()
                        st.success(f"🎉 Nota {slot_code_c} ({trim_code_c}) formada com sucesso para {len(students)} alunos!")
                        st.rerun()

                with col_btn_reset:
                    if st.button(f"🗑️ Zerar {slot_code_c} ({trim_code_c})", type="secondary", use_container_width=True, key="btn_zero_slot", help=f"Reseta a nota {slot_code_c} ({trim_code_c}) para 0.00 de todos os alunos da turma para refazer a composição"):
                        sid_str = str(selected_subject_id)
                        for st_obj in students:
                            target_uname = st_obj['username']
                            st_json = all_scores_data["students_data"].setdefault(target_uname, {})
                            st_json.setdefault("subjects", {}).setdefault(sid_str, {}).setdefault(trim_code_c, {})
                            st_json["subjects"][sid_str][trim_code_c][slot_code_c] = 0.0
                            st_json[f"overall_{target_nm_c.lower()}"] = 0.0

                        save_json(SCORES_FILE, all_scores_data)
                        st.cache_data.clear()
                        st.warning(f"Nota {slot_code_c} ({trim_code_c}) zerada para todos os alunos!")
                        st.rerun()

            # --- ABA 3: REPLICAR NOTAS ENTRE TRIMESTRES (DISCIPLINA MENSAL) ---
            with tab_rep_trim:
                st.markdown("##### 🔄 Replicar Notas N1, N2 e N3 para os Demais Trimestres")
                st.caption("Em disciplinas mensais e modulares, as notas obtidas no período são replicadas para todos os trimestres para fechar a média anual de forma consistente.")

                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    src_trim = st.selectbox("1. Trimestre de Origem (Notas Base):", ["1º Trimestre (T1)", "2º Trimestre (T2)", "3º Trimestre (T3)"], key="src_trim_rep_tab")
                    src_code = "T1" if "1º" in src_trim else ("T2" if "2º" in src_trim else "T3")
                with col_r2:
                    st.markdown("**2. Trimestres de Destino:**")
                    target_trims = [t for t in ["T1", "T2", "T3"] if t != src_code]
                    chk_targets = {}
                    for t_code in target_trims:
                        t_lbl = "1º Trimestre (T1)" if t_code == "T1" else ("2º Trimestre (T2)" if t_code == "T2" else "3º Trimestre (T3)")
                        chk_targets[t_code] = st.checkbox(f"Replicar para {t_lbl}", value=True, key=f"chk_rep_to_{t_code}")

                # Prévia da Replicação
                rep_preview = []
                for st_obj in students:
                    un = st_obj['username']
                    rn = st_obj['name']
                    st_json = all_scores_data["students_data"].get(un, {})
                    sid_s = str(selected_subject_id)
                    s_data = st_json.get("subjects", {}).get(sid_s, {}).get(src_code, {})
                    
                    n1_val = s_data.get("N1", 0.0)
                    n2_val = s_data.get("N2", 0.0)
                    n3_val = s_data.get("N3", 0.0)

                    rep_preview.append({
                        "Estudante": rn,
                        f"N1 ({src_code})": n1_val,
                        f"N2 ({src_code})": n2_val,
                        f"N3 ({src_code})": n3_val,
                    })

                with st.expander("👀 Ver Notas Base a Serem Replicadas", expanded=False):
                    st.dataframe(pd.DataFrame(rep_preview), hide_index=True, use_container_width=True)

                if st.button(f"🚀 Confirmar e Replicar Notas de {src_code} para os Trimestres Selecionados", type="primary", use_container_width=True, key="btn_confirm_rep_trim"):
                    active_targets = [t_code for t_code, checked in chk_targets.items() if checked]
                    if not active_targets:
                        st.warning("Selecione pelo menos um trimestre de destino.")
                    else:
                        sid_str = str(selected_subject_id)
                        count_rep = 0
                        for st_obj in students:
                            un = st_obj['username']
                            st_json = all_scores_data["students_data"].setdefault(un, {})
                            st_json.setdefault("subjects", {}).setdefault(sid_str, {})
                            
                            src_data = st_json["subjects"][sid_str].get(src_code, {})
                            n1 = src_data.get("N1", 0.0)
                            n2 = src_data.get("N2", 0.0)
                            n3 = src_data.get("N3", 0.0)

                            for dest_t in active_targets:
                                st_json["subjects"][sid_str][dest_t] = {"N1": n1, "N2": n2, "N3": n3}
                                if dest_t == "T1":
                                    st_json["overall_nm1"], st_json["overall_nm2"], st_json["overall_nm3"] = n1, n2, n3
                                elif dest_t == "T2":
                                    st_json["overall_nm4"], st_json["overall_nm5"], st_json["overall_nm6"] = n1, n2, n3
                                elif dest_t == "T3":
                                    st_json["overall_nm7"], st_json["overall_nm8"], st_json["overall_nm9"] = n1, n2, n3

                            count_rep += 1

                        save_json(SCORES_FILE, all_scores_data)
                        st.cache_data.clear()
                        st.success(f"🎉 Notas N1, N2 e N3 replicadas de {src_code} para {', '.join(active_targets)} para {count_rep} aluno(s)!")
                        st.rerun()

    st.divider()

    # --- PAINEL INDIVIDUAL DO ALUNO ---
    st.subheader("👤 Análise Individual e Pontos Qualitativos")

    student_names = edited_df['Nome'].tolist()
    selected_student_name = st.selectbox(
        "Selecione um aluno para ver detalhes",
        ["-- Selecione --"] + student_names,
        key="student_detail_selector"
    )

    if selected_student_name != "-- Selecione --":
        student_row = edited_df[edited_df['Nome'] == selected_student_name].iloc[0]
        username = student_row['Username']
        student_json = all_scores_data["students_data"][username]

        st.markdown(f"#### Detalhes de **{selected_student_name}**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Média Final (Calculada)", f"{student_row['Média']:.2f}")
        with col2:
            st.metric("Score de Engajamento", f"{student_row['🌐 Engaj.']:.2f}")
        with col3:
            st.metric("Pontos Qualitativos", f"{student_row['⭐ Qualit.']:.1f}")

        with st.expander("➕ Adicionar Pontos Qualitativos"):
            with st.form(key=f"form_qual_{username}"):
                points_to_add = st.number_input("Pontos a adicionar", min_value=0.0, max_value=5.0, step=0.5, value=1.0)
                reason = st.text_input("Motivo/Atividade", placeholder="Ex: Participação em aula, projeto extra...")
                submitted = st.form_submit_button("Adicionar Ponto")

                if submitted:
                    if reason:
                        entry = {
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "points": points_to_add,
                            "notes": reason
                        }
                        if selected_subject_id is not None:
                            entry["subject_id"] = selected_subject_id
                        
                        student_json.setdefault("daily_qualitative_points", []).append(entry)
                        save_json(SCORES_FILE, all_scores_data)
                        st.success(f"{points_to_add} ponto(s) adicionado(s) para {selected_student_name}!")
                        st.rerun()
                    else:
                        st.warning("Por favor, informe o motivo da pontuação.")

        st.markdown("##### 📜 Histórico de Pontos Qualitativos")
        qual_history = student_json.get("daily_qualitative_points", [])
        
        if qual_history:
            if selected_subject_id:
                sid_str = str(selected_subject_id)
                matching_str_ids = {str(i) for i in matching_subject_ids} if matching_subject_ids else {sid_str}
                filtered_history = []
                for p in qual_history:
                    p_sid = p.get('subject_id')
                    p_lid = p.get('lesson_id')
                    if p_sid is None and p_lid and lesson_sub_map and p_lid in lesson_sub_map:
                        p_sid = lesson_sub_map[p_lid]
                    if p_sid is None or str(p_sid) in matching_str_ids or p_sid in matching_subject_ids:
                        filtered_history.append(p)
                qual_history = filtered_history

            if qual_history:
                df_qual = pd.DataFrame(qual_history).sort_values(by="date", ascending=False)
                df_qual = df_qual.rename(columns={"date": "Data", "points": "Pontos", "notes": "Motivo"})
                st.dataframe(df_qual[['Data', 'Pontos', 'Motivo']], hide_index=True, use_container_width=True)
            else:
                st.info(f"Nenhum ponto qualitativo registrado para esta disciplina.")
        else:
            st.info("Nenhum ponto qualitativo registrado para este aluno.")

    # --- EXPORTAÇÃO COLORIDA PARA APRESENTAÇÃO EM SALA ---
    with st.expander("🎨 Exportar Relatório Colorido para Comentar em Sala", expanded=False):
        st.caption("Gere relatórios visuais com notas coloridas por nível de desempenho (Verde: ≥ 6.0, Amarelo: 4.0 - 5.9, Vermelho: < 4.0) ideais para projetor, slide ou impressão.")

        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            if not MATPLOTLIB_AVAILABLE:
                st.error("Matplotlib não disponível para exportação PNG.")
            else:
                if st.button("🖼️ Gerar Imagem Colorida (PNG)", use_container_width=True, key="btn_gen_png_color"):
                    with st.spinner("Renderizando imagem colorida em alta resolução..."):
                        df_export = edited_df.drop(columns=['Username']) if 'Username' in edited_df.columns else edited_df
                        png_data = create_scores_png(df_export, selected_class_name, selected_subject_name, school_name, prof_name, selected_trim)
                        st.session_state['last_scores_png'] = png_data
                        st.session_state['last_scores_png_name'] = f"quadro_notas_{selected_class_name}_{selected_trim.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.png"

                if 'last_scores_png' in st.session_state:
                    st.download_button(
                        label="💾 Download Imagem PNG (200 DPI)",
                        data=st.session_state['last_scores_png'],
                        file_name=st.session_state.get('last_scores_png_name', 'quadro_notas.png'),
                        mime="image/png",
                        use_container_width=True
                    )
                    with st.expander("👀 Ver Prévia da Imagem", expanded=True):
                        st.image(st.session_state['last_scores_png'], use_container_width=True)

        with col_exp2:
            html_report = generate_scores_html_report(edited_df, selected_class_name, selected_subject_name, school_name, prof_name, selected_trim)
            st.download_button(
                label="🖨️ Download Relatório Colorido (HTML/Impressão)",
                data=html_report,
                file_name=f"relatorio_notas_{selected_class_name}_{selected_trim.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True
            )
            st.info("💡 Abra o arquivo HTML no navegador para projetar ou imprimir via `Ctrl + P`.")

# Se o script for executado diretamente (para testes)
if __name__ == "__main__":
    # Detecta se está rodando dentro do Streamlit ou via Terminal (External Plugin)
    is_streamlit = False
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(): is_streamlit = True
    except: pass

    if is_streamlit:
        show_student_scores()
    else:
        # Se rodar via "Executar" na aba de Plugins Externos
        run_cli_report()