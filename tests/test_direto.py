"""Balanço direto (T10): E10, E13 (não circularidade) e E15 (intervalo)."""

import inspect

import pytest
from construtor_caso import Periodo, montar

from euler import combustivel, direto, periodos, vapor
from euler.direto import balanco_direto
from euler.periodos import resumir_periodo

G01 = 11.773


def test_eficiencia_nunca_e_entrada_e13():
    proibidos = ("eficien", "rendimento")
    for modulo in (direto, combustivel, vapor, periodos):
        for nome, funcao in inspect.getmembers(modulo, inspect.isfunction):
            if funcao.__module__ != modulo.__name__:
                continue
            for parametro in inspect.signature(funcao).parameters:
                assert not any(p in parametro.lower() for p in proibidos), (modulo.__name__, nome)
                assert parametro != "eta", (modulo.__name__, nome)
    campos = periodos.ResumoPeriodo.__dataclass_fields__
    assert not any("eficien" in c or "rendimento" in c for c in campos)


@pytest.fixture(scope="module")
def caso():
    return montar([Periodo(G01, outras_perdas_pp=8)])


def test_eficiencia_direta_recupera_o_rendimento_do_caso(caso):
    pacote, limites = caso
    b = balanco_direto(resumir_periodo(pacote, *limites[0]))
    assert b.eficiencia.valor == pytest.approx(1 - (G01 + 8) / 100, abs=0.003)
    assert b.eficiencia.origem == "estimado"


def test_estado_do_vapor_assumido_fica_explicito_no_resultado(caso):
    pacote, limites = caso
    b = balanco_direto(resumir_periodo(pacote, *limites[0]))
    assert b.estado_vapor == "saturado_seco"
    assert b.estado_vapor_origem == "assumido"
    assert b.titulo_vapor == pytest.approx(1.0)
    assert "saturado" in b.fronteira.lower()


def test_resultado_tem_intervalo_quando_ha_incerteza_declarada(caso):
    pacote, limites = caso
    b = balanco_direto(resumir_periodo(pacote, *limites[0]))
    assert b.eficiencia.incerteza is not None
    assert 0.005 < b.eficiencia.incerteza < 0.05
    assert b.sem_incerteza == []


def test_sem_incerteza_declarada_diz_o_que_falta():
    pacote, limites = montar([Periodo(G01)], instrumentos=False)
    b = balanco_direto(resumir_periodo(pacote, *limites[0]))
    assert b.eficiencia is not None and b.eficiencia.incerteza is None
    assert set(b.sem_incerteza) == {"medidor de vapor", "medição de estoque"}


def test_sem_totalizador_bloqueia_com_motivo():
    pacote, limites = montar([Periodo(G01, totalizador=False)])
    b = balanco_direto(resumir_periodo(pacote, *limites[0]))
    assert b.eficiencia is None and b.consumo_t_por_t is None
    assert any("totalizador" in x.motivo for x in b.bloqueios)
