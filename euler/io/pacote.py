"""Importação do conjunto de tabelas de uma caldeira e verificações entre tabelas (T03, T05)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from euler import qualidade
from euler.io.combustivel import importar_combustivel
from euler.io.diario import importar_diario
from euler.io.esquemas import TABELAS, rotulo_coluna
from euler.io.leitura import (
    ALIASES_COLUNAS,
    FUSO_PADRAO,
    Aviso,
    Fonte,
    Importacao,
    importar_tabela,
    ler_csv,
    ler_planilha,
)

ORDEM_GRAVIDADE = {"erro": 0, "atencao": 1, "info": 2}
ROTULO_GRAVIDADE = {"erro": "Erro", "atencao": "Atenção", "info": "Informação"}


@dataclass
class Pacote:
    """Todas as tabelas importadas de uma caldeira, com os avisos."""

    importacoes: dict[str, Importacao] = field(default_factory=dict)
    avisos_gerais: list[Aviso] = field(default_factory=list)
    p_atm_bar: float | None = None

    def dados(self, nome: str) -> pd.DataFrame | None:
        """Tabela normalizada, ou None se não foi enviada ou está bloqueada."""
        imp = self.importacoes.get(nome)
        if imp is None or imp.bloqueada:
            return None
        return imp.dados

    def origens_de_dado(self) -> set[str]:
        """Valores da coluna `origem_dado` em todas as tabelas (ex.: {"sintetico"})."""
        origens: set[str] = set()
        for imp in self.importacoes.values():
            if "origem_dado" in imp.dados:
                origens |= set(imp.dados["origem_dado"].dropna().astype(str))
        return origens

    @property
    def sintetico(self) -> bool:
        """True só quando todas as linhas com origem declarada dizem `sintetico`."""
        return self.origens_de_dado() == {"sintetico"}

    @property
    def avisos(self) -> list[Aviso]:
        todos = [a for imp in self.importacoes.values() for a in imp.avisos]
        return todos + self.avisos_gerais

    def tabela_avisos(self) -> pd.DataFrame:
        """Avisos em formato de tabela legível, dos mais graves para os menos graves."""
        linhas = [
            {
                "Gravidade": ROTULO_GRAVIDADE[a.gravidade],
                "Tabela": _titulo(a.tabela),
                "Linha": a.linha,
                "Coluna": rotulo_coluna(a.coluna) if a.coluna else "",
                "Aviso": a.mensagem,
                "Tipo": a.tipo,
                "_ordem": ORDEM_GRAVIDADE[a.gravidade],
            }
            for a in self.avisos
        ]
        df = pd.DataFrame(
            linhas, columns=["Gravidade", "Tabela", "Linha", "Coluna", "Aviso", "Tipo", "_ordem"]
        )
        df["Linha"] = df["Linha"].astype("Int64")
        return (
            df.sort_values(["_ordem", "Tabela", "Linha"], na_position="first")
            .drop(columns="_ordem")
            .reset_index(drop=True)
        )


def _importar_uma(nome: str, fonte: Fonte, p_atm_bar: float | None, fuso: str) -> Importacao:
    if nome == "diario":
        return importar_diario(fonte, p_atm_bar=p_atm_bar, fuso=fuso)
    if nome == "combustivel":
        return importar_combustivel(fonte, fuso=fuso)
    imp = importar_tabela(nome, fonte, fuso)
    if nome == "amostras" and not imp.bloqueada:
        imp.avisos += qualidade.verificar_amostras(imp.dados)
    return imp


def _relacoes(p: Pacote) -> list[Aviso]:
    """Verificações entre tabelas: lotes das amostras e instrumentos citados no diário."""
    avisos = []
    comb, amos, diar, inst = (
        p.dados(n) for n in ("combustivel", "amostras", "diario", "instrumentos")
    )
    if comb is not None and amos is not None:
        lotes = set(comb["lote_id"].dropna())
        for _, a in amos[~amos["lote_id"].isin(lotes) & amos["lote_id"].notna()].iterrows():
            avisos.append(
                Aviso(
                    "amostras",
                    int(a["linha"]),
                    "lote_id",
                    "lote_desconhecido",
                    f"Amostra do lote '{a['lote_id']}', que não aparece nos recebimentos de combustível.",
                )
            )
        com_umidade = set(amos.loc[amos["umidade_bu_frac"].notna(), "lote_id"].dropna())
        receb = comb[(comb["tipo"] == "recebimento") & comb["lote_id"].notna()]
        for _, r in receb[~receb["lote_id"].isin(com_umidade)].iterrows():
            avisos.append(
                Aviso(
                    "combustivel",
                    int(r["linha"]),
                    "lote_id",
                    "lote_sem_umidade",
                    f"Lote '{r['lote_id']}' sem umidade medida: energia entregue não determinada.",
                    "info",
                )
            )
    if diar is not None and inst is not None:
        conhecidos = set(inst["instrumento_id"].dropna())
        citados = set(diar["instrumento_o2_id"].dropna())
        for ident in sorted(citados - conhecidos):
            avisos.append(
                Aviso(
                    "diario",
                    None,
                    "instrumento_o2_id",
                    "instrumento_sem_cadastro",
                    f"Instrumento '{ident}' citado no diário não está no cadastro de "
                    "instrumentos: incerteza desconhecida.",
                    "info",
                )
            )
    return avisos


def importar_pacote(
    fontes: Mapping[str, Fonte], p_atm_bar: float | None = None, fuso: str = FUSO_PADRAO
) -> Pacote:
    """Importa as tabelas recebidas ({nome_da_tabela: fonte}) e cruza as relações."""
    p = Pacote(p_atm_bar=p_atm_bar)
    for nome in TABELAS:
        if nome in fontes:
            p.importacoes[nome] = _importar_uma(nome, fontes[nome], p_atm_bar, fuso)
    p.avisos_gerais = _relacoes(p)
    return p


def _inferir_tabela_csv(conteudo: bytes) -> str | None:
    """Reconhece uma tabela por cabeçalho sem depender do nome do arquivo.

    Só aceita quando as chaves mínimas da tabela aparecem explicitamente (ou por alias
    unitário). Em caso ambíguo, não escolhe.
    """
    bruto, _, _ = ler_csv(conteudo, "—")
    cols = {
        ALIASES_COLUNAS.get(str(c).strip(), str(c).strip())
        for c in bruto.columns
        if c != "linha"
    }
    candidatos = []
    for nome, tabela in TABELAS.items():
        obrig = {c.nome for c in tabela.colunas if c.obrigatoria}
        if obrig and obrig <= cols:
            score = len(cols & {c.nome for c in tabela.colunas})
            candidatos.append((score, nome))
    if not candidatos:
        return None
    candidatos.sort(reverse=True)
    if len(candidatos) > 1 and candidatos[0][0] == candidatos[1][0]:
        return None
    return candidatos[0][1]


def fontes_de_arquivos(arquivos: Mapping[str, bytes]) -> tuple[dict[str, Fonte], list[Aviso]]:
    """Identifica as tabelas pelos nomes dos arquivos enviados.

    `diario.csv` → diario; `.xlsx` → cada aba com nome de tabela. Arquivos com
    nome desconhecido geram aviso e são ignorados.
    """
    fontes: dict[str, Fonte] = {}
    avisos = []
    for nome_arquivo, conteudo in arquivos.items():
        caminho = Path(nome_arquivo)
        base = caminho.stem.strip().lower()
        if caminho.suffix.lower() == ".xlsx":
            for nome, aba in ler_planilha(conteudo).items():
                fontes[nome] = aba
        elif caminho.suffix.lower() == ".csv" and base in TABELAS:
            fontes[base] = conteudo
        elif caminho.suffix.lower() == ".csv":
            inferida = _inferir_tabela_csv(conteudo)
            if inferida is not None and inferida not in fontes:
                fontes[inferida] = conteudo
                avisos.append(
                    Aviso(
                        inferida,
                        None,
                        None,
                        "arquivo_inferido",
                        f"Arquivo '{nome_arquivo}' reconhecido pelo cabeçalho como "
                        f"{TABELAS[inferida].rotulo}.",
                        "info",
                    )
                )
            else:
                avisos.append(
                    Aviso(
                        "—",
                        None,
                        None,
                        "arquivo_desconhecido",
                        f"Arquivo '{nome_arquivo}' não pôde ser associado com segurança a "
                        "nenhum registro conhecido.",
                        "info",
                    )
                )
        else:
            avisos.append(
                Aviso(
                    "—",
                    None,
                    None,
                    "arquivo_desconhecido",
                    f"Arquivo '{nome_arquivo}' não foi reconhecido.",
                    "info",
                )
            )
    return fontes, avisos


def importar_pasta(
    pasta: str | Path, p_atm_bar: float | None = None, fuso: str = FUSO_PADRAO
) -> Pacote:
    """Importa os CSVs de uma pasta com os nomes do contrato (diario.csv, combustivel.csv…)."""
    pasta = Path(pasta)
    fontes = {n: pasta / t.arquivo for n, t in TABELAS.items() if (pasta / t.arquivo).exists()}
    return importar_pacote(fontes, p_atm_bar=p_atm_bar, fuso=fuso)


def _titulo(tabela: str | None) -> str:
    """Nome da tabela como o usuário a conhece (linguagem de fábrica, D64)."""
    return TABELAS[tabela].titulo if tabela in TABELAS else (tabela or "—")
