import nicegui

def dashboard_page():
    with nicegui.ui.column().classes("p-4"):
        nicegui.ui.html('<h1>✅ Bem-vindo ao SysAva!</h1><p>Sistema de gerenciamento de documentos e IA.</p>')
        nicegui.ui.button('Ir para PDF Manager', on_click=lambda: nicegui.ui.open('/pdf_manager'))

# Iniciar a aplicação
if __name__ == '__main__':
    nicegui.ui.run(title='SysAva - Dashboard', port=8080, debug=True)