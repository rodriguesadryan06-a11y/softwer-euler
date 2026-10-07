"""Condições comparadas (D113): carga e regime de operação na referência e no período.

A conta ajusta o esperado por produção de vapor e, quando há dados, por condição do vapor e
da água e por qualidade do combustível. Carga e regime NÃO são ajustados (não há modelo
validado de consumo por carga nesta versão). Este módulo só mostra, com números medidos,
se a operação foi parecida nos dois períodos, para o desvio não ser lido como piora da
caldeira quando a operação mudou.

Carga: vazão de vapor entre leituras consecutivas do totalizador (t/h), ponderada pelo
tempo. Intervalos com totalizador reiniciado, sem leitura por muito tempo ou com o
instrumento indisponível ficam de fora (não viram zero). "Carga baixa" é relativa à
própria referência: abaixo do percentil 10 da carga da referência.
Regime: contagem das leituras do diário por regime declarado (estável, parada, partida…).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from euler.formato import num


def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t if t.tzinfo else t.tz_localize("UTC")


def _cargas(diario: pd.DataFrame, inicio, fim) -> pd.DataFrame:
    """Vazão média entre leituras consecutivas do totalizador dentro da janela (t/h)."""
    if diario is None or "totalizador_vapor_t" not in diario:
        return pd.DataFrame(columns=["horas", "carga_t_h"])
    d = diario[
        (diario["instante_observado"] > _ts(inicio))
        & (diario["instante_observado"] <= _ts(fim))
        & diario["totalizador_vapor_t"].notna()
    ]
    if "flag_instrumento_indisponivel" in d:
        d = d[~d["flag_instrumento_indisponivel"].fillna(False).astype(bool)]
    d = d.sort_values("instante_observado")
    horas = d["instante_observado"].diff().dt.total_seconds() / 3600
    vapor = d["totalizador_vapor_t"].astype(float).diff()
    passo = float(horas[horas > 0].median()) if (horas > 0).any() else 0.0
    ok = (horas > 0) & (vapor >= 0) & (horas <= 4 * passo)
    return pd.DataFrame({"horas": horas[ok], "carga_t_h": vapor[ok] / horas[ok]})


def _resumo_carga(c: pd.DataFrame) -> dict | None:
    if c.empty or c["horas"].sum() <= 0:
        return None
    ordem = c.sort_values("carga_t_h")
    acumulado = ordem["horas"].cumsum() / ordem["horas"].sum()

    def percentil(q: float) -> float:
        return float(ordem["carga_t_h"].iloc[int(np.searchsorted(acumulado.to_numpy(), q))])

    return {
        "media_t_h": float((c["carga_t_h"] * c["horas"]).sum() / c["horas"].sum()),
        "p10_t_h": percentil(0.10),
        "p25_t_h": percentil(0.25),
        "p75_t_h": percentil(0.75),
        "horas": float(c["horas"].sum()),
    }


def _regimes(diario: pd.DataFrame, inicio, fim) -> dict[str, int]:
    if diario is None or "regime" not in diario:
        return {}
    d = diario[
        (diario["instante_observado"] > _ts(inicio)) & (diario["instante_observado"] <= _ts(fim))
    ]
    return {str(k): int(v) for k, v in d["regime"].dropna().value_counts().items()}


def condicoes_comparadas(pacote, ref_inicio, ref_fim, inicio, fim) -> dict:
    """Carga e regime na referência e no período, com a leitura em linguagem simples.

    Saída: `carga` {referencia, periodo: média, percentis e horas medidas; None se não
    medida}, `carga_baixa_pct` {referencia, periodo: % do tempo abaixo do percentil 10 da
    referência}, `regimes` {referencia, periodo: leituras por regime}, `parecidas` (True,
    False ou None quando não dá para comparar), `frases` (o que se pode dizer) e
    `nao_ajustado` (texto fixo: carga e regime não entram no esperado).
    """
    diario = pacote.dados("diario")
    c_ref, c_per = _cargas(diario, ref_inicio, ref_fim), _cargas(diario, inicio, fim)
    r_ref, r_per = _resumo_carga(c_ref), _resumo_carga(c_per)
    regimes = {
        "referencia": _regimes(diario, ref_inicio, ref_fim),
        "periodo": _regimes(diario, inicio, fim),
    }
    frases, parecidas = [], None
    baixa = {"referencia": None, "periodo": None}
    if r_ref and r_per:
        limite = r_ref["p10_t_h"]
        for nome, c in (("referencia", c_ref), ("periodo", c_per)):
            baixa[nome] = float(
                100 * c.loc[c["carga_t_h"] < limite, "horas"].sum() / c["horas"].sum()
            )
        dentro = r_ref["p25_t_h"] <= r_per["media_t_h"] <= r_ref["p75_t_h"]
        parecidas = dentro and abs(baixa["periodo"] - baixa["referencia"]) < 10
        frases.append(
            f"Carga média: {num(r_ref['media_t_h'], 1)} t/h na referência e "
            f"{num(r_per['media_t_h'], 1)} t/h no período"
            + (
                " (dentro da faixa usual da referência)."
                if dentro
                else f" (fora da faixa usual da referência, {num(r_ref['p25_t_h'], 1)} a "
                f"{num(r_ref['p75_t_h'], 1)} t/h)."
            )
        )
        frases.append(
            f"Tempo em carga baixa (abaixo de {num(limite, 1)} t/h, o nível mais baixo comum na "
            f"referência): {num(baixa['referencia'], 0)}% na referência e "
            f"{num(baixa['periodo'], 0)}% no período."
        )
    else:
        frases.append(
            "Carga não comparada: faltam leituras do totalizador de vapor em um dos períodos."
        )
    paradas = {k: v.get("parada", 0) + v.get("partida", 0) for k, v in regimes.items()}
    if any(paradas.values()):
        frases.append(
            f"Leituras em parada ou partida: {paradas['referencia']} na referência e "
            f"{paradas['periodo']} no período."
        )
        if paradas["periodo"] > paradas["referencia"] and parecidas:
            parecidas = False
    if parecidas is True:
        frases.append(
            "A operação foi parecida nos dois períodos: carga e regime não explicam o desvio."
        )
    elif parecidas is False:
        frases.append(
            "A operação mudou (carga ou paradas): isso costuma aumentar o consumo por tonelada "
            "de vapor. Esse efeito não foi ajustado e continua dentro do desvio; não leia a "
            "diferença inteira como piora da caldeira."
        )
    return {
        "carga": {"referencia": r_ref, "periodo": r_per},
        "carga_baixa_pct": baixa,
        "regimes": regimes,
        "parecidas": parecidas,
        "frases": frases,
        "nao_ajustado": (
            "Carga e regime de operação não entram no consumo esperado (sem modelo validado "
            "nesta versão): o efeito deles, se houver, fica dentro do desvio."
        ),
    }
