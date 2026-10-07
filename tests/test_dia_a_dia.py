"""Dia a dia da caldeira (D114): agregados diários dos registros, ausente nunca zero."""

import pandas as pd
import pytest

from euler.dia_a_dia import dia_a_dia, diario_por_dia

FUSO = "America/Sao_Paulo"


class Pacote:
    def __init__(self, diario, combustivel=None):
        self.d, self.c = diario, combustivel

    def dados(self, nome):
        return {"diario": self.d, "combustivel": self.c}.get(nome)


def _diario(dias=20, carga=15.0, tg=185.0, falta=(), reset_dia=None):
    linhas, total = [], 0.0
    t = pd.Timestamp("2026-09-01T00:00", tz=FUSO)
    fim = t + pd.Timedelta(days=dias)
    while t < fim:
        t += pd.Timedelta(hours=2)
        total += 2 * carga
        if reset_dia is not None and t == pd.Timestamp(reset_dia, tz=FUSO) + pd.Timedelta(hours=10):
            total = 0.0
        if t.day in falta and 6 <= t.hour <= 20:
            continue  # leituras perdidas durante o dia
        linhas.append(
            {
                "instante_observado": t,
                "totalizador_vapor_t": total,
                "t_gases_c": tg + (5 if t.day >= 15 else 0),
                "o2_seco_pct": 7.5,
            }
        )
    return pd.DataFrame(linhas)


def test_vazao_por_dia_so_com_dia_coberto_e_sem_reinicio():
    df = diario_por_dia(Pacote(_diario(falta=(5,), reset_dia="2026-09-08")))
    por_dia = {r["dia"].day: r for r in df.to_dict(orient="records")}
    assert por_dia[3]["vazao_t_h"] == pytest.approx(15.0)
    assert pd.isna(por_dia[5]["vazao_t_h"])  # menos de 12 h cobertas: em branco, não zero
    # o intervalo do reinício sai, mas a média das horas cobertas continua certa
    assert por_dia[8]["horas_cobertas"] == pytest.approx(22.0)
    assert por_dia[8]["vazao_t_h"] == pytest.approx(15.0)
    assert por_dia[5]["t_gases_c"] == pytest.approx(185.0)  # a média das leituras existe


def test_quadros_comparam_a_semana_com_a_referencia():
    ref = {"inicio": "2026-09-01T00:00:00-03:00", "fim": "2026-09-12T00:00:00-03:00"}
    comb = pd.DataFrame(
        {
            "data": [pd.Timestamp("2026-09-18T09:00", tz=FUSO)],
            "tipo": ["recebimento"],
            "massa_kg": [30000.0],
        }
    )
    r = dia_a_dia(Pacote(_diario(), comb), ref)
    q = {x["grandeza"]: x for x in r["quadros"]}
    assert q["vazao_t_h"]["fora_da_faixa"] is False
    assert q["t_gases_c"]["fora_da_faixa"] is True  # 190 °C contra 185 °C na referência
    assert "acima do comum na referência" in q["t_gases_c"]["frase"]
    assert q["recebido_t"]["frase"] == "compras registradas (não é consumo)"
    assert q["recebido_t"]["fora_da_faixa"] is None


def test_sem_registros():
    r = dia_a_dia(Pacote(pd.DataFrame(columns=["instante_observado"])))
    assert r["serie"] == [] and r["quadros"] == []
