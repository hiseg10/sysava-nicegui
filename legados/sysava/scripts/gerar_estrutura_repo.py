import os
from pathlib import Path

def replicar_estrutura_pastas(origem: str, destino: str):
    """
    Replica a estrutura de diretórios da pasta de origem para a pasta de destino.
    Apenas cria as pastas, não copia os arquivos.
    """
    origem_path = Path(origem)
    destino_path = Path(destino)
    
    if not origem_path.exists():
        print(f"Erro: O diretório de origem '{origem}' não existe.")
        return
        
    print(f"Lendo estrutura de '{origem_path}'...")
    print(f"Criando estrutura em '{destino_path}'...\n")
    
    if not destino_path.exists():
        destino_path.mkdir(parents=True, exist_ok=True)
        
    pastas_criadas = 0
    
    # Percorre toda a árvore de diretórios da origem
    for root, dirs, files in os.walk(origem_path):
        root_path = Path(root)
        caminho_relativo = root_path.relative_to(origem_path)
        
        for d in dirs:
            destino_dir = destino_path / caminho_relativo / d
            if not destino_dir.exists():
                destino_dir.mkdir(parents=True, exist_ok=True)
                print(f"Criada: {destino_dir}")
                pastas_criadas += 1
                
    print(f"\nOperação concluída. {pastas_criadas} nova(s) pasta(s) criada(s) em '{destino_path}'.")

if __name__ == "__main__":
    # Define os caminhos absolutos com base no diretório atual (raiz do projeto se rodar da raiz)
    # script na pasta scripts: BASE_DIR será b:/Dev/SysAva
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    SOURCE_DIR = BASE_DIR / "data" / "Turmas"
    TARGET_DIR = BASE_DIR / "data" / "repo"
    
    replicar_estrutura_pastas(str(SOURCE_DIR), str(TARGET_DIR))
