"""
Grade Semanal de Aulas

Este plugin permite gerenciar e visualizar o mapa de horários das turmas.
Como o SysAva foca em conteúdo, este plugin estende a funcionalidade para 
organização do tempo.

Uso:
1. Executar via SysAva (Visualização)
2. Executar via Terminal: python grade_semanal.py --edit (Para cadastrar horários)
"""

import os
import sys
import json
from io import BytesIO
from datetime import datetime
import pandas as pd
import streamlit as st

# Tenta importar Matplotlib para geração de PNG
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# --- Configuração de Path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from legados.sysava.services import database as db
except ImportError:
    print("Erro: Não foi possível importar o serviço de banco de dados.")
    sys.exit(1)

DATA_FILE = os.path.join(os.path.dirname(__file__), "grade_horaria.json")
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
# Horários padrão (podem ser personalizados no JSON manualmente)
HORARIOS_PADRAO = ["07:10", "08:10", "09:10", "10:10", "10:30", "11:30", "12:30", "13:30", "14:30", "14:50", "15:50", "16:50"]

def create_grade_png(df, selected_turmas, school_name, prof_name):
    """Gera uma imagem PNG da grade horária usando Matplotlib."""
    # Aumenta um pouco a altura para acomodar o cabeçalho superior
    fig, ax = plt.subplots(figsize=(14, len(df) * 0.6 + 2.5))
    ax.axis('off')

    # Cabeçalho da Imagem
    plt.text(0.5, 0.97, school_name, fontsize=18, fontweight='bold', ha='center', va='top', transform=fig.transFigure)
    plt.text(0.5, 0.93, f"Professor: {prof_name} | Turmas: {', '.join([get_turma_label(t) for t in selected_turmas])}", 
             fontsize=12, ha='center', va='top', transform=fig.transFigure)
    plt.text(0.5, 0.90, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
             fontsize=9, color='gray', ha='center', va='top', transform=fig.transFigure)

    # Fundo cinza para o cabeçalho da tabela (melhor contraste)
    header_bg = '#e9ecef'
    
    # Cria a tabela no plot
    the_table = ax.table(
        cellText=df.values, 
        colLabels=df.columns, 
        cellLoc='center', 
        loc='center',
        bbox=[0, 0, 1, 0.88]
    )

    # Estilização das células
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(10)
    the_table.scale(1.2, 1.5)

    for (row, col), cell in the_table.get_celld().items():
        # Cabeçalho
        if row == 0:
            cell.set_facecolor(header_bg)
            cell.get_text().set_weight('bold')
            cell.get_text().set_color('#343a40')
        else:
            val = cell.get_text().get_text()
            # Horários (Coluna 0)
            if col == 0:
                cell.get_text().set_color('#fd7e14')
                cell.get_text().set_weight('bold')
            # Estilo para Intervalos (Lanche/Almoço) no PNG
            elif "Lanche" in val or "Almoço" in val:
                cell.set_facecolor('#f8f9fa')
                cell.get_text().set_color('#6c757d')
            # Cores por turma
            elif "[2.DS.A]" in val and "[2.DS.B]" not in val: cell.set_facecolor('#e7f3ff')
            elif "[2.DS.B]" in val and "[2.DS.A]" not in val: cell.set_facecolor('#e6fcf5')
            elif "[2.DS.A]" in val and "[2.DS.B]" in val: cell.set_facecolor('#fff9db')

    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=200)
    plt.close(fig)
    return buf.getvalue()

def get_turma_label(name):
    """Abrevia o nome das turmas para rótulos compactos (ex: 2.DS.A)."""
    name_up = name.upper()
    if "I-A" in name_up or "TURMA A" in name_up: return "2.DS.A"
    if "I-B" in name_up or "TURMA B" in name_up: return "2.DS.B"
    return name

def load_grade():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_grade(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def show_grade_semanal():
    """Interface visual para o SysAva."""
    # Injeção de CSS para transparência, cores nas letras e células compactas (estilo mural)
    st.markdown("""
        <style>
            .grade-container { overflow-x: auto; margin-top: 10px; }
            .grade-html { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 12px; color: #333; }
            .grade-html th, .grade-html td { border: 1px solid #eee; padding: 3px 6px; text-align: center; vertical-align: middle; min-width: 90px; }
            .grade-html th { background-color: #fcfcfc; font-weight: 600; color: #666; }
            
            /* Coluna de Horário em Laranja */
            .cell-time { color: #fd7e14 !important; font-weight: bold; }
            
            /* Estilo dos Intervalos */
            .row-interval { background-color: rgba(0, 0, 0, 0.03) !important; color: #999 !important; font-size: 11px !important; }
            
            /* Turma A: Azul Transparente */
            .cell-a { background-color: rgba(0, 123, 255, 0.08) !important; color: #007bff !important; font-weight: bold; }
            /* Turma B: Verde Transparente */
            .cell-b { background-color: rgba(40, 167, 69, 0.08) !important; color: #28a745 !important; font-weight: bold; }
            /* Intersecção: Amarelo Transparente */
            .cell-both { background-color: rgba(255, 193, 7, 0.12) !important; color: #856404 !important; font-weight: bold; }

            @media print {
                .no-print { display: none !important; }
                .grade-html { font-size: 10px; }
                th, td { border: 1px solid #000; }
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("🗓️ Mapa de Grade Semanal")
    grade = load_grade()

    # Busca informações para os labels (Escola e Professor)
    school_info = db.get_school()
    school_name = school_info.get('name', 'SysAva') if school_info else "SysAva"
    prof_name = st.session_state.get('usuario', 'Professor')

    if not grade:
        st.warning("Nenhuma grade horária encontrada. Use o modo de edição no terminal ou na Agenda.")
        return

    with st.sidebar:
        st.header("Configurações")
        turmas = list(grade.keys())
        selected_turmas = st.multiselect("Selecione as Turmas para comparar", turmas, default=turmas[:2] if len(turmas) >= 2 else turmas[:1])

    if selected_turmas:
        st.subheader(f"Mapa Comparativo: {', '.join(selected_turmas)}")

        # Adicionar o cabeçalho visual na página
        labels_turmas = [get_turma_label(t) for t in selected_turmas]
        st.markdown(f"""
            <div style='text-align: center; margin-bottom: 20px; padding: 15px; border-radius: 10px; background-color: rgba(253, 126, 20, 0.05); border: 1px solid rgba(253, 126, 20, 0.1);'>
                <h2 style='margin: 0; color: #333;'>{school_name}</h2>
                <p style='margin: 5px 0; color: #666; font-size: 1.1em;'>👨‍🏫 <b>Professor:</b> {prof_name} | 🏫 <b>Turmas:</b> {', '.join(labels_turmas)}</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Consolida todos os horários únicos das turmas selecionadas
        all_horarios = set()
        for t in selected_turmas:
            all_horarios.update(grade[t].get("config_horarios", HORARIOS_PADRAO))
        horarios_sorted = sorted(list(all_horarios))

        # Construção do DataFrame de Intersecção (Grade Unificada)
        # Uma única linha por horário, mesclando as turmas selecionadas.
        grid_data = []
        intervalos_times = ["10:10", "11:30", "14:30"]

        for h in horarios_sorted:
            row = {"Horário": h}
            has_any_lesson = False
            is_interval = h in intervalos_times
            
            for dia in DIAS_SEMANA:
                cell_items = []
                for t_name in selected_turmas:
                    disciplina = grade[t_name].get(dia, {}).get(h, "---")
                    if disciplina != "---":
                        t_label = get_turma_label(t_name)
                        display_text = f"[{t_label}] {disciplina}"
                        cell_items.append(display_text)
                
                if cell_items:
                    row[dia] = " / ".join(cell_items)
                    has_any_lesson = True
                else:
                    if is_interval:
                        row[dia] = "☕ Lanche" if h != "11:30" else "🍽️ Almoço"
                    else:
                        row[dia] = "---"
            
            # Mantém a linha se houver aula ou se for um horário de intervalo/almoço
            if has_any_lesson or is_interval:
                grid_data.append(row)

        df = pd.DataFrame(grid_data)
        
        # Montagem da Tabela em HTML Puro para controle total de estilo e PNG
        table_html = "<div class='grade-container'><table class='grade-html'><thead><tr><th>Horário</th>"
        for dia in DIAS_SEMANA:
            table_html += f"<th>{dia}</th>"
        table_html += "</tr></thead><tbody>"

        for _, row in df.iterrows():
            is_interval = row["Horário"] in intervalos_times
            tr_class = "row-interval" if is_interval else ""
            table_html += f"<tr class='{tr_class}'><td class='cell-time'><b>{row['Horário']}</b></td>"
            
            for dia in DIAS_SEMANA:
                val = row[dia]
                td_class = ""
                if not is_interval and val != "---":
                    if "[2.DS.A]" in val and "[2.DS.B]" not in val: td_class = "cell-a"
                    elif "[2.DS.B]" in val and "[2.DS.A]" not in val: td_class = "cell-b"
                    elif "[2.DS.A]" in val and "[2.DS.B]" in val: td_class = "cell-both"
                
                table_html += f"<td class='{td_class}'>{val}</td>"
            table_html += "</tr>"
        
        table_html += "</tbody></table></div>"
        
        # Renderiza a tabela na tela
        st.markdown(table_html, unsafe_allow_html=True)
        
        # Auxiliar de Exportação
        with st.expander("📸 Salvar como PNG / Imprimir"):
            if not MATPLOTLIB_AVAILABLE:
                st.error("Biblioteca 'matplotlib' não encontrada. Instale com `pip install matplotlib` para baixar em PNG.")
            else:
                st.info("Clique no botão abaixo para baixar a imagem PNG gerada pelo sistema.")
                if st.button("🖼️ Gerar e Baixar Imagem PNG", use_container_width=True):
                    with st.spinner("Renderizando imagem..."):
                        png_data = create_grade_png(df, selected_turmas, school_name, prof_name)
                        st.download_button(
                            label="💾 Confirmar Download (PNG)",
                            data=png_data,
                            file_name=f"grade_{datetime.now().strftime('%Y%m%d')}.png",
                            mime="image/png",
                            use_container_width=True
                        )

            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Planilha (CSV)", data=csv, file_name=f"grade_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)

        st.info("💡 Grade unificada. Use o seletor lateral para comparar as turmas.")

def exibir_grade(turma_nome, data):
    turma_data = data.get(turma_nome, {})
    horarios = turma_data.get("config_horarios", HORARIOS_PADRAO)
    
    print(f"\n📅 GRADE SEMANAL - TURMA: {turma_nome}")
    print("=" * 105)
    
    # Cabeçalho
    header = f"{'Horário':<10}"
    for dia in DIAS_SEMANA:
        header += f"| {dia:^16} "
    print(header)
    print("-" * 105)

    # Linhas
    for h in horarios:
        row = f"{h:<10}"
        for dia in DIAS_SEMANA:
            disciplina = turma_data.get(dia, {}).get(h, "---")
            # Trunca o nome da disciplina para caber na coluna
            row += f"| {disciplina[:16]:^16} "
        print(row)
    print("=" * 105)

def menu_edicao():
    print("\n--- MODO DE EDIÇÃO DE GRADE ---")
    grade = load_grade()
    
    # 1. Selecionar Turma
    classes = db.get_classes()
    if not classes:
        print("Nenhuma turma encontrada no banco de dados.")
        return

    print("\nTurmas disponíveis:")
    for i, c in enumerate(classes):
        print(f"[{i+1}] {c['name']}")
    
    try:
        idx = int(input("\nSelecione o número da turma (ou 0 para cancelar): ")) - 1
        if idx == -1: return
        turma_nome = classes[idx]['name']
    except (ValueError, IndexError):
        print("Seleção inválida.")
        return

    if turma_nome not in grade:
        grade[turma_nome] = {dia: {} for dia in DIAS_SEMANA}
        grade[turma_nome]["config_horarios"] = HORARIOS_PADRAO
        save_grade(grade)

    while True:
        # 2. Selecionar Dia
        print(f"\n--- Editando Turma: {turma_nome} ---")
        print("Dias da Semana:")
        for i, dia in enumerate(DIAS_SEMANA):
            print(f"[{i+1}] {dia}")
        print("[0] Sair ou Trocar de Turma")
        
        try:
            sel_dia = input("\nSelecione o dia: ").strip()
            if sel_dia == '0': break
            dia_idx = int(sel_dia) - 1
            dia_selecionado = DIAS_SEMANA[dia_idx]
        except (ValueError, IndexError):
            print("Opção inválida.")
            continue

        while True:
            # 3. Selecionar Horário
            horarios = grade[turma_nome].get("config_horarios", HORARIOS_PADRAO)
            print(f"\nHorários para {dia_selecionado} ({turma_nome}):")
            for i, h in enumerate(horarios):
                # Garante que o dicionário do dia existe
                if dia_selecionado not in grade[turma_nome]:
                    grade[turma_nome][dia_selecionado] = {}
                
                atual = grade[turma_nome][dia_selecionado].get(h, "---")
                print(f"[{i+1}] {h} -> {atual}")
            print("[0] Voltar para seleção de dia")

            try:
                sel_h = input("Selecione o horário para editar: ").strip()
                if sel_h == '0': break
                h_idx = int(sel_h) - 1
                horario_selecionado = horarios[h_idx]
            except (ValueError, IndexError):
                print("Opção inválida.")
                continue

            # 4. Definir Disciplina
            nova_disc = input(f"Disciplina para {dia_selecionado} as {horario_selecionado} (Enter p/ limpar): ").strip()
            
            if nova_disc:
                grade[turma_nome][dia_selecionado][horario_selecionado] = nova_disc
                print("✅ Atualizado!")
            else:
                if horario_selecionado in grade[turma_nome][dia_selecionado]:
                    del grade[turma_nome][dia_selecionado][horario_selecionado]
                    print("🗑️ Removido.")
            
            # Salva a cada modificação para garantir persistência
            save_grade(grade)

def main():
    print("="*50)
    print("PLUGIN: MAPA DE GRADE SEMANAL")
    print("="*50)

    # Detecta contexto Streamlit
    is_streamlit = False
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(): is_streamlit = True
    except: pass

    if is_streamlit:
        show_grade_semanal()
        return

    if "--edit" in sys.argv:
        if not db.is_db_connected():
            print("Erro: Banco de dados não conectado. Verifique o .env")
            return
        menu_edicao()
    else:
        grade = load_grade()
        if not grade:
            print("\nNenhuma grade horária cadastrada. Execute com --edit.")
        else:
            for turma in grade:
                exibir_grade(turma, grade)

if __name__ == "__main__":
    main()