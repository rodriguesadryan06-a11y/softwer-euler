"""Conta do combustível (D112): preço que muda dentro do período na tabela de preços e a
resposta "a conta mudou por produção, por preço ou por consumo?". Dados sintéticos."""

import pandas as pd
import pytest
from construtor_caso import Periodo
from test_fechamento import EQ, G01, planta_com

from euler.conta import explicar_conta, resposta_da_ponte
from euler.fechamento import (
    criar_referencia,
    preco_do_periodo,
    produzir_fechamento,
    registrar_preco,
)


def _meio(p) -> pd.Timestamp:
    return p[0] + (p[1] - p[0]) / 2


def test_preco_que_muda_no_periodo_e_rateado_pelo_vapor(tmp_path):
    a, s = planta_com(tmp_path, [Periodo(G01), Periodo(G01)])
    try:
        pacote = a.pacote(EQ)
        meio = _meio(s[1]).normalize()  # o contrato muda à 0h de um dia no meio do período
        registrar_preco(a, EQ, "cavaco", 180.0, s[0][0], "contrato 1", "Ana", valido_ate=meio)
        registrar_preco(a, EQ, "cavaco", 220.0, meio, "contrato 2", "Ana")
        p = preco_do_periodo(a, EQ, pacote, s[1][0], s[1][1], "tabela_de_precos")
        assert 180 < p["preco_brl_t"] < 220
        assert (p["preco_min_brl_t"], p["preco_max_brl_t"]) == (180.0, 220.0)
        assert p["rateio"] == "vapor medido em cada trecho"
        v = [t["vapor_t"] for t in p["trechos"]]
        assert p["preco_brl_t"] == pytest.approx((v[0] * 180 + v[1] * 220) / (v[0] + v[1]))
        assert "entre R$ 180,00 e R$ 220,00/t" in p["motivo"]
        # um só preço cobre o primeiro período: vale ele, sem rateio
        assert preco_do_periodo(a, EQ, pacote, s[0][0], s[0][1], "tabela_de_precos")[
            "preco_brl_t"
        ] == pytest.approx(180.0)
        # o fechamento usa o preço rateado e guarda os limites como cenários de preço
        a.configurar(EQ, {"politica_custo": "tabela_de_precos"}, autor="Ana")
        criar_referencia(a, EQ, s[0][0], s[0][1], "inicial", "Base", "Ana")
        f = produzir_fechamento(a, EQ, "Ana")
        n = f["resultado"]["nucleo"]
        assert n["politica_custo"]["preco_brl_t"] == pytest.approx(p["preco_brl_t"])
        assert n["explicacao_conta"]["desvio"]["cenarios_preco_brl"] is not None
    finally:
        a.fechar()


def test_buraco_na_tabela_deixa_o_preco_ausente_com_o_motivo(tmp_path):
    a, s = planta_com(tmp_path, [Periodo(G01), Periodo(G01)])
    try:
        pacote = a.pacote(EQ)
        meio = _meio(s[1]).normalize()
        registrar_preco(a, EQ, "cavaco", 180.0, s[0][0], "contrato 1", "Ana", valido_ate=meio)
        registrar_preco(a, EQ, "cavaco", 220.0, meio + pd.Timedelta(days=1), "contrato 2", "Ana")
        p = preco_do_periodo(a, EQ, pacote, s[1][0], s[1][1], "tabela_de_precos")
        assert p["preco_brl_t"] is None
        assert "sem preço de" in p["motivo"] and "começando no dia" in p["motivo"]
    finally:
        a.fechar()


def _conta(**k):
    base = {
        "combustivel_ref_t": 100.0,
        "vapor_ref_t": 300.0,
        "combustivel_t": 120.0,
        "vapor_t": 330.0,
        "preco_ref_brl_t": 150.0,
        "preco_brl_t": 165.0,
        "incerteza_consumo_t_t": 0.001,
    }
    return explicar_conta(**{**base, **k})


def test_ponte_responde_producao_preco_e_consumo():
    from euler.conta import conclusao_financeira

    q = conclusao_financeira(_conta(), dias={"referencia": 28.0, "comparacao": 28.0})
    ponte = q["ponte"]
    assert ponte["disponivel"]
    r = ponte["resposta"]
    assert r.startswith("Em relação à referência, a conta subiu")
    for trecho in (
        "pela produção de vapor",
        "pelo preço do combustível",
        "pelo consumo nas condições comparadas",
    ):
        assert trecho in r
    # a ordem é a do tamanho de cada parcela
    valores = {g["id"]: abs(g["custo_brl"]) for g in ponte["grupos"] if g["custo_brl"] is not None}
    maior = max(valores, key=valores.get)
    primeira = r.split(": ", 1)[1]
    assert {
        "producao": "produção",
        "preco": "preço",
        "sem_explicacao": "consumo",
    }[maior] in primeira.split(";")[0]
    # o que não foi separado aparece dito
    assert "condição do vapor e da água" in r and "qualidade do combustível" in r


def test_resposta_da_ponte_com_conta_que_caiu():
    grupos = [
        {"id": "preco", "custo_brl": -1000.0, "nota": None},
        {
            "id": "producao",
            "custo_brl": -5000.0,
            "nota": "inclui a diferença de duração (28 → 14 dias)",
        },
        {"id": "ajustes", "custo_brl": None, "nota": None},
        {"id": "sem_explicacao", "custo_brl": 300.0, "nota": "igual à diferença"},
    ]
    r = resposta_da_ponte(grupos, -5700.0)
    assert r.startswith("Em relação à referência, a conta caiu R$ 5.700")
    assert "R$ 5.000 a menos pela produção de vapor — inclui a diferença de duração" in r
    assert "R$ 300 a mais pelo consumo nas condições comparadas." in r
