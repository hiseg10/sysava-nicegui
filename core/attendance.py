"""
Frequência: chamada diária por turma/disciplina/data, relatórios e export CSV.

A chave de um registro é (student_name, class_name, subject_id, date), igual à
constraint do Supabase. O status tem três valores (`Presente`, `Falta`,
`Atraso`) e é guardado numa coluna local `status` (a nuvem só tem o booleano
`is_present`, derivado como `status in {Presente, Atraso}`).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from core import db, repositories

STATUS_PRESENTE = "Presente"
STATUS_FALTA = "Falta"
STATUS_ATRASO = "Atraso"
STATUS = (STATUS_PRESENTE, STATUS_FALTA, STATUS_ATRASO)
_STATUS_PRESENTE = {STATUS_PRESENTE, STATUS_ATRASO}
_VALORES_PRESENTE = {"1", "true", "t", "sim", "yes"}

TABELA = "attendance"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _tem_coluna(con, tabela: str, coluna: str) -> bool:
    return any(linha[1] == coluna for linha in con.execute(f'PRAGMA table_info("{tabela}")'))


def _chave_subject(subject_id) -> str | None:
    return None if subject_id is None else str(subject_id)


def _status_de(is_present, status=None) -> str:
    """Deriva o status a partir da coluna `status` ou do booleano `is_present`."""
    if status in STATUS:
        return status
    if isinstance(is_present, bool):
        return STATUS_PRESENTE if is_present else STATUS_FALTA
    if str(is_present).strip().lower() in _VALORES_PRESENTE:
        return STATUS_PRESENTE
    return STATUS_FALTA


def _presente(status: str) -> int:
    return 1 if status in _STATUS_PRESENTE else 0


def _dedupe_por_id(linhas: list) -> list:
    """Remove linhas repetidas pelo `id` (o backup legado duplicou registros)."""
    vistos: set[str] = set()
    resultado = []
    for linha in linhas:
        chave = str(linha["id"])
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(linha)
    return resultado


# --------------------------------------------------------------------------
# Seleções
# --------------------------------------------------------------------------
def listar_turmas() -> list[dict]:
    return repositories.listar_turmas()


def listar_disciplinas(class_id) -> list[dict]:
    return repositories.listar_disciplinas_da_turma(class_id)


def listar_alunos(class_id) -> list[dict]:
    """Alunos da turma, ordenados por nome (define o número na lista)."""
    return sorted(
        repositories.listar_alunos_da_turma(class_id),
        key=lambda aluno: str(aluno.get("name") or ""),
    )


# --------------------------------------------------------------------------
# Chamada
# --------------------------------------------------------------------------
def carregar_chamada(class_name: str, subject_id, data: str) -> dict[str, str]:
    """Mapa {student_name: status} dos registros já existentes."""
    if not class_name or not data:
        return {}
    resultado: dict[str, str] = {}
    try:
        with db.abrir() as con:
            tem_status = _tem_coluna(con, TABELA, "status")
            colunas = "student_name, is_present" + (", status" if tem_status else "")
            linhas = con.execute(
                f"SELECT {colunas} FROM {TABELA} "
                "WHERE class_name = ? AND date = ? "
                "AND COALESCE(subject_id, '') = COALESCE(?, '')",
                (class_name, data, _chave_subject(subject_id)),
            ).fetchall()
    except Exception:
        return {}
    for linha in linhas:
        nome = linha["student_name"]
        status = linha["status"] if tem_status else None
        resultado[nome] = _status_de(linha["is_present"], status)
    return resultado


def salvar_chamada(
    class_name: str,
    subject_id,
    data: str,
    registros: list[dict],
    professor: str = "",
) -> dict:
    """
    Faz upsert dos registros da chamada.

    `registros`: lista de {"student_name", "student_number", "status"}.
    Devolve {"inseridos", "atualizados", "total"}.
    """
    if not class_name or not data or not registros:
        return {"inseridos": 0, "atualizados": 0, "total": 0}

    agora = datetime.now().isoformat(timespec="seconds")
    chave_subject = _chave_subject(subject_id)
    inseridos = atualizados = 0

    with db.abrir(somente_leitura=False) as con:
        if not _tem_coluna(con, TABELA, "status"):
            con.execute(f'ALTER TABLE "{TABELA}" ADD COLUMN status TEXT')

        for registro in registros:
            nome = registro.get("student_name")
            if not nome:
                continue
            status = registro.get("status") or STATUS_PRESENTE
            presente = _presente(status)
            numero = registro.get("student_number")

            existente = con.execute(
                f"SELECT id FROM {TABELA} WHERE student_name = ? AND class_name = ? "
                "AND date = ? AND COALESCE(subject_id, '') = COALESCE(?, '') LIMIT 1",
                (nome, class_name, data, chave_subject),
            ).fetchone()

            if existente:
                con.execute(
                    f"UPDATE {TABELA} SET is_present = ?, student_number = ?, "
                    "professor_name = ?, status = ? WHERE id = ?",
                    (str(presente), str(numero), professor, status, existente[0]),
                )
                atualizados += 1
            else:
                con.execute(
                    f"INSERT INTO {TABELA} "
                    "(id, student_name, student_number, is_present, class_name, date, "
                    " professor_name, created_at, subject_id, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        uuid.uuid4().hex,
                        nome,
                        str(numero),
                        str(presente),
                        class_name,
                        data,
                        professor,
                        agora,
                        chave_subject,
                        status,
                    ),
                )
                inseridos += 1

        con.commit()

    return {"inseridos": inseridos, "atualizados": atualizados, "total": len(registros)}


# --------------------------------------------------------------------------
# Relatórios
# --------------------------------------------------------------------------
def resumo_disciplina(class_name: str, subject_id) -> list[dict]:
    """Presenças/faltas/atrasos e % de frequência por aluno na disciplina."""
    if not class_name:
        return []
    try:
        with db.abrir() as con:
            tem_status = _tem_coluna(con, TABELA, "status")
            colunas = "id, student_name, is_present" + (", status" if tem_status else "")
            linhas = con.execute(
                f"SELECT {colunas} FROM {TABELA} "
                "WHERE class_name = ? AND COALESCE(subject_id, '') = COALESCE(?, '')",
                (class_name, _chave_subject(subject_id)),
            ).fetchall()
    except Exception:
        return []

    agregado: dict[str, dict] = {}
    for linha in _dedupe_por_id(linhas):
        nome = linha["student_name"]
        status = _status_de(linha["is_present"], linha["status"] if tem_status else None)
        item = agregado.setdefault(
            nome,
            {"student_name": nome, "presencas": 0, "faltas": 0, "atrasos": 0},
        )
        if status == STATUS_PRESENTE:
            item["presencas"] += 1
        elif status == STATUS_ATRASO:
            item["atrasos"] += 1
        else:
            item["faltas"] += 1

    for item in agregado.values():
        total = item["presencas"] + item["faltas"] + item["atrasos"]
        item["total"] = total
        item["percentual"] = (
            round((item["presencas"] + item["atrasos"]) / total * 100, 1) if total else 0.0
        )

    return sorted(agregado.values(), key=lambda x: (-x["faltas"], x["student_name"]))


def historico_turma(class_name: str) -> list[dict]:
    """Todos os registros da turma (qualquer disciplina/data), para export."""
    if not class_name:
        return []
    try:
        with db.abrir() as con:
            tem_status = _tem_coluna(con, TABELA, "status")
            colunas = (
                "id, student_name, is_present, class_name, date, subject_id, professor_name"
                + (", status" if tem_status else "")
            )
            linhas = con.execute(
                f"SELECT {colunas} FROM {TABELA} WHERE class_name = ? ORDER BY date, student_name",
                (class_name,),
            ).fetchall()
    except Exception:
        return []

    nomes = {str(disciplina["id"]): disciplina["name"] for disciplina in repositories.listar_disciplinas()}
    resultado = []
    for linha in _dedupe_por_id(linhas):
        item = dict(linha)
        item["status"] = _status_de(linha["is_present"], linha["status"] if tem_status else None)
        item["disciplina"] = nomes.get(str(linha["subject_id"]), "")
        resultado.append(item)
    return resultado


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
def _csv(cabecalho: list[str], linhas: list[list]) -> bytes:
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";")
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return buffer.getvalue().encode("utf-8-sig")


def gerar_csv_resumo(linhas: list[dict]) -> bytes:
    return _csv(
        ["Estudante", "Presencas", "Faltas", "Atrasos", "Total", "% Frequencia"],
        [
            [
                item["student_name"],
                item["presencas"],
                item["faltas"],
                item["atrasos"],
                item["total"],
                f"{item['percentual']:.1f}",
            ]
            for item in linhas
        ],
    )


def gerar_csv_historico(linhas: list[dict]) -> bytes:
    return _csv(
        ["Data", "Disciplina", "Estudante", "Status", "Professor"],
        [
            [
                item.get("date") or "",
                item.get("disciplina") or "",
                item.get("student_name") or "",
                item.get("status") or "",
                item.get("professor_name") or "",
            ]
            for item in linhas
        ],
    )
