"""Medição de escala: quanto custa levar cada cliente do envio ao primeiro fechamento (D109).

Simula clientes com planilhas SINTÉTICAS em formatos que fábricas costumam mandar, feitas a
partir do caso de demonstração (demo/caso_demo_completo: 8 semanas, marcado como sintético).
Cada cliente percorre o mesmo caminho das telas "Atualizar dados" e "Fechamentos":

1. envio dos arquivos → leitura e sugestões da EULER (o que a tela já traz preenchido);
2. conferência: a "pessoa" do teste corrige o que a sugestão errou ou deixou em branco até
   chegar ao gabarito do cenário (cada campo mudado ou preenchido conta 1 ajuste);
3. lote adaptado, prévia e confirmação no armazém da planta;
4. referência (as 4 primeiras semanas) e primeiro fechamento;
5. envio do mês seguinte (o mesmo arquivo, atualizado) e segundo fechamento.

Mede o tempo de máquina de cada etapa (cronômetro) e conta ajustes e confirmações. O tempo
de uma pessoa NÃO é medido aqui: o relatório mostra uma faixa ASSUMIDA e explícita, até o
registro de atendimento (T16) medir clientes reais.

Uso: python scripts/medir_escala.py [--saida docs/produto/escala_atendimento.md]
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

RAIZ = Path(__file__).resolve().parents[1]
for caminho in (RAIZ, RAIZ / "app"):
    if str(caminho) not in sys.path:
        sys.path.insert(0, str(caminho))

from importacao_guiada import (
    ajustes_do_lote,
    contar_ajustes,
    ler_fontes,
    preparar_lote,
    sugerir_tabela,
    sugestao_da_fonte,
    valores_unicos_da_tela,
)

from euler.atendimento import registro_atendimento
from euler.fechamento import criar_referencia, produzir_fechamento
from euler.io.esquemas import TABELAS
from euler.periodos import periodos_entre_estoques
from euler.persistencia import Repositorio

DEMO = RAIZ / "demo" / "caso_demo_completo"
FUSO = "America/Sao_Paulo"
CALDEIRA = "CALD-DEMO-01"
# fim do primeiro envio: medição de estoque de 14/09 (4 semanas de referência + 2 a fechar)
CORTE = pd.Timestamp("2026-09-14T07:30:00-03:00")
COLUNA_TEMPO = {
    "diario": "instante_observado",
    "combustivel": "data",
    "amostras": "data",
    "eventos": "instante",
}
# confirmações que não dependem da planilha (cliques do caminho)
CONFIRMACOES_PRIMEIRO = (
    "Conferi as colunas, as unidades e a origem",
    "Preparar prévia",
    "Confirmar registros novos",
    "Definir a referência (período e motivo)",
    "Produzir o fechamento",
)
CONFIRMACOES_SEGUINTE = (
    "Conferi as colunas, as unidades e a origem",
    "Preparar prévia",
    "Confirmar registros novos",
    "Produzir o fechamento",
)
# Faixas ASSUMIDAS (não medidas) para o tempo de uma pessoa; ver D109.
ASSUMIDO_S = {
    "ajuste": (10, 30),  # escolher uma coluna, unidade ou valor numa lista
    "fonte": (30, 90),  # ler o cartão "O que a EULER entendeu" de cada aba ou arquivo
    "confirmacao": (3, 10),  # um clique de confirmação
    "referencia": (60, 180),  # escolher o período de referência e escrever o motivo
}


# ------------------------------------------------------------ dados de partida


def carregar_demo() -> dict[str, pd.DataFrame]:
    """Tabelas do caso de demonstração (sintéticas), texto intacto."""
    return {
        p.stem: pd.read_csv(p, dtype=str, keep_default_na=False) for p in sorted(DEMO.glob("*.csv"))
    }


def ate(dfs: dict[str, pd.DataFrame], corte: pd.Timestamp | None) -> dict[str, pd.DataFrame]:
    """Linhas registradas até `corte` (inclusive); tabelas sem instante vão inteiras."""
    if corte is None:
        return dfs
    out = {}
    for nome, df in dfs.items():
        coluna = COLUNA_TEMPO.get(nome)
        if coluna is None:
            out[nome] = df
            continue
        instante = pd.to_datetime(df[coluna], utc=True)
        out[nome] = df[instante <= corte].reset_index(drop=True)
    return out


def _local(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, utc=True).dt.tz_convert(FUSO)


def _data(serie: pd.Series) -> list[str]:
    return _local(serie).dt.strftime("%d/%m/%Y").fillna("").tolist()


def _hora(serie: pd.Series) -> list[str]:
    return _local(serie).dt.strftime("%H:%M").fillna("").tolist()


def _num(serie: pd.Series, f: Callable[[float], float] = lambda x: x) -> list[float | None]:
    """Número da célula; vazio continua vazio (ausente ≠ zero)."""
    return [f(float(v)) if str(v).strip() else None for v in serie]


def _texto(serie: pd.Series) -> list[str | None]:
    return [v if str(v).strip() else None for v in serie]


# ------------------------------------------------------------ formatos de cliente


@dataclass(frozen=True)
class Coluna:
    """Uma coluna da planilha do cliente e o que ela é no modelo da EULER (gabarito)."""

    cabecalho: str
    valores: list
    alvo: str | None = None  # None: coluna que fica de fora (observação, assinatura…)
    unidade: str | None = None


@dataclass
class Aba:
    """Uma aba (ou CSV) do cliente: títulos, cabeçalho e o gabarito de leitura."""

    nome: str
    tabela: str
    colunas: list[Coluna]
    titulos: list[str] = field(default_factory=list)
    grupos: list[str] | None = None  # linha de cima de um cabeçalho em duas linhas
    combinar: tuple[str, str] | None = None  # colunas de data e de hora
    valores_unicos: dict[str, str] = field(default_factory=dict)  # tipo dos registros

    @property
    def linha_cabecalho(self) -> int:
        return len(self.titulos) + 1

    def gabarito(self) -> dict:
        mapa = {c.cabecalho: c.alvo for c in self.colunas if c.alvo}
        if self.grupos:
            nomes = _nomes_duplos(self.grupos, [c.cabecalho for c in self.colunas])
            mapa = {nomes[i]: c.alvo for i, c in enumerate(self.colunas) if c.alvo}
            unidades = {nomes[i]: c.unidade for i, c in enumerate(self.colunas) if c.unidade}
        else:
            unidades = {c.cabecalho: c.unidade for c in self.colunas if c.unidade}
        g = {
            "tabela": self.tabela,
            "mapeamento": mapa,
            "unidades": unidades,
            "linha_cabecalho": self.linha_cabecalho,
            "cabecalho_duplo": bool(self.grupos),
            "valores_unicos": self.valores_unicos,
        }
        if self.combinar:
            alvo = next(c.nome for c in TABELAS[self.tabela].colunas if c.tipo == "instante")
            g["combinar"] = {"alvo": alvo, "data": self.combinar[0], "hora": self.combinar[1]}
        return g


def _nomes_duplos(grupos: list[str], sub: list[str]) -> list[str]:
    from importacao_guiada import juntar_cabecalho_duplo

    return juntar_cabecalho_duplo(
        grupos, ["" if g and s == g else s for g, s in zip(grupos, sub, strict=True)]
    )


def _linhas(aba: Aba) -> list[list]:
    """Linhas da aba como a fábrica as escreve: títulos, cabeçalho e dados."""
    linhas = [[t] for t in aba.titulos]
    if aba.grupos:
        linhas.append(aba.grupos)
        linhas.append(
            [
                ("" if g and c.cabecalho == g else c.cabecalho)
                for g, c in zip(aba.grupos, aba.colunas, strict=True)
            ]
        )
    else:
        linhas.append([c.cabecalho for c in aba.colunas])
    n = len(aba.colunas[0].valores) if aba.colunas else 0
    linhas += [[c.valores[i] for c in aba.colunas] for i in range(n)]
    return linhas


def xlsx(abas: list[Aba]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for aba in abas:
        ws = wb.create_sheet(aba.nome)
        for linha in _linhas(aba):
            ws.append(linha)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def csv_br(aba: Aba) -> bytes:
    """CSV como sai de um supervisório brasileiro: ";" e vírgula decimal."""

    def celula(v) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.6g}".replace(".", ",")
        return str(v)

    return "\n".join(";".join(celula(v) for v in linha) for linha in _linhas(aba)).encode("utf-8")


# ---- abas comuns


def aba_diario_fabrica(d: pd.DataFrame, nome: str, titulos: list[str]) -> Aba:
    return Aba(
        nome,
        "diario",
        [
            Coluna("Data", _data(d.instante_observado)),
            Coluna("Hora", _hora(d.instante_observado)),
            Coluna("Turno", _texto(d.turno), "turno"),
            Coluna("Operador", _texto(d.operador_id), "operador_id"),
            Coluna("Regime", _texto(d.regime), "regime"),
            Coluna(
                "Pressão vapor (kgf/cm²)",
                _num(d.p_vapor_bar_man, lambda x: x / 0.980665),
                "p_vapor_bar_man",
                "kgf/cm² manométrico",
            ),
            Coluna("Temp. chaminé (°C)", _num(d.t_gases_c), "t_gases_c", "°C"),
            Coluna("O2 base seca (%)", _num(d.o2_seco_pct), "o2_seco_pct", "% em base seca"),
            Coluna("CO (ppm)", _num(d.co_ppm), "co_ppm", "ppm"),
            Coluna("Temp. água alimentação (°C)", _num(d.t_agua_alim_c), "t_agua_alim_c", "°C"),
            Coluna("Temp. ar (°C)", _num(d.t_ar_c), "t_ar_c", "°C"),
            Coluna("Nº purgas", _num(d.purgas_n), "purgas_n", "contagem"),
            Coluna("Duração purgas (s)", _num(d.purgas_s), "purgas_s", "s"),
            Coluna(
                "Totalizador vapor (t)",
                _num(d.totalizador_vapor_t),
                "totalizador_vapor_t",
                "t (acumulado)",
            ),
            Coluna("Ocorrências", _texto(d.ocorrencia), "ocorrencia"),
            Coluna("Assinatura", _texto(d.operador_id)),
        ],
        titulos=titulos,
        combinar=("Data", "Hora"),
    )


def aba_diario_duplo(d: pd.DataFrame, nome: str) -> Aba:
    """Diário mensal com cabeçalho em duas linhas (células mescladas)."""
    colunas = [
        Coluna("Data", _data(d.instante_observado)),
        Coluna("Hora", _hora(d.instante_observado)),
        Coluna("Turno", _texto(d.turno), "turno"),
        Coluna("Operador", _texto(d.operador_id), "operador_id"),
        Coluna(
            "Pressão vapor (kgf/cm²)",
            _num(d.p_vapor_bar_man, lambda x: x / 0.980665),
            "p_vapor_bar_man",
            "kgf/cm² manométrico",
        ),
        Coluna("Chaminé (°C)", _num(d.t_gases_c), "t_gases_c", "°C"),
        Coluna("Água alimentação (°C)", _num(d.t_agua_alim_c), "t_agua_alim_c", "°C"),
        Coluna("Ar (°C)", _num(d.t_ar_c), "t_ar_c", "°C"),
        Coluna("O2 base seca (%)", _num(d.o2_seco_pct), "o2_seco_pct", "% em base seca"),
        Coluna("CO (ppm)", _num(d.co_ppm), "co_ppm", "ppm"),
        Coluna("Nº", _num(d.purgas_n), "purgas_n", "contagem"),
        Coluna("Duração (s)", _num(d.purgas_s), "purgas_s", "s"),
        Coluna(
            "Totalizador vapor (t)",
            _num(d.totalizador_vapor_t),
            "totalizador_vapor_t",
            "t (acumulado)",
        ),
        Coluna("Ocorrências", _texto(d.ocorrencia), "ocorrencia"),
    ]
    grupos = [
        "Data",
        "Hora",
        "Turno",
        "Operador",
        "Pressão vapor (kgf/cm²)",
        "Temperaturas",
        "",
        "",
        "Gases",
        "",
        "Purgas",
        "",
        "Totalizador vapor (t)",
        "Ocorrências",
    ]
    return Aba(
        nome,
        "diario",
        colunas,
        titulos=[f"Diário da caldeira 1 · {nome}/2026 (dados sintéticos)"],
        grupos=grupos,
        combinar=("Data", "Hora"),
    )


def abas_combustivel(c: pd.DataFrame, a: pd.DataFrame, nomes: tuple[str, str, str]) -> list[Aba]:
    receb = c[c.tipo == "recebimento"]
    estoque = c[c.tipo == "estoque"]
    return [
        Aba(
            nomes[0],
            "combustivel",
            [
                Coluna("Data", _data(receb.data)),
                Coluna("Hora", _hora(receb.data)),
                Coluna("Fornecedor", _texto(receb.fornecedor_id), "fornecedor_id"),
                Coluna("Lote", _texto(receb.lote_id), "lote_id"),
                Coluna(
                    "Peso líquido (t)", _num(receb.massa_kg, lambda x: x / 1000), "massa_kg", "t"
                ),
                Coluna(
                    "Valor total (R$)", _num(receb.preco_brl), "preco_brl", "R$ (total do lote)"
                ),
                Coluna("Nota fiscal", [f"NF-{i + 1001}" for i in range(len(receb))]),
            ],
            combinar=("Data", "Hora"),
            valores_unicos={"tipo": "recebimento"},
        ),
        Aba(
            nomes[1],
            "combustivel",
            [
                Coluna("Data", _data(estoque.data)),
                Coluna("Hora", _hora(estoque.data)),
                Coluna(
                    "Estoque medido (t)",
                    _num(estoque.massa_kg, lambda x: x / 1000),
                    "massa_kg",
                    "t",
                ),
            ],
            combinar=("Data", "Hora"),
            valores_unicos={"tipo": "estoque"},
        ),
        Aba(
            nomes[2],
            "amostras",
            [
                Coluna("Amostra", _texto(a.amostra_id), "amostra_id"),
                Coluna("Lote", _texto(a.lote_id), "lote_id"),
                Coluna("Data", _data(a.data)),
                Coluna("Hora", _hora(a.data)),
                Coluna(
                    "Umidade (%)",
                    _num(a.umidade_bu_frac, lambda x: 100 * x),
                    "umidade_bu_frac",
                    "%, base úmida",
                ),
                Coluna(
                    "PCI base seca (MJ/kg)", _num(a.pci_seco_mj_kg), "pci_seco_mj_kg", "MJ/kg seco"
                ),
                Coluna("Carbono (%)", _num(a.C, lambda x: 100 * x), "C", "%, base seca"),
                Coluna("Hidrogênio (%)", _num(a.H, lambda x: 100 * x), "H", "%, base seca"),
                Coluna("Oxigênio (%)", _num(a.O, lambda x: 100 * x), "O", "%, base seca"),
                Coluna("Nitrogênio (%)", _num(a.N, lambda x: 100 * x), "N", "%, base seca"),
                Coluna("Enxofre (%)", _num(a.S, lambda x: 100 * x), "S", "%, base seca"),
                Coluna("Cinzas (%)", _num(a.cinzas, lambda x: 100 * x), "cinzas", "%, base seca"),
                Coluna("Método", _texto(a.metodo), "metodo"),
                Coluna("Laboratório", _texto(a.laboratorio), "laboratorio"),
            ],
            combinar=("Data", "Hora"),
        ),
    ]


def aba_ocorrencias(e: pd.DataFrame) -> Aba:
    return Aba(
        "Ocorrências",
        "eventos",
        [
            Coluna("Data", _data(e.instante)),
            Coluna("Hora", _hora(e.instante)),
            Coluna("Tipo", _texto(e.tipo), "tipo"),
            Coluna("Descrição", _texto(e.descricao), "descricao"),
            Coluna("Autorizado por", _texto(e.autorizado_por), "autorizado_por"),
        ],
        combinar=("Data", "Hora"),
    )


def aba_instrumentos(i: pd.DataFrame) -> Aba:
    """Cadastro de instrumentos com nomes em português e os códigos da lista da EULER."""
    return Aba(
        "Instrumentos",
        "instrumentos",
        [
            Coluna("Tag", _texto(i.instrumento_id), "instrumento_id"),
            Coluna("Tipo", _texto(i.tipo), "tipo"),
            Coluna("Ponto", _texto(i.ponto), "ponto"),
            Coluna("Unidade", _texto(i.unidade), "unidade"),
            Coluna("Resolução", _num(i.resolucao), "resolucao", "na unidade do instrumento"),
            Coluna(
                "Incerteza", _num(i.incerteza_declarada), "incerteza_declarada",
                "na unidade do instrumento",
            ),
            Coluna("Tipo de incerteza", _texto(i.incerteza_tipo), "incerteza_tipo"),
            Coluna("Última verificação", _texto(i.ultima_verificacao), "ultima_verificacao"),
            Coluna("Observação", _texto(i.observacao), "observacao"),
        ],
    )  # fmt: skip


def abas_abreviadas(dfs) -> list[Aba]:
    """Planilha sem unidades e com abreviações: o que a EULER não reconhece sozinha."""
    d, c, a = dfs["diario"], dfs["combustivel"], dfs["amostras"]
    receb, estoque = c[c.tipo == "recebimento"], c[c.tipo == "estoque"]
    kgf = lambda x: x / 0.980665
    return [
        Aba(
            "Plan1",
            "diario",
            [
                Coluna("Data", _data(d.instante_observado)),
                Coluna("Hora", _hora(d.instante_observado)),
                Coluna("Press", _num(d.p_vapor_bar_man, kgf), "p_vapor_bar_man", "kgf/cm² manométrico"),
                Coluna("T1", _num(d.t_gases_c), "t_gases_c", "°C"),
                Coluna("T2", _num(d.t_agua_alim_c), "t_agua_alim_c", "°C"),
                Coluna("T3", _num(d.t_ar_c), "t_ar_c", "°C"),
                Coluna("O2", _num(d.o2_seco_pct), "o2_seco_pct", "% em base seca"),
                Coluna("CO", _num(d.co_ppm), "co_ppm", "ppm"),
                Coluna("Purg", _num(d.purgas_n), "purgas_n", "contagem"),
                Coluna("Tot", _num(d.totalizador_vapor_t), "totalizador_vapor_t", "t (acumulado)"),
                Coluna("Obs", _texto(d.ocorrencia)),
            ],
            combinar=("Data", "Hora"),
        ),
        Aba(
            "Plan2",
            "combustivel",
            [
                Coluna("Data", _data(receb.data)),
                Coluna("Hora", _hora(receb.data)),
                Coluna("Forn", _texto(receb.fornecedor_id), "fornecedor_id"),
                Coluna("Lote", _texto(receb.lote_id), "lote_id"),
                Coluna("Kg", _num(receb.massa_kg), "massa_kg", "kg"),
                Coluna("Valor", _num(receb.preco_brl), "preco_brl", "R$ (total do lote)"),
            ],
            combinar=("Data", "Hora"),
            valores_unicos={"tipo": "recebimento"},
        ),
        Aba(
            "Plan3",
            "combustivel",
            [
                Coluna("Data", _data(estoque.data)),
                Coluna("Hora", _hora(estoque.data)),
                Coluna("Kg", _num(estoque.massa_kg), "massa_kg", "kg"),
            ],
            combinar=("Data", "Hora"),
            valores_unicos={"tipo": "estoque"},
        ),
        Aba(
            "Plan4",
            "amostras",
            [
                Coluna("Amostra", _texto(a.amostra_id), "amostra_id"),
                Coluna("Lote", _texto(a.lote_id), "lote_id"),
                Coluna("Data", _data(a.data)),
                Coluna("Hora", _hora(a.data)),
                Coluna("Umid", _num(a.umidade_bu_frac, lambda x: 100 * x), "umidade_bu_frac", "%, base úmida"),
            ],
            combinar=("Data", "Hora"),
        ),
    ]  # fmt: skip


# ---- cenários: dados → (arquivos, gabarito por fonte)


def modelo_euler(dfs):
    """Arquivos no modelo da EULER (CSV com os nomes do contrato)."""
    arquivos, gabarito = {}, {}
    for nome, df in dfs.items():
        arquivos[f"{nome}.csv"] = df.to_csv(index=False, lineterminator="\n").encode("utf-8")
        tab = TABELAS[nome]
        gabarito[f"{nome}.csv"] = {
            "tabela": nome,
            "mapeamento": {c: c for c in df.columns},
            "unidades": {
                c: tab.coluna(c).unidade for c in df.columns if tab.coluna(c).tipo == "numero"
            },
            "linha_cabecalho": 1,
            "cabecalho_duplo": False,
            "valores_unicos": {},
        }
    return arquivos, gabarito


def _juntar(nome_arquivo: str, abas: list[Aba]) -> tuple[dict, dict]:
    return {nome_arquivo: xlsx(abas)}, {f"{nome_arquivo}::{a.nome}": a.gabarito() for a in abas}


def planilha_de_fabrica(dfs):
    """Um Excel com título em cima, nomes de fábrica, unidades no cabeçalho e Data + Hora."""
    abas = [
        aba_diario_fabrica(
            dfs["diario"],
            "Diário caldeira",
            ["Indústria Exemplo (sintética) · Diário da caldeira 1", "Agosto e setembro/2026", ""],
        ),
        *abas_combustivel(
            dfs["combustivel"],
            dfs["amostras"],
            ("Entrada de lenha", "Estoque do pátio", "Umidade da lenha"),
        ),
        aba_ocorrencias(dfs["eventos"]),
        aba_instrumentos(dfs["instrumentos"]),
    ]
    return _juntar("planilha_caldeira.xlsx", abas)


def mes_por_aba(dfs):
    """Diário com um mês por aba e cabeçalho em duas linhas; lenha em outro arquivo."""
    d = dfs["diario"]
    mes = _local(d.instante_observado).dt.month
    diario = [
        aba_diario_duplo(d[mes == m].reset_index(drop=True), n)
        for m, n in ((8, "Ago"), (9, "Set"))
        if (mes == m).any()
    ]
    a1, g1 = _juntar("diario_caldeira_2026.xlsx", diario)
    a2, g2 = _juntar(
        "lenha_2026.xlsx",
        abas_combustivel(
            dfs["combustivel"], dfs["amostras"], ("Recebimentos", "Estoque", "Umidade")
        ),
    )
    a3, g3 = _juntar("cadastro_instrumentos.xlsx", [aba_instrumentos(dfs["instrumentos"])])
    return {**a1, **a2, **a3}, {**g1, **g2, **g3}


def supervisorio(dfs):
    """Exportação do supervisório (tags de instrumento, ";" e vírgula decimal) + lenha."""
    d = dfs["diario"]
    instante = _local(d.instante_observado).dt.strftime("%d/%m/%Y %H:%M:%S").fillna("").tolist()
    scada = Aba(
        "export_scada_caldeira1.csv",
        "diario",
        [
            Coluna("Timestamp", instante, "instante_observado"),
            Coluna("PT-101 (bar)", _num(d.p_vapor_bar_man), "p_vapor_bar_man", "bar manométrico"),
            Coluna("TT-102 (°C)", _num(d.t_gases_c), "t_gases_c", "°C"),
            Coluna("AT-103 (%)", _num(d.o2_seco_pct), "o2_seco_pct", "% em base seca"),
            Coluna("AT-104 (ppm)", _num(d.co_ppm), "co_ppm", "ppm"),
            Coluna("TT-105 (°C)", _num(d.t_agua_alim_c), "t_agua_alim_c", "°C"),
            Coluna("TT-106 (°C)", _num(d.t_ar_c), "t_ar_c", "°C"),
            Coluna(
                "FQ-107 (t)", _num(d.totalizador_vapor_t), "totalizador_vapor_t", "t (acumulado)"
            ),
        ],
    )
    a2, g2 = _juntar(
        "balanca_lenha.xlsx",
        abas_combustivel(
            dfs["combustivel"], dfs["amostras"], ("Recebimentos", "Estoque", "Umidade")
        ),
    )
    a3, g3 = _juntar("cadastro_instrumentos.xlsx", [aba_instrumentos(dfs["instrumentos"])])
    return {scada.nome: csv_br(scada), **a2, **a3}, {scada.nome: scada.gabarito(), **g2, **g3}


def abreviacoes(dfs):
    """Planilha com abas "Plan1…Plan4", abreviações e nenhuma unidade no cabeçalho."""
    a1, g1 = _juntar("leituras.xlsx", abas_abreviadas(dfs))
    a2, g2 = _juntar("cadastro_instrumentos.xlsx", [aba_instrumentos(dfs["instrumentos"])])
    return {**a1, **a2}, {**g1, **g2}


@dataclass(frozen=True)
class Cenario:
    chave: str
    nome: str
    descricao: str
    montar: Callable[[dict[str, pd.DataFrame]], tuple[dict[str, bytes], dict[str, dict]]]


CENARIOS = (
    Cenario(
        "modelo",
        "Modelo EULER",
        "CSVs com os nomes do modelo (diário, combustível, amostras, eventos, instrumentos).",
        modelo_euler,
    ),
    Cenario(
        "fabrica",
        "Planilha de fábrica",
        "Um Excel com título em cima, nomes de fábrica com unidade, Data e Hora separadas; "
        "recebimentos, estoque, laboratório, ocorrências e instrumentos em abas.",
        planilha_de_fabrica,
    ),
    Cenario(
        "mensal",
        "Um mês por aba",
        "Diário com uma aba por mês e cabeçalho em duas linhas (células mescladas); lenha "
        "em outro arquivo, com recebimentos e estoque em abas separadas; instrumentos à parte.",
        mes_por_aba,
    ),
    Cenario(
        "supervisorio",
        "Supervisório + balança",
        'CSV exportado do supervisório com tags de instrumento (PT-101, TT-102…), ";" e '
        "vírgula decimal; lenha e instrumentos em planilhas à parte.",
        supervisorio,
    ),
    Cenario(
        "abreviacoes",
        "Abreviações sem unidade",
        'Abas "Plan1…Plan4" com cabeçalhos curtos ("Press", "T1", "T2", "O2", "Kg") e nenhuma '
        "unidade escrita: o pior caso realista para o reconhecimento automático.",
        abreviacoes,
    ),
)


# ------------------------------------------------------------ a conferência da pessoa


def conferir(
    arquivos: dict[str, bytes],
    gabarito: dict[str, dict],
    *,
    salvo: dict | None,
    origem: str,
    caldeira: str,
) -> tuple[dict, dict]:
    """Decisões finais (as do gabarito) com o que a tela sugeriu, e a contagem de ajustes.

    Reproduz a tela: lê com a linha e a forma do cabeçalho do gabarito, calcula o que a tela
    traria preenchido para a tabela escolhida e compara com o gabarito.
    """
    auto = {f.chave: f for f in ler_fontes(arquivos)}
    cabecalhos = {k: g["linha_cabecalho"] for k, g in gabarito.items()}
    duplos = {k: g["cabecalho_duplo"] for k, g in gabarito.items()}
    fontes = ler_fontes(arquivos, cabecalhos, duplos)
    verdade = {"caldeira_id": caldeira, "origem_dado": origem}
    decisoes, ajustes = {}, {}
    for fonte in fontes:
        g = gabarito.get(fonte.chave)
        if g is None:
            # fonte que não entra: a pessoa só ajusta se a EULER tiver sugerido uma tabela
            ajustes[fonte.chave] = {"tabela": int(sugerir_tabela(auto[fonte.chave]) is not None)}
            continue
        sugerido = sugestao_da_fonte(
            fonte, g["tabela"], salvo=salvo, origem=origem, caldeira=caldeira
        )
        sugerido["linha_cabecalho"] = auto[fonte.chave].linha_cabecalho
        sugerido["cabecalho_duplo"] = auto[fonte.chave].cabecalho_duplo
        colunas = [c for c in fonte.bruto if c != "linha"]
        pede = valores_unicos_da_tela(g["tabela"], g["mapeamento"], colunas)
        final = {
            "tabela": g["tabela"],
            "mapeamento": g["mapeamento"],
            "unidades": g["unidades"],
            "constantes": {k: {**verdade, **g["valores_unicos"]}.get(k, "") for k in pede},
            "linha_cabecalho": g["linha_cabecalho"],
            "cabecalho_duplo": g["cabecalho_duplo"],
            **({"combinar": g["combinar"]} if g.get("combinar") else {}),
        }
        ajustes[fonte.chave] = contar_ajustes(final, sugerido)
        decisoes[fonte.chave] = {**final, "sugerido": sugerido}
    return decisoes, ajustes


# ------------------------------------------------------------ medição


@dataclass
class Envio:
    fontes: int
    colunas: int
    colunas_usadas: int
    ajustes: int
    ajustes_detalhe: dict
    ajustes_por_fonte: dict
    confirmacoes: int
    tempos_s: dict
    contagem: dict
    fechamento: dict | None = None

    @property
    def maquina_s(self) -> float:
        return sum(self.tempos_s.values())


@dataclass
class Resultado:
    cenario: Cenario
    primeiro: Envio
    seguinte: Envio
    registro: dict


def _cronometro(tempos: dict, etapa: str, acao):
    t0 = time.perf_counter()
    r = acao()
    tempos[etapa] = tempos.get(etapa, 0.0) + time.perf_counter() - t0
    return r


def _envio(a, arquivos, gabarito, *, salvo, primeiro: bool) -> tuple[Envio, dict]:
    tempos: dict[str, float] = {}

    def preparar():
        decisoes, ajustes = conferir(
            arquivos, gabarito, salvo=salvo, origem="sintetico", caldeira=CALDEIRA
        )
        return decisoes, ajustes, preparar_lote(arquivos, decisoes)

    decisoes, ajustes, lote = _cronometro(tempos, "leitura e lote", preparar)
    soma: dict[str, int] = {}
    for por_fonte in ajustes.values():
        for k, v in por_fonte.items():
            if k != "total":
                soma[k] = soma.get(k, 0) + v
    total = sum(soma.values())
    # o manifesto guardado no lote precisa dizer o mesmo que a conferência
    no_lote = ajustes_do_lote(lote)
    if no_lote is None or no_lote["total"] != sum(ajustes[k]["total"] for k in decisoes):
        raise AssertionError("A contagem do manifesto difere da contagem da conferência.")
    previa = _cronometro(
        tempos,
        "prévia",
        lambda: a.previa(CALDEIRA, lote, fonte="Planilhas do cliente", mapeamento={}),
    )
    previa.mapeamento = {c: alvo for d in decisoes.values() for c, alvo in d["mapeamento"].items()}
    r = _cronometro(
        tempos,
        "confirmação",
        lambda: a.confirmar(
            previa,
            autor="medição de escala",
            salvar_perfil=True,
            atendimento={"ajustes": no_lote},
        ),
    )
    if primeiro:

        def referencia():
            s = periodos_entre_estoques(a.pacote(CALDEIRA))
            return criar_referencia(
                a,
                CALDEIRA,
                s[0][0],
                s[3][1],
                "inicial",
                "Quatro primeiras semanas (medição de escala)",
                "medição de escala",
            )

        _cronometro(tempos, "referência", referencia)
    fechamento = _cronometro(
        tempos, "fechamento", lambda: produzir_fechamento(a, CALDEIRA, "medição de escala")
    )
    fontes_lidas = ler_fontes(
        arquivos,
        {k: g["linha_cabecalho"] for k, g in gabarito.items()},
        {k: g["cabecalho_duplo"] for k, g in gabarito.items()},
    )
    envio = Envio(
        fontes=len(decisoes),
        colunas=sum(len([c for c in f.bruto if c != "linha"]) for f in fontes_lidas),
        colunas_usadas=sum(
            len(d["mapeamento"]) + (2 if d.get("combinar") else 0) for d in decisoes.values()
        ),
        ajustes=total,
        ajustes_detalhe=soma,
        ajustes_por_fonte={
            k: v for k, v in ajustes.items() if sum(x for kk, x in v.items() if kk != "total")
        },
        confirmacoes=len(CONFIRMACOES_PRIMEIRO if primeiro else CONFIRMACOES_SEGUINTE),
        tempos_s=tempos,
        contagem={"novos": r["novas"], "conflitos": r["conflitos_pendentes"]},
        fechamento={
            "inicio": fechamento["inicio"],
            "fim": fechamento["fim"],
            "situacao": fechamento["resultado"]["situacao"],
            "frase": fechamento["resultado"]["situacao_frase"],
            "consumo_t_t": fechamento["resultado"]["nucleo"]["consumo_especifico"]["periodo_t_t"],
            "efeito_qualidade_pct": fechamento["resultado"]["nucleo"]["explicacao_conta"]
            .get("entradas", {})
            .get("efeito_qualidade_pct"),
        },
    )
    perfil = a.perfil(CALDEIRA, "Planilhas do cliente") or {}
    return envio, perfil


def medir(cenario: Cenario, raiz: Path, dfs: dict[str, pd.DataFrame] | None = None) -> Resultado:
    """Um cliente do primeiro envio ao segundo fechamento, numa planta nova em `raiz`."""
    dfs = dfs or carregar_demo()
    repo = Repositorio(raiz)
    planta = repo.criar_planta(f"Cliente sintético · {cenario.nome}", classe="sintetico")
    a = repo.armazem(planta["id"])
    try:
        a.criar_equipamento(
            CALDEIRA,
            "Caldeira 1",
            CALDEIRA,
            config={"altitude_m": 1000.0},
            autor="medição de escala",
        )
        arquivos, gabarito = cenario.montar(ate(dfs, CORTE))
        primeiro, perfil = _envio(a, arquivos, gabarito, salvo=None, primeiro=True)
        registro = registro_atendimento(a, CALDEIRA)
        arquivos, gabarito = cenario.montar(dfs)  # o mesmo arquivo, atualizado no mês seguinte
        seguinte, _ = _envio(a, arquivos, gabarito, salvo=perfil, primeiro=False)
    finally:
        a.fechar()
    return Resultado(cenario, primeiro, seguinte, registro)


def faixa_humana_s(envio: Envio, primeiro: bool) -> tuple[float, float]:
    """Faixa ASSUMIDA de tempo de uma pessoa (D109): não é medição."""
    lo = hi = 0.0
    for chave, n in (
        ("ajuste", envio.ajustes),
        ("fonte", envio.fontes),
        ("confirmacao", envio.confirmacoes - int(primeiro)),
    ):
        lo += n * ASSUMIDO_S[chave][0]
        hi += n * ASSUMIDO_S[chave][1]
    if primeiro:
        lo += ASSUMIDO_S["referencia"][0]
        hi += ASSUMIDO_S["referencia"][1]
    return lo, hi


# ------------------------------------------------------------ relatório


def _min(s: float) -> str:
    return f"{s / 60:.0f}" if s >= 60 else f"{s / 60:.1f}"


def resposta_curta(resultados: list[Resultado]) -> list[str]:
    """Resumo em linguagem simples, calculado dos resultados (nada estimado além do rótulo)."""
    prim = [r.primeiro.maquina_s for r in resultados]
    seg = sorted(r.seguinte.maquina_s for r in resultados)
    mediana = seg[len(seg) // 2]
    humanos_1 = [faixa_humana_s(r.primeiro, True) for r in resultados]
    humanos_2 = [faixa_humana_s(r.seguinte, False) for r in resultados]
    ajustes_1 = ", ".join(f"{r.cenario.nome} {r.primeiro.ajustes}" for r in resultados)
    ajustes_2 = ", ".join(f"{r.cenario.nome} {r.seguinte.ajustes}" for r in resultados)
    return [
        "## Resposta curta",
        "",
        (
            f"- **Máquina (medido):** do envio ao primeiro fechamento, {min(prim):.0f} a "
            f"{max(prim):.0f} s por cliente; no mês seguinte, {min(seg):.0f} a {max(seg):.0f} s."
        ),
        f"- **Ajustes à mão no primeiro envio (contado):** {ajustes_1}.",
        f"- **Ajustes à mão no mês seguinte (contado):** {ajustes_2}.",
        (
            f"- **Pessoa (assumido, não medido):** {_min(min(h[0] for h in humanos_1))} a "
            f"{_min(max(h[1] for h in humanos_1))} min no primeiro envio; "
            f"{_min(min(h[0] for h in humanos_2))} a {_min(max(h[1] for h in humanos_2))} min "
            "nos meses seguintes."
        ),
        (
            f"- **Conta simples sobre o tempo medido:** com {mediana:.0f} s de máquina por cliente "
            f"por mês (mediana), 100 clientes somam cerca de {100 * mediana / 60:.0f} min de "
            "máquina por mês, um cliente por vez, num computador como o da medição."
        ),
        "",
    ]


# Achados da medição de 07/10/2026 (texto fixo: histórico do que o teste encontrou).
ACHADOS = (
    "## Achados da medição (07/10/2026)",
    "",
    (
        "1. **Corrigido na importação.** Na primeira rodada, a planilha de fábrica pedia 11 "
        "ajustes, o mês por aba 13 e o supervisório 16. Causas: a hora dos recebimentos e das "
        'amostras se perdia ("Data" era associada sozinha e a junção Data + Hora não era '
        'oferecida); "(s)" e contagem sem unidade sugerida; "Estoque medido (t)" sem '
        "regra; o tipo (recebimento ou estoque) não vinha do nome da aba; o cadastro de "
        'instrumentos não tinha vocabulário ("Tag", "Incerteza"). As regras novas valem '
        "para qualquer planilha, não só para estes cenários."
    ),
    (
        '2. **Sem cadastro de instrumentos, o fechamento não classifica a diferença** ("sem '
        'faixa de incerteza"). O cadastro entra uma vez, na implantação.'
    ),
    (
        "3. **Unidade que não está escrita no cabeçalho é confirmada a cada envio** (pior caso: "
        "12 re-confirmações por mês). Lembrar a unidade junto do mapeamento salvo zeraria esse "
        "custo, mas é decisão de produto: proposta pendente em D109."
    ),
    (
        "4. **Sem PCI do laboratório, a mesma operação muda de situação.** Com PCI, a conta "
        "separa o efeito do combustível mais úmido e o resto fica dentro da incerteza; só com a "
        'umidade, esse efeito fica ausente e o período aparece como "acima da referência '
        'ajustada (estabelecido)". A conta está coerente com o que foi medido, mas a frase pode '
        "ser lida como problema da caldeira: pergunta para a revisão em D109."
    ),
    (
        "5. **Os mesmos dados dão a mesma conta em qualquer formato**: o consumo por tonelada de "
        "vapor é igual nos cinco clientes (as conversões de unidade e Data + Hora não mudam a "
        "conta)."
    ),
)


def relatorio(resultados: list[Resultado]) -> str:
    maquina = f"{platform.system()} · {os.cpu_count()} núcleos · Python {platform.python_version()}"
    linhas = [
        "# Escala do atendimento: do envio ao primeiro fechamento",
        "",
        (
            "> Gerado por `python scripts/medir_escala.py` (D109). Dados **sintéticos**, feitos a "
            "partir do caso de demonstração. Tempo de máquina **medido**; ajustes e confirmações "
            "**contados**; tempo de pessoa **assumido** (faixa explícita abaixo), até o registro de "
            "atendimento medir clientes reais."
        ),
        "",
        f"Máquina da medição: {maquina}.",
        "",
        *resposta_curta(resultados),
        "## Primeiro envio → primeiro fechamento",
        "",
        "| Cliente (formato) | Arquivos/abas | Colunas | Usadas | Ajustes à mão | Confirmações | Máquina (s) | Pessoa (min, assumido) | Fechamento |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        p = r.primeiro
        lo, hi = faixa_humana_s(p, True)
        linhas.append(
            f"| {r.cenario.nome} | {p.fontes} | {p.colunas} | {p.colunas_usadas} | {p.ajustes} | "
            f"{p.confirmacoes} | {p.maquina_s:.1f} | {_min(lo)}–{_min(hi)} | {p.fechamento['frase']} |"
        )
    linhas += [
        "",
        "## Envio do mês seguinte → próximo fechamento",
        "",
        (
            "O cliente manda o mesmo arquivo, atualizado. O que já estava gravado é reconhecido e "
            "ignorado; o mapeamento salvo no primeiro envio é reaproveitado."
        ),
        "",
        "| Cliente (formato) | Ajustes à mão | Confirmações | Registros novos | Máquina (s) | Pessoa (min, assumido) |",
        "|---|---|---|---|---|---|",
    ]
    for r in resultados:
        s = r.seguinte
        lo, hi = faixa_humana_s(s, False)
        linhas.append(
            f"| {r.cenario.nome} | {s.ajustes} | {s.confirmacoes} | {s.contagem['novos']} | "
            f"{s.maquina_s:.1f} | {_min(lo)}–{_min(hi)} |"
        )
    linhas += ["", "## Tempo de máquina por etapa (s)", ""]
    etapas = list(
        dict.fromkeys(e for r in resultados for e in [*r.primeiro.tempos_s, *r.seguinte.tempos_s])
    )
    linhas += [
        "| Cliente | Envio | " + " | ".join(etapas) + " |",
        "|---|---|" + "---|" * len(etapas),
    ]
    for r in resultados:
        for rotulo, env in (("primeiro", r.primeiro), ("seguinte", r.seguinte)):
            linhas.append(
                f"| {r.cenario.nome} | {rotulo} | "
                + " | ".join(f"{env.tempos_s[e]:.1f}" if e in env.tempos_s else "—" for e in etapas)
                + " |"
            )
    linhas += ["", "## Onde estão os ajustes à mão", ""]
    for r in resultados:
        for rotulo, env in (("primeiro envio", r.primeiro), ("mês seguinte", r.seguinte)):
            if not env.ajustes:
                linhas.append(f"- **{r.cenario.nome}**, {rotulo}: nenhum.")
                continue
            partes = []
            for fonte, aj in env.ajustes_por_fonte.items():
                itens = ", ".join(f"{k} {v}" for k, v in aj.items() if k != "total" and v)
                partes.append(f"“{fonte}” ({itens})")
            linhas.append(f"- **{r.cenario.nome}**, {rotulo}: " + "; ".join(partes) + ".")
    linhas += ["", *ACHADOS, "", "## Cenários", ""]
    linhas += [f"- **{r.cenario.nome}**: {r.cenario.descricao}" for r in resultados]
    linhas += [
        "",
        "## Como ler",
        "",
        (
            "- **Ajuste à mão**: cada campo que a pessoa precisou mudar ou preencher na conferência "
            "(tabela, linha do cabeçalho, junção Data + Hora, associação de coluna, unidade, valor "
            "único como o tipo dos registros). Contado comparando o que a tela traz preenchido com "
            "o gabarito do cenário."
        ),
        "- **Confirmações**: cliques fixos do caminho ("
        + "; ".join(CONFIRMACOES_PRIMEIRO)
        + "). No mês seguinte não há referência a definir.",
        "- **Pessoa (assumido)**: faixa calculada com tempos ASSUMIDOS por ação — "
        + "; ".join(f"{k} {lo}–{hi} s" for k, (lo, hi) in ASSUMIDO_S.items())
        + ". Não é medição; serve só para ordem de grandeza até o registro de atendimento "
        "(Dados → Histórico → Atendimento) medir clientes reais.",
        (
            "- O tempo de calendário até o primeiro fechamento depende de o cliente já ter "
            "semanas suficientes de dados (referência + um período novo). Aqui, ele já tinha: tudo "
            "acontece no mesmo dia."
        ),
        "",
        "## Limites",
        "",
        (
            "- Dados sintéticos e formatos montados a partir do que fábricas costumam mandar; "
            "planilhas reais trazem variações que estes cenários não cobrem."
        ),
        (
            "- Tempo de máquina medido num único computador, um cliente por vez; não inclui envio "
            "pela rede nem espera de servidor."
        ),
        (
            "- Nos formatos de fábrica não há cadastro de instrumentos: o fechamento sai, mas com "
            "a incerteza dos instrumentos desconhecida, como no uso real."
        ),
    ]
    return "\n".join(linhas) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", default=str(RAIZ / "docs" / "produto" / "escala_atendimento.md"))
    args = parser.parse_args()
    dfs = carregar_demo()
    resultados = []
    with tempfile.TemporaryDirectory() as pasta:
        for cenario in CENARIOS:
            r = medir(cenario, Path(pasta) / cenario.chave, dfs)
            resultados.append(r)
            print(
                f"{cenario.nome}: 1º envio {r.primeiro.ajustes} ajustes, {r.primeiro.maquina_s:.1f} s; "
                f"mês seguinte {r.seguinte.ajustes} ajustes, {r.seguinte.maquina_s:.1f} s"
            )
    Path(args.saida).write_text(relatorio(resultados), encoding="utf-8")
    print(f"Relatório: {args.saida}")


if __name__ == "__main__":
    main()
