"""Armazém persistente de uma planta (D92).

Um arquivo SQLite por planta: plantas nunca compartilham arquivo (isolamento físico).
Dentro de uma planta, todo registro pertence a um equipamento e nunca se mistura com o
de outro. Guarda registros de dados versionados, importações, conflitos, correções,
perfis de importação, tabela de preços, referências, fechamentos, investigações,
intervenções e custos do serviço.

Regras:
- nada é apagado nem substituído em silêncio: correção cria nova versão e guarda a
  anterior, com motivo, autor e data (AGENTS.md, regra 2);
- cada escrita incrementa a "revisão" da planta; qualquer análise pode ser reproduzida
  com os registros ativos numa revisão;
- importação repetida não duplica: registro igual é reconhecido pela chave natural;
- valor diferente para uma chave já existente vira conflito pendente, salvo importação
  explícita de correção (com motivo e autor);
- a classe da planta (sintética, pública, cliente autorizado) é fixa e precisa bater com
  a origem declarada das linhas.

Controle de acesso: este armazém é local (um usuário da máquina). Uma instalação com
vários clientes exige autenticação por cliente, ainda não implementada; separar telas não
substitui isso.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from math import isfinite
from pathlib import Path

import pandas as pd

from euler.io import Pacote
from euler.io.esquemas import TABELAS
from euler.io.leitura import Aviso
from euler.io.pacote import fontes_de_arquivos, importar_pacote

ESQUEMA_VERSAO = 2
RAIZ_CODIGO = Path(__file__).resolve().parents[1]


def raiz_padrao() -> Path:
    """Mesma raiz da biblioteca de arquivos e análises."""
    from euler.persistencia import raiz_padrao as raiz_unica

    return raiz_unica()


CLASSES = {
    "sintetico": "Dados sintéticos",
    "publico": "Dados públicos",
    "cliente_autorizado": "Dados de cliente (autorizados)",
}
ORIGEM_DA_CLASSE = {"sintetico": "sintetico", "publico": "publico", "cliente_autorizado": "real"}
# tarefas do registro de horas de atendimento (T16)
TAREFAS_ATENDIMENTO = {
    "implantacao": "Implantação (cadastro, primeira conversa)",
    "planilha": "Conferência ou ajuste de planilha",
    "duvida": "Dúvida do cliente",
    "fechamento": "Revisão do fechamento com o cliente",
    "outro": "Outro",
}

# colunas calculadas pelos importadores: não são dado de entrada
DERIVADAS = {
    "diario": {
        "p_vapor_bar_abs",
        "p_purga_bar_abs",
        "p_agua_referencia_bar_abs",
        "p_agua_eco_bar_abs",
    },
    "combustivel": {"massa_kg_calc", "massa_origem"},
}
COLUNA_TEMPO = {
    "diario": "instante_observado",
    "combustivel": "data",
    "amostras": "data",
    "eventos": "instante",
    "instrumentos": "ultima_verificacao",
}
# configuração padrão de cada equipamento (editável sem mudar código)
CONFIG_PADRAO = {
    "altitude_m": None,
    "dias_para_desatualizado": 14,
    "politica_custo": "recebimentos_do_periodo",
    "periodos_minimos_pos_intervencao": 2,
}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS equipamento (
    id TEXT PRIMARY KEY, nome TEXT NOT NULL, caldeira_id TEXT NOT NULL,
    config TEXT NOT NULL, criado_em TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evento (
    id INTEGER PRIMARY KEY, revisao INTEGER NOT NULL, quando TEXT NOT NULL,
    equipamento_id TEXT, entidade TEXT NOT NULL, entidade_id TEXT, tipo TEXT NOT NULL,
    autor TEXT, dados TEXT);
CREATE TABLE IF NOT EXISTS perfil (
    id INTEGER PRIMARY KEY, equipamento_id TEXT NOT NULL, fonte TEXT NOT NULL,
    mapeamento TEXT NOT NULL, criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL,
    usos INTEGER NOT NULL DEFAULT 0, UNIQUE (equipamento_id, fonte));
CREATE TABLE IF NOT EXISTS lote (
    id INTEGER PRIMARY KEY, revisao INTEGER NOT NULL, equipamento_id TEXT NOT NULL,
    recebido_em TEXT NOT NULL, autor TEXT, fonte TEXT, modo TEXT NOT NULL, motivo TEXT,
    arquivos TEXT NOT NULL, resumo TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS registro (
    id INTEGER PRIMARY KEY, equipamento_id TEXT NOT NULL, tabela TEXT NOT NULL,
    chave TEXT NOT NULL, versao INTEGER NOT NULL, conteudo TEXT, original TEXT,
    lote_id INTEGER, revisao_de INTEGER NOT NULL, revisao_ate INTEGER,
    motivo TEXT, autor TEXT, UNIQUE (equipamento_id, tabela, chave, versao));
CREATE INDEX IF NOT EXISTS registro_ativo ON registro (equipamento_id, tabela, revisao_ate);
CREATE TABLE IF NOT EXISTS conflito (
    id INTEGER PRIMARY KEY, equipamento_id TEXT NOT NULL, tabela TEXT NOT NULL,
    chave TEXT NOT NULL, proposto TEXT NOT NULL, original TEXT, lote_id INTEGER,
    situacao TEXT NOT NULL, decidido_em TEXT, decidido_por TEXT, motivo TEXT);
CREATE TABLE IF NOT EXISTS preco (
    id INTEGER PRIMARY KEY, equipamento_id TEXT NOT NULL, combustivel TEXT NOT NULL,
    fornecedor TEXT, preco_brl_t REAL NOT NULL, moeda TEXT NOT NULL, unidade TEXT NOT NULL,
    valido_de TEXT NOT NULL, valido_ate TEXT, custo_adicional_brl_t REAL,
    custo_adicional_desc TEXT, origem TEXT NOT NULL, criado_em TEXT NOT NULL, autor TEXT,
    anulado_motivo TEXT);
CREATE TABLE IF NOT EXISTS referencia (
    id INTEGER PRIMARY KEY, equipamento_id TEXT NOT NULL, versao INTEGER NOT NULL,
    inicio TEXT NOT NULL, fim TEXT NOT NULL, tipo TEXT NOT NULL, motivo TEXT NOT NULL,
    autor TEXT, criada_em TEXT NOT NULL, revisao INTEGER NOT NULL, intervencao_id INTEGER,
    dados TEXT, UNIQUE (equipamento_id, versao));
CREATE TABLE IF NOT EXISTS fechamento (
    id INTEGER PRIMARY KEY, equipamento_id TEXT NOT NULL, inicio TEXT NOT NULL,
    fim TEXT NOT NULL, referencia_id INTEGER NOT NULL, revisao_dados INTEGER NOT NULL,
    conjunto_sha TEXT NOT NULL, resultado TEXT NOT NULL, resultado_sha TEXT NOT NULL,
    versao_euler TEXT NOT NULL, criado_em TEXT NOT NULL, autor TEXT);
CREATE TABLE IF NOT EXISTS investigacao (
    id INTEGER PRIMARY KEY, equipamento_id TEXT NOT NULL, chave_grupo TEXT NOT NULL,
    titulo TEXT NOT NULL, estado TEXT NOT NULL, responsavel TEXT, criada_em TEXT NOT NULL,
    atualizada_em TEXT NOT NULL, dados TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inv_evento (
    id INTEGER PRIMARY KEY, investigacao_id INTEGER NOT NULL, quando TEXT NOT NULL,
    tipo TEXT NOT NULL, autor TEXT, texto TEXT, dados TEXT);
CREATE TABLE IF NOT EXISTS intervencao (
    id INTEGER PRIMARY KEY, equipamento_id TEXT NOT NULL, data TEXT NOT NULL,
    tipo TEXT NOT NULL, descricao TEXT NOT NULL, responsavel TEXT, investigacao_id INTEGER,
    custo_brl REAL, custo_origem TEXT, criada_em TEXT NOT NULL, autor TEXT, dados TEXT);
CREATE TABLE IF NOT EXISTS avaliacao (
    id INTEGER PRIMARY KEY, intervencao_id INTEGER NOT NULL, criada_em TEXT NOT NULL,
    revisao_dados INTEGER NOT NULL, referencia_id INTEGER, resultado TEXT NOT NULL,
    resultado_sha TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS custo_servico (
    id INTEGER PRIMARY KEY, equipamento_id TEXT, data TEXT NOT NULL, tipo TEXT NOT NULL,
    descricao TEXT NOT NULL, valor_brl REAL NOT NULL, origem TEXT NOT NULL,
    criado_em TEXT NOT NULL, autor TEXT);
"""


class ErroArmazem(ValueError):
    """Operação recusada com motivo legível (nunca corrigida em silêncio)."""


def agora_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def jdump(obj) -> str:
    """JSON canônico (chaves ordenadas, UTF-8), usado em conteúdo e em hashes."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha(obj) -> str:
    return hashlib.sha256(jdump(obj).encode("utf-8")).hexdigest()


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "planta"


# ---------------------------------------------------------------- plantas


def _arquivo_planta(raiz: Path, planta_id: str) -> Path:
    return raiz / planta_id / "euler.sqlite"


def _dentro_do_codigo(caminho: Path) -> bool:
    try:
        caminho.resolve().relative_to(RAIZ_CODIGO)
        return True
    except ValueError:
        return False


def criar_planta(
    nome: str,
    classe: str,
    raiz: Path | None = None,
    autorizacao: str | None = None,
    autor: str | None = None,
) -> Armazem:
    """Cria a planta num arquivo próprio. Dados de cliente exigem registro da autorização
    e não podem ficar dentro da pasta do código (repositório)."""
    if classe not in CLASSES:
        raise ErroArmazem(f"Classe de dados desconhecida: {classe}.")
    from euler.persistencia import Repositorio

    raiz = Path(raiz or raiz_padrao())
    if classe == "cliente_autorizado":
        if not (autorizacao or "").strip():
            raise ErroArmazem("Dados de cliente exigem registrar quem autorizou e quando.")
        if _dentro_do_codigo(raiz):
            raise ErroArmazem(
                "Dados de cliente não podem ficar dentro da pasta do código: escolha uma "
                "pasta de dados fora do repositório."
            )
    base = _slug(nome)
    planta_id, n = base, 2
    repo = Repositorio(raiz)
    while repo._caminho(planta_id).exists():
        planta_id, n = f"{base}-{n}", n + 1
    repo._criar(nome, classe=classe, autorizacao=autorizacao, planta_id=planta_id, pasta=True)
    a = repo.armazem(planta_id)
    with a._transacao() as cur:
        a._evento(cur, None, "planta", planta_id, "criada", autor, {"classe": classe})
    return a


def listar_plantas(raiz: Path | None = None) -> list[dict]:
    from euler.persistencia import Repositorio

    repo = Repositorio(raiz)
    plantas = []
    for planta in repo.listar_plantas():
        a = repo.armazem(planta["id"])
        try:
            plantas.append({**a.info, "arquivo": str(a.arquivo)})
        finally:
            a.fechar()
    return plantas


def abrir_planta(planta_id: str, raiz: Path | None = None) -> Armazem:
    from euler.persistencia import Repositorio

    return Repositorio(raiz).armazem(planta_id)


def restaurar_copia(
    arquivo: Path, raiz: Path | None = None, substituir: bool = False, autor: str | None = None
) -> Armazem:
    """Restaura uma cópia de segurança. Se a planta existe, só substitui com
    `substituir=True`, e antes guarda uma cópia da versão atual."""
    from euler.persistencia import Repositorio, _planta_id

    origem = Armazem(Path(arquivo), somente_leitura=True)
    info = origem.info
    origem.fechar()
    raiz = Path(raiz or raiz_padrao())
    repo = Repositorio(raiz)
    _planta_id(info["planta_id"])
    destino = repo._caminho(info["planta_id"])
    if not destino.exists():
        destino = _arquivo_planta(repo.raiz, info["planta_id"])
    if destino.exists():
        if not substituir:
            raise ErroArmazem(
                f"A planta {info['planta_id']} já existe. Confirme a substituição; a versão "
                "atual será guardada como cópia antes."
            )
        existente = Armazem(destino)
        try:
            existente.copia_seguranca(destino.parent / "copias")
        finally:
            existente.fechar()
    destino.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(arquivo))
    dst = sqlite3.connect(str(destino))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    a = Armazem(destino)
    with a._transacao() as cur:
        a._evento(cur, None, "planta", info["planta_id"], "restaurada", autor, {"de": str(arquivo)})
    return a


# ---------------------------------------------------------------- valores canônicos


def _valor(v, tipo: str):
    if v is None or (not isinstance(v, str | bool) and pd.isna(v)):
        return None
    if tipo == "instante":
        return pd.Timestamp(v).isoformat()
    if tipo == "data":
        return pd.Timestamp(v).date().isoformat()
    if tipo == "numero":
        return float(v)
    if tipo == "booleano":
        return bool(v)
    return str(v)


def _texto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "sim" if v else "nao"
    if isinstance(v, float):
        return repr(v)
    return str(v)


def canonico(tabela: str, linha: pd.Series) -> dict:
    """Linha normalizada → valores do contrato em forma canônica (sem colunas derivadas)."""
    return {
        c.nome: _valor(linha.get(c.nome), c.tipo)
        for c in TABELAS[tabela].colunas
        if c.nome not in DERIVADAS.get(tabela, set())
    }


def chave_natural(tabela: str, c: dict) -> str | None:
    """Identidade do registro para reconhecer o mesmo dado em importações repetidas.

    diário: caldeira + instante observado; combustível: lote do recebimento (ou tipo, data
    e fornecedor quando não há lote); amostras: id; eventos: instante + tipo;
    instrumentos: id. Sem chave → a linha é recusada com motivo.
    """
    if tabela == "diario":
        partes = (c.get("caldeira_id"), c.get("instante_observado"))
    elif tabela == "combustivel":
        if c.get("tipo") == "recebimento" and c.get("lote_id"):
            partes = ("recebimento", c["lote_id"])
        else:
            partes = (c.get("tipo"), c.get("data"), c.get("fornecedor_id") or "")
    elif tabela == "amostras":
        partes = (c.get("amostra_id"),)
    elif tabela == "eventos":
        partes = (c.get("instante"), c.get("tipo"))
    elif tabela == "instrumentos":
        partes = (c.get("instrumento_id"),)
    else:
        return None
    if any(p is None for p in partes):
        return None
    return jdump(list(partes))


def aplicar_mapeamento(conteudo: bytes, mapeamento: dict[str, str]) -> bytes:
    """Renomeia só o cabeçalho de um CSV (coluna da fonte → coluna do contrato).

    Valores, separador e linhas ficam como vieram; o arquivo original é guardado à parte.
    """
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("cp1252")
    primeira = texto.split("\n", 1)[0]
    sep = ";" if primeira.count(";") > primeira.count(",") else ","
    linhas = list(csv.reader(io.StringIO(texto), delimiter=sep))
    if not linhas:
        return conteudo
    linhas[0] = [mapeamento.get(c.strip(), c.strip()) for c in linhas[0]]
    saida = io.StringIO()
    csv.writer(saida, delimiter=sep, lineterminator="\n").writerows(linhas)
    return saida.getvalue().encode("utf-8")


def cabecalho_csv(conteudo: bytes) -> list[str]:
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("cp1252")
    primeira = texto.split("\n", 1)[0]
    sep = ";" if primeira.count(";") > primeira.count(",") else ","
    return [c.strip() for c in next(csv.reader(io.StringIO(primeira), delimiter=sep), [])]


# ---------------------------------------------------------------- prévia de importação


@dataclass
class LinhaPrevia:
    tabela: str
    linha: int
    chave: str | None
    conteudo: dict
    original: dict
    situacao: str  # nova | igual | conflito | rejeitada | repetida_no_arquivo
    motivo: str | None = None
    tardia: bool = False
    diferencas: dict = field(default_factory=dict)


@dataclass
class Previa:
    equipamento_id: str
    arquivos: dict[str, str]  # nome → sha256
    fonte: str | None
    mapeamento: dict[str, str]
    linhas: list[LinhaPrevia]
    avisos: list[Aviso]
    tabelas_bloqueadas: dict[str, list[str]]
    planta_id: str
    revisao: int
    originais: dict[str, bytes]
    config_sha: str

    def contagem(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for x in self.linhas:
            t = out.setdefault(
                x.tabela,
                {
                    "nova": 0,
                    "igual": 0,
                    "conflito": 0,
                    "rejeitada": 0,
                    "repetida_no_arquivo": 0,
                    "tardia": 0,
                },
            )
            t[x.situacao] += 1
            t["tardia"] += int(x.tardia)
        return out


# ---------------------------------------------------------------- armazém


class Armazem:
    """Arquivo de uma planta. Todas as operações são transacionais."""

    def __init__(self, arquivo: Path, somente_leitura: bool = False):
        from euler.persistencia import preparar_banco

        self.arquivo = Path(arquivo).resolve()
        uri = self.arquivo.as_uri() + ("?mode=ro" if somente_leitura else "?mode=rw")
        self.con = sqlite3.connect(uri, uri=True, timeout=30)
        self.con.row_factory = sqlite3.Row
        try:
            self.con.execute("PRAGMA foreign_keys=ON")
            versao = self.con.execute("PRAGMA user_version").fetchone()[0]
            if versao not in (1, ESQUEMA_VERSAO):
                raise ErroArmazem("Arquivo de uma versão mais nova da EULER.")
            if not somente_leitura:
                preparar_banco(self.con, self.arquivo)
        except BaseException:
            self.con.close()
            raise

    def fechar(self) -> None:
        self.con.close()

    # ------------------------------------------------ infraestrutura
    @contextmanager
    def _transacao(self):
        cur = self.con.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            yield cur
            self.con.commit()
        except BaseException:
            self.con.rollback()
            raise

    def _nova_revisao(self, cur) -> int:
        atual = int(cur.execute("SELECT valor FROM meta WHERE chave='revisao'").fetchone()[0])
        cur.execute("UPDATE meta SET valor=? WHERE chave='revisao'", (str(atual + 1),))
        return atual + 1

    def _evento(self, cur, equip, entidade, entidade_id, tipo, autor, dados=None) -> None:
        rev = int(cur.execute("SELECT valor FROM meta WHERE chave='revisao'").fetchone()[0])
        cur.execute(
            "INSERT INTO evento (revisao, quando, equipamento_id, entidade, entidade_id, tipo, "
            "autor, dados) VALUES (?,?,?,?,?,?,?,?)",
            (rev, agora_iso(), equip, entidade, str(entidade_id), tipo, autor, jdump(dados or {})),
        )

    @property
    def info(self) -> dict:
        meta = dict(self.con.execute("SELECT chave, valor FROM meta").fetchall())
        if "planta_id" not in meta:
            raise ErroArmazem("Arquivo sem identificação de planta.")
        meta["revisao"] = int(meta["revisao"])
        meta["classe_rotulo"] = CLASSES.get(meta["classe"], meta["classe"])
        return meta

    @property
    def revisao(self) -> int:
        return self.info["revisao"]

    def eventos(self, equip: str | None = None, limite: int = 200) -> list[dict]:
        sql = "SELECT * FROM evento"
        args: tuple = ()
        if equip:
            sql += " WHERE equipamento_id=? OR equipamento_id IS NULL"
            args = (equip,)
        sql += " ORDER BY id DESC LIMIT ?"
        return [
            {**dict(r), "dados": json.loads(r["dados"] or "{}")}
            for r in self.con.execute(sql, (*args, limite))
        ]

    # ------------------------------------------------ equipamentos
    def criar_equipamento(
        self,
        equip_id: str,
        nome: str,
        caldeira_id: str | None = None,
        config: dict | None = None,
        autor: str | None = None,
    ) -> dict:
        if self.con.execute("SELECT 1 FROM equipamento WHERE id=?", (equip_id,)).fetchone():
            raise ErroArmazem(f"Equipamento já existe: {equip_id}.")
        if not (equip_id or "").strip() or not (nome or "").strip():
            raise ErroArmazem("Informe identificação e nome do equipamento.")
        cfg = self._validar_config({**CONFIG_PADRAO, **(config or {})})
        with self._transacao() as cur:
            cur.execute(
                "INSERT INTO equipamento VALUES (?,?,?,?,?)",
                (equip_id, nome, caldeira_id or equip_id, jdump(cfg), agora_iso()),
            )
            self._evento(cur, equip_id, "equipamento", equip_id, "criado", autor, cfg)
        return self.equipamento(equip_id)

    def equipamento(self, equip_id: str) -> dict:
        r = self.con.execute("SELECT * FROM equipamento WHERE id=?", (equip_id,)).fetchone()
        if r is None:
            raise ErroArmazem(f"Equipamento não encontrado: {equip_id}.")
        return {**dict(r), "config": {**CONFIG_PADRAO, **json.loads(r["config"])}}

    def equipamentos(self) -> list[dict]:
        return [
            self.equipamento(r["id"])
            for r in self.con.execute("SELECT id FROM equipamento ORDER BY id")
        ]

    def configurar(self, equip_id: str, mudancas: dict, autor: str | None = None) -> dict:
        """Altera a configuração do equipamento; o valor anterior fica no histórico."""
        atual = self.equipamento(equip_id)["config"]
        desconhecidas = set(mudancas) - set(CONFIG_PADRAO)
        if desconhecidas:
            raise ErroArmazem(f"Configuração desconhecida: {', '.join(sorted(desconhecidas))}.")
        if "politica_custo" in mudancas and mudancas["politica_custo"] not in POLITICAS_CUSTO:
            raise ErroArmazem("Política de custo desconhecida.")
        novo = self._validar_config({**atual, **mudancas})
        with self._transacao() as cur:
            self._nova_revisao(cur)
            cur.execute("UPDATE equipamento SET config=? WHERE id=?", (jdump(novo), equip_id))
            self._evento(
                cur,
                equip_id,
                "equipamento",
                equip_id,
                "configurado",
                autor,
                {"antes": {k: atual.get(k) for k in mudancas}, "depois": mudancas},
            )
        return self.equipamento(equip_id)

    @staticmethod
    def _validar_config(cfg):
        if set(cfg) != set(CONFIG_PADRAO) or cfg["politica_custo"] not in POLITICAS_CUSTO:
            raise ErroArmazem("Configuração desconhecida.")
        if cfg["altitude_m"] is not None and not _finito(cfg["altitude_m"]):
            raise ErroArmazem("Altitude deve ser finita ou ausente.")
        for campo in ("dias_para_desatualizado", "periodos_minimos_pos_intervencao"):
            if type(cfg[campo]) is not int or cfg[campo] < 1:
                raise ErroArmazem(f"{campo} deve ser um inteiro positivo.")
        return cfg

    # ------------------------------------------------ perfis de importação
    def salvar_perfil(self, equip_id: str, fonte: str, mapeamento: dict[str, str]) -> None:
        """Mapeamento de colunas (fonte → contrato) salvo por fonte e equipamento."""
        self.equipamento(equip_id)
        colunas = {c.nome for t in TABELAS.values() for c in t.colunas}
        invalidas = sorted(set(mapeamento.values()) - colunas)
        if invalidas:
            raise ErroArmazem(f"Colunas de destino fora do contrato: {', '.join(invalidas)}.")
        agora = agora_iso()
        with self._transacao() as cur:
            cur.execute(
                "INSERT INTO perfil (equipamento_id, fonte, mapeamento, criado_em, atualizado_em)"
                " VALUES (?,?,?,?,?) ON CONFLICT (equipamento_id, fonte) DO UPDATE SET "
                "mapeamento=excluded.mapeamento, atualizado_em=excluded.atualizado_em",
                (equip_id, fonte, jdump(mapeamento), agora, agora),
            )
            self._evento(cur, equip_id, "perfil", fonte, "salvo", None, mapeamento)

    # ------------------------------------------------ atendimento (T16)
    def registrar_atendimento(
        self,
        equip_id: str,
        dia: str,
        tarefa: str,
        minutos: float,
        autor: str,
        nota: str | None = None,
    ) -> None:
        """Tempo da equipe com este equipamento, lançado por quem atendeu (T16).

        Fica no log de eventos (só acrescenta; nada é editado) e não muda a revisão dos
        dados. `dia` em ISO (AAAA-MM-DD), sem data futura; `minutos` entre 1 e 1440.
        """
        self.equipamento(equip_id)
        if tarefa not in TAREFAS_ATENDIMENTO:
            raise ErroArmazem("Tarefa de atendimento desconhecida.")
        if not (autor or "").strip():
            raise ErroArmazem("Informe quem fez o atendimento.")
        if isinstance(minutos, bool) or not _finito(minutos) or not 1 <= minutos <= 1440:
            raise ErroArmazem("Informe os minutos do atendimento (de 1 a 1440).")
        try:
            data_atendimento = date.fromisoformat(str(dia)[:10])
        except ValueError as exc:
            raise ErroArmazem("Data do atendimento inválida.") from exc
        if data_atendimento > datetime.now(UTC).date():
            raise ErroArmazem("A data do atendimento não pode estar no futuro.")
        dados = {"dia": data_atendimento.isoformat(), "tarefa": tarefa, "minutos": float(minutos)}
        if (nota or "").strip():
            dados["nota"] = nota.strip()[:500]
        with self._transacao() as cur:
            self._evento(cur, equip_id, "atendimento", dados["dia"], "registrado", autor, dados)

    def perfil(self, equip_id: str, fonte: str) -> dict[str, str] | None:
        r = self.con.execute(
            "SELECT mapeamento FROM perfil WHERE equipamento_id=? AND fonte=?", (equip_id, fonte)
        ).fetchone()
        return None if r is None else json.loads(r["mapeamento"])

    def perfis(self, equip_id: str) -> list[dict]:
        return [
            {**dict(r), "mapeamento": json.loads(r["mapeamento"])}
            for r in self.con.execute(
                "SELECT * FROM perfil WHERE equipamento_id=? ORDER BY fonte", (equip_id,)
            )
        ]

    # ------------------------------------------------ registros
    def _ativos(self, equip_id: str, tabela: str, revisao: int | None = None) -> dict[str, dict]:
        """{chave: linha do registro} ativo na revisão (None = atual)."""
        if revisao is None:
            rows = self.con.execute(
                "SELECT * FROM registro WHERE equipamento_id=? AND tabela=? AND revisao_ate IS NULL",
                (equip_id, tabela),
            )
        else:
            rows = self.con.execute(
                "SELECT * FROM registro WHERE equipamento_id=? AND tabela=? AND revisao_de<=? "
                "AND (revisao_ate IS NULL OR revisao_ate>?)",
                (equip_id, tabela, revisao, revisao),
            )
        return {r["chave"]: dict(r) for r in rows if r["conteudo"] is not None}

    def registros(self, equip_id: str, tabela: str, revisao: int | None = None) -> list[dict]:
        return [json.loads(r["conteudo"]) for r in self._ativos(equip_id, tabela, revisao).values()]

    def historico(self, equip_id: str, tabela: str, chave: str) -> list[dict]:
        """Todas as versões de um registro, da original à atual."""
        return [
            {
                **dict(r),
                "conteudo": None if r["conteudo"] is None else json.loads(r["conteudo"]),
                "original": None if r["original"] is None else json.loads(r["original"]),
            }
            for r in self.con.execute(
                "SELECT * FROM registro WHERE equipamento_id=? AND tabela=? AND chave=? "
                "ORDER BY versao",
                (equip_id, tabela, chave),
            )
        ]

    def _nova_versao(
        self, cur, equip_id, tabela, chave, conteudo, original, lote_id, rev, motivo, autor
    ):
        atual = cur.execute(
            "SELECT id, versao, conteudo FROM registro WHERE equipamento_id=? AND tabela=? AND "
            "chave=? AND revisao_ate IS NULL",
            (equip_id, tabela, chave),
        ).fetchone()
        versao = 1
        if atual is not None:
            cur.execute("UPDATE registro SET revisao_ate=? WHERE id=?", (rev, atual["id"]))
            versao = atual["versao"] + 1
        cur.execute(
            "INSERT INTO registro (equipamento_id, tabela, chave, versao, conteudo, original, "
            "lote_id, revisao_de, motivo, autor) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                equip_id,
                tabela,
                chave,
                versao,
                None if conteudo is None else jdump(conteudo),
                None if original is None else jdump(original),
                lote_id,
                rev,
                motivo,
                autor,
            ),
        )
        if atual is not None:
            antes = json.loads(atual["conteudo"]) if atual["conteudo"] else {}
            depois = conteudo or {}
            self._evento(
                cur,
                equip_id,
                "registro",
                f"{tabela}:{chave}",
                "correcao" if conteudo else "anulacao",
                autor,
                {
                    "motivo": motivo,
                    "versao": versao,
                    "campos": {
                        k: {"original": antes.get(k), "novo": depois.get(k)}
                        for k in sorted(set(antes) | set(depois))
                        if antes.get(k) != depois.get(k)
                    },
                },
            )

    def corrigir(
        self, equip_id: str, tabela: str, chave: str, mudancas: dict, motivo: str, autor: str
    ) -> int:
        """Corrige campos de um registro: nova versão; a anterior fica no histórico."""
        if not (motivo or "").strip() or not (autor or "").strip():
            raise ErroArmazem("Correção exige motivo e autor.")
        atuais = self._ativos(equip_id, tabela)
        if chave not in atuais:
            raise ErroArmazem("Registro não encontrado.")
        conteudo = {**json.loads(atuais[chave]["conteudo"]), **mudancas}
        if chave_natural(tabela, conteudo) != chave:
            raise ErroArmazem("A correção mudaria a identidade do registro; registre um novo.")
        motivo_rejeicao = self._motivo_rejeicao(
            tabela, conteudo, self.equipamento(equip_id), self.info["classe"]
        )
        if motivo_rejeicao:
            raise ErroArmazem(motivo_rejeicao)
        with self._transacao() as cur:
            rev = self._nova_revisao(cur)
            self._nova_versao(
                cur, equip_id, tabela, chave, conteudo, None, None, rev, motivo, autor
            )
        return rev

    def anular(self, equip_id: str, tabela: str, chave: str, motivo: str, autor: str) -> int:
        """Retira um registro das análises (versão anulada); o conteúdo antigo é preservado."""
        if not (motivo or "").strip() or not (autor or "").strip():
            raise ErroArmazem("Anulação exige motivo e autor.")
        if chave not in self._ativos(equip_id, tabela):
            raise ErroArmazem("Registro não encontrado.")
        with self._transacao() as cur:
            rev = self._nova_revisao(cur)
            self._nova_versao(cur, equip_id, tabela, chave, None, None, None, rev, motivo, autor)
        return rev

    # ------------------------------------------------ importação incremental
    def previa(
        self,
        equip_id: str,
        arquivos: dict[str, bytes],
        fonte: str | None = None,
        mapeamento: dict[str, str] | None = None,
    ) -> Previa:
        """Lê e classifica tudo antes de gravar: novas, iguais, conflitos, rejeitadas.

        Usa o perfil salvo da fonte quando não se passa um mapeamento. Nada é gravado.
        """
        equip = self.equipamento(equip_id)
        classe = self.info["classe"]
        if classe not in CLASSES:
            raise ErroArmazem("Classifique a origem da planta antes de importar registros.")
        mapa = (
            mapeamento
            if mapeamento is not None
            else (self.perfil(equip_id, fonte) if fonte else None) or {}
        )
        convertidos = {
            nome: aplicar_mapeamento(conteudo, mapa)
            if mapa and nome.lower().endswith(".csv")
            else conteudo
            for nome, conteudo in arquivos.items()
        }
        fontes, avisos = fontes_de_arquivos(convertidos)
        from euler.vapor import p_atm_por_altitude_bar

        altitude = equip["config"].get("altitude_m")
        pacote = importar_pacote(
            fontes, p_atm_bar=None if altitude is None else p_atm_por_altitude_bar(altitude)
        )  # colunas derivadas continuam excluídas de canonico; altitude é rastreada na prévia
        linhas: list[LinhaPrevia] = []
        bloqueadas: dict[str, list[str]] = {}
        for tabela, imp in pacote.importacoes.items():
            avisos += imp.avisos
            if imp.bloqueada:
                bloqueadas[tabela] = [a.mensagem for a in imp.avisos if a.gravidade == "erro"]
                continue
            ativos = self._ativos(equip_id, tabela)
            tempo = COLUNA_TEMPO[tabela]
            existentes = [json.loads(r["conteudo"]).get(tempo) for r in ativos.values()]
            existentes = [x for x in existentes if x]
            ini_exist, fim_exist = (
                (min(existentes), max(existentes)) if existentes else (None, None)
            )
            vistos: dict[str, LinhaPrevia] = {}
            original = imp.original.set_index("linha")
            for _, row in imp.dados.iterrows():
                c = canonico(tabela, row)
                orig = (
                    {
                        k: str(v)
                        for k, v in original.loc[int(row["linha"])].items()
                        if v not in ("", None)
                    }
                    if int(row["linha"]) in original.index
                    else {}
                )
                lp = LinhaPrevia(
                    tabela, int(row["linha"]), chave_natural(tabela, c), c, orig, "nova"
                )
                motivo = self._motivo_rejeicao(tabela, c, equip, classe)
                if lp.chave is None:
                    lp.situacao, lp.motivo = (
                        "rejeitada",
                        "Sem os campos que identificam o registro.",
                    )
                elif motivo:
                    lp.situacao, lp.motivo = "rejeitada", motivo
                elif lp.chave in vistos:
                    anterior = vistos[lp.chave]
                    if anterior.conteudo == c:
                        lp.situacao = "repetida_no_arquivo"
                    else:
                        for x in (anterior, lp):
                            x.situacao = "rejeitada"
                            x.motivo = (
                                "A mesma identificação aparece mais de uma vez no arquivo com "
                                "valores diferentes; nenhuma foi escolhida."
                            )
                elif lp.chave in ativos:
                    atual = json.loads(ativos[lp.chave]["conteudo"])
                    if atual == c:
                        lp.situacao = "igual"
                    else:
                        lp.situacao = "conflito"
                        lp.diferencas = {
                            k: {"atual": atual.get(k), "novo": c.get(k)}
                            for k in sorted(set(atual) | set(c))
                            if atual.get(k) != c.get(k)
                        }
                if (
                    lp.situacao == "nova"
                    and ini_exist
                    and c.get(tempo)
                    and ini_exist <= c[tempo] <= fim_exist
                ):
                    lp.tardia = True
                if lp.chave is not None and lp.situacao != "rejeitada":
                    vistos.setdefault(lp.chave, lp)
                linhas.append(lp)
            avisos += self._unidades(equip_id, tabela, imp.dados, ativos)
        # uma origem declarada diferente da classe contamina o lote inteiro: tabelas sem
        # coluna de origem (ex.: instrumentos) vieram do mesmo conjunto e também são recusadas
        esperado = ORIGEM_DA_CLASSE[classe]
        estranhas = sorted({x.conteudo.get("origem_dado") for x in linhas} - {None, esperado})
        if estranhas:
            for x in linhas:
                if x.situacao != "rejeitada":
                    x.situacao = "rejeitada"
                    x.motivo = (
                        f"O lote contém linhas de origem {', '.join(estranhas)}, diferente da "
                        f"classe desta planta ({CLASSES[classe]}): o lote inteiro foi recusado; "
                        "dados sintéticos, públicos e de cliente nunca se misturam."
                    )
        return Previa(
            equip_id,
            {n: hashlib.sha256(b).hexdigest() for n, b in arquivos.items()},
            fonte,
            mapa,
            linhas,
            avisos,
            bloqueadas,
            self.info["planta_id"],
            self.revisao,
            dict(arquivos),
            sha(equip),
        )

    @staticmethod
    def _motivo_rejeicao(tabela: str, c: dict, equip: dict, classe: str) -> str | None:
        if tabela == "diario" and c.get("caldeira_id") != equip["caldeira_id"]:
            return (
                f"Linha da caldeira '{c.get('caldeira_id')}', não do equipamento "
                f"'{equip['caldeira_id']}': dados de equipamentos diferentes não se misturam."
            )
        origem = c.get("origem_dado")
        esperado = ORIGEM_DA_CLASSE[classe]
        if origem and origem != esperado:
            return (
                f"Origem '{origem}' diferente da classe desta planta ({CLASSES[classe]}): "
                "dados sintéticos, públicos e de cliente nunca se misturam."
            )
        return None

    def _unidades(self, equip_id, tabela, dados: pd.DataFrame, ativos: dict) -> list[Aviso]:
        """Alerta (não bloqueia) quando a mediana de uma coluna numérica muda mais de 3×
        entre o que já está gravado e o arquivo novo: possível unidade diferente."""
        if len(ativos) < 5 or len(dados) < 5:
            return []
        gravados = pd.DataFrame([json.loads(r["conteudo"]) for r in ativos.values()])
        avisos = []
        for col in TABELAS[tabela].colunas:
            if col.tipo != "numero" or col.nome not in gravados or col.nome not in dados:
                continue
            a = pd.to_numeric(gravados[col.nome], errors="coerce").dropna()
            b = pd.to_numeric(dados[col.nome], errors="coerce").dropna()
            if len(a) < 5 or len(b) < 5:
                continue
            ma, mb = float(a.median()), float(b.median())
            if ma > 0 and mb > 0 and not 1 / 3 <= mb / ma <= 3:
                avisos.append(
                    Aviso(
                        tabela,
                        None,
                        col.nome,
                        "unidade_incompativel",
                        f"{col.rotulo}: mediana {mb:g} no arquivo novo contra {ma:g} nos dados "
                        "já gravados. Confira a unidade antes de confirmar.",
                    )
                )
        return avisos

    def confirmar(
        self,
        previa: Previa,
        autor: str,
        modo: str = "incremental",
        motivo: str | None = None,
        salvar_perfil: bool = False,
        importacao_id: str | None = None,
        atendimento: dict | None = None,
    ) -> dict:
        """Grava a prévia. Incremental: novas entram, iguais são ignoradas, conflitos ficam
        pendentes. Correção: conflitos viram nova versão, com motivo e autor obrigatórios.

        `atendimento` (T16, opcional): o que a tela mediu neste envio, guardado no lote e no
        evento: {"segundos_na_tela": s, "ajustes": {...} ou None}. Sem medição, nada é gravado
        (ausente não vira zero)."""
        if modo not in ("incremental", "correcao"):
            raise ErroArmazem("Modo de importação desconhecido.")
        atendimento = _validar_atendimento(atendimento)
        if not (autor or "").strip():
            raise ErroArmazem("Informe quem está importando.")
        if modo == "correcao" and not (motivo or "").strip():
            raise ErroArmazem("Importação de correção exige motivo.")
        from euler.persistencia import Repositorio

        resumo = {"contagem": previa.contagem(), "tabelas_bloqueadas": previa.tabelas_bloqueadas}
        if atendimento:
            resumo["atendimento"] = atendimento
        e = previa.equipamento_id
        with self._transacao() as cur:
            if previa.planta_id != self.info["planta_id"]:
                raise ErroArmazem("A prévia pertence a outra planta.")
            equip = self.equipamento(e)
            if previa.revisao != self.revisao or previa.config_sha != sha(equip):
                raise ErroArmazem("Os dados mudaram. Prepare uma nova prévia antes de confirmar.")
            if previa.arquivos != {
                n: hashlib.sha256(b).hexdigest() for n, b in previa.originais.items()
            }:
                raise ErroArmazem("Os arquivos da prévia foram alterados.")
            # Uma classe incompatível não pode nem arquivar um lote na planta errada.
            origem = ORIGEM_DA_CLASSE[self.info["classe"]]
            Repositorio._validar_origens(
                previa.originais, self.info["classe"], self.info["classe"] == "sintetico"
            )
            if any(x.conteudo.get("origem_dado") not in (None, origem) for x in previa.linhas):
                raise ErroArmazem("A origem do lote é diferente da classe da planta.")
            importacao_id = Repositorio.preservar_lote(
                self.con,
                previa.originais,
                altitude=equip["config"].get("altitude_m"),
                sinteticos=self.info["classe"] == "sintetico",
                autor=autor,
                motivo=motivo,
                importacao_id=importacao_id,
            )
            rev = self._nova_revisao(cur)
            cur.execute(
                "INSERT INTO lote (revisao, equipamento_id, recebido_em, autor, fonte, modo, motivo, "
                "arquivos, resumo) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    rev,
                    e,
                    agora_iso(),
                    autor,
                    previa.fonte,
                    modo,
                    motivo,
                    jdump(previa.arquivos),
                    jdump(resumo),
                ),
            )
            lote_id = cur.lastrowid
            cur.execute("INSERT INTO vinculo_lote VALUES (?,?)", (lote_id, importacao_id))
            if salvar_perfil and previa.fonte and previa.mapeamento:
                cur.execute(
                    "INSERT INTO perfil (equipamento_id,fonte,mapeamento,criado_em,atualizado_em) "
                    "VALUES (?,?,?,?,?) ON CONFLICT(equipamento_id,fonte) DO UPDATE SET "
                    "mapeamento=excluded.mapeamento, atualizado_em=excluded.atualizado_em",
                    (e, previa.fonte, jdump(previa.mapeamento), agora_iso(), agora_iso()),
                )
            pendentes = corrigidas = novas = 0
            for x in previa.linhas:
                if x.situacao == "nova":
                    self._nova_versao(
                        cur, e, x.tabela, x.chave, x.conteudo, x.original, lote_id, rev, None, autor
                    )
                    novas += 1
                elif x.situacao == "conflito" and modo == "correcao":
                    self._nova_versao(
                        cur,
                        e,
                        x.tabela,
                        x.chave,
                        x.conteudo,
                        x.original,
                        lote_id,
                        rev,
                        motivo,
                        autor,
                    )
                    corrigidas += 1
                elif x.situacao == "conflito":
                    cur.execute(
                        "INSERT INTO conflito (equipamento_id, tabela, chave, proposto, original, "
                        "lote_id, situacao) VALUES (?,?,?,?,?,?, 'pendente')",
                        (e, x.tabela, x.chave, jdump(x.conteudo), jdump(x.original), lote_id),
                    )
                    pendentes += 1
            if previa.fonte:
                cur.execute(
                    "UPDATE perfil SET usos = usos + 1 WHERE equipamento_id=? AND fonte=?",
                    (e, previa.fonte),
                )
            resumo.update(novas=novas, corrigidas=corrigidas, conflitos_pendentes=pendentes)
            cur.execute("UPDATE lote SET resumo=? WHERE id=?", (jdump(resumo), lote_id))
            self._evento(cur, e, "lote", lote_id, "importado", autor, resumo)
        return {"lote_id": lote_id, "importacao_id": importacao_id, "revisao": rev, **resumo}

    def conflitos(self, equip_id: str, situacao: str = "pendente") -> list[dict]:
        out = []
        for r in self.con.execute(
            "SELECT * FROM conflito WHERE equipamento_id=? AND situacao=? ORDER BY id",
            (equip_id, situacao),
        ):
            atual = self._ativos(equip_id, r["tabela"]).get(r["chave"])
            out.append(
                {
                    **dict(r),
                    "proposto": json.loads(r["proposto"]),
                    "atual": None if atual is None else json.loads(atual["conteudo"]),
                }
            )
        return out

    def resolver_conflito(self, conflito_id: int, aceitar: bool, autor: str, motivo: str) -> None:
        """Aceitar = o valor proposto vira nova versão (original preservado); recusar = fica
        o valor atual. As duas decisões ficam registradas com autor e motivo."""
        if not (motivo or "").strip() or not (autor or "").strip():
            raise ErroArmazem("Decidir um conflito exige motivo e autor.")
        r = self.con.execute("SELECT * FROM conflito WHERE id=?", (conflito_id,)).fetchone()
        if r is None or r["situacao"] != "pendente":
            raise ErroArmazem("Conflito inexistente ou já decidido.")
        with self._transacao() as cur:
            rev = self._nova_revisao(cur)
            if aceitar:
                self._nova_versao(
                    cur,
                    r["equipamento_id"],
                    r["tabela"],
                    r["chave"],
                    json.loads(r["proposto"]),
                    json.loads(r["original"] or "{}"),
                    r["lote_id"],
                    rev,
                    motivo,
                    autor,
                )
            cur.execute(
                "UPDATE conflito SET situacao=?, decidido_em=?, decidido_por=?, motivo=? WHERE id=?",
                ("aceito" if aceitar else "recusado", agora_iso(), autor, motivo, conflito_id),
            )
            self._evento(
                cur,
                r["equipamento_id"],
                "conflito",
                conflito_id,
                "aceito" if aceitar else "recusado",
                autor,
                {"motivo": motivo},
            )

    def importacoes(self, equip_id: str) -> list[dict]:
        return [
            {**dict(r), "resumo": json.loads(r["resumo"]), "arquivos": json.loads(r["arquivos"])}
            for r in self.con.execute(
                "SELECT * FROM lote WHERE equipamento_id=? ORDER BY id DESC", (equip_id,)
            )
        ]

    # ------------------------------------------------ dados para as análises
    def arquivos(self, equip_id: str, revisao: int | None = None) -> dict[str, bytes]:
        """CSVs canônicos dos registros ativos na revisão: entrada do motor existente."""
        saida = {}
        for tabela, t in TABELAS.items():
            regs = self.registros(equip_id, tabela, revisao)
            if not regs:
                continue
            colunas = [c.nome for c in t.colunas if c.nome not in DERIVADAS.get(tabela, set())]
            tempo = COLUNA_TEMPO[tabela]
            regs.sort(key=lambda c: (c.get(tempo) or "", chave_natural(tabela, c) or ""))
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(colunas)
            for c in regs:
                w.writerow([_texto(c.get(col)) for col in colunas])
            saida[t.arquivo] = buf.getvalue().encode("utf-8")
        return saida

    def pacote(
        self, equip_id: str, revisao: int | None = None, p_atm_bar: float | None = None
    ) -> Pacote:
        fontes, _ = fontes_de_arquivos(self.arquivos(equip_id, revisao))
        return importar_pacote(fontes, p_atm_bar=p_atm_bar)

    def conjunto_sha(self, equip_id: str, revisao: int | None = None) -> str:
        """Impressão digital dos registros ativos (o que entrou numa análise)."""
        return sha(
            {
                tabela: sorted(jdump(c) for c in self.registros(equip_id, tabela, revisao))
                for tabela in TABELAS
            }
        )

    def cobertura(self, equip_id: str, agora: datetime | None = None) -> dict:
        """Última atualização, período coberto e se o acompanhamento está desatualizado."""
        cfg = self.equipamento(equip_id)["config"]
        agora = agora or datetime.now(UTC)
        tabelas = {}
        for tabela in TABELAS:
            tempos = sorted(
                c[COLUNA_TEMPO[tabela]]
                for c in self.registros(equip_id, tabela)
                if c.get(COLUNA_TEMPO[tabela])
            )
            n = len(self._ativos(equip_id, tabela))
            if n:
                tabelas[tabela] = {
                    "registros": n,
                    "inicio": tempos[0] if tempos else None,
                    "fim": tempos[-1] if tempos else None,
                }
        lotes = self.importacoes(equip_id)
        ultimo = (tabelas.get("diario") or {}).get("fim")
        limite = cfg["dias_para_desatualizado"]
        if ultimo is None:
            estado, frase = "sem_dados", "Sem dados do diário: não há acompanhamento."
            dias = None
        else:
            ts = pd.Timestamp(ultimo)
            dias = (pd.Timestamp(agora) - (ts if ts.tzinfo else ts.tz_localize("UTC"))).days
            if dias > limite:
                estado = "desatualizado"
                frase = (
                    f"Acompanhamento desatualizado: a última leitura do diário tem {dias} dias "
                    f"(limite configurado: {limite}). As análises descrevem o passado, não o "
                    "momento atual."
                )
            else:
                estado = "atualizado"
                frase = f"Dados atualizados: última leitura do diário há {dias} dias."
        return {
            "estado": estado,
            "frase": frase,
            "dias_desde_ultima_leitura": dias,
            "limite_dias": limite,
            "tabelas": tabelas,
            "ultima_importacao": lotes[0]["recebido_em"] if lotes else None,
            "importacoes": len(lotes),
            "conflitos_pendentes": len(self.conflitos(equip_id)),
        }

    # ------------------------------------------------ cópia de segurança
    def copia_seguranca(self, pasta: Path) -> Path:
        """Cópia consistente do arquivo da planta (API de backup do SQLite)."""
        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        carimbo = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        destino = pasta / f"{self.info['planta_id']}-{carimbo}.euler.sqlite"
        dst = sqlite3.connect(str(destino))
        with dst:
            self.con.backup(dst)
        dst.close()
        return destino

    def exportar(self) -> dict:
        """Exportação completa e legível (JSON) para auditoria ou migração."""
        import base64

        tabelas = [
            r["name"]
            for r in self.con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        return {
            "formato": "euler-planta/1",
            "planta": self.info,
            "tabelas": {
                t: [
                    {
                        k: {"base64": base64.b64encode(v).decode("ascii")}
                        if isinstance(v, bytes)
                        else v
                        for k, v in dict(r).items()
                    }
                    for r in self.con.execute(f'SELECT * FROM "{t}" ORDER BY rowid')
                ]
                for t in tabelas
            },
        }


# ---------------------------------------------------------------- política de custo

POLITICAS_CUSTO = {
    "recebimentos_do_periodo": (
        "Média ponderada pela massa dos lotes recebidos no próprio período (notas)."
    ),
    "fifo": ("Custo do combustível que saiu do pátio na ordem de chegada (FIFO), lote a lote."),
    "tabela_de_precos": (
        "Preço vigente na tabela de preços cadastrada (com custos adicionais declarados)."
    ),
}


def _validar_atendimento(atendimento: dict | None) -> dict | None:
    """Medição do atendimento (T16): só campos conhecidos, números finitos e não negativos."""
    if not atendimento:
        return None
    if set(atendimento) - {"segundos_na_tela", "ajustes"}:
        raise ErroArmazem("Registro de atendimento com campo desconhecido.")
    out = {}
    s = atendimento.get("segundos_na_tela")
    if s is not None:
        if isinstance(s, bool) or not _finito(s) or float(s) < 0:
            raise ErroArmazem("Tempo de atendimento inválido.")
        out["segundos_na_tela"] = round(float(s), 1)
    ajustes = atendimento.get("ajustes")
    if ajustes is not None:
        if not isinstance(ajustes, dict) or any(
            not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in ajustes.values()
        ):
            raise ErroArmazem("Contagem de ajustes inválida.")
        out["ajustes"] = {str(k): int(v) for k, v in ajustes.items()}
    return out or None


def _finito(x) -> bool:
    return isinstance(x, int | float) and isfinite(x)
