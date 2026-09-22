import os
import re

def fix_gabaritos():
    # Define o caminho raiz (assumindo que este script está na pasta scripts/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_path = os.path.join(project_root, 'data', 'Turmas')

    print(f"🔍 Iniciando varredura e padronização de gabaritos em: {base_path}")

    files_modified = 0

    # Dicionário de mapeamento para garantir a normalização
    gabarito_map = {
        'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e',
        'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e'
    }

    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content

                # --- PASS 1: Corrige gabaritos "inline" (tudo na mesma linha) ---
                # Ex: "**Gabarito:** 1-c, 2-b" -> "**✅ Gabarito:**\n1. c\n2. b"
                def replacer_inline(match_obj):
                    line_with_answers = match_obj.group(0)
                    # Regex para encontrar pares de numero-letra
                    answers = re.findall(r'(\d+)\s*[:\.\)\-\s\[\(]*\s*([a-eA-E])(?:[:\.\)\-\]\}]|\b)', line_with_answers)
                    
                    if not answers:
                        return line_with_answers # Retorna original se não encontrar pares

                    new_block = ["**✅ Gabarito:**"]
                    for num, letter in sorted(answers, key=lambda x: int(x[0])):
                        if letter in gabarito_map:
                            new_block.append(f"{num}. {gabarito_map[letter]}")
                    
                    return "\n".join(new_block)

                # Regex para encontrar a linha de cabeçalho que também contém respostas
                header_with_answers_regex = r'^(?:(?:\*\*|##).*?(?:Gabarito|Resposta|Solução)).*?\d+.*[a-eA-E].*$'
                content = re.sub(header_with_answers_regex, replacer_inline, content, flags=re.MULTILINE | re.IGNORECASE)

                # --- PASS 2: Corrige gabaritos comentados (um por linha) ---
                # Ex: "1. **Resposta: (B).** ..." -> "1. b"
                def replacer_commented(match_obj):
                    num = match_obj.group(1)
                    letter = match_obj.group(2)
                    if letter in gabarito_map:
                        return f"{num}. {gabarito_map[letter]}"
                    return match_obj.group(0) # Retorna original se a letra não for válida

                # Regex para encontrar a linha de resposta comentada
                commented_answer_regex = r'^\s*(\d+)\.\s*\*\*Resposta:\s*\(([a-eA-E])\)\..*$'
                content = re.sub(commented_answer_regex, replacer_commented, content, flags=re.MULTILINE)

                # --- PASS 3: Corrige gabaritos em lista simples com texto extra ---
                # Ex: "1. b) switch-case" -> "1. b"
                def replacer_simple_list(match_obj):
                    num = match_obj.group(1)
                    letter = match_obj.group(2)
                    if letter in gabarito_map:
                        return f"{num}. {gabarito_map[letter]}"
                    return match_obj.group(0)

                # Regex para encontrar a linha de resposta em lista simples
                # Captura: Numero + Ponto + Espaços + Letra + (Ponto ou Parentese) + Espaços + Texto
                simple_list_regex = r'^\s*(\d+)\.\s*([a-eA-E])[\.\)]\s+.*$'
                content = re.sub(simple_list_regex, replacer_simple_list, content, flags=re.MULTILINE)

                # --- PASS 4: Corrige gabaritos com letra em negrito ---
                # Ex: "1. **c)** Texto..." -> "1. c"
                def replacer_bold_letter(match_obj):
                    num = match_obj.group(1)
                    letter = match_obj.group(2)
                    if letter in gabarito_map:
                        return f"{num}. {gabarito_map[letter]}"
                    return match_obj.group(0)

                # Regex para encontrar a linha de resposta com letra em negrito
                bold_letter_regex = r'^\s*(\d+)\.\s*\*\*([a-eA-E])[\.\)]\*\*\s*.*$'
                content = re.sub(bold_letter_regex, replacer_bold_letter, content, flags=re.MULTILINE)

                if content != original_content:
                    print(f"  🛠️  Corrigindo gabarito em: {file}")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    files_modified += 1

    if files_modified == 0:
        print("\n✅ Nenhum arquivo precisou de correção. Tudo parece estar nos conformes!")
    else:
        print(f"\n✅ Concluído! Total de arquivos padronizados: {files_modified}")

if __name__ == "__main__":
    fix_gabaritos()