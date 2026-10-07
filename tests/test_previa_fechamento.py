"""Prévia do próximo fechamento no Painel (D108): a mesma conta do fechamento, rotulada como
prévia e nunca gravada. Dados sintéticos do caso de demonstração."""

import pytest

from euler.fechamento import (
    criar_referencia,
    fechamentos,
    mudanca_de_situacao,
    previa_do_proximo_fechamento,
    produzir_fechamento,
)
from euler.periodos import periodos_entre_estoques
from euler.persistencia import Repositorio
from scripts.medir_escala import CALDEIRA, CORTE, ate, carregar_demo, modelo_euler


@pytest.mark.parametrize(
    ("antes", "novo", "esperado"),
    [
        ("nao_estabelecido", "acima", "saiu_da_faixa"),
        ("nao_estabelecido", "abaixo", "saiu_da_faixa"),
        ("acima", "nao_estabelecido", "voltou_a_faixa"),
        ("acima", "acima", "continua"),
        ("nao_estabelecido", "nao_estabelecido", "continua"),
        ("acima", "abaixo", "indefinida"),
        ("sem_faixa", "acima", "indefinida"),
        (None, "acima", "indefinida"),
        ("acima", None, "indefinida"),
    ],
)
def test_mudanca_de_situacao(antes, novo, esperado):
    assert mudanca_de_situacao(antes, novo) == esperado


def _estado(a):
    return a.revisao, len(fechamentos(a, CALDEIRA)), len(a.eventos(CALDEIRA, limite=100_000))


def test_previa_nao_grava_e_bate_com_o_fechamento(tmp_path):
    dfs = carregar_demo()
    repo = Repositorio(tmp_path)
    planta = repo.criar_planta("Prévia (sintética)", classe="sintetico")
    a = repo.armazem(planta["id"])
    try:
        a.criar_equipamento(CALDEIRA, "Caldeira 1", CALDEIRA, config={"altitude_m": 1000.0})
        a.confirmar(a.previa(CALDEIRA, modelo_euler(ate(dfs, CORTE))[0]), autor="teste")
        assert previa_do_proximo_fechamento(a, CALDEIRA) is None  # sem fechamento ainda
        s = periodos_entre_estoques(a.pacote(CALDEIRA))
        criar_referencia(a, CALDEIRA, s[0][0], s[3][1], "inicial", "Agosto (sintético)", "teste")
        produzir_fechamento(a, CALDEIRA, "teste")
        assert previa_do_proximo_fechamento(a, CALDEIRA) is None  # nada novo para fechar
        # chegam as semanas seguintes
        a.confirmar(a.previa(CALDEIRA, modelo_euler(dfs)[0]), autor="teste")
        vistos = 0
        while True:
            antes = _estado(a)
            prev = previa_do_proximo_fechamento(a, CALDEIRA)
            assert _estado(a) == antes  # a prévia não gravou nada
            if prev is None:
                break
            f = produzir_fechamento(a, CALDEIRA, "teste")
            assert (prev["inicio"], prev["fim"]) == (f["inicio"], f["fim"])
            assert prev["situacao"] == f["resultado"]["situacao"]
            assert prev["revisao_dados"] == f["revisao_dados"]
            if prev["situacao"] is None:
                assert prev["mudanca"] == "indefinida" and "não pode ser feita" in prev["frase"]
            else:
                assert prev["situacao_frase"] in prev["frase"]
            vistos += 1
        assert vistos >= 1
    finally:
        a.fechar()
