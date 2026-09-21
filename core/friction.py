"""
Análise de fricção dos cursos (porte de data/repo/plugins/friction_radar.py).

Aponta aulas problemáticas em três critérios:
1. Aula sem quiz de fixação.
2. Baixo engajamento no fórum (0 ou 1 post — considera o post do bot).
3. Conteúdo descritivo muito curto (< LIMITE_CONTEUDO caracteres).
"""

from __future__ import annotations

from core import repositories as repo

LIMITE_CONTEUDO = 200

ROTULOS = {
    "sem_quiz": "Sem quiz",
    "forum_fraco": "Fórum fraco",
    "conteudo_curto": "Conteúdo curto",
}


def analisar_atrito(incluir_treinamento: bool = False) -> dict:
    """
    Executa a análise em todas as disciplinas.

    Retorna:
        {
          "disciplinas": [
              {"subject_id", "nome", "total_aulas", "total_problemas",
               "aulas": [{"lesson_id", "titulo", "problemas": [{tipo, descricao}]}]}
          ],
          "total_problemas", "total_aulas", "total_disciplinas",
          "por_tipo": {"sem_quiz": n, "forum_fraco": n, "conteudo_curto": n},
        }
    """
    disciplinas = repo.listar_disciplinas(incluir_treinamento=incluir_treinamento)
    quizzes_por_aula = repo.mapa_quizzes_por_aula()
    posts_por_aula = repo.contagem_posts_por_aula()

    resultado_disciplinas = []
    total_problemas = 0
    total_aulas = 0
    por_tipo = {chave: 0 for chave in ROTULOS}

    for disciplina in disciplinas:
        aulas = repo.listar_aulas(disciplina["id"])
        total_aulas += len(aulas)
        aulas_com_problema = []

        for aula in aulas:
            problemas = []

            if str(aula["id"]) not in quizzes_por_aula:
                problemas.append({
                    "tipo": "sem_quiz",
                    "descricao": "Aula sem quiz de fixação.",
                })

            quantidade_posts = posts_por_aula.get(str(aula["id"]), 0)
            if quantidade_posts <= 1:
                problemas.append({
                    "tipo": "forum_fraco",
                    "descricao": f"Baixo engajamento no fórum ({quantidade_posts} post).",
                })

            descricao = aula.get("description") or ""
            if len(descricao) < LIMITE_CONTEUDO:
                problemas.append({
                    "tipo": "conteudo_curto",
                    "descricao": f"Conteúdo muito curto ({len(descricao)} caracteres).",
                })

            if problemas:
                aulas_com_problema.append({
                    "lesson_id": aula["id"],
                    "titulo": aula.get("title") or "(sem título)",
                    "problemas": problemas,
                })
                for problema in problemas:
                    por_tipo[problema["tipo"]] += 1

        subtotal = sum(len(item["problemas"]) for item in aulas_com_problema)
        total_problemas += subtotal

        resultado_disciplinas.append({
            "subject_id": disciplina["id"],
            "nome": disciplina.get("name") or "(sem nome)",
            "tipo": disciplina.get("type") or "",
            "total_aulas": len(aulas),
            "total_problemas": subtotal,
            "aulas": aulas_com_problema,
        })

    # Disciplinas com mais problemas primeiro
    resultado_disciplinas.sort(key=lambda item: item["total_problemas"], reverse=True)

    return {
        "disciplinas": resultado_disciplinas,
        "total_problemas": total_problemas,
        "total_aulas": total_aulas,
        "total_disciplinas": len(resultado_disciplinas),
        "por_tipo": por_tipo,
    }
