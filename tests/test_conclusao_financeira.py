"""Conclusão financeira em um quadro (D101): só reorganiza a conta E16, sem criar números."""

from copy import deepcopy
from math import exp

import pytest

from euler.conta import conclusao_financeira, explicar_conta


def conta(**alteracoes):
    """Referência: 1000 t de combustível para 4000 t de vapor (0,25 t/t), a R$ 300/t.
    Período: 1200 t para 4400 t de vapor, a R$ 350/t."""
    return explicar_conta(
        **{
            "combustivel_ref_t": 1000.0,
            "vapor_ref_t": 4000.0,
            "combustivel_t": 1200.0,
            "vapor_t": 4400.0,
            "preco_ref_brl_t": 300.0,
            "preco_brl_t": 350.0,
            "incerteza_consumo_t_t": 0.001,
            **alteracoes,
        }
    )


def test_conta_do_periodo_refeita_a_mao():
    q = conclusao_financeira(conta())
    assert q["disponivel"]
    # consumido 1200 t × 350; esperado 0,25 × 4400 = 1100 t × 350; diferença 100 t × 350
    assert q["consumido"]["custo_brl"] == pytest.approx(420_000)
    assert q["esperado"]["custo_brl"] == pytest.approx(385_000)
    assert q["sem_explicacao"]["custo_brl"] == pytest.approx(35_000)
    assert q["sem_explicacao"]["combustivel_t"] == pytest.approx(100)


def test_ponte_separa_preco_producao_e_ajustes_e_fecha_a_variacao():
    q = conclusao_financeira(conta(), dias={"referencia": 28.0, "comparacao": 14.0})
    p = q["ponte"]
    assert p["disponivel"]
    # variação 420.000 − 300.000; preço 1000 × (350 − 300); produção (1100 − 1000) × 350
    assert p["variacao_brl"] == pytest.approx(120_000)
    g = {x["id"]: x for x in p["grupos"]}
    assert g["preco"]["custo_brl"] == pytest.approx(50_000)
    assert g["producao"]["custo_brl"] == pytest.approx(35_000)
    assert g["ajustes"]["custo_brl"] is None, "sem ajuste separado não vira zero"
    assert g["sem_explicacao"]["custo_brl"] == pytest.approx(35_000)
    assert "28 → 14 dias" in g["producao"]["nota"]
    assert p["nao_separados"] == ["Condição do vapor e da água", "Qualidade do combustível"]


def test_ajuste_de_qualidade_entra_em_outros_ajustes_e_a_soma_continua_fechando():
    q = conclusao_financeira(conta(efeito_qualidade_pct=5.0))
    e2 = 1100 * exp(0.05)
    g = {x["id"]: x for x in q["ponte"]["grupos"]}
    assert g["ajustes"]["custo_brl"] == pytest.approx((e2 - 1100) * 350)
    assert g["sem_explicacao"]["custo_brl"] == pytest.approx((1200 - e2) * 350)
    soma = sum(x["custo_brl"] for x in q["ponte"]["grupos"] if x["custo_brl"] is not None)
    assert soma == pytest.approx(q["ponte"]["variacao_brl"])
    assert q["sem_explicacao"]["custo_brl"] == pytest.approx(g["sem_explicacao"]["custo_brl"])


def test_parcela_evitavel_nunca_e_preenchida_e_entrada_nao_muda():
    c = conta(efeito_qualidade_pct=5.0)
    original = deepcopy(c)
    q = conclusao_financeira(c)
    assert q["evitavel"]["custo_brl"] is None
    assert q["evitavel"]["situacao"] == "Parcela evitável: não apurada"
    assert "não se somam" in q["evitavel"]["condicao"]
    assert c == original


def test_verificacoes_dizem_onde_o_impacto_aparece_sem_somar():
    ops_investigacao = [
        {
            "id": "umidade_combustivel",
            "titulo": "Combustível mais úmido",
            "prioridade": "alta",
            "impacto": {"custo_brl": 19_000.0, "faixa_brl": [5_000.0, 30_000.0]},
            "verificacao": {"acao": "Conferir a umidade dos lotes.", "distingue": "a × b"},
        },
        {
            "id": "temperatura_gases",
            "titulo": "Mais calor pela chaminé",
            "prioridade": "media",
            "impacto": {"custo_brl": 7_000.0, "faixa_brl": None},
            "verificacao": {"acao": "Conferir o termopar.", "distingue": None},
        },
        {
            "id": "excesso_ar",
            "titulo": "O₂ maior",
            "prioridade": "baixa",
            "impacto": {"custo_brl": 1.0},
            "verificacao": {"acao": "x"},
        },
    ]
    q = conclusao_financeira(conta(efeito_qualidade_pct=5.0), ops_investigacao)
    v = q["evitavel"]["verificacoes"]
    assert [x["id"] for x in v] == ["umidade_combustivel", "temperatura_gases"]
    assert v[0]["onde"] == "na parcela de qualidade do combustível"
    assert v[1]["onde"] == "dentro da diferença sem explicação"
    assert v[0]["impacto_brl"] == 19_000.0 and v[0]["distingue"] == "a × b"
    assert "soma" not in str(q["evitavel"].keys())
    # sem a parcela de qualidade separada, a umidade fica dentro da diferença
    q2 = conclusao_financeira(conta(), ops_investigacao)
    assert q2["evitavel"]["verificacoes"][0]["onde"] == "dentro da diferença sem explicação"


def test_aceita_a_forma_resumida_do_fechamento():
    op_fechamento = {
        "id": "temperatura_gases",
        "titulo": "Mais calor pela chaminé",
        "prioridade": "alta",
        "impacto_brl": 7_000.0,
        "faixa_brl": [6_000.0, 8_000.0],
        "verificacao": "Conferir o termopar.",
    }
    v = conclusao_financeira(conta(), [op_fechamento])["evitavel"]["verificacoes"]
    assert v[0]["acao"] == "Conferir o termopar." and v[0]["faixa_brl"] == [6_000.0, 8_000.0]


def test_diferenca_dentro_da_incerteza_pede_primeiro_confirmar_que_ela_existe():
    q = conclusao_financeira(conta(incerteza_consumo_t_t=0.05))
    assert q["estado"] == "nao_estabelecido"
    assert q["evitavel"]["antes"][0].startswith("Confirmar que a diferença existe")
    q2 = conclusao_financeira(conta(incerteza_consumo_t_t=None))
    assert q2["estado"] == "sem_faixa"
    # motivo padronizado (D110): a falta de incerteza declarada, não "dentro da incerteza"
    assert "sem a incerteza declarada" in q2["evitavel"]["antes"][0]


def test_sem_preco_a_conta_nao_aparece_e_a_ponte_nao_e_inventada():
    q = conclusao_financeira(conta(preco_brl_t=None))
    assert not q["disponivel"] or q["ponte"]["disponivel"] is False
    q3 = conclusao_financeira(conta(preco_ref_brl_t=None))
    assert q3["disponivel"] and not q3["ponte"]["disponivel"] and q3["ponte"]["motivo"]


def test_ponte_que_nao_fecha_nao_e_mostrada():
    c = conta()
    c["variacao"]["variacao_brl"] += 1000
    assert not conclusao_financeira(c)["ponte"]["disponivel"]


def test_conta_indisponivel_devolve_o_motivo():
    q = conclusao_financeira(conta(vapor_t=None))
    assert not q["disponivel"] and "vapor" in q["motivo"]
    assert conclusao_financeira(None)["disponivel"] is False
