import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv

# Adiciona o diretório raiz ao path para encontrar o .env corretamente
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
env_path = os.path.join(root_dir, '.env')
load_dotenv(env_path)

def list_available_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY não encontrada no .env")
        return

    genai.configure(api_key=api_key)
    
    print("🔍 Listando modelos disponíveis para sua chave de API...")
    print("-" * 50)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" ✅ {m.name}")
    except Exception as e:
        print(f"❌ Erro ao listar modelos: {e}")

if __name__ == "__main__":
    list_available_models()