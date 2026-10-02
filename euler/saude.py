"""Saúde da caldeira: consumo por tonelada de vapor período a período, eventos e selo (D65).

Painel logo depois de carregar os dados. O selo principal continua usando, para cada período
entre medições de estoque, o consumo específico do balanço direto (combustível queimado ÷
vapor, E9) e a mesma regra da Investigação (`comparar`, U = 2u da diferença, D25/D37).

Como camada secundária (D70), quando a referência contém períodos explicitamente estáveis,
é ajustado um baseline simples por carga. Ele não muda o selo, não extrapola e não atribui
causa ao residual.

Referência = a primeira metade dos períodos (a mesma escolha padrão da tela Investigação).
Cada período depois dela recebe um estado:
- `mudou`: diferença maior que a incerteza (detectável, "sim");
- `estavel`: diferença dentro da incerteza ("nao");
- `nao_da_para_dizer`: falta o consumo do período ou a incerteza para decidir.

Selo geral: `mudou` se algum período mudou; `estavel` se todos os períodos depois da
referência têm consumo e ficaram dentro da incerteza; senão `nao_da_para_dizer`. A mudança
a investigar é a primeira sequência de períodos seguidos que mudaram no mesmo sentido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from euler.baseline import (
    BaselineCarga,
    ObservacaoCarga,
    ajustar_baseline_carga,
    residual_normalizado,
)
from euler.deteccao import Comparacao, comparar
from euler.direto import balanco_direto
from euler.formato import num
from euler.io import Pacote
from euler.periodos import periodos_entre_estoques, resumir_periodo
from euler.tipos import AnaliseBloqueada, Grandeza

Estado = Literal["referencia", "mudou", "estavel", "nao_da_para_dizer"]
Selo = Literal["mudou", "estavel", "nao_da_para_dizer"]

ROTULO_EVENTO = {
    "limpeza": "Limpeza",
    "manutencao": "Manutenção",
    "troca_instrumento": "Troca de instrumento",
    "calibracao": "Calibração",
    "parada": "Parada",
    "partida": "Partida",
    "mudanca_combustivel": "Troca de combustível ou fornecedor",
    "outro": "Outro",
}


@dataclass(frozen=True)
class Periodo:
    """Um período entre medições de estoque, com o consumo e o estado frente à referência."""

    indice: int
    inicio: pd.Timestamp
    fim: pd.Timestamp
    consumo: Grandeza | None
    """Consumo específico, t de combustível por t de vapor (None quando não dá)."""
    motivo: str | None
    """Por que não há consumo no período (quando não há)."""
    estado: Estado
    comparacao: Comparacao | None = None


@dataclass(frozen=True)
class Saude:
    periodos: list[Periodo]
    referencia: tuple[int, int] | None
    consumo_referencia: Grandeza | None
    selo: Selo
    frase: str
    mudanca: tuple[int, int] | None = None
    """Índices (primeiro, último) dos períodos a investigar, quando mudou."""
    comparacao_mudanca: Comparacao | None = None
    eventos: list[dict] = field(default_factory=list)
    baseline_carga: BaselineCarga | None = None
    residuos_carga: dict[int, float | None] = field(default_factory=dict)


def _consumo(pacote: Pacote, inicio: pd.Timestamp, fim: pd.Timestamp):
    b = balanco_direto(resumir_periodo(pacote, inicio, fim))
    motivo = None if b.consumo_t_por_t else (b.bloqueios[0].motivo if b.bloqueios else None)
    return b.consumo_t_por_t, motivo


def _baseline_carga(
    pacote: Pacote, datas: list[tuple[pd.Timestamp, pd.Timestamp]], fim_referencia: int
) -> tuple[BaselineCarga | None, dict[int, float | None]]:
    """Baseline secundário condicionado à carga; nunca substitui a comparação principal.

    A referência usa somente períodos explicitamente quase estacionários. O modelo não
    extrapola: períodos fora da faixa de carga ficam sem residual.
    """
    obs: list[ObservacaoCarga] = []
    resumos = {}
    for i, (inicio, fim) in enumerate(datas):
        r = resumir_periodo(pacote, inicio, fim)
        resumos[i] = r
        if i > fim_referencia or not r.apto_baseline_carga:
            continue
        if r.vapor_t is None or r.combustivel_kg is None or r.horas <= 0:
            continue
        obs.append(
            ObservacaoCarga(
                carga_t_h=r.vapor_t.valor / r.horas,
                combustivel_t_h=(r.combustivel_kg.valor / 1000) / r.horas,
            )
        )
    try:
        modelo = ajustar_baseline_carga(obs)
    except AnaliseBloqueada:
        return None, {}

    residuos: dict[int, float | None] = {}
    for i, r in resumos.items():
        if i <= fim_referencia or not r.apto_baseline_carga:
            continue
        if r.vapor_t is None or r.combustivel_kg is None or r.horas <= 0:
            continue
        carga = r.vapor_t.valor / r.horas
        combustivel = (r.combustivel_kg.valor / 1000) / r.horas
        try:
            residuos[i] = residual_normalizado(
                modelo, carga_t_h=carga, combustivel_t_h=combustivel
            )
        except AnaliseBloqueada:
            residuos[i] = None
    return modelo, residuos


def _estado(c: Comparacao) -> Estado:
    if c.detectabilidade == "sim":
        return "mudou"
    if c.detectabilidade == "nao":
        return "estavel"
    return "nao_da_para_dizer"


def _eventos(pacote: Pacote) -> list[dict]:
    ev = pacote.dados("eventos")
    if ev is None or ev.empty:
        return []
    ev = ev.dropna(subset=["instante"]).sort_values("instante")
    return [
        {
            "instante": e.instante,
            "tipo": ROTULO_EVENTO.get(str(e.tipo), str(e.tipo).replace("_", " ")),
            "descricao": "" if pd.isna(e.descricao) else str(e.descricao),
        }
        for e in ev.itertuples()
    ]


def _sequencia(periodos: list[Periodo]) -> tuple[int, int] | None:
    """Primeira sequência de períodos seguidos que mudaram no mesmo sentido."""
    inicio = sinal = None
    for p in periodos:
        if p.estado == "mudou":
            s = p.comparacao.delta > 0
            if inicio is None:
                inicio, sinal, fim = p.indice, s, p.indice
                continue
            if s == sinal and p.indice == fim + 1:
                fim = p.indice
                continue
            break
        if inicio is not None:
            break
    return None if inicio is None else (inicio, fim)


def _datas(periodos, a: int, b: int) -> str:
    return f"{periodos[a][0]:%d/%m} a {periodos[b][1]:%d/%m}"


def avaliar_saude(pacote: Pacote) -> Saude:
    """Consumo por tonelada de vapor período a período, com o selo mudou/estável.

    Entrada: o pacote importado. Saída: `Saude` com um item por período entre medições de
    estoque, a referência (primeira metade dos períodos), o selo, a frase para a tela e,
    quando mudou, os períodos a investigar. Nenhum número é preenchido: período sem consumo
    fica com `consumo=None` e o motivo.
    """
    datas = periodos_entre_estoques(pacote)
    eventos = _eventos(pacote)
    if len(datas) < 2:
        return Saude(
            [],
            None,
            None,
            "nao_da_para_dizer",
            "Não dá para dizer se o consumo mudou: são precisos ao menos dois períodos, ou seja, "
            "três medições de estoque no pátio.",
            eventos=eventos,
        )
    n = len(datas)
    ref = (0, max(1, n // 2) - 1)
    c_ref, motivo_ref = _consumo(pacote, datas[ref[0]][0], datas[ref[1]][1])
    periodos = []
    for i, (inicio, fim) in enumerate(datas):
        consumo, motivo = _consumo(pacote, inicio, fim)
        if i <= ref[1]:
            periodos.append(Periodo(i, inicio, fim, consumo, motivo, "referencia"))
            continue
        c = comparar("consumo específico", "t/t", c_ref, consumo)
        estado = _estado(c) if c.disponivel else "nao_da_para_dizer"
        periodos.append(Periodo(i, inicio, fim, consumo, motivo, estado, c))

    baseline_carga, residuos_carga = _baseline_carga(pacote, datas, ref[1])
    extras = {"baseline_carga": baseline_carga, "residuos_carga": residuos_carga}

    depois = periodos[ref[1] + 1 :]
    mudanca = _sequencia(depois)
    texto_ref = _datas(datas, *ref)
    if c_ref is None:
        return Saude(
            periodos, ref, None, "nao_da_para_dizer",
            "Não dá para dizer se o consumo mudou: o consumo por tonelada de vapor da referência "
            f"({texto_ref}) não pôde ser calculado. {motivo_ref or ''}".strip(),
            eventos=eventos, **extras,
        )  # fmt: skip
    if mudanca is not None:
        c_mud, _ = _consumo(pacote, datas[mudanca[0]][0], datas[mudanca[1]][1])
        cmp = comparar("consumo específico", "t/t", c_ref, c_mud)
        variacao = 100 * cmp.delta / cmp.referencia if cmp.disponivel else None
        sentido = "subiu" if (cmp.delta or 0) > 0 else "caiu"
        frase = (
            f"O consumo por tonelada de vapor {sentido}"
            + (f" {num(abs(variacao), 1)}%" if variacao is not None else "")
            + f" de {_datas(datas, *mudanca)} em relação à referência ({texto_ref}), "
            "além da incerteza das medições."
        )
        return Saude(
            periodos, ref, c_ref, "mudou", frase, mudanca, cmp, eventos, **extras
        )
    if depois and all(p.estado == "estavel" for p in depois):
        return Saude(
            periodos, ref, c_ref, "estavel",
            "O consumo por tonelada de vapor ficou estável: nenhum período depois da referência "
            f"({texto_ref}) se afastou dela além da incerteza das medições.",
            eventos=eventos, **extras,
        )  # fmt: skip
    sem = [p for p in depois if p.estado == "nao_da_para_dizer"]
    if any(p.consumo is None for p in sem):
        lista = ", ".join(f"{p.inicio:%d/%m} a {p.fim:%d/%m}" for p in sem if p.consumo is None)
        motivo = f"sem consumo calculado em {lista}"
    elif any(p.comparacao.detectabilidade == "condicional" for p in sem):
        motivo = "a diferença só é real se o erro do mesmo instrumento se repetir nos dois períodos"
    else:
        motivo = "falta a incerteza de alguma medição usada no consumo"
    return Saude(
        periodos, ref, c_ref, "nao_da_para_dizer",
        f"Não dá para dizer se o consumo mudou depois da referência ({texto_ref}): {motivo}.",
        eventos=eventos, **extras,
    )  # fmt: skip
