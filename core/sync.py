"""
Sincronização Supabase -> SQLite (cache local do escola_ativa.db).

Baixa as tabelas do Supabase via PostgREST e grava no SQLite local com upsert
**não-destrutivo**: insere linhas novas e atualiza as existentes (pela chave),
sem apagar dados locais que não existam na nuvem. Colunas novas vindas da
nuvem são adicionadas às tabelas existentes; tabelas que só existem no
Supabase são criadas localmente.

As credenciais são lidas de variáveis de ambiente ou de um arquivo `.env`
(procura em `SYSAVA_ENV_FILE`, depois `<projeto>/.env` e `<projeto>/data/.env`).
Nenhuma chave é exibida em log ou tela: apenas o host e uma versão mascarada.

Uso típico:
    from core import sync
    resumo = sync.sincronizar(modo="incremental", progresso=lambda msg, frac: print(msg))
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from core import db

PROJETO_DIR = db.PROJETO_DIR
STATE_PATH = PROJETO_DIR / "data" / "sync_state.json"
CONFIG_PATH = PROJETO_DIR / "data" / "sync_config.json"
BACKUP_DIR = PROJETO_DIR / "backups"

TAMANHO_PAGINA = 1000
LIMITE_AMOSTRA = 50

# Colunas de data/hora usadas para o modo incremental, em ordem de preferência.
COLUNAS_TEMPO = (
    "updated_at",
    "updated",
    "atualizado_em",
    "created_at",
    "created",
    "criado_em",
    "submitted_at",
    "timestamp",
)

# Chaves candidatas quando a tabela local não declara PRIMARY KEY.
CANDIDATOS_CHAVE = ("id", "username", "key", "chave", "user_username", "code", "uuid")

Progresso = Callable[[str, float | None], None]


class SyncError(RuntimeError):
    """Erro de configuração ou de sincronização."""


# --------------------------------------------------------------------------
# Credenciais e conexão
# --------------------------------------------------------------------------
def caminho_env() -> Path:
    """Caminho do arquivo .env usado para as credenciais do Supabase."""
    explicito = os.environ.get("SYSAVA_ENV_FILE")
    if explicito:
        return Path(os.path.expandvars(explicito)).expanduser()
    for candidato in (PROJETO_DIR / ".env", PROJETO_DIR / "data" / ".env"):
        if candidato.exists():
            return candidato
    return PROJETO_DIR / ".env"


def carregar_credenciais(recarregar: bool = False) -> dict:
    """Lê SUPABASE_URL/SUPABASE_KEY das variáveis de ambiente ou do .env."""
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_KEY") or "").strip()
    env_file = caminho_env()

    if not (url and key) and env_file.exists():
        try:
            from dotenv import dotenv_values

            valores = dotenv_values(env_file)
            url = url or (valores.get("SUPABASE_URL") or "").strip()
            key = key or (valores.get("SUPABASE_KEY") or "").strip()
        except Exception:
            pass

    return {"url": url, "key": key, "env_file": str(env_file)}


def _mascarar(valor: str) -> str:
    """Devolve uma versão segura para exibição de um segredo."""
    if not valor:
        return ""
    if len(valor) <= 8:
        return "*" * len(valor)
    return f"{valor[:4]}...{valor[-4:]}"


def descrever_conexao() -> dict:
    """Resumo da configuração atual (sem expor a chave)."""
    cred = carregar_credenciais()
    host = ""
    if cred["url"]:
        host = cred["url"].split("//")[-1].split("/")[0]
    return {
        "configurado": bool(cred["url"] and cred["key"]),
        "env_file": cred["env_file"],
        "env_existe": Path(cred["env_file"]).exists(),
        "host": host,
        "chave": _mascarar(cred["key"]),
    }


_cliente = None
_cliente_lock = threading.Lock()


def cliente(recriar: bool = False):
    """Cria (e mantém em cache) o cliente Supabase. Importa o pacote sob demanda."""
    global _cliente
    with _cliente_lock:
        if _cliente is None or recriar:
            cred = carregar_credenciais()
            if not (cred["url"] and cred["key"]):
                raise SyncError(
                    "Credenciais do Supabase ausentes. Defina SUPABASE_URL e SUPABASE_KEY "
                    f"(por exemplo em {caminho_env()})."
                )
            try:
                from supabase import create_client
            except ImportError as erro:
                raise SyncError(
                    "Pacote 'supabase' não instalado. Rode: pip install supabase"
                ) from erro
            _cliente = create_client(cred["url"], cred["key"])
        return _cliente


def testar_conexao() -> dict:
    """Testa a conexão com o Supabase e devolve um status legível."""
    info = descrever_conexao()
    if not info["configurado"]:
        info.update({"ok": False, "erro": "SUPABASE_URL/SUPABASE_KEY não configuradas."})
        return info
    try:
        resposta = cliente(recriar=True).table("app_users").select("username").limit(1).execute()
        info.update({"ok": True, "erro": None, "amostra": len(resposta.data or [])})
    except Exception as erro:
        info.update({"ok": False, "erro": str(erro)})
    return info


# --------------------------------------------------------------------------
# Descoberta de tabelas e colunas no Supabase
# --------------------------------------------------------------------------
_esquema_cache: dict[str, list[str]] | None = None
_esquema_lock = threading.Lock()


def esquema_remoto(recarregar: bool = False) -> dict[str, list[str]]:
    """Mapa {tabela: [colunas]} obtido do OpenAPI do PostgREST."""
    global _esquema_cache
    with _esquema_lock:
        if _esquema_cache is None or recarregar:
            cred = carregar_credenciais()
            if not (cred["url"] and cred["key"]):
                raise SyncError("Credenciais do Supabase ausentes para listar as tabelas.")
            import httpx

            resposta = httpx.get(
                cred["url"].rstrip("/") + "/rest/v1/",
                headers={
                    "apikey": cred["key"],
                    "Authorization": f"Bearer {cred['key']}",
                },
                timeout=30,
            )
            resposta.raise_for_status()
            definicoes = (resposta.json() or {}).get("definitions", {})
            _esquema_cache = {
                nome: sorted((definicao.get("properties") or {}).keys())
                for nome, definicao in definicoes.items()
            }
        return _esquema_cache


def listar_tabelas_remotas() -> list[str]:
    """Nomes das tabelas disponíveis no Supabase, em ordem alfabética."""
    return sorted(esquema_remoto().keys())


# --------------------------------------------------------------------------
# Contagens e auditoria
# --------------------------------------------------------------------------
def _q(nome: str) -> str:
    """Escapa um identificador SQL entre aspas duplas."""
    return '"' + str(nome).replace('"', '""') + '"'


def contar_local(tabela: str) -> int:
    """Contagem de linhas no SQLite local. Retorna -1 se a tabela não existir."""
    with db.abrir() as con:
        return _contar_local_con(con, tabela)


def _contar_local_con(con, tabela: str) -> int:
    if not _existe_tabela(con, tabela):
        return -1
    try:
        return con.execute(f"SELECT COUNT(*) FROM {_q(tabela)}").fetchone()[0]
    except sqlite3.Error:
        return -1


def contar_remoto(tabela: str) -> int:
    """Contagem exata de linhas no Supabase."""
    resposta = cliente().table(tabela).select("*", count="exact").limit(1).execute()
    return int(resposta.count or 0)


def auditar(tabelas: Iterable[str] | None = None, progresso: Progresso | None = None) -> list[dict]:
    """Compara as contagens local × nuvem, tabela por tabela."""
    log = _preparar_log(progresso)
    lista = list(tabelas) if tabelas else listar_tabelas_remotas()
    resultado: list[dict] = []
    total = len(lista)

    for indice, tabela in enumerate(lista, start=1):
        log(f"[{indice}/{total}] Auditando '{tabela}'...", (indice - 1) / max(total, 1))
        item = {"tabela": tabela, "remoto": None, "local": None, "diferenca": None, "status": "ok"}
        try:
            item["remoto"] = contar_remoto(tabela)
        except Exception as erro:
            item["status"] = "erro"
            item["erro"] = str(erro)
        item["local"] = contar_local(tabela)
        if item["local"] < 0:
            item["local"] = 0
            item["status"] = "ausente_local"
        if item["remoto"] is not None:
            item["diferenca"] = item["remoto"] - item["local"]
        resultado.append(item)

    log(f"Auditoria concluída ({total} tabelas).", 1.0)
    return resultado


# --------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------
def backup_banco(destino_dir: Path | str | None = None) -> Path:
    """Copia o .db em uso para a pasta de backups com carimbo de data/hora."""
    origem = db.caminho_atual()
    if not origem.exists():
        raise SyncError(f"Banco local não encontrado: {origem}")

    pasta = Path(destino_dir) if destino_dir else BACKUP_DIR
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = pasta / f"backup_SysAva_{carimbo}.db"
    shutil.copy2(origem, destino)
    return destino


# --------------------------------------------------------------------------
# Introspecção do SQLite local
# --------------------------------------------------------------------------
def _existe_tabela(con, tabela: str) -> bool:
    linha = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabela,)
    ).fetchone()
    return linha is not None


def _colunas_locais(con, tabela: str) -> list[str]:
    return [linha[1] for linha in con.execute(f"PRAGMA table_info({_q(tabela)})")]


def _pk_local(con, tabela: str) -> list[str]:
    return [linha[1] for linha in con.execute(f"PRAGMA table_info({_q(tabela)})") if linha[5]]


def _indice_unico(con, tabela: str) -> list[str]:
    """Primeiro índice UNIQUE com colunas simples (ignora índices de expressão)."""
    try:
        indices = list(con.execute(f"PRAGMA index_list({_q(tabela)})"))
    except sqlite3.Error:
        return []
    for indice in indices:
        if not indice[2]:
            continue
        colunas = [linha[2] for linha in con.execute(f"PRAGMA index_info({_q(indice[1])})")]
        if colunas and all(coluna is not None for coluna in colunas):
            return colunas
    return []


def _chave_heuristica(colunas: Sequence[str]) -> list[str]:
    for candidato in CANDIDATOS_CHAVE:
        if candidato in colunas:
            return [candidato]
    return list(colunas)


def _chave_efetiva(con, tabela: str, colunas: Sequence[str]) -> list[str]:
    """Chave de upsert: PK, senão índice UNIQUE, senão heurística."""
    pk = _pk_local(con, tabela)
    unica = _indice_unico(con, tabela)
    if unica and set(unica) != set(pk):
        return unica
    if pk:
        return pk
    return _chave_heuristica(colunas)


# --------------------------------------------------------------------------
# Conversão de valores
# --------------------------------------------------------------------------
def _valor_sql(valor):
    """Adapta valores do PostgREST para tipos aceitos pelo sqlite3."""
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return valor


def _chave_normalizada(valores: Sequence) -> tuple[str, ...]:
    """Normaliza a chave para comparar tipos diferentes (TEXT x INTEGER)."""
    return tuple("" if valor is None else str(valor) for valor in valores)


def _normalizar_valor(valor) -> str | None:
    """Forma comparável de um valor (para detectar registros inalterados)."""
    adaptado = _valor_sql(valor)
    if adaptado is None:
        return None
    if isinstance(adaptado, bytes):
        return adaptado.decode("utf-8", "replace")
    return str(adaptado)


def _inferir_tipo(valores: Sequence) -> str:
    """Infere o tipo SQLite a partir de uma amostra de valores."""
    tipos = set()
    for valor in valores:
        if valor is None:
            continue
        if isinstance(valor, bool):
            tipos.add("INTEGER")
        elif isinstance(valor, int):
            tipos.add("INTEGER")
        elif isinstance(valor, float):
            tipos.add("REAL")
        else:
            tipos.add("TEXT")
    if not tipos:
        return "TEXT"
    if tipos == {"INTEGER"}:
        return "INTEGER"
    if tipos <= {"INTEGER", "REAL"}:
        return "REAL"
    return "TEXT"


# --------------------------------------------------------------------------
# Gravação (upsert)
# --------------------------------------------------------------------------
def _garantir_tabela(con, tabela: str, colunas: Sequence[str], linhas: Sequence[dict]):
    """Cria a tabela se faltar e adiciona colunas novas. Devolve (criada, adicionadas)."""
    if not _existe_tabela(con, tabela):
        chave = _chave_heuristica(colunas)
        definicoes = []
        for coluna in colunas:
            tipo = _inferir_tipo([linha.get(coluna) for linha in linhas[:LIMITE_AMOSTRA]])
            if chave == [coluna]:
                definicoes.append(f"{_q(coluna)} {tipo} PRIMARY KEY")
            else:
                definicoes.append(f"{_q(coluna)} {tipo}")
        con.execute(f"CREATE TABLE IF NOT EXISTS {_q(tabela)} ({', '.join(definicoes)})")
        return True, list(colunas)

    locais = _colunas_locais(con, tabela)
    adicionadas = []
    for coluna in colunas:
        if coluna in locais:
            continue
        tipo = _inferir_tipo([linha.get(coluna) for linha in linhas[:LIMITE_AMOSTRA]])
        con.execute(f"ALTER TABLE {_q(tabela)} ADD COLUMN {_q(coluna)} {tipo}")
        adicionadas.append(coluna)
    return False, adicionadas


def _carregar_existentes(con, tabela: str, chave: Sequence[str], colunas: Sequence[str]) -> dict:
    """Mapa {chave_normalizada: valores_normalizados} das linhas locais."""
    if not chave:
        return {}
    colunas_chave = ", ".join(_q(coluna) for coluna in chave)
    colunas_dados = ", ".join(_q(coluna) for coluna in colunas)
    existentes: dict = {}
    try:
        cursor = con.execute(f"SELECT {colunas_chave}, {colunas_dados} FROM {_q(tabela)}")
    except sqlite3.Error:
        return {}
    tamanho = len(chave)
    for linha in cursor:
        normalizada = _chave_normalizada(linha[:tamanho])
        existentes[normalizada] = tuple(_normalizar_valor(valor) for valor in linha[tamanho:])
    return existentes


def _planejar(con, tabela: str, linhas: Sequence[dict], colunas: Sequence[str], chave: Sequence[str]):
    """Calcula quantos registros seriam inseridos/atualizados/inalterados/ignorados."""
    existentes = _carregar_existentes(con, tabela, chave, colunas)
    inseridos = atualizados = inalterados = ignorados = 0
    vistos: set = set()
    for linha in linhas:
        normalizada = _chave_normalizada([linha.get(coluna) for coluna in chave])
        if normalizada in vistos:
            ignorados += 1
            continue
        vistos.add(normalizada)
        if normalizada in existentes:
            if existentes[normalizada] == tuple(_normalizar_valor(linha.get(coluna)) for coluna in colunas):
                inalterados += 1
            else:
                atualizados += 1
        else:
            inseridos += 1
    return inseridos, atualizados, inalterados, ignorados


def _gravar(con, tabela: str, linhas: Sequence[dict], colunas: Sequence[str], chave: Sequence[str]):
    """Faz upsert (insert/update) por chave. Devolve (inseridos, atualizados, inalterados, ignorados)."""
    if not linhas or not colunas:
        return 0, 0, 0, 0

    lista_colunas = ", ".join(_q(coluna) for coluna in colunas)
    marcadores = ", ".join("?" for _ in colunas)
    existentes = _carregar_existentes(con, tabela, chave, colunas)

    inserir: list[tuple] = []
    atualizar: list[tuple] = []
    inalterados = 0
    ignorados = 0
    vistos: set = set()
    for linha in linhas:
        valores = tuple(_valor_sql(linha.get(coluna)) for coluna in colunas)
        if chave:
            normalizada = _chave_normalizada([linha.get(coluna) for coluna in chave])
            if normalizada in vistos:
                ignorados += 1
                continue
            vistos.add(normalizada)
            if normalizada in existentes:
                if existentes[normalizada] == tuple(_normalizar_valor(valor) for valor in valores):
                    inalterados += 1
                    continue
                chave_valores = tuple(_valor_sql(linha.get(coluna)) for coluna in chave)
                atualizar.append(valores + chave_valores)
                continue
        inserir.append(valores)

    inseridos = 0
    if inserir:
        cursor = con.executemany(
            f"INSERT OR IGNORE INTO {_q(tabela)} ({lista_colunas}) VALUES ({marcadores})", inserir
        )
        aplicados = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
        inseridos = min(aplicados, len(inserir))
        ignorados += len(inserir) - inseridos

    atualizados = 0
    if atualizar and chave:
        sets = ", ".join(f"{_q(coluna)} = ?" for coluna in colunas)
        where = " AND ".join(f"{_q(coluna)} = ?" for coluna in chave)
        sql = f"UPDATE {_q(tabela)} SET {sets} WHERE {where}"
        for valores in atualizar:
            try:
                con.execute(sql, valores)
                atualizados += 1
            except sqlite3.IntegrityError:
                ignorados += 1

    return inseridos, atualizados, inalterados, ignorados


# --------------------------------------------------------------------------
# Download das linhas remotas
# --------------------------------------------------------------------------
def _escolher_coluna_tempo(colunas: Sequence[str]) -> str | None:
    for candidato in COLUNAS_TEMPO:
        if candidato in colunas:
            return candidato
    return None


def _maior_tempo(linhas: Sequence[dict], colunas: Sequence[str]) -> str | None:
    coluna = _escolher_coluna_tempo(colunas)
    if not coluna:
        return None
    valores = [str(linha.get(coluna)) for linha in linhas if linha.get(coluna) is not None]
    return max(valores) if valores else None


def _buscar_remoto(
    tabela: str,
    coluna_tempo: str | None = None,
    desde: str | None = None,
    log: Progresso | None = None,
) -> list[dict]:
    """Baixa todas as linhas da tabela (paginado em 1000, limite do PostgREST)."""
    linhas: list[dict] = []
    inicio = 0
    while True:
        consulta = cliente().table(tabela).select("*")
        if coluna_tempo and desde:
            consulta = consulta.gt(coluna_tempo, desde)
        if coluna_tempo:
            consulta = consulta.order(coluna_tempo)
        consulta = consulta.range(inicio, inicio + TAMANHO_PAGINA - 1)
        resposta = consulta.execute()
        pagina = resposta.data or []
        if not pagina:
            break
        linhas.extend(pagina)
        if log and inicio and (inicio // TAMANHO_PAGINA) % 5 == 0:
            log(f"  {tabela}: {len(linhas)} registros baixados...", None)
        if len(pagina) < TAMANHO_PAGINA:
            break
        inicio += TAMANHO_PAGINA
    return linhas


# --------------------------------------------------------------------------
# Resultado por tabela
# --------------------------------------------------------------------------
@dataclass
class ResultadoTabela:
    tabela: str
    modo: str = "full"
    remoto: int = 0
    baixados: int = 0
    local_antes: int = 0
    local_depois: int = 0
    inseridos: int = 0
    atualizados: int = 0
    inalterados: int = 0
    ignorados: int = 0
    colunas_adicionadas: list[str] = field(default_factory=list)
    criada: bool = False
    existe_local: bool = True
    ultimo_tempo: str | None = None
    status: str = "ok"
    erro: str | None = None
    duracao: float = 0.0

    def as_dict(self) -> dict:
        return {
            "tabela": self.tabela,
            "modo": self.modo,
            "remoto": self.remoto,
            "baixados": self.baixados,
            "local_antes": self.local_antes,
            "local_depois": self.local_depois,
            "inseridos": self.inseridos,
            "atualizados": self.atualizados,
            "inalterados": self.inalterados,
            "ignorados": self.ignorados,
            "colunas_adicionadas": self.colunas_adicionadas,
            "criada": self.criada,
            "existe_local": self.existe_local,
            "ultimo_tempo": self.ultimo_tempo,
            "status": self.status,
            "erro": self.erro,
            "duracao": round(self.duracao, 3),
        }


def _preparar_log(progresso: Progresso | None) -> Progresso:
    if progresso is None:
        return lambda _mensagem, _fracao=None: None
    return progresso


def _sincronizar_tabela(
    tabela: str,
    modo: str,
    dry_run: bool,
    ultimo_tempo: str | None,
    log: Progresso,
) -> ResultadoTabela:
    inicio = time.time()
    resultado = ResultadoTabela(tabela=tabela, modo=modo, ultimo_tempo=ultimo_tempo)

    try:
        colunas_remotas = list(esquema_remoto().get(tabela, []))
        resultado.remoto = contar_remoto(tabela)

        coluna_tempo = None
        desde = None
        if modo == "incremental" and ultimo_tempo:
            coluna_tempo = _escolher_coluna_tempo(colunas_remotas)
            desde = ultimo_tempo if coluna_tempo else None

        linhas = _buscar_remoto(tabela, coluna_tempo, desde, log)
        resultado.baixados = len(linhas)

        if not linhas:
            resultado.local_antes = max(contar_local(tabela), 0)
            resultado.local_depois = resultado.local_antes
            resultado.status = "sem_novidades"
            resultado.duracao = time.time() - inicio
            return resultado

        colunas_dados = sorted({coluna for linha in linhas for coluna in linha.keys()})
        novo_tempo = _maior_tempo(linhas, colunas_dados) or ultimo_tempo

        if dry_run:
            with db.abrir() as con:
                existe = _existe_tabela(con, tabela)
                resultado.existe_local = existe
                if existe:
                    locais = _colunas_locais(con, tabela)
                    resultado.colunas_adicionadas = [
                        coluna for coluna in colunas_dados if coluna not in locais
                    ]
                    chave = _chave_efetiva(con, tabela, colunas_dados)
                    (
                        resultado.inseridos,
                        resultado.atualizados,
                        resultado.inalterados,
                        resultado.ignorados,
                    ) = _planejar(con, tabela, linhas, colunas_dados, chave)
                    resultado.local_antes = _contar_local_con(con, tabela)
                else:
                    resultado.criada = True
                    resultado.colunas_adicionadas = list(colunas_dados)
                    resultado.inseridos = len(linhas)
            resultado.local_depois = resultado.local_antes
            resultado.status = "dry-run"
        else:
            with db.abrir(somente_leitura=False) as con:
                resultado.local_antes = max(_contar_local_con(con, tabela), 0)
                criada, adicionadas = _garantir_tabela(con, tabela, colunas_dados, linhas)
                resultado.criada = criada
                resultado.colunas_adicionadas = adicionadas
                chave = _chave_efetiva(con, tabela, colunas_dados)
                try:
                    (
                        resultado.inseridos,
                        resultado.atualizados,
                        resultado.inalterados,
                        resultado.ignorados,
                    ) = _gravar(con, tabela, linhas, colunas_dados, chave)
                    con.commit()
                except Exception:
                    con.rollback()
                    raise
                resultado.local_depois = max(_contar_local_con(con, tabela), 0)

        resultado.ultimo_tempo = novo_tempo

    except Exception as erro:
        resultado.status = "erro"
        resultado.erro = str(erro)
        resultado.ultimo_tempo = ultimo_tempo

    resultado.duracao = time.time() - inicio
    return resultado


# --------------------------------------------------------------------------
# Estado e configuração
# --------------------------------------------------------------------------
def carregar_estado() -> dict:
    """Lê o resumo do último sync (data/sync_state.json)."""
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, encoding="utf-8") as arquivo:
                return json.load(arquivo)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def salvar_estado(resumo: dict) -> None:
    """Atualiza o resumo do último sync por tabela."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    atual = carregar_estado()
    tabelas = dict(atual.get("tabelas") or {})
    for item in resumo.get("tabelas", []):
        anterior = tabelas.get(item["tabela"]) or {}
        if item.get("ultimo_tempo") is None:
            item = {**item, "ultimo_tempo": anterior.get("ultimo_tempo")}
        tabelas[item["tabela"]] = item

    dados = {
        "ultimo_sync": resumo.get("fim"),
        "modo": resumo.get("modo"),
        "dry_run": bool(resumo.get("dry_run")),
        "backup": resumo.get("backup"),
        "duracao": resumo.get("duracao"),
        "totais": resumo.get("totais"),
        "tabelas": tabelas,
    }
    with open(STATE_PATH, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def carregar_config() -> dict:
    """Configuração do agendamento (data/sync_config.json)."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as arquivo:
                return json.load(arquivo)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def salvar_config(dados: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    atual = carregar_config()
    atual.update(dados)
    with open(CONFIG_PATH, "w", encoding="utf-8") as arquivo:
        json.dump(atual, arquivo, ensure_ascii=False, indent=2)


def proxima_execucao(hora: str) -> datetime:
    """Próximo horário (HH:MM) a partir de agora."""
    try:
        partes = str(hora).split(":")
        alvo_hora, alvo_minuto = int(partes[0]), int(partes[1])
    except (ValueError, IndexError):
        alvo_hora, alvo_minuto = 3, 0
    agora = datetime.now()
    alvo = agora.replace(hour=alvo_hora, minute=alvo_minuto, second=0, microsecond=0)
    if alvo <= agora:
        alvo += timedelta(days=1)
    return alvo


# --------------------------------------------------------------------------
# Sincronização
# --------------------------------------------------------------------------
def sincronizar(
    tabelas: Iterable[str] | None = None,
    modo: str = "incremental",
    dry_run: bool = False,
    backup: bool = True,
    progresso: Progresso | None = None,
) -> dict:
    """
    Baixa o Supabase e grava no SQLite local.

    modo="incremental" usa a coluna de data/hora (updated_at/created_at) para
    buscar só o que mudou desde o último sync; modo="full" baixa tudo. Em
    dry_run nada é gravado (apenas simula). backup copia o .db antes de gravar.
    """
    log = _preparar_log(progresso)
    if modo not in ("incremental", "full"):
        raise SyncError(f"Modo inválido: {modo!r} (use 'incremental' ou 'full').")

    cred = carregar_credenciais()
    if not (cred["url"] and cred["key"]):
        raise SyncError(
            "Credenciais do Supabase ausentes. Defina SUPABASE_URL e SUPABASE_KEY "
            f"(por exemplo em {caminho_env()})."
        )

    inicio = time.time()
    carimbo_inicio = datetime.now().isoformat(timespec="seconds")
    estado_anterior = carregar_estado()
    tempos_anteriores = {
        nome: dados.get("ultimo_tempo")
        for nome, dados in (estado_anterior.get("tabelas") or {}).items()
    }

    lista = list(tabelas) if tabelas else listar_tabelas_remotas()
    log(f"{len(lista)} tabela(s) remota(s) encontrada(s) (modo {modo}).", 0.0)

    caminho_backup = None
    if backup and not dry_run:
        caminho_backup = backup_banco()
        log(f"Backup criado: {caminho_backup.name}", None)

    resultados: list[ResultadoTabela] = []
    total = max(len(lista), 1)
    for indice, tabela in enumerate(lista, start=1):
        log(f"[{indice}/{total}] Sincronizando '{tabela}'...", (indice - 1) / total)
        resultado = _sincronizar_tabela(
            tabela, modo, dry_run, tempos_anteriores.get(tabela), log
        )
        resultados.append(resultado)
        detalhe = f"  {tabela}: +{resultado.inseridos} ~{resultado.atualizados}"
        if resultado.inalterados:
            detalhe += f" ={resultado.inalterados}"
        if resultado.ignorados:
            detalhe += f" !{resultado.ignorados}"
        if resultado.status == "erro":
            detalhe += f" (erro: {resultado.erro})"
        elif resultado.status == "sem_novidades":
            detalhe += " (sem novidades)"
        log(detalhe, indice / total)

    fim = datetime.now()
    resumo = {
        "inicio": carimbo_inicio,
        "fim": fim.isoformat(timespec="seconds"),
        "duracao": round(time.time() - inicio, 2),
        "modo": modo,
        "dry_run": dry_run,
        "backup": str(caminho_backup) if caminho_backup else None,
        "tabelas": [resultado.as_dict() for resultado in resultados],
        "totais": {
            "tabelas": len(resultados),
            "inseridos": sum(resultado.inseridos for resultado in resultados),
            "atualizados": sum(resultado.atualizados for resultado in resultados),
            "inalterados": sum(resultado.inalterados for resultado in resultados),
            "ignorados": sum(resultado.ignorados for resultado in resultados),
            "erros": sum(1 for resultado in resultados if resultado.status == "erro"),
        },
    }

    if not dry_run:
        salvar_estado(resumo)

    prefixo = "Simulação" if dry_run else "Sincronização"
    log(
        f"{prefixo} concluída em {resumo['duracao']}s — "
        f"+{resumo['totais']['inseridos']} inseridos, "
        f"~{resumo['totais']['atualizados']} atualizados, "
        f"={resumo['totais']['inalterados']} inalterados, "
        f"!{resumo['totais']['ignorados']} ignorados, "
        f"{resumo['totais']['erros']} erro(s).",
        1.0,
    )
    return resumo
