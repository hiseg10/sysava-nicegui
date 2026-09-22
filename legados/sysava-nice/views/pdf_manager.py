import nicegui

def pdf_manager_page():
    with nicegui.ui.column().classes("p-4"):
        nicegui.ui.html('<h1>📄 Gerenciador de PDFs</h1><p>Carregue ou gerencie seus arquivos PDF.</p>')
        nicegui.ui.button('Carregar arquivo', on_click=lambda: nicegui.ui.open('/upload'))
        nicegui.ui.label("Status: Sem arquivos carregados")

# Iniciar a aplicação
if __name__ == '__main__':
    nicegui.ui.run(title='SysAva - PDF Manager', port=8080, debug=True)