"""Balanço adaptativo por vazões do historiador.

Esta rota existe para plantas sem balanço de pátio/totalizadores adequados. Integra apenas
intervalos observados e não atravessa lacunas grandes. Resultado de eficiência só existe
quando vapor e combustível cobrem os mesmos intervalos válidos.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

from euler.tipos import AnaliseBloqueada
from euler.vapor import delta_h_mj_kg, t_sat_c


@dataclass(frozen=True)
class BalancoFluxos:
    energia_vapor_gj: float
    energia_combustivel_gj: float
    eficiencia: float
    horas_cobertas: float
    horas_totais: float
    cobertura: float
    intervalos_usados: int
    intervalos_pulados: int
    nota: str


def _estado_linha(row) -> tuple[str, dict]:
    estado = None if pd.isna(row.estado_vapor) else str(row.estado_vapor)
    if estado == "superaquecido":
        if pd.isna(row.t_vapor_c):
            raise AnaliseBloqueada("Vapor superaquecido sem temperatura.")
        return estado, {"t_vapor_c": float(row.t_vapor_c)}
    if estado == "umido":
        if pd.isna(row.titulo_vapor):
            raise AnaliseBloqueada("Vapor úmido sem título.")
        return estado, {"titulo": float(row.titulo_vapor)}
    if estado == "saturado_seco":
        return estado, {}

    # Sem rótulo: P + T muito acima da saturação identifica superaquecimento.
    if not pd.isna(row.t_vapor_c):
        tsat = t_sat_c(float(row.p_vapor_bar_abs))
        if float(row.t_vapor_c) > tsat + 1.0:
            return "superaquecido", {"t_vapor_c": float(row.t_vapor_c)}
        raise AnaliseBloqueada(
            "Temperatura do vapor próxima/abaixo da saturação sem estado/título declarado.",
            ["estado do vapor ou título quando aplicável"],
        )

    # Compatibilidade com o motor histórico: sem T e sem estado, x=1 fica assumido.
    return "saturado_seco", {}


def _potencia_vapor_mw(row) -> float:
    estado, kwargs = _estado_linha(row)
    dh = delta_h_mj_kg(
        float(row.p_vapor_bar_abs),
        estado,
        float(row.t_agua_alim_c),
        **kwargs,
    )
    return float(row.vazao_vapor_t_h) * 1000 / 3600 * dh


def _potencia_combustivel_mw(row) -> float:
    if hasattr(row, "potencia_combustivel_mw") and not pd.isna(row.potencia_combustivel_mw):
        q = float(row.potencia_combustivel_mw)
    else:
        if pd.isna(row.vazao_combustivel_kg_h) or pd.isna(row.pci_combustivel_mj_kg):
            raise AnaliseBloqueada(
                "Sem potência térmica do combustível nem vazão mássica + PCI no mesmo instante."
            )
        q = float(row.vazao_combustivel_kg_h) * float(row.pci_combustivel_mj_kg) / 3600
    if not isfinite(q) or q <= 0:
        raise AnaliseBloqueada("Potência térmica do combustível precisa ser positiva e finita.")
    return q


def balanco_por_vazoes(
    diario: pd.DataFrame,
    *,
    max_gap_factor: float = 3.0,
    cobertura_minima: float = 0.5,
) -> BalancoFluxos:
    """Integra potência útil do vapor e potência do combustível pelo trapézio.

    Não interpola tags ausentes. Intervalos maiores que max_gap_factor × passo mediano são
    pulados. A eficiência usa somente intervalos em que os dois lados existem simultaneamente.
    """
    obrig = {
        "instante_observado",
        "vazao_vapor_t_h",
        "p_vapor_bar_abs",
        "t_agua_alim_c",
    }
    faltam = obrig - set(diario.columns)
    if faltam:
        raise AnaliseBloqueada(
            "Faltam colunas para o balanço por vazões.",
            sorted(faltam),
        )
    d = diario.copy()
    if "regime" in d:
        d = d[d["regime"].fillna("estavel") != "parada"]
    d = d.sort_values("instante_observado").drop_duplicates("instante_observado")
    if len(d) < 2:
        raise AnaliseBloqueada("São necessárias ao menos duas leituras no tempo.")

    tempos = pd.to_datetime(d["instante_observado"])
    passos_h = tempos.diff().dt.total_seconds().div(3600).dropna()
    positivos = passos_h[passos_h > 0]
    if positivos.empty:
        raise AnaliseBloqueada("Os instantes não formam intervalos positivos.")
    passo_mediano = float(positivos.median())
    limite_gap = max_gap_factor * passo_mediano

    qv = []
    qf = []
    validos = []
    for row in d.itertuples(index=False):
        try:
            if pd.isna(row.vazao_vapor_t_h) or float(row.vazao_vapor_t_h) <= 0:
                raise AnaliseBloqueada("Vazão de vapor ausente ou não positiva.")
            qv.append(_potencia_vapor_mw(row))
            qf.append(_potencia_combustivel_mw(row))
            validos.append(True)
        except (AnaliseBloqueada, ValueError, TypeError):
            qv.append(float("nan"))
            qf.append(float("nan"))
            validos.append(False)
    d["_qv"] = qv
    d["_qf"] = qf
    d["_valido"] = validos

    ev = ef = 0.0
    horas = 0.0
    usados = pulados = 0
    rows = list(d.itertuples(index=False))
    for a, b in zip(rows[:-1], rows[1:], strict=True):
        dt_h = (b.instante_observado - a.instante_observado).total_seconds() / 3600
        if dt_h <= 0 or dt_h > limite_gap or not (a._valido and b._valido):
            pulados += 1
            continue
        # MW × h × 3,6 = GJ
        ev += 0.5 * (a._qv + b._qv) * dt_h * 3.6
        ef += 0.5 * (a._qf + b._qf) * dt_h * 3.6
        horas += dt_h
        usados += 1

    total_h = (tempos.iloc[-1] - tempos.iloc[0]).total_seconds() / 3600
    cobertura = 0.0 if total_h <= 0 else horas / total_h
    if usados == 0 or ev <= 0 or ef <= 0:
        raise AnaliseBloqueada("Nenhum intervalo comum válido para fechar o balanço por vazões.")
    if cobertura < cobertura_minima:
        raise AnaliseBloqueada(
            f"Cobertura comum insuficiente para o balanço por vazões ({100*cobertura:.0f}%).",
            [f"cobertura de ao menos {100*cobertura_minima:.0f}% nos mesmos intervalos"],
        )
    eta = ev / ef
    if not isfinite(eta) or eta <= 0:
        raise AnaliseBloqueada("Eficiência por vazões não finita ou não positiva.")
    return BalancoFluxos(
        energia_vapor_gj=ev,
        energia_combustivel_gj=ef,
        eficiencia=eta,
        horas_cobertas=horas,
        horas_totais=total_h,
        cobertura=cobertura,
        intervalos_usados=usados,
        intervalos_pulados=pulados,
        nota=(
            "Integração trapezoidal nos intervalos comuns observados; lacunas grandes não são "
            "interpoladas. Sem orçamento de incerteza nesta rota inicial."
        ),
    )
