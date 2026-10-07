"""Condições comparadas (D113): carga e regime medidos, sem ajuste inventado. Sintético."""

import pandas as pd

from euler.condicoes import condicoes_comparadas

REF = (pd.Timestamp("2026-08-01T00:00-03:00"), pd.Timestamp("2026-08-08T00:00-03:00"))
PER = (pd.Timestamp("2026-08-08T00:00-03:00"), pd.Timestamp("2026-08-15T00:00-03:00"))


class Pacote:
    def __init__(self, diario):
        self.diario = diario

    def dados(self, nome):
        return self.diario if nome == "diario" else None


def _diario(carga_ref, carga_per, regime_per="estavel", reset=False):
    linhas, total = [], 1000.0
    t = REF[0]
    while t < PER[1]:
        t += pd.Timedelta(hours=2)
        carga = carga_ref(t) if t <= REF[1] else carga_per(t)
        total += 2 * carga
        if reset and t == PER[0] + pd.Timedelta(hours=24):
            total = 0.0  # totalizador reiniciado: esse intervalo sai, não vira zero
        linhas.append(
            {
                "instante_observado": t,
                "totalizador_vapor_t": total,
                "regime": regime_per if t > PER[0] and t.hour == 12 and t.day == 10 else "estavel",
            }
        )
    return pd.DataFrame(linhas)


def _variando(base):
    return lambda t: base * (0.8 + 0.4 * ((t.hour // 2) % 6) / 5)


def test_operacao_parecida():
    c = condicoes_comparadas(Pacote(_diario(_variando(15), _variando(15))), *REF, *PER)
    assert c["parecidas"] is True
    assert c["carga"]["referencia"]["media_t_h"] == c["carga"]["periodo"]["media_t_h"]
    assert "não explicam o desvio" in " ".join(c["frases"])
    assert "não entram no consumo esperado" in c["nao_ajustado"]


def test_carga_mais_baixa_fica_dita_e_nao_ajustada():
    c = condicoes_comparadas(Pacote(_diario(_variando(15), _variando(8))), *REF, *PER)
    assert c["parecidas"] is False
    assert c["carga_baixa_pct"]["periodo"] > c["carga_baixa_pct"]["referencia"]
    texto = " ".join(c["frases"])
    assert "fora da faixa usual da referência" in texto
    assert "não foi ajustado e continua dentro do desvio" in texto


def test_totalizador_reiniciado_nao_vira_carga_zero():
    c = condicoes_comparadas(Pacote(_diario(_variando(15), _variando(15), reset=True)), *REF, *PER)
    assert c["carga"]["periodo"]["horas"] < 7 * 24  # o intervalo do reinício ficou de fora
    assert c["parecidas"] is True


def test_paradas_a_mais_tornam_a_operacao_diferente():
    c = condicoes_comparadas(
        Pacote(_diario(_variando(15), _variando(15), regime_per="parada")), *REF, *PER
    )
    assert c["regimes"]["periodo"].get("parada") == 1
    assert c["parecidas"] is False


def test_sem_totalizador_nao_compara():
    d = _diario(_variando(15), _variando(15)).drop(columns="totalizador_vapor_t")
    c = condicoes_comparadas(Pacote(d), *REF, *PER)
    assert c["parecidas"] is None and c["carga"]["periodo"] is None
    assert "Carga não comparada" in c["frases"][0]
