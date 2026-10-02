"""Baseline físico simples por carga para o primeiro piloto da EULER.

O modelo usa uma relação afim entre vazão de combustível e vazão de vapor:

    m_f = a + b * m_s

Interpretação: `a` captura uma parcela fixa aparente e `b` a parcela marginal no domínio
observado. É uma referência empírica condicionada à carga, não uma lei universal da caldeira.
Não extrapola além da faixa usada no ajuste e não atribui causa ao residual.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

import numpy as np

from euler.tipos import AnaliseBloqueada


@dataclass(frozen=True)
class ObservacaoCarga:
    carga_t_h: float
    combustivel_t_h: float


@dataclass(frozen=True)
class BaselineCarga:
    intercepto_t_h: float
    inclinacao_t_t: float
    carga_min_t_h: float
    carga_max_t_h: float
    carga_media_t_h: float
    sxx: float
    rmse_t_h: float
    n: int

    def prever_combustivel_t_h(self, carga_t_h: float) -> float:
        """Combustível esperado na carga, sem extrapolar fora do domínio observado."""
        if not self.carga_min_t_h <= carga_t_h <= self.carga_max_t_h:
            raise AnaliseBloqueada(
                f"Carga de {carga_t_h:g} t/h fora da faixa usada no baseline "
                f"({self.carga_min_t_h:g} a {self.carga_max_t_h:g} t/h).",
                ["dados de referência em carga semelhante"],
            )
        return self.intercepto_t_h + self.inclinacao_t_t * carga_t_h

    def sigma_predicao_t_h(self, carga_t_h: float) -> float | None:
        """Desvio-padrão de previsão OLS dentro da faixa de referência.

        Inclui a dispersão residual de uma nova observação. Não inclui, nesta fase,
        incertezas instrumentais separadas; isso fica explícito na decisão D70.
        """
        self.prever_combustivel_t_h(carga_t_h)  # também protege contra extrapolação
        if self.n < 3 or self.rmse_t_h <= 0 or self.sxx <= 0:
            return None
        alavancagem = 1 / self.n + (carga_t_h - self.carga_media_t_h) ** 2 / self.sxx
        return self.rmse_t_h * sqrt(1 + alavancagem)


def ajustar_baseline_carga(observacoes: list[ObservacaoCarga]) -> BaselineCarga:
    """Ajusta m_combustível/h = a + b·m_vapor/h por mínimos quadrados ordinários.

    Exige ao menos três pontos válidos e pelo menos duas cargas distintas. O motor não
    preenche observações ausentes e não extrapola o modelo fora do domínio de referência.
    """
    if len(observacoes) < 3:
        raise AnaliseBloqueada(
            "São necessários ao menos três períodos de referência para ajustar o baseline por carga.",
            ["três ou mais períodos de referência quase estacionários"],
        )
    x = np.array([o.carga_t_h for o in observacoes], dtype=float)
    y = np.array([o.combustivel_t_h for o in observacoes], dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or (x <= 0).any() or (y <= 0).any():
        raise AnaliseBloqueada(
            "O baseline recebeu carga ou combustível inválido.",
            ["vazões positivas e finitas de vapor e combustível"],
        )
    xbar = float(x.mean())
    sxx = float(((x - xbar) ** 2).sum())
    if sxx <= 0:
        raise AnaliseBloqueada(
            "A referência não contém variação de carga suficiente para ajustar o baseline.",
            ["períodos de referência em pelo menos duas cargas diferentes"],
        )
    b = float(((x - xbar) * (y - y.mean())).sum() / sxx)
    a = float(y.mean() - b * xbar)
    residuos = y - (a + b * x)
    dof = len(x) - 2
    rmse = float(sqrt(float((residuos**2).sum()) / dof)) if dof > 0 else 0.0
    return BaselineCarga(
        intercepto_t_h=a,
        inclinacao_t_t=b,
        carga_min_t_h=float(x.min()),
        carga_max_t_h=float(x.max()),
        carga_media_t_h=xbar,
        sxx=sxx,
        rmse_t_h=rmse,
        n=len(x),
    )


def residual_normalizado(
    modelo: BaselineCarga, *, carga_t_h: float, combustivel_t_h: float
) -> float | None:
    """(observado − esperado) / sigma de previsão; None quando o ruído não é estimável."""
    if not isfinite(combustivel_t_h) or combustivel_t_h <= 0:
        raise AnaliseBloqueada(
            "Vazão de combustível inválida para calcular o residual.",
            ["vazão positiva e finita de combustível"],
        )
    esperado = modelo.prever_combustivel_t_h(carga_t_h)
    sigma = modelo.sigma_predicao_t_h(carga_t_h)
    return None if sigma is None or sigma == 0 else (combustivel_t_h - esperado) / sigma
