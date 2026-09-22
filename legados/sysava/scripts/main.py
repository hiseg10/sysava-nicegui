import os
import sys
import traceback

# from apps.utils import stop_ollama_server

# Adiciona o diretório 'apps' ao sys.path para garantir que os módulos possam ser encontrados
# Isso pode não ser estritamente necessário se você executar main.py da raiz do projeto,
# mas adiciona robustez.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# --- Importar as funções principais dos outros scripts ---
# NOTA: Os scripts importados precisam ser refatorados para ter uma função principal
#       que possa ser chamada (ex: run_ler_livro(), run_processar_textos(), etc.)

try:
    # Exemplo de como seria a importação (assumindo refatoração)
    from ler_livro_pdf import run_ler_livro # Precisa criar esta função em ler_livro_pdf.py
    from processar_textos import run_processar_textos # Precisa criar esta função em processar_textos.py
    from extrair_aula_especifica import run_extrair_aula # Precisa criar/adaptar esta função
    from atualiza_includes_livro import run_atualizar_includes # Precisa criar esta função
    from muda_templates import run_muda_templates # Precisa criar esta função
    # from alterar_templates import run_alterar_templates # Descomente se quiser usar este também
    from ask_ollama import run_ask_ollama # Precisa criar esta função
    from utils import stop_ollama_server # Importa diretamente, pois está na mesma pasta

except ImportError as e:
    print(f"Erro de importação: {e}")
    print("Certifique-se de que os scripts Python em 'apps/' foram refatorados")
    print("para terem uma função principal (ex: run_script_nome()) e que não há erros de sintaxe.")
    sys.exit(1)

def exibir_menu():
    """Exibe o menu de opções para o usuário."""
    print("\n--- Menu Principal de Ferramentas ---")
    print("1. Extrair Texto de PDF (Intervalo de Páginas)")
    print("2. Processar/Limpar Textos Extraídos (.txt)")
    print("3. Extrair Aula Específica de Arquivo .txt")
    print("4. Atualizar Includes Markdown dos Livros (.txt -> .md)")
    print("5. Processar Templates Jinja nos Rascunhos (.md -> .md)")
    # print("6. Alterar Templates (Alternativo)") # Opção comentada
    print("7. Perguntar ao Ollama (Deepseek Coder)")
    print("8. Parar Servidor Ollama") # Nova opção
    print("0. Sair")
    print("------------------------------------")

def main():
    """Função principal que executa o menu."""
    while True:
        exibir_menu()
        escolha = input("Digite o número da opção desejada: ")

        try:
            if escolha == '1':
                run_ler_livro()
            elif escolha == '2':
                run_processar_textos()
            elif escolha == '3':
                run_extrair_aula()
            elif escolha == '4':
                run_atualizar_includes()
            elif escolha == '5':
                run_muda_templates()
            # elif escolha == '6':
            #     run_alterar_templates()
            elif escolha == '7':
                run_ask_ollama()
            elif escolha == '8':
                stop_ollama_server()
            elif escolha == '0':
                print("Saindo...")
                break
            else:
                print("Opção inválida. Tente novamente.")
        except Exception as e:
            print(f"\nERRO ao executar a opção {escolha}: {e}")
            traceback.print_exc() # Imprime detalhes do erro
        print("\nPressione Enter para continuar...")
        input()

if __name__ == "__main__":
    main()