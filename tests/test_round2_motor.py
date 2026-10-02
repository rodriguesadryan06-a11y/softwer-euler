"""Segunda rodada do motor físico: vapor medido, regime, baseline, purga e UA.

Os testes são intencionalmente conservadores: novas camadas só concluem quando os dados
necessários existem; ausência continua sendo ausência, nunca zero.
"""

import pytest
from construtor_caso import Periodo, montar

from euler.baseline import ObservacaoCarga, ajustar_baseline_carga, residual_normalizado
from euler.direto import balanco_direto
from euler.periodos import resumir_periodo
from euler.purga import energia_purga_gj
from euler.tipos import AnaliseBloqueada
from euler.transferencia import ua_economizador
from euler.vapor import delta_h_mj_kg

G01 = 11.773


def _periodo_com_vapor(estado: str, *, t_vapor_c=None, titulo_vapor=None):
    pacote, limites = montar([Periodo(G01, dias=3)])
    diario = pacote.importacoes["diario"].dados
    ini, fim = limites[0]
    sel = (diario["instante_observado"] >= ini) & (diario["instante_observado"] < fim)
    diario.loc[sel, "estado_vapor"] = estado
    diario.loc[sel, "t_vapor_c"] = t_vapor_c
    diario.loc[sel, "titulo_vapor"] = titulo_vapor
    return resumir_periodo(pacote, ini, fim)


def test_vapor_superaquecido_medido_entra_no_balanco_principal():
    r = _periodo_com_vapor("superaquecido", t_vapor_c=250.0)
    b = balanco_direto(r)
    assert b.estado_vapor == "superaquecido"
    assert b.estado_vapor_origem == "medido"
    assert b.delta_h_mj_kg is not None
    p = r.leituras["p_vapor_bar_abs"].media
    t_agua = r.leituras["t_agua_alim_c"].media
    esperado = delta_h_mj_kg(p, "superaquecido", t_agua, t_vapor_c=250.0)
    assert b.delta_h_mj_kg.valor == pytest.approx(esperado)


def test_vapor_umido_com_titulo_medido_reduz_delta_h():
    r = _periodo_com_vapor("umido", titulo_vapor=0.98)
    b = balanco_direto(r)
    assert b.estado_vapor == "umido"
    assert b.estado_vapor_origem == "medido"
    assert b.titulo_vapor == pytest.approx(0.98)
    p = r.leituras["p_vapor_bar_abs"].media
    t_agua = r.leituras["t_agua_alim_c"].media
    assert b.delta_h_mj_kg.valor == pytest.approx(
        delta_h_mj_kg(p, "umido", t_agua, titulo=0.98)
    )
    assert b.delta_h_mj_kg.valor < delta_h_mj_kg(p, "saturado_seco", t_agua)


def test_estado_do_vapor_misto_bloqueia_em_vez_de_fazer_media():
    pacote, limites = montar([Periodo(G01, dias=3)])
    diario = pacote.importacoes["diario"].dados
    ini, fim = limites[0]
    sel = diario.index[
        (diario["instante_observado"] >= ini) & (diario["instante_observado"] < fim)
    ]
    diario.loc[sel, "estado_vapor"] = "saturado_seco"
    diario.loc[sel[len(sel) // 2 :], "estado_vapor"] = "superaquecido"
    diario.loc[sel[len(sel) // 2 :], "t_vapor_c"] = 250.0
    r = resumir_periodo(pacote, ini, fim)
    assert "estado_vapor" in r.bloqueios
    b = balanco_direto(r)
    assert b.eficiencia is None


def test_periodo_com_transitorio_nao_e_apto_para_baseline_estacionario():
    pacote, limites = montar([Periodo(G01, dias=3)])
    diario = pacote.importacoes["diario"].dados
    ini, fim = limites[0]
    sel = diario.index[
        (diario["instante_observado"] >= ini) & (diario["instante_observado"] < fim)
    ]
    diario.loc[sel[0], "regime"] = "transitorio"
    r = resumir_periodo(pacote, ini, fim)
    assert "transitorio" in r.regimes_presentes
    assert r.apto_baseline_carga is False


def test_baseline_carga_recupera_reta_e_recusa_extrapolacao():
    obs = [
        ObservacaoCarga(carga_t_h=x, combustivel_t_h=0.8 + 0.22 * x)
        for x in (5.0, 7.0, 9.0, 11.0, 13.0)
    ]
    modelo = ajustar_baseline_carga(obs)
    assert modelo.intercepto_t_h == pytest.approx(0.8, abs=1e-10)
    assert modelo.inclinacao_t_t == pytest.approx(0.22, abs=1e-10)
    assert modelo.prever_combustivel_t_h(10.0) == pytest.approx(3.0)
    with pytest.raises(AnaliseBloqueada):
        modelo.prever_combustivel_t_h(20.0)


def test_residual_normalizado_so_sai_quando_ha_ruido_de_referencia():
    obs = [
        ObservacaoCarga(carga_t_h=5.0, combustivel_t_h=1.9),
        ObservacaoCarga(carga_t_h=7.0, combustivel_t_h=2.36),
        ObservacaoCarga(carga_t_h=9.0, combustivel_t_h=2.75),
        ObservacaoCarga(carga_t_h=11.0, combustivel_t_h=3.27),
        ObservacaoCarga(carga_t_h=13.0, combustivel_t_h=3.62),
    ]
    modelo = ajustar_baseline_carga(obs)
    z = residual_normalizado(modelo, carga_t_h=9.0, combustivel_t_h=3.2)
    assert z is not None and z > 0


def test_purga_quantificada_usa_entalpia_do_liquido_saturado():
    q = energia_purga_gj(
        massa_purga_kg=1000.0,
        p_bar_abs=10.0,
        t_agua_referencia_c=80.0,
    )
    assert q > 0
    assert q < 1.0


def test_ua_economizador_positivo_e_bloqueia_cruzamento_impossivel():
    r = ua_economizador(
        vazao_agua_t_h=20.0,
        p_agua_bar_abs=10.0,
        t_agua_entrada_c=80.0,
        t_agua_saida_c=120.0,
        t_gases_entrada_c=260.0,
        t_gases_saida_c=170.0,
    )
    assert r.q_mw > 0
    assert r.ua_mw_k > 0
    assert r.delta_t_lm_k > 0

    with pytest.raises(AnaliseBloqueada):
        ua_economizador(
            vazao_agua_t_h=20.0,
            p_agua_bar_abs=10.0,
            t_agua_entrada_c=80.0,
            t_agua_saida_c=190.0,
            t_gases_entrada_c=180.0,
            t_gases_saida_c=170.0,
        )
