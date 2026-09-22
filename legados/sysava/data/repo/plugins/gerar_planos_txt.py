"""
Plugin: Gerador de Planos de Aula em TXT (SysAva)

Estrutura em 3 abas (passo a passo):
  Aba 1 - Diagnóstico: seleciona turma/disciplina e investiga o historico_aulas
          (última aula, data, total registrado e faltante para a carga horária).
  Aba 2 - Planejamento: lê os TXT de aulas/pendentes e aulas/prontas, cruza com a
          tabela lessons e sugere quais planos devem ir para prontas ou pendentes.
  Aba 3 - Operações: visualizar, gerar individual ou em lote.

Saída:
  - data/repo/plugins/aulas/prontas/   (conteúdo real: lessons ou .md)
  - data/repo/plugins/aulas/pendentes/ (valores padrão de fallback)
  - espelhado também em plugins/aulas/...
"""

import os
import sys
import re
import json
from datetime import datetime, date, timedelta
import streamlit as st
import pandas as pd

# Adiciona a raiz do projeto ao sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from legados.sysava.services import database as db
    from legados.sysava.services.contexto_aulas import resolver_pasta_turma, resolver_pasta_disciplina, normalizar_para_matching
except ImportError:
    db = None

# --- Diretórios de saída ---
OUTPUT_DIR_PRONTAS_REPO = os.path.join(PROJECT_ROOT, "data", "repo", "plugins", "aulas", "prontas")
OUTPUT_DIR_PRONTAS_ROOT = os.path.join(PROJECT_ROOT, "plugins", "aulas", "prontas")
OUTPUT_DIR_PENDENTES_REPO = os.path.join(PROJECT_ROOT, "data", "repo", "plugins", "aulas", "pendentes")
OUTPUT_DIR_PENDENTES_ROOT = os.path.join(PROJECT_ROOT, "plugins", "aulas", "pendentes")

# Aliases retrocompatíveis
OUTPUT_DIR_REPO = OUTPUT_DIR_PRONTAS_REPO
OUTPUT_DIR_ROOT = OUTPUT_DIR_PRONTAS_ROOT

PASTAS_PLANOS = {
    "prontas": {"repo": OUTPUT_DIR_PRONTAS_REPO, "root": OUTPUT_DIR_PRONTAS_ROOT},
    "pendentes": {"repo": OUTPUT_DIR_PENDENTES_REPO, "root": OUTPUT_DIR_PENDENTES_ROOT},
}

for _pasta in (OUTPUT_DIR_PRONTAS_REPO, OUTPUT_DIR_PRONTAS_ROOT, OUTPUT_DIR_PENDENTES_REPO, OUTPUT_DIR_PENDENTES_ROOT):
    os.makedirs(_pasta, exist_ok=True)

PADRAO_ARQUIVO_PLANO = re.compile(r'^PLANO_TURMA_(\d+)_DISC_(\d+)_AULA_(\d+)\.txt$', re.IGNORECASE)

DIAS_SEMANA_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

ESTRATEGIAS_OPCOES = [
    "Aula expositiva com demonstracao e discussao.",
    "Aula pratica em laboratorio com resolucao de desafios.",
    "Aprendizagem baseada em problemas (PBL) e discussao em grupo.",
    "Sala de aula invertida com estudo de caso e apresentacao.",
    "Desenvolvimento orientado a projetos (Hands-on Coding)."
]

HORARIOS_PADRAO = [
    "07:10 - 08:10", "08:10 - 09:10", "09:10 - 10:10", "09:30 - 10:30",
    "10:30 - 11:30", "11:30 - 12:30", "13:30 - 14:30", "14:30 - 15:30",
    "14:50 - 15:50", "15:50 - 16:50"
]


# =============================================================================
# UTILITÁRIOS DE TEXTO / EXTRAÇÃO DE CONTEÚDO
# =============================================================================

def limpar_markdown(texto: str) -> str:
    """Remove marcações Markdown para obter texto limpo."""
    if not texto:
        return ""
    t = str(texto)
    t = re.sub(r'#+\s*', '', t)
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = re.sub(r'`(.*?)`', r'\1', t)
    return t.strip()


def extrair_objetivos(content: str) -> str:
    """Extrai os objetivos de aprendizagem do markdown da aula."""
    if not content:
        return "- Compreender os conceitos teóricos e práticos abordados na aula."

    # Procura por seção de objetivos
    match = re.search(r'##\s*(?:🎯\s*)?Objetivos(?: de Aprendizagem)?\n+(.*?)(?=\n##|\n---|\Z)', content, re.DOTALL | re.IGNORECASE)
    if match:
        raw_objs = match.group(1).strip()
        linhas = []
        for line in raw_objs.splitlines():
            line_s = line.strip()
            if line_s.startswith(('*', '-', '•')):
                item = re.sub(r'^[\*\-•]\s*', '', line_s)
                item_clean = limpar_markdown(item)
                if item_clean:
                    linhas.append(f"- {item_clean}")
            elif line_s:
                item_clean = limpar_markdown(line_s)
                if item_clean:
                    linhas.append(f"- {item_clean}")
        if linhas:
            return "\n".join(linhas)

    return "- Compreender os conceitos fundamentais e aplicar as técnicas apresentadas."


def extrair_atividade(content: str) -> str:
    """Extrai o exemplo/desafio prático ou atividade da aula."""
    if not content:
        return "Cenário: Atividade prática orientada em laboratório com desenvolvimento de código e análise dos resultados."

    # Tenta Desafio Prático, Exemplo Prático ou Atividade
    match = re.search(r'##\s*(?:🛠️|🚀|🎯|💻)?\s*(?:Exemplo Prático|Desafio Prático|Atividade Prática|Atividade)\n+(.*?)(?=\n##\s*[🏁🧰❓]|\n##\s*Conclusão|\n---|\Z)', content, re.DOTALL | re.IGNORECASE)
    if match:
        raw_act = match.group(1).strip()
        # Remove blocos longos de código e mantém o enunciado descritivo
        texto_limpo = re.sub(r'```[\s\S]*?```', '', raw_act).strip()
        linhas = [l.strip() for l in texto_limpo.splitlines() if l.strip() and not l.strip().startswith(('<!DOCTYPE', '<html', '<head', '<body', '<style', 'import '))]
        resumo = " ".join(linhas[:8])
        if resumo:
            if not resumo.lower().startswith("cenário"):
                resumo = f"Cenário: {resumo}"
            return resumo[:500] + ("..." if len(resumo) > 500 else "")

    # Fallback para a introdução
    intro_match = re.search(r'##\s*(?:🏁\s*)?Introdução\n+(.*?)(?=\n##|\n---|\Z)', content, re.DOTALL | re.IGNORECASE)
    if intro_match:
        intro_clean = limpar_markdown(intro_match.group(1).strip())
        return f"Cenário: Desenvolvimento de atividades práticas baseadas no tema: {intro_clean[:300]}..."

    return "Cenário: Atividade prática orientada em laboratório com desenvolvimento de código e análise dos resultados."


def extrair_recursos(content: str, title: str) -> str:
    """Extrai recursos, links de referência e termos recomendados."""
    if not content:
        return f"Material didático digital, slides de aula e referências técnicas sobre {title}."

    match = re.search(r'##\s*(?:🧰\s*)?Recursos(?: e Links)?\n+(.*?)(?=\n##|\n---|\Z)', content, re.DOTALL | re.IGNORECASE)
    if match:
        rec_raw = match.group(1).strip()
        linhas = []
        for line in rec_raw.splitlines():
            line_s = line.strip()
            if line_s.startswith(('*', '-', '•')):
                clean_l = limpar_markdown(line_s)
                if clean_l:
                    linhas.append(clean_l)
            elif line_s:
                linhas.append(limpar_markdown(line_s))
        if linhas:
            return " ".join(linhas)

    return f"Referência técnica e documentação sobre {title}. Ferramentas de desenvolvimento e editor de código."


def conteudo_padrao(disciplina_nome: str, aula_num: int) -> dict:
    """Valores padrão (fallback) usados em planos pendentes."""
    return {
        'titulo': f"Aula {aula_num:02d} - {disciplina_nome}",
        'objetivos': "- Compreender os conceitos teóricos e práticos abordados na aula.",
        'atividade': "Cenário: Atividade prática orientada em laboratório com desenvolvimento de código e análise dos resultados.",
        'recursos': f"Material didático digital, slides de aula e referências técnicas sobre {disciplina_nome}.",
        'fonte': "padrão",
    }


def extrair_dados_aula_md(turma_nome: str, disciplina_nome: str, aula_num: int) -> dict:
    """Busca o arquivo .md da aula correspondente no disco ou no catálogo."""
    turmas_dir = os.path.join(PROJECT_ROOT, "data", "Turmas")
    turma_real = resolver_pasta_turma(turmas_dir, turma_nome)
    turma_path = os.path.join(turmas_dir, turma_real)

    if not os.path.exists(turma_path):
        return {"found": False, "title": f"Aula {aula_num:02d} - {disciplina_nome}", "content": "", "path": None}

    # Tenta resolver a pasta exata da disciplina primeiro
    disc_real = resolver_pasta_disciplina(turma_path, disciplina_nome)
    disc_path = os.path.join(turma_path, disc_real)

    search_paths = []
    if os.path.exists(disc_path) and os.path.isdir(disc_path):
        search_paths.append(disc_path)

    # Adiciona outras pastas caso necessário como fallback
    norm_disc = normalizar_para_matching(disciplina_nome)
    try:
        for d_pasta in os.listdir(turma_path):
            d_full = os.path.join(turma_path, d_pasta)
            if not os.path.isdir(d_full) or d_full in search_paths:
                continue
            norm_pasta = normalizar_para_matching(d_pasta)
            if norm_disc == norm_pasta or norm_disc in norm_pasta or norm_pasta in norm_disc:
                search_paths.append(d_full)
    except Exception:
        pass

    for s_path in search_paths:
        for root, _, files in os.walk(s_path):
            for file in files:
                if file.lower().endswith(".md") and not file.startswith("links_"):
                    m = re.search(r'Aula[_\s]*(\d+)', file, re.IGNORECASE)
                    if m and int(m.group(1)) == aula_num:
                        try:
                            with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                                content = f.read()
                            m_title = re.search(r'^#\s*(.*)', content, re.MULTILINE)
                            title = m_title.group(1).strip() if m_title else file.replace(".md", "")
                            return {
                                "found": True,
                                "title": title,
                                "content": content,
                                "path": os.path.join(root, file)
                            }
                        except Exception:
                            pass

    return {
        "found": False,
        "title": f"Aula {aula_num:02d} - {disciplina_nome}",
        "content": "",
        "path": None
    }


# =============================================================================
# CONSULTAS CACHEADAS (evita egress repetido no rerun do Streamlit)
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def buscar_historico_aulas(disciplina_id: int, turma_nome: str, turma_id=None) -> list:
    """Busca registros do historico_aulas filtrando por disciplina e turma."""
    if not db or not db.is_db_connected():
        return []
    try:
        res = db.supabase.table("historico_aulas")\
            .select("id, data_aula, horario, turma, turma_id, disciplina, disciplina_id, status, created_at")\
            .eq("disciplina_id", disciplina_id)\
            .execute()
        rows = res.data or []
    except Exception:
        return []

    norm_turma = normalizar_para_matching(turma_nome or "")
    if not norm_turma and turma_id is None:
        return rows

    filtrados = []
    for r in rows:
        r_tid = r.get("turma_id")
        r_turma_norm = normalizar_para_matching(r.get("turma") or "")
        match_id = turma_id is not None and r_tid is not None and str(r_tid) == str(turma_id)
        match_nome = bool(norm_turma) and bool(r_turma_norm) and (
            norm_turma in r_turma_norm or r_turma_norm in norm_turma
        )
        if match_id or match_nome:
            filtrados.append(r)
    return filtrados


@st.cache_data(ttl=300, show_spinner=False)
def ultima_data_turma(turma_nome: str, turma_id=None):
    """Última data de aula registrada para a TURMA (qualquer disciplina).

    Usada como referência quando a disciplina selecionada não tem histórico
    próprio (ex.: Front-End, que não vem no historico_aulas)."""
    if not db or not db.is_db_connected():
        return None

    rows = []
    try:
        if turma_id is not None:
            res = db.supabase.table("historico_aulas")\
                .select("data_aula")\
                .eq("turma_id", turma_id)\
                .execute()
            rows = res.data or []
    except Exception:
        rows = []

    # Fallback por nome (caso turma_id não bata)
    if not rows:
        try:
            res = db.supabase.table("historico_aulas").select("data_aula, turma").execute()
            norm_turma = normalizar_para_matching(turma_nome or "")
            for r in (res.data or []):
                rn = normalizar_para_matching(r.get("turma") or "")
                if norm_turma and rn and (norm_turma in rn or rn in norm_turma):
                    rows.append(r)
        except Exception:
            rows = []

    datas = [_parse_data(r.get("data_aula")) for r in rows]
    datas = [d for d in datas if d]
    return max(datas) if datas else None


@st.cache_data(ttl=300, show_spinner=False)
def _lessons_light(disciplina_id: int) -> list:
    """Listagem leve de lessons (sem full_content) para análise de disponibilidade."""
    if not db or not db.is_db_connected():
        return []
    try:
        return db.get_lessons_for_subject(disciplina_id)
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _classes_cached() -> list:
    """Turmas cacheadas para evitar leitura repetida a cada rerun."""
    if not db or not db.is_db_connected():
        return []
    try:
        return db.get_classes()
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _subjects_for_class_cached(class_id) -> list:
    """Disciplinas da turma cacheadas."""
    if not db or not db.is_db_connected():
        return []
    try:
        return db.get_subjects_for_class(class_id)
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _lessons_full_cached(disciplina_id: int) -> list:
    """Listagem completa de lessons cacheada.

    Evita baixar full_content repetidamente (1 query por lote em vez de 1 por aula)."""
    if not db or not db.is_db_connected():
        return []
    try:
        return db.get_lessons_for_subject_full(disciplina_id)
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def resolver_raiz(subject_id):
    """Resolve a disciplina selecionada (filha, com sufixo) para a raiz/mãe.

    A raiz é a dona do historico_aulas (vem do portal). Usa o RPC central
    `resolver_subject_raiz` (via services.database.get_subject_raiz) e, se
    indisponível, cai no walk local de `aliases_id` ou devolve o próprio id.
    """
    if subject_id is None:
        return None
    if db and db.is_db_connected():
        try:
            return int(db.get_subject_raiz(subject_id))
        except Exception:
            pass
    return int(subject_id)


def resolver_nome_mae(subject_id, nome_fallback: str = "") -> str:
    """Retorna o nome da raiz/mãe da disciplina (sem sufixo) para exibição/TXT."""
    if db and db.is_db_connected():
        try:
            raiz_id = resolver_raiz(subject_id)
            if raiz_id is not None:
                row = db.get_subject_by_id(raiz_id)
                if row and row.get('name'):
                    return row['name']
        except Exception:
            pass
    return nome_fallback


# =============================================================================
# DIAGNÓSTICO E PLANEJAMENTO
# =============================================================================

def _parse_data(valor) -> date:
    """Converte datas do histórico (dd/mm/aaaa ou ISO) em date."""
    if not valor:
        return None
    valor = str(valor).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(valor[:10], fmt).date()
        except Exception:
            continue
    return None


def listar_planos_pasta(nome_pasta: str) -> list:
    """Lista os TXT de plano em uma pasta (prontas/pendentes) com metadados."""
    info = PASTAS_PLANOS.get(nome_pasta)
    if not info:
        return []
    pasta = info["repo"]
    if not os.path.isdir(pasta):
        return []

    resultados = []
    for arq in sorted(os.listdir(pasta)):
        if not arq.lower().endswith(".txt"):
            continue
        m = PADRAO_ARQUIVO_PLANO.match(arq)
        if not m:
            continue
        caminho = os.path.join(pasta, arq)
        dados = {
            "arquivo": arq,
            "caminho": caminho,
            "turma_id": int(m.group(1)),
            "disciplina_id": int(m.group(2)),
            "aula_num": int(m.group(3)),
            "pasta": nome_pasta,
            "tamanho": os.path.getsize(caminho),
            "data": "",
            "titulo": "",
        }
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                conteudo = f.read()
            md = re.search(r'DATA:\s*([\d\-/]+)', conteudo)
            mt = re.search(r'\[CONTEUDO\]\n(.*?)(?=\n\n|\Z)', conteudo, re.DOTALL)
            dados["data"] = md.group(1) if md else ""
            dados["titulo"] = mt.group(1).strip() if mt else ""
        except Exception:
            pass
        resultados.append(dados)
    return resultados


def _plano_pertence(plano: dict, turma_id, disciplina_id) -> bool:
    """Verifica se o plano pertence à turma/disciplina selecionada."""
    return (str(plano.get('turma_id')) == str(turma_id)
            and str(plano.get('disciplina_id')) == str(disciplina_id))


def calcular_n_aula_automatico(disciplina_id: int, disciplina_nome: str = "", turma_nome: str = "", turma_id=None) -> int:
    """Calcula o número da próxima aula baseado no histórico de registros do portal."""
    if not db or not db.is_db_connected():
        return 1
    try:
        return len(buscar_historico_aulas(disciplina_id, turma_nome, turma_id)) + 1
    except Exception:
        return 1


def calcular_diagnostico(turma_nome: str, turma_id, disciplina_id: int) -> dict:
    """Investiga o historico_aulas e resume a situação da disciplina/turma."""
    registros = buscar_historico_aulas(disciplina_id, turma_nome, turma_id)

    datas_validas = []
    for r in registros:
        d = _parse_data(r.get("data_aula"))
        if d:
            datas_validas.append((d, r))
    datas_validas.sort(key=lambda x: x[0])

    ultima_data = datas_validas[-1][0] if datas_validas else None
    ultimo_registro = datas_validas[-1][1] if datas_validas else None

    return {
        "registros": registros,
        "qtd": len(registros),
        "ultima_data": ultima_data,
        "ultimo_registro": ultimo_registro,
        "datas_validas": datas_validas,
    }


def montar_analise_planejamento(carga_horaria: int, aulas_lessons: dict,
                                aulas_prontas: set, aulas_pendentes: set,
                                qtd_historico: int) -> list:
    """Cruza lessons x histórico x pastas e sugere o destino de cada aula."""
    linhas = []
    for n in range(1, int(carga_horaria) + 1):
        tem_lesson = n in aulas_lessons
        tem_pronta = n in aulas_prontas
        tem_pendente = n in aulas_pendentes
        registrada = n <= qtd_historico

        titulo_lesson = aulas_lessons[n].get('title', '') if tem_lesson else ""

        if tem_pronta:
            sugestao, acao = "✅ Pronta já existe", "nenhuma"
        elif tem_lesson:
            sugestao, acao = "🟢 Gerar PRONTA (conteúdo de lessons)", "pronta"
        elif tem_pendente:
            sugestao, acao = "⏳ Pendente já existe", "nenhuma"
        else:
            sugestao, acao = "🟡 Gerar PENDENTE (valores padrão)", "pendente"

        linhas.append({
            'Aula': n,
            'Tem em lessons': "🟢 Sim" if tem_lesson else "🔴 Não",
            'Título (lessons)': titulo_lesson[:70],
            'Registrada no histórico': "✔️" if registrada else "—",
            'Pronta': "✅" if tem_pronta else "—",
            'Pendente': "🟡" if tem_pendente else "—",
            'Sugestão': sugestao,
            '_acao': acao,
        })
    return linhas


# =============================================================================
# PREENCHIMENTO E GERAÇÃO
# =============================================================================

def auto_preencher_conteudo(turma_nome: str, disciplina_nome: str, disciplina_id: int, aula_num: int) -> dict:
    """Preenche automaticamente título, objetivos, atividade e recursos."""

    # 1. Busca no catálogo de arquivos .md
    dados_md = extrair_dados_aula_md(turma_nome, disciplina_nome, aula_num)

    # 2. Busca no banco de dados usando disciplina_id (não nome)
    lesson_db = None
    if db and db.is_db_connected():
        try:
            lessons = _lessons_full_cached(disciplina_id)
            for l in lessons:
                if re.search(rf"Aula\s*0?{aula_num}\b", l['title'], re.IGNORECASE):
                    lesson_db = l
                    break
        except Exception:
            pass

    # 3. Prioriza banco > .md > fallback
    titulo = (lesson_db or {}).get('title') or dados_md.get('title') or f"Aula {aula_num:02d}"
    conteudo_md = dados_md.get('content', '')
    if lesson_db and lesson_db.get('full_content'):
        conteudo_md = lesson_db['full_content']

    objetivos = (lesson_db or {}).get('objective') or extrair_objetivos(conteudo_md)
    atividade = extrair_atividade(conteudo_md)
    recursos = (lesson_db or {}).get('resources') or extrair_recursos(conteudo_md, titulo)

    # 4. Determina fonte
    if lesson_db:
        fonte = "banco de dados"
    elif dados_md.get('found'):
        fonte = "arquivo local"
    else:
        fonte = "padrão"

    return {
        'titulo': titulo,
        'objetivos': objetivos,
        'atividade': atividade,
        'recursos': recursos,
        'fonte': fonte,
        'lesson_db': lesson_db,
        'dados_md': dados_md
    }


def verificar_plano_existente(turma_id: int, disciplina_id: int, aula_num: int, pasta: str = "prontas") -> dict:
    """Verifica se já existe plano gerado para esta aula em uma das pastas."""
    info = PASTAS_PLANOS.get(pasta)
    if not info:
        return {'existe': False}
    nome_arquivo = f"PLANO_TURMA_{turma_id}_DISC_{disciplina_id}_AULA_{aula_num:02d}.txt"
    caminho = os.path.join(info["repo"], nome_arquivo)

    if os.path.exists(caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            conteudo = f.read()

        match_data = re.search(r'DATA:\s*(\d{4}-\d{2}-\d{2})', conteudo)
        match_titulo = re.search(r'\[CONTEUDO\]\n(.*?)(?=\n\n|\Z)', conteudo, re.DOTALL)

        return {
            'existe': True,
            'data': match_data.group(1) if match_data else "desconhecida",
            'titulo': match_titulo.group(1).strip() if match_titulo else "N/A",
            'caminho': caminho,
            'tamanho': os.path.getsize(caminho)
        }

    return {'existe': False}


def calcular_datas_sequenciais(turma_nome: str, disciplina_nome: str, data_inicio: date, num_aulas: int) -> list:
    """Calcula datas sequenciais baseado na grade semanal."""
    dias_disciplina = set()

    try:
        if db and db.is_db_connected():
            res_slots = db.supabase.table("weekly_schedule")\
                .select("day_of_week, subject_name")\
                .eq("class_name", turma_nome)\
                .execute()

            if res_slots.data:
                for row in res_slots.data:
                    disc = row.get('subject_name', '')
                    dia = row.get('day_of_week', '')
                    if disciplina_nome.upper() in disc.upper() or disc.upper() in disciplina_nome.upper():
                        dia_lower = dia.lower()[:3]
                        for nome_completo in ["segunda", "terça", "quarta", "quinta", "sexta"]:
                            if dia_lower in nome_completo:
                                dias_disciplina.add(nome_completo.capitalize())
                                break
    except Exception:
        pass

    if not dias_disciplina:
        dias_disciplina = {"Segunda", "Terça", "Quarta", "Quinta", "Sexta"}

    datas = []
    data_atual = data_inicio
    dias_semana_map = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}

    while len(datas) < num_aulas:
        dia_nome = dias_semana_map[data_atual.weekday()]
        if dia_nome in dias_disciplina:
            datas.append(data_atual)
        data_atual += timedelta(days=1)

    return datas


def buscar_alunos_presenca(class_id: int, class_name: str, subject_id: int, subject_name: str, data_str: str) -> list:
    """Busca os alunos matriculados e o status de presença na tabela attendance ou arquivo local."""
    attendance_map = {}

    # 1. Tenta carregar do Supabase (tabela attendance)
    if db and db.is_db_connected():
        try:
            res = db.supabase.table("attendance")\
                .select("student_name, is_present, subject_id, subject_name")\
                .eq("class_name", class_name)\
                .eq("date", data_str)\
                .execute()
            if res.data:
                for item in res.data:
                    s_id = item.get('subject_id')
                    s_name = item.get('subject_name', '')
                    id_match = (s_id is not None and str(s_id) == str(subject_id))
                    name_match = (s_name and subject_name.upper() in s_name.upper())
                    sem_id = (s_id is None and name_match)
                    if id_match or name_match or sem_id:
                        st_name = item['student_name'].strip().upper()
                        is_pres = item.get('is_present', True)
                        attendance_map[st_name] = "Presente" if is_pres else "Falta"
        except Exception:
            pass

    # 2. Tenta carregar do arquivo local student_attendance.json como fallback
    try:
        att_json_path = os.path.join(os.path.dirname(__file__), "student_attendance.json")
        if os.path.exists(att_json_path):
            with open(att_json_path, 'r', encoding='utf-8') as f:
                att_data = json.load(f)
            for c_k, subj_dict in att_data.items():
                if class_name.upper() in c_k.upper() or c_k.upper() in class_name.upper():
                    for s_k, date_dict in subj_dict.items():
                        if str(subject_id) in s_k or subject_name.upper() in s_k.upper():
                            if data_str in date_dict:
                                students_map_local = {s['username']: s['name'].upper() for s in (db.get_students_by_class(class_id) if db else [])}
                                for uname, status_val in date_dict.items():
                                    if uname in students_map_local:
                                        attendance_map[students_map_local[uname]] = status_val
    except Exception:
        pass

    # Carrega exceções/regras do arquivo attendance_exceptions.json (<turma>, <ra>, <nome_aluno>, <status>)
    excecoes_ra = {}
    excecoes_norm = {}
    try:
        exc_path = os.path.join(os.path.dirname(__file__), "attendance_exceptions.json")
        if os.path.exists(exc_path):
            with open(exc_path, 'r', encoding='utf-8') as f:
                exc_data = json.load(f)
            for exc in exc_data.get("exceptions", []):
                t_name = str(exc.get("turma", "geral")).strip()
                ra = str(exc.get("ra", "")).strip()
                n_aluno = str(exc.get("nome_aluno", "")).strip()
                st_exc = str(exc.get("status", "Falta")).strip()
                t_lower = t_name.lower()
                c_upper = class_name.upper()
                if (t_lower in ["geral", "todos", "all", "*", ""] or
                        t_name.upper() in c_upper or
                        c_upper in t_name.upper() or
                        str(class_id) in t_name or
                        normalizar_para_matching(t_name) in normalizar_para_matching(class_name)):
                    if ra:
                        excecoes_ra[ra] = st_exc
                    if n_aluno:
                        excecoes_norm[normalizar_para_matching(n_aluno)] = st_exc
    except Exception:
        pass

    # Busca alunos da turma
    students = db.get_students_by_class(class_id) if db else []
    if not students and db:
        all_users = db.get_all_users()
        students = [u for u in all_users if u.get('role', 'student') == 'student']
        if not students:
            students = all_users

    students = [s for s in students if s.get('is_active', True)]

    lista_final = []
    for std in sorted(students, key=lambda x: x.get('name', '')):
        nome = std.get('name', '').strip()
        if not nome:
            continue
        nome_upper = nome.upper()

        if "TESTE" in nome_upper:
            continue

        username = str(std.get('username', '')).strip()
        ra_val = str(std.get('ra', '')).strip()
        norm_nome = normalizar_para_matching(nome)

        forced_status = None
        if username and username in excecoes_ra:
            forced_status = excecoes_ra[username]
        elif ra_val and ra_val in excecoes_ra:
            forced_status = excecoes_ra[ra_val]
        else:
            for exc_norm, exc_status in excecoes_norm.items():
                if exc_norm in norm_nome or norm_nome in exc_norm:
                    forced_status = exc_status
                    break

        if forced_status:
            status = forced_status
        else:
            status = attendance_map.get(nome_upper, "Presente")

        lista_final.append({"name": nome_upper, "status": status})

    for item in lista_final:
        n_norm = normalizar_para_matching(item['name'])
        for exc_norm, exc_status in excecoes_norm.items():
            if exc_norm in n_norm or n_norm in exc_norm:
                item['status'] = exc_status
                break

    return lista_final


def gerar_plano_txt_conteudo(
    turma_code: int,
    disciplina_id: int,
    data_str: str,
    horario_str: str,
    aula_num: int,
    disciplina_nome: str,
    titulo_aula: str,
    estrategia: str,
    objetivos_str: str,
    atividade_str: str,
    frequencia_lista: list,
    recursos_str: str
) -> str:
    """Monta a string final do arquivo .txt no formato padronizado."""

    linhas_freq = []
    for item in frequencia_lista:
        linhas_freq.append(f"- {item['name']}: {item['status']}")
    freq_bloco = "\n".join(linhas_freq) if linhas_freq else "- NENHUM ALUNO REGISTRADO"

    titulo_limpo = limpar_markdown(titulo_aula)

    objs_linhas = [l.strip() for l in objetivos_str.splitlines() if l.strip()]
    dois_objs = "\n".join(objs_linhas[:2]) if objs_linhas else "- Compreender os conceitos fundamentais da aula."

    conteudo_bloco = f"{titulo_limpo}\n\nObjetivos Principais:\n{dois_objs}"

    txt = f"""# PLANO PREENCHIDO
TURMA_ID: {turma_code}
DISCIPLINA_ID: {disciplina_id}
DATA: {data_str}
HORARIO: {horario_str}
AULA_NUM: {aula_num:02d}
DISCIPLINA_NOME: {disciplina_nome}

[CONTEUDO]
{conteudo_bloco}

[ESTRATEGIA]
{estrategia.strip()}

[PLANO_DE_AULA]
### Objetivos da Aula
{objetivos_str.strip()}

### Atividade
{atividade_str.strip()}

[FREQUENCIA]
### Lista de Presença
{freq_bloco.strip()}

[RECURSOS_DIDATICOS]
### Recursos Utilizados
- Título: {titulo_limpo}
- Comentário: {recursos_str.strip()}
"""
    return txt.strip() + "\n"


def salvar_plano_disco(nome_arquivo: str, conteudo: str, pasta: str = "prontas") -> tuple:
    """Salva o plano nas pastas de saída (repo + espelho na raiz)."""
    info = PASTAS_PLANOS.get(pasta)
    if not info:
        return False, [f"Pasta inválida: {pasta}"]

    caminhos_salvos = []
    try:
        for chave in ("repo", "root"):
            destino = info[chave]
            os.makedirs(destino, exist_ok=True)
            p = os.path.join(destino, nome_arquivo)
            with open(p, "w", encoding="utf-8") as f:
                f.write(conteudo)
            caminhos_salvos.append(p)
        return True, caminhos_salvos
    except Exception as e:
        return False, [str(e)]


def montar_plano_aula(turma_nome: str, turma_id, nome_filha: str, id_filha: int,
                      id_mae: int, nome_mae: str,
                      aula_num: int, data_str: str, horario_str: str, estrategia: str,
                      frequencia_lista: list, forcar_pendente: bool = False) -> tuple:
    """Monta o TXT de uma aula.

    - Conteúdo (lessons/.md) vem da FILHA (`nome_filha`/`id_filha`).
    - Identificação no TXT/arquivo usa a MÃE (`nome_mae`/`id_mae`), que é o id do portal.
    Retorna (conteudo, fonte, nome_arquivo).
    """
    dados = auto_preencher_conteudo(turma_nome, nome_filha, id_filha, aula_num)

    if forcar_pendente or dados['fonte'] == 'padrão':
        padrao = conteudo_padrao(nome_mae, aula_num)
        titulo = padrao['titulo']
        objetivos = padrao['objetivos']
        atividade = padrao['atividade']
        recursos = padrao['recursos']
    else:
        titulo = dados['titulo']
        objetivos = dados['objetivos']
        atividade = dados['atividade']
        recursos = dados['recursos']

    txt = gerar_plano_txt_conteudo(
        turma_code=turma_id,
        disciplina_id=id_mae,
        data_str=data_str,
        horario_str=horario_str,
        aula_num=int(aula_num),
        disciplina_nome=nome_mae,
        titulo_aula=titulo,
        estrategia=estrategia,
        objetivos_str=objetivos,
        atividade_str=atividade,
        frequencia_lista=frequencia_lista,
        recursos_str=recursos
    )
    nome = f"PLANO_TURMA_{turma_id}_DISC_{id_mae}_AULA_{int(aula_num):02d}.txt"
    return txt, dados['fonte'], nome


def gerar_lote_planos(turma_nome: str, turma_id, nome_filha: str, id_filha: int,
                      id_mae: int, nome_mae: str,
                      aulas: list, destino: str, data_inicio: date, horario_str: str,
                      estrategia: str, frequencia_lista: list, subject: dict = None) -> list:
    """Gera e salva planos para uma lista de aulas.

    destino: "auto" | "prontas" | "pendentes".
    Em "auto": conteúdo de lessons/.md -> prontas; fallback -> pendentes.
    Retorna lista de dicts {aula, destino, fonte, arquivo, ok}.
    """
    aulas_ordenadas = sorted(set(int(a) for a in aulas))
    datas = calcular_datas_aulas(turma_nome, nome_mae, subject, data_inicio, max(len(aulas_ordenadas), 1))
    resultados = []

    for idx, aula_num in enumerate(aulas_ordenadas):
        data_aula = datas[idx] if idx < len(datas) else data_inicio
        data_str = data_aula.strftime("%Y-%m-%d")

        forcar_pendente = (destino == "pendentes")
        txt, fonte, nome = montar_plano_aula(
            turma_nome=turma_nome,
            turma_id=turma_id,
            nome_filha=nome_filha,
            id_filha=id_filha,
            id_mae=id_mae,
            nome_mae=nome_mae,
            aula_num=aula_num,
            data_str=data_str,
            horario_str=horario_str,
            estrategia=estrategia,
            frequencia_lista=frequencia_lista,
            forcar_pendente=forcar_pendente
        )

        if destino == "auto":
            destino_real = "prontas" if fonte in ("banco de dados", "arquivo local") else "pendentes"
        elif destino == "prontas":
            destino_real = "prontas" if fonte in ("banco de dados", "arquivo local") else "pendentes"
        else:
            destino_real = "pendentes"

        ok, _ = salvar_plano_disco(nome, txt, pasta=destino_real)
        resultados.append({
            "aula": aula_num,
            "destino": destino_real,
            "fonte": fonte,
            "arquivo": nome,
            "data": data_str,
            "ok": ok,
        })

    return resultados


# =============================================================================
# RENDER
# =============================================================================

def _render_horario_selector(selected_class_name: str, dia_semana_nome: str) -> tuple:
    """Seleciona o horário da grade semanal e devolve a disciplina sugerida."""
    horarios_grade = []
    disciplinas_por_horario = {}
    try:
        if db and db.is_db_connected():
            res_slots = db.supabase.table("weekly_schedule")\
                .select("time_slot, subject_name")\
                .eq("class_name", selected_class_name)\
                .ilike("day_of_week", f"%{dia_semana_nome[:3]}%")\
                .execute()
            if res_slots.data:
                for row in res_slots.data:
                    slot = row['time_slot']
                    subj = row['subject_name']
                    if slot not in horarios_grade:
                        horarios_grade.append(slot)
                    disciplinas_por_horario[slot] = subj
    except Exception:
        pass

    if not horarios_grade:
        horarios_grade = list(HORARIOS_PADRAO)
        st.warning(f"⚠️ Nenhum horário cadastrado na Grade Semanal para {dia_semana_nome}. Exibindo horários padrão.")

    # Se o dia mudou e o horário salvo não existe mais, limpa para não quebrar o selectbox.
    if st.session_state.get("plan_horario_sel") not in horarios_grade:
        st.session_state.pop("plan_horario_sel", None)

    horario_str = st.selectbox("Horário da Aula (Grade Semanal):", options=horarios_grade, key="plan_horario_sel")
    return horario_str, disciplinas_por_horario.get(horario_str)


def _cadencia_semanal(subject: dict) -> bool:
    """True se a disciplina tem ~1 aula por semana (típico de anual)."""
    if not subject:
        return False
    try:
        lpw = int(subject.get('lessons_per_week'))
        if lpw >= 1:
            return lpw <= 1
    except (TypeError, ValueError):
        pass
    return str(subject.get('duration_type', '')).strip().lower() == 'anual'


def calcular_datas_aulas(turma_nome: str, disciplina_nome: str, subject: dict,
                         data_inicio: date, num_aulas: int) -> list:
    """Datas das aulas respeitando a cadência da disciplina.

    - Anual (1 aula/semana): 1 aula a cada 7 dias.
    - Modular/mensal (várias por semana): usa a grade semanal (fallback Seg-Sex).
    """
    if num_aulas <= 0:
        return []
    if _cadencia_semanal(subject):
        return [data_inicio + timedelta(days=7 * i) for i in range(num_aulas)]
    return calcular_datas_sequenciais(turma_nome, disciplina_nome, data_inicio, num_aulas)


def sugerir_proxima_data(turma_nome: str, disciplina_nome: str, ultima_data,
                         subject: dict = None, data_base: date = None) -> date:
    """Sugere a data da próxima aula com base no histórico + cadência da disciplina.

    - Anual (1 aula/semana): última data + 7 dias (mesmo dia da semana).
    - Modular/mensal (várias por semana): próximo dia de aula pela grade (fallback Seg-Sex).
    - Sem última data: usa `data_base` (hoje).
    """
    base = data_base or date.today()

    if _cadencia_semanal(subject):
        if ultima_data:
            # Continua a partir dela MESMO no passado (permite planos retroativos).
            return ultima_data + timedelta(days=7)
        try:
            datas = calcular_datas_sequenciais(turma_nome, disciplina_nome, base, 1)
            return datas[0] if datas else base
        except Exception:
            return base

    # Modular/mensal: várias aulas por semana.
    start = ultima_data + timedelta(days=1) if ultima_data else base
    try:
        datas = calcular_datas_sequenciais(turma_nome, disciplina_nome, start, 1)
        if datas:
            return datas[0]
    except Exception:
        pass
    return start


def _render_aba_diagnostico(classes_map: dict) -> dict:
    """Aba 1: contexto + diagnóstico do historico_aulas. Retorna o contexto selecionado."""
    st.subheader("1. Contexto da Turma e Disciplina")
    st.caption(
        "Selecione a turma e a **disciplina**; o sistema consulta o `historico_aulas`, mostra a última aula "
        "e sugere a data da próxima."
    )

    col_t, col_bt = st.columns([0.8, 0.2])
    with col_t:
        selected_class_name = st.selectbox("Turma:", list(classes_map.keys()), key="plan_sel_class")
    with col_bt:
        st.write("")
        st.write("")
        if st.button("🔄 Recarregar dados", use_container_width=True, key="plan_reload"):
            st.cache_data.clear()
            st.rerun()

    selected_class = classes_map[selected_class_name]
    turma_id = selected_class.get('code') or selected_class.get('id')

    # 1) Disciplina ANTES da data: é ela que define o histórico a consultar.
    subjects = _subjects_for_class_cached(selected_class['id'])
    subjects = [s for s in subjects if s.get('is_active', True)]
    subject_map = {s['name']: s for s in subjects} if subjects else {}

    if not subject_map:
        st.warning("Nenhuma disciplina vinculada a esta turma.")
        return None

    selected_subject_name = st.selectbox("Disciplina:", list(subject_map.keys()), key="plan_sel_subj")
    selected_subject = subject_map[selected_subject_name]
    disciplina_id = selected_subject['id']

    # --- Resolução mãe x filha ---------------------------------------------
    # Filha (com sufixo, ex.: 2026A) é dona das lessons; a mãe/raiz é dona do
    # historico_aulas (vem do portal) e do identificador usado no TXT do plano.
    id_filha = disciplina_id
    id_mae = resolver_raiz(id_filha)
    nome_mae = resolver_nome_mae(id_filha, selected_subject_name)
    if id_mae is not None and str(id_mae) != str(id_filha):
        st.info(
            f"🔗 Disciplina selecionada **{selected_subject_name}** (id {id_filha}) → "
            f"mãe **{nome_mae}** (id {id_mae}). O histórico é lido da mãe; as aulas (`lessons`) da filha."
        )

    max_horas = selected_subject.get('max_hours') or selected_subject.get('workload') or 40
    try:
        carga_horaria = int(max_horas)
    except Exception:
        carga_horaria = 40
    if carga_horaria <= 0:
        carga_horaria = 40

    # 2) Histórico (mãe/raiz) -> última aula/data -> sugestão de data.
    diag = calcular_diagnostico(selected_class_name, turma_id, id_mae)
    ultima_data = diag['ultima_data']

    # Se a disciplina não tem histórico próprio (ex.: Front-End), usa a última aula da TURMA.
    referencia = ultima_data
    ref_da_turma = False
    if referencia is None:
        referencia = ultima_data_turma(selected_class_name, turma_id)
        ref_da_turma = referencia is not None

    data_sugerida = sugerir_proxima_data(selected_class_name, nome_mae, referencia, subject=selected_subject)

    cadencia = "semanal (1/semana)" if _cadencia_semanal(selected_subject) else "modular/mensal"

    if ultima_data:
        st.caption(
            f"📅 Última aula desta disciplina em **{ultima_data.strftime('%d/%m/%Y')}** "
            f"[cadência {cadencia}] → data sugerida: **{data_sugerida.strftime('%d/%m/%Y')}**."
        )
    elif ref_da_turma:
        st.caption(
            f"📅 Sem histórico desta disciplina; usando a última aula da turma "
            f"(**{referencia.strftime('%d/%m/%Y')}**) [cadência {cadencia}] → "
            f"data sugerida: **{data_sugerida.strftime('%d/%m/%Y')}**."
        )
    else:
        st.caption(
            f"📅 Sem histórico para esta turma/disciplina [cadência {cadencia}] → "
            f"data sugerida: **{data_sugerida.strftime('%d/%m/%Y')}**."
        )

    # Ao trocar turma/disciplina, atualiza a data para a nova sugestão (sem travar edição manual).
    sugestao_key = f"{selected_class_name}|{id_mae}"
    if st.session_state.get("plan_data_sugestao_key") != sugestao_key:
        st.session_state["plan_data_sugestao_key"] = sugestao_key
        st.session_state["plan_data"] = data_sugerida

    # 3) Data e horário (o horário depende do dia da semana da data escolhida).
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        data_selecionada = st.date_input("Data da Aula:", key="plan_data")
        data_str = data_selecionada.strftime("%Y-%m-%d")
        dia_semana_nome = DIAS_SEMANA_PT[data_selecionada.weekday()]
        st.caption(f"📅 Dia da semana: **{dia_semana_nome}**")
    with col_d2:
        horario_str, disciplina_sugerida_grade = _render_horario_selector(selected_class_name, dia_semana_nome)
        if disciplina_sugerida_grade:
            norm_sug = normalizar_para_matching(disciplina_sugerida_grade)
            norm_sel = normalizar_para_matching(selected_subject_name)
            if norm_sug in norm_sel or norm_sel in norm_sug:
                st.success(f"📌 **Grade Semanal:** {dia_semana_nome} às {horario_str} → **{disciplina_sugerida_grade}**.")
            else:
                st.warning(
                    f"⚠️ **Grade Semanal:** {dia_semana_nome} às {horario_str} está como "
                    f"**{disciplina_sugerida_grade}**, diferente da disciplina selecionada."
                )

    st.divider()
    st.subheader("📊 Diagnóstico do Histórico")

    qtd_reg = diag['qtd']
    faltantes = max(0, carga_horaria - qtd_reg)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Carga horária prevista", f"{carga_horaria} aulas")
    c2.metric("Aulas registradas", qtd_reg)
    c3.metric("Faltantes p/ carga", faltantes)
    c4.metric("Próxima aula", f"{qtd_reg + 1:02d}")

    if diag['ultima_data']:
        ult = diag['ultima_data']
        reg = diag['ultimo_registro'] or {}
        st.info(
            f"📅 **Última aula registrada:** {ult.strftime('%d/%m/%Y')} "
            f"(horário: {reg.get('horario', 'N/A')} | status: {reg.get('status', 'N/A')})"
        )
    else:
        st.info("Nenhum registro em `historico_aulas` para esta turma/disciplina.")

    if diag['datas_validas']:
        with st.expander(f"📋 Últimos registros ({min(15, len(diag['datas_validas']))} de {qtd_reg})", expanded=False):
            ultimos = list(reversed(diag['datas_validas']))[:15]
            df_hist = pd.DataFrame([
                {
                    "Data": d.strftime('%d/%m/%Y'),
                    "Horário": r.get('horario', ''),
                    "Status": r.get('status', ''),
                    "Registrado em": r.get('created_at', ''),
                }
                for d, r in ultimos
            ])
            st.dataframe(df_hist, use_container_width=True, hide_index=True)

    return {
        'class_name': selected_class_name,
        'class': selected_class,
        'turma_id': turma_id,
        'data_selecionada': data_selecionada,
        'data_str': data_str,
        'dia_semana_nome': dia_semana_nome,
        'horario_str': horario_str,
        'subject_name': selected_subject_name,
        'subject': selected_subject,
        'disciplina_id': id_filha,
        'id_filha': id_filha,
        'id_mae': id_mae,
        'nome_mae': nome_mae,
        'carga_horaria': carga_horaria,
        'diag': diag,
        'qtd_reg': qtd_reg,
        'faltantes': faltantes,
    }


def _render_aba_planejamento(ctx: dict, frequencia_base: list) -> dict:
    """Aba 2: cruza lessons x histórico x pastas e sugere prontas/pendentes."""
    st.subheader("2. Planejamento (Prontas × Pendentes)")
    st.caption("O sistema lê os TXT das pastas `aulas/pendentes` e `aulas/prontas` e cruza com a tabela `lessons`.")

    id_filha = ctx['id_filha']
    id_mae = ctx['id_mae']
    turma_id = ctx['turma_id']
    carga_horaria = ctx['carga_horaria']

    # lessons vêm da FILHA (com sufixo); planos/ histórico usam a MÃE.
    lessons_light = _lessons_light(id_filha)
    aulas_lessons = {}
    for l in lessons_light:
        m = re.search(r'Aula\s*0?(\d+)', l.get('title', '') or '', re.IGNORECASE)
        if m:
            aulas_lessons.setdefault(int(m.group(1)), l)

    planos_prontas = [p for p in listar_planos_pasta("prontas") if _plano_pertence(p, turma_id, id_mae)]
    planos_pendentes = [p for p in listar_planos_pasta("pendentes") if _plano_pertence(p, turma_id, id_mae)]
    aulas_prontas = {p['aula_num'] for p in planos_prontas}
    aulas_pendentes = {p['aula_num'] for p in planos_pendentes}

    analise = montar_analise_planejamento(carga_horaria, aulas_lessons, aulas_prontas, aulas_pendentes, ctx['qtd_reg'])

    n_lessons = len(aulas_lessons)
    n_prontas = len(aulas_prontas)
    n_pendentes = len(aulas_pendentes)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aulas em `lessons`", n_lessons)
    c2.metric("Planos em prontas", n_prontas)
    c3.metric("Planos em pendentes", n_pendentes)
    c4.metric("Carga horária", f"{carga_horaria} aulas")

    st.markdown(
        f"**Comparação:** {n_lessons} aulas no banco (`lessons`) × {ctx['qtd_reg']} registradas no histórico "
        f"(`historico_aulas`) × {n_prontas} prontas + {n_pendentes} pendentes em disco."
    )

    df = pd.DataFrame([{k: v for k, v in a.items() if not k.startswith('_')} for a in analise])
    st.dataframe(df, use_container_width=True, hide_index=True, height=360)

    st.divider()
    st.markdown("#### ⚙️ Aplicar sugestões")
    st.caption("As ações abaixo geram os planos nas pastas correspondentes (prontas com conteúdo real, pendentes com valores padrão).")

    aulas_sug_prontas = [a['Aula'] for a in analise if a['_acao'] == 'pronta']
    aulas_sug_pendentes = [a['Aula'] for a in analise if a['_acao'] == 'pendente']

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(
            f"🟢 Gerar {len(aulas_sug_prontas)} PRONTAS sugeridas",
            type="primary",
            use_container_width=True,
            disabled=not aulas_sug_prontas,
            key="plan_aplicar_prontas"
        ):
            with st.spinner("Gerando planos prontos..."):
                res = gerar_lote_planos(
                    ctx['class_name'], turma_id, ctx['subject_name'], id_filha, id_mae, ctx['nome_mae'],
                    aulas_sug_prontas, "prontas", ctx['data_selecionada'], ctx['horario_str'],
                    ESTRATEGIAS_OPCOES[0], frequencia_base, subject=ctx['subject']
                )
            n_ok = sum(1 for r in res if r['ok'])
            st.success(f"✅ {n_ok} planos prontos gerados.")
            st.cache_data.clear()
    with col_b:
        if st.button(
            f"🟡 Gerar {len(aulas_sug_pendentes)} PENDENTES sugeridas",
            use_container_width=True,
            disabled=not aulas_sug_pendentes,
            key="plan_aplicar_pendentes"
        ):
            with st.spinner("Gerando planos pendentes..."):
                res = gerar_lote_planos(
                    ctx['class_name'], turma_id, ctx['subject_name'], id_filha, id_mae, ctx['nome_mae'],
                    aulas_sug_pendentes, "pendentes", ctx['data_selecionada'], ctx['horario_str'],
                    ESTRATEGIAS_OPCOES[0], frequencia_base, subject=ctx['subject']
                )
            n_ok = sum(1 for r in res if r['ok'])
            st.success(f"✅ {n_ok} planos pendentes gerados.")
            st.cache_data.clear()

    return {
        'aulas_lessons': aulas_lessons,
        'planos_prontas': planos_prontas,
        'planos_pendentes': planos_pendentes,
        'analise': analise,
    }


def _render_aba_operacoes(ctx: dict, planejamento: dict) -> None:
    """Aba 3: visualizar, gerar individual e gerar em lote."""
    st.subheader("3. Operações")

    op_view, op_single, op_batch = st.tabs(["👁️ Visualizar", "✍️ Gerar Individual", "📦 Gerar em Lote"])

    turma_id = ctx['turma_id']
    id_filha = ctx['id_filha']
    id_mae = ctx['id_mae']
    nome_mae = ctx['nome_mae']
    alunos_final = []

    # ---------------------------------------------------------------- Visualizar
    with op_view:
        col_p, col_f = st.columns([0.4, 0.6])
        with col_p:
            pasta_view = st.radio("Pasta:", ["prontas", "pendentes"], horizontal=True, key="plan_view_pasta")
        with col_f:
            mostrar_todos = st.checkbox("Mostrar todos os planos da pasta", value=False, key="plan_view_todos")

        planos = listar_planos_pasta(pasta_view)
        if not mostrar_todos:
            planos = [p for p in planos if _plano_pertence(p, turma_id, id_mae)]
        planos = sorted(planos, key=lambda x: (x['turma_id'], x['disciplina_id'], x['aula_num']))

        if not planos:
            st.info("Nenhum plano encontrado nesta pasta para o filtro atual.")
        else:
            opcoes = {
                f"[T{x['turma_id']}/D{x['disciplina_id']}] Aula {x['aula_num']:02d} — {x['titulo'][:60]}": x
                for x in planos
            }
            sel = st.selectbox(f"{len(planos)} plano(s) encontrado(s):", list(opcoes.keys()), key="plan_view_sel")
            plano = opcoes[sel]
            try:
                with open(plano['caminho'], 'r', encoding='utf-8') as f:
                    conteudo = f.read()
            except Exception as e:
                conteudo = f"Erro ao ler arquivo: {e}"

            st.text_area("Conteúdo do plano:", conteudo, height=340)
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                st.download_button(
                    "📥 Baixar .TXT",
                    data=conteudo.encode('utf-8'),
                    file_name=plano['arquivo'],
                    mime="text/plain",
                    use_container_width=True
                )
            with col_v2:
                st.caption(f"📄 {plano['arquivo']} • {plano['tamanho']} bytes • {plano['caminho']}")

    # --------------------------------------------------------------- Individual
    with op_single:
        aulas_lessons = planejamento.get('aulas_lessons', {})
        n_proxima = ctx['qtd_reg'] + 1
        max_aula = max(ctx['carga_horaria'] + 40, 120)
        valor_inicial = int(min(max(n_proxima, 1), max_aula))

        col_n1, col_n2 = st.columns([0.5, 0.5])
        with col_n1:
            aula_num = st.number_input(
                "Número da Aula (AULA_NUM):",
                min_value=1,
                max_value=max_aula,
                value=valor_inicial,
                step=1,
                key="plan_aula_num"
            )
        with col_n2:
            tem_lesson = int(aula_num) in aulas_lessons
            destino = st.radio(
                "Destino do arquivo:",
                ["prontas", "pendentes"],
                index=0 if tem_lesson else 1,
                horizontal=True,
                key="plan_destino_ind"
            )

        # Conteúdo das aulas vem da FILHA (com sufixo).
        dados_auto = auto_preencher_conteudo(ctx['class_name'], ctx['subject_name'], id_filha, int(aula_num))
        fonte_cor = {"banco de dados": "🟢", "arquivo local": "🟡", "padrão": "🔴"}
        st.caption(
            f"{fonte_cor.get(dados_auto['fonte'], '⚪')} Fonte dos dados: **{dados_auto['fonte']}** | "
            f"{'✅ aula encontrada em `lessons`' if tem_lesson else '⚠️ aula não encontrada em `lessons`'}"
        )

        existente = verificar_plano_existente(turma_id, id_mae, int(aula_num), destino)
        if existente.get('existe'):
            st.warning(
                f"⚠️ Já existe plano para a Aula {int(aula_num):02d} em `aulas/{destino}/` "
                f"(gerado em {existente.get('data', 'desconhecida')}). Salvar irá sobrescrever."
            )

        cache_key = f"{ctx['class_name']}_{ctx['subject_name']}_{int(aula_num)}_{ctx['data_str']}"
        if st.session_state.get("plan_last_cache_key") != cache_key:
            st.session_state["plan_last_cache_key"] = cache_key
            st.session_state["plan_titulo"] = dados_auto['titulo']
            st.session_state["plan_objs"] = dados_auto['objetivos']
            st.session_state["plan_act"] = dados_auto['atividade']
            st.session_state["plan_rec"] = dados_auto['recursos']
            st.session_state.pop("plan_alunos_table", None)

        titulo_aula = st.text_input("Título / Conteúdo da Aula:", key="plan_titulo")
        estrategia_selecionada = st.selectbox("Estratégia Pedagógica:", ESTRATEGIAS_OPCOES, key="plan_estrategia")

        tab1, tab2, tab3, tab4 = st.tabs(["🎯 Objetivos", "🛠️ Atividade", "👥 Lista de Presença", "🧰 Recursos"])
        with tab1:
            objetivos_edit = st.text_area("Objetivos da Aula:", height=120, key="plan_objs")
        with tab2:
            atividade_edit = st.text_area("Atividade Prática / Cenário:", height=120, key="plan_act")
        with tab3:
            alunos_lista = buscar_alunos_presenca(
                ctx['class']['id'], ctx['class_name'], id_filha, ctx['subject_name'], ctx['data_str']
            )
            st.caption(f"Total de {len(alunos_lista)} alunos carregados para a frequência.")

            df_alunos = pd.DataFrame(alunos_lista)
            if not df_alunos.empty:
                edited_alunos = st.data_editor(
                    df_alunos,
                    column_config={
                        "name": st.column_config.TextColumn("Nome do Aluno", disabled=True),
                        "status": st.column_config.SelectboxColumn("Presença", options=["Presente", "Falta"])
                    },
                    hide_index=True,
                    height=220,
                    key="plan_alunos_table"
                )

                exc_overrides_ra = {}
                exc_overrides_nome = {}
                try:
                    exc_path = os.path.join(os.path.dirname(__file__), "attendance_exceptions.json")
                    if os.path.exists(exc_path):
                        with open(exc_path, 'r', encoding='utf-8') as f:
                            exc_data = json.load(f)
                        for exc in exc_data.get("exceptions", []):
                            t_name = str(exc.get("turma", "geral")).strip()
                            ra = str(exc.get("ra", "")).strip()
                            n_aluno = str(exc.get("nome_aluno", "")).strip().upper()
                            st_exc = str(exc.get("status", "Falta")).strip()
                            t_lower = t_name.lower()
                            c_upper = ctx['class_name'].upper()
                            if (t_lower in ["geral", "todos", "all", "*", ""] or
                                    t_name.upper() in c_upper or
                                    c_upper in t_name.upper() or
                                    str(ctx['class'].get('id')) in t_name or
                                    normalizar_para_matching(t_name) in normalizar_para_matching(ctx['class_name'])):
                                if ra:
                                    exc_overrides_ra[ra] = st_exc
                                if n_aluno:
                                    exc_overrides_nome[normalizar_para_matching(n_aluno)] = st_exc
                except Exception:
                    pass

                students_tab = db.get_students_by_class(ctx['class']['id']) if db else []
                if not students_tab and db:
                    students_tab = db.get_all_students()
                student_ra_lookup = {s['name'].strip().upper(): str(s.get('username', '')).strip() for s in students_tab}

                alunos_final = []
                for row in edited_alunos.to_dict('records'):
                    n_up = str(row.get('name', '')).upper()
                    st_val = row.get('status', 'Presente')
                    s_ra = student_ra_lookup.get(n_up, "")

                    forced_val = None
                    if s_ra and s_ra in exc_overrides_ra:
                        forced_val = exc_overrides_ra[s_ra]
                    else:
                        for exc_n, exc_s in exc_overrides_nome.items():
                            if exc_n in n_up or n_up in exc_n:
                                forced_val = exc_s
                                break

                    if forced_val:
                        st_val = forced_val

                    alunos_final.append({"name": n_up, "status": st_val})
            else:
                alunos_final = alunos_lista
        with tab4:
            recursos_edit = st.text_area("Recursos e Comentários:", height=120, key="plan_rec")

        # O TXT do plano é voltado ao portal: usa o id/nome da MÃE.
        plano_gerado_txt = gerar_plano_txt_conteudo(
            turma_code=turma_id,
            disciplina_id=id_mae,
            data_str=ctx['data_str'],
            horario_str=ctx['horario_str'],
            aula_num=int(aula_num),
            disciplina_nome=nome_mae,
            titulo_aula=titulo_aula,
            estrategia=estrategia_selecionada,
            objetivos_str=objetivos_edit,
            atividade_str=atividade_edit,
            frequencia_lista=alunos_final,
            recursos_str=recursos_edit
        )

        st.divider()
        st.markdown("### 👁️ Pré-visualização do Arquivo TXT")
        st.text_area("Conteúdo do arquivo:", plano_gerado_txt, height=260)

        nome_arquivo_sugerido = f"PLANO_TURMA_{turma_id}_DISC_{id_mae}_AULA_{int(aula_num):02d}.txt"

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(f"💾 Salvar em aulas/{destino}/", type="primary", use_container_width=True, key="plan_salvar_ind"):
                sucesso, caminhos = salvar_plano_disco(nome_arquivo_sugerido, plano_gerado_txt, pasta=destino)
                if sucesso:
                    st.success(f"✅ Salvo em `aulas/{destino}/{nome_arquivo_sugerido}`.")
                    st.cache_data.clear()
                else:
                    st.error(f"Erro ao salvar: {caminhos}")
        with col_btn2:
            st.download_button(
                label="📥 Baixar Arquivo .TXT",
                data=plano_gerado_txt.encode('utf-8'),
                file_name=nome_arquivo_sugerido,
                mime="text/plain",
                use_container_width=True
            )

    # ---------------------------------------------------------------------- Lote
    with op_batch:
        analise = planejamento.get('analise', [])
        sugestoes = sorted({a['Aula'] for a in analise if a['_acao'] in ('pronta', 'pendente')})

        col_l1, col_l2 = st.columns([0.6, 0.4])
        with col_l1:
            aulas_lote = st.multiselect(
                "Aulas a gerar (padrão = sugestões das abas anteriores):",
                options=list(range(1, int(ctx['carga_horaria']) + 1)),
                default=sugestoes,
                key="plan_lote_aulas"
            )
        with col_l2:
            destino_lote = st.radio(
                "Destino:",
                ["auto", "prontas", "pendentes"],
                index=0,
                horizontal=True,
                key="plan_lote_destino"
            )
            st.caption("auto: lessons/.md → prontas; fallback → pendentes.")

        max_horas = ctx['subject'].get('max_hours') or ctx['subject'].get('workload') or 40
        st.info(
            f"**Cenário:** Turma {ctx['class_name']} (ID {turma_id}) • Disciplina {ctx['subject_name']} "
            f"(filha ID {id_filha} → mãe {nome_mae} ID {id_mae}, {max_horas}h) • Horário {ctx['horario_str']} • "
            f"{len(aulas_lote)} aula(s) selecionada(s)."
        )

        if st.button("🚀 Gerar planos em lote", type="primary", use_container_width=True, key="plan_lote_gerar"):
            if not aulas_lote:
                st.warning("Selecione ao menos uma aula.")
            else:
                with st.spinner("Gerando planos em lote..."):
                    resultados = gerar_lote_planos(
                        ctx['class_name'], turma_id, ctx['subject_name'], id_filha, id_mae, nome_mae,
                        aulas_lote, destino_lote, ctx['data_selecionada'], ctx['horario_str'],
                        ESTRATEGIAS_OPCOES[0], alunos_final, subject=ctx['subject']
                    )
                n_ok = sum(1 for r in resultados if r['ok'])
                n_pr = sum(1 for r in resultados if r['ok'] and r['destino'] == 'prontas')
                n_pe = sum(1 for r in resultados if r['ok'] and r['destino'] == 'pendentes')
                st.success(f"🎉 {n_ok} plano(s) gerado(s): {n_pr} em prontas e {n_pe} em pendentes.")
                st.dataframe(pd.DataFrame(resultados), use_container_width=True, hide_index=True)
                st.cache_data.clear()


def render():
    st.header("📄 Gerador de Planos de Aula (TXT)")
    st.markdown(
        "Fluxo em 3 passos: **diagnóstico do histórico** → **planejamento (prontas/pendentes)** → "
        "**geração individual ou em lote**."
    )

    if not db or not db.is_db_connected():
        st.warning("⚠️ Banco de dados desconectado. Alguns recursos podem operar em modo de fallback.")

    classes = _classes_cached()
    if not classes:
        st.error("Nenhuma turma encontrada no sistema.")
        return

    class_map = {c['name']: c for c in classes}

    tab_diag, tab_plan, tab_ops = st.tabs([
        "1️⃣ Diagnóstico (Histórico)",
        "2️⃣ Planejamento (Prontas/Pendentes)",
        "3️⃣ Operações (Visualizar / Gerar)",
    ])

    with tab_diag:
        ctx = _render_aba_diagnostico(class_map)

    if not ctx:
        return

    frequencia_base = buscar_alunos_presenca(
        ctx['class']['id'], ctx['class_name'], ctx['disciplina_id'], ctx['subject_name'], ctx['data_str']
    )

    with tab_plan:
        planejamento = _render_aba_planejamento(ctx, frequencia_base)

    with tab_ops:
        _render_aba_operacoes(ctx, planejamento)


def show_planos_plugin():
    render()


def show_page():
    render()


def main():
    render()


if __name__ == "__main__":
    render()
