import streamlit as st
from legados.sysava.services import database as db
import os
import re
import sys
import subprocess
import base64
import importlib.util

# Tenta importar o visualizador de PDF, se não existir, a funcionalidade ficará desabilitada.
try:
    from streamlit_pdf_viewer import pdf_viewer
    PDF_VIEWER_AVAILABLE = True
except ImportError:
    PDF_VIEWER_AVAILABLE = False

def find_local_pdfs():
    """Encontra todos os arquivos PDF nos diretórios de dados."""
    pdf_files = {}
    search_paths = [os.path.join("data", "repo", "ebooks"), os.path.join("data", "Turmas")]
    
    for path in search_paths:
        if os.path.exists(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if file.lower().endswith(".pdf"):
                        # Usa o caminho relativo como chave para evitar nomes duplicados
                        relative_path = os.path.relpath(os.path.join(root, file), "data")
                        pdf_files[relative_path] = os.path.join(root, file)
    return pdf_files

def render_plugin_integrated(plugin_path):
    """
    Importa e executa um plugin dentro do contexto atual do Streamlit.
    Isso evita o erro de 'missing ScriptRunContext'.
    """
    try:
        module_name = os.path.basename(plugin_path).replace(".py", "")
        # Define o nome do módulo no sys.modules para evitar conflitos
        spec = importlib.util.spec_from_file_location(module_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # Procura por pontos de entrada conhecidos no plugin (como o da Agenda)
        if hasattr(module, "show_agenda"):
            module.show_agenda()
        elif hasattr(module, "show_student_scores"):
            module.show_student_scores()
        elif hasattr(module, "show_attendance_plugin"):
            module.show_attendance_plugin()
        elif hasattr(module, "show_daily_activities"):
            module.show_daily_activities()
        elif hasattr(module, "show_grade_semanal"):
            module.show_grade_semanal()
        elif hasattr(module, "show_page"):
            module.show_page()
        elif hasattr(module, "main"):
            module.main()
    except Exception as e:
        st.error(f"Erro ao integrar plugin: {e}")

def show_page():
    st.header("🧩 Extensões e Plugins")

    # Verificação de permissão
    if st.session_state.get('role') not in ['admin', 'teacher']:
        st.error("Acesso negado. Esta área é restrita a professores e administradores.")
        return

    st.markdown("""
    Esta seção permite executar funcionalidades nativas e scripts Python externos para estender as capacidades do SysAva.
    """)

    # Substituímos st.tabs por um seletor de rádio horizontal para controle de execução.
    # O Streamlit avalia o conteúdo de todas as abas no st.tabs, o que causava a poluição do sidebar.
    # Com o if/elif, apenas o código (e o sidebar) do plugin selecionado é processado.
    menu_options = ["Nativos", "Externos", "Agenda", "Atividades", "Notas", "Frequência", "Grade"]
    icons = {
        "Nativos": "🔌", 
        "Externos": "📂", 
        "Agenda": "📅", 
        "Atividades": "🎯",
        "Notas": "📊", 
        "Frequência": "📝",
        "Grade": "🗓️"
    }
    
    selected_tab = st.radio(
        "Menu de Plugins",
        options=menu_options,
        format_func=lambda x: f"{icons[x]} {x}",
        horizontal=True,
        label_visibility="collapsed"
    )
    st.divider()

    # --- Aba de Plugins Nativos ---
    if selected_tab == "Nativos":
        with st.expander("🎓 Gerador de Certificados (Exemplo)"):
            st.info("Exemplo de integração de um componente para gerar certificados de conclusão.")

            # Lógica para selecionar aluno e curso para gerar certificado
            classes_cert = db.get_classes()
            if not classes_cert:
                st.warning("Nenhuma turma cadastrada para emitir certificados.")
            else:
                class_options_cert = {c['name']: c['id'] for c in classes_cert}
                selected_class_name_cert = st.selectbox("Selecione a Turma para emitir certificados", options=["-- Selecione --"] + list(class_options_cert.keys()), key="cert_class")

                if selected_class_name_cert != "-- Selecione --":
                    class_id_cert = class_options_cert[selected_class_name_cert]
                    students_cert = db.get_students_by_class(class_id_cert)
                    student_options_cert = {s['name']: s['username'] for s in students_cert}
                    
                    selected_student_name_cert = st.selectbox("Selecione o Aluno", options=["-- Selecione --"] + list(student_options_cert.keys()), key="cert_student")

                    if selected_student_name_cert != "-- Selecione --":
                        st.success(f"Pronto para gerar o certificado para **{selected_student_name_cert}** da turma **{selected_class_name_cert}**.")
                        if st.button("📄 Gerar Certificado (Exemplo)"):
                            st.balloons()
                            st.success("Certificado gerado! (Esta é uma demonstração da funcionalidade).")
        
        st.divider()
        st.markdown("### 📚 Leitor de E-books (PDF)")

        if not PDF_VIEWER_AVAILABLE:
            st.error("O componente de visualização de PDF não está instalado. Execute `pip install streamlit-pdf-viewer` no seu terminal.")
        else:
            pdf_files_map = find_local_pdfs()
            if not pdf_files_map:
                st.warning("Nenhum arquivo PDF encontrado nas pastas `data/repo/ebooks` ou `data/Turmas`.")
            else:
                # Exibe os nomes dos arquivos de forma mais amigável
                display_names = sorted(list(pdf_files_map.keys()))
                selected_pdf_key = st.selectbox("Selecione um e-book para ler:", ["-- Selecione --"] + display_names)

                if selected_pdf_key != "-- Selecione --":
                    pdf_path = pdf_files_map[selected_pdf_key]
                    try:
                        with open(pdf_path, "rb") as f:
                            pdf_data = f.read()
                        pdf_viewer(pdf_data)
                    except Exception as e:
                        st.error(f"Não foi possível abrir o PDF: {e}")

    # --- Aba de Plugins Externos ---
    elif selected_tab == "Externos":
        st.markdown("### 📂 Executar Plugins Externos")
        st.warning("⚠️ **Atenção:** Esta funcionalidade executa scripts Python diretamente. Use apenas scripts de fontes confiáveis.")

        plugins_dir = os.path.join("data", "repo", "plugins")

        if not os.path.exists(plugins_dir):
            st.info(f"Para adicionar plugins externos, crie a pasta `{plugins_dir}` e coloque seus arquivos `.py` nela.")
        else:
            # Removemos a lógica de 'active_plugin' daqui para não ficar estranho,
            # deixando esta aba apenas para gerenciamento e execução de scripts rápidos.
            
            plugin_files = [f for f in os.listdir(plugins_dir) if f.endswith(".py")]
            st.success(f"Encontrados {len(plugin_files)} plugins:")
            for plugin_file in plugin_files:
                plugin_path = os.path.join(plugins_dir, plugin_file)
                with st.expander(f"**{plugin_file}**"):
                    try:
                        with open(plugin_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            docstring_match = re.match(r'^\s*"""(.*?)"""', content, re.DOTALL)
                            if docstring_match:
                                st.caption(docstring_match.group(1).strip())
                    except Exception:
                        st.caption("Sem descrição.")

                    if st.button(f"Executar no Terminal", key=f"run_{plugin_file}"):
                        with st.spinner(f"Executando..."):
                            result = subprocess.run([sys.executable, plugin_path], capture_output=True, text=True, encoding='utf-8')
                            st.code(result.stdout if result.stdout else "Executado sem saída.")

    # --- Aba de Agenda (Dedicada) ---
    elif selected_tab == "Agenda":
        agenda_path = os.path.join("data", "repo", "plugins", "agenda.py")
        if os.path.exists(agenda_path):
            render_plugin_integrated(agenda_path)
        else:
            st.info("O plugin de agenda não foi encontrado em `data/repo/plugins/agenda.py`.")

    # --- Aba de Atividades Diárias ---
    elif selected_tab == "Atividades":
        activities_path = os.path.join("data", "repo", "plugins", "daily_activities.py")
        if os.path.exists(activities_path):
            render_plugin_integrated(activities_path)
        else:
            st.info("O plugin de atividades não foi encontrado.")

    # --- Aba de Gestão de Notas ---
    elif selected_tab == "Notas":
        scores_path = os.path.join("data", "repo", "plugins", "student_scores.py")
        if os.path.exists(scores_path):
            render_plugin_integrated(scores_path)
        else:
            st.info("O plugin de gestão de notas não foi encontrado em `data/repo/plugins/student_scores.py`.")

    # --- Aba de Frequência ---
    elif selected_tab == "Frequência":
        attendance_path = os.path.join("data", "repo", "plugins", "student_attendance.py")
        if os.path.exists(attendance_path):
            render_plugin_integrated(attendance_path)
        else:
            st.info("O plugin de frequência não foi encontrado em `data/repo/plugins/student_attendance.py`.")

    # --- Aba de Grade Semanal ---
    elif selected_tab == "Grade":
        grade_path = os.path.join("data", "repo", "plugins", "grade_semanal.py")
        if os.path.exists(grade_path):
            render_plugin_integrated(grade_path)
        else:
            st.info("O plugin de grade semanal não foi encontrado.")