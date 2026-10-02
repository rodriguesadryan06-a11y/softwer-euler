"""Smoke tests do motor com telemetria industrial pública não sintética.

Fonte/proveniência: validation/public/manifest.json.
O fixture contém apenas o prefixo declarado como operação real no dataset derivado.
"""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path

import pandas as pd
import pytest

from euler.capacidades import avaliar
from euler.io import importar_pacote
from euler.io.diario import importar_diario
from euler.vapor import h_agua_mj_kg, h_vapor_mj_kg, t_sat_c

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "validation" / "public" / "zhejiang_real_sample.csv"
MANIFESTO = RAIZ / "validation" / "public" / "manifest.json"
BEE = RAIZ / "validation" / "public" / "bee_direct_method_benchmark.json"

PSI_PARA_BAR = 0.0689475729
P_ATM_BAR = 1.01325
KPPH_PARA_T_H = 0.45359237


@pytest.fixture(scope="module")
def real():
    return pd.read_csv(DADOS)


def _bruto_euler(real: pd.DataFrame) -> pd.DataFrame:
    inicio = pd.Timestamp("2022-03-27T14:28:54-03:00")
    return pd.DataFrame(
        {
            "linha": range(2, len(real) + 2),
            "caldeira_id": "PUBLIC-ZHEJIANG-CFB",
            "instante_observado": [
                (inicio + pd.Timedelta(seconds=5 * int(i))).isoformat() for i in real["source_row"]
            ],
            "regime": "estavel",
            "p_vapor_bar_man": real["steam_pressure_psig"] * PSI_PARA_BAR,
            "estado_vapor": "superaquecido",
            "t_vapor_c": _f_para_c(real["steam_temperature_f"]),
            # O₂ é publicado na entrada superior do economizador (lado esquerdo).
            "o2_seco_pct": real["flue_gas_o2_left_pct"],
            "ponto_gases_id": "ECONOMIZADOR-ENTRADA-ESQ",
            "instrumento_o2_id": "AIR_8301A",
            "origem_dado": "publico",
        }
    )


def _p_abs_bar(psig: pd.Series) -> pd.Series:
    return psig * PSI_PARA_BAR + P_ATM_BAR


def _f_para_c(f: pd.Series) -> pd.Series:
    return (f - 32.0) * 5.0 / 9.0


def test_fixture_tem_proveniencia_e_so_linhas_reais_normais(real):
    manifesto = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    assert manifesto["materialized_rows"] == len(real) == 20
    assert set(real["fault_label"]) == {"normal"}
    assert "CC0" in manifesto["provenance"]["original_paper"]["license"]
    assert "CC BY 4.0" in manifesto["provenance"]["materialized_source"]["license"]


def test_conversoes_publicadas_geram_estado_fisico_plausivel(real):
    p_abs = _p_abs_bar(real["steam_pressure_psig"])
    t_vapor = _f_para_c(real["steam_temperature_f"])
    vazao = real["steam_flow_kpph"] * KPPH_PARA_T_H
    t_gases = _f_para_c(real["flue_gas_temp_f"])

    assert p_abs.between(90, 100).all()
    assert vazao.between(50, 70).all()
    assert t_gases.between(300, 400).all()
    assert real["flue_gas_o2_left_pct"].between(0, 21).all()
    assert real["flue_gas_o2_right_pct"].between(0, 21).all()

    # A publicação original define 530–545 °C como a faixa normal do KPI.
    assert t_vapor.between(530, 545).all()


def test_if97_aceita_todas_as_linhas_reais_como_vapor_superaquecido(real):
    for linha in real.itertuples(index=False):
        p_abs = linha.steam_pressure_psig * PSI_PARA_BAR + P_ATM_BAR
        t_vapor = (linha.steam_temperature_f - 32.0) * 5.0 / 9.0
        assert t_vapor > t_sat_c(p_abs)
        h = h_vapor_mj_kg(p_abs, "superaquecido", t_vapor_c=t_vapor)
        assert isfinite(h)
        assert 2.0 < h < 4.0


def test_importador_euler_aceita_recorte_real_apos_conversao_explicita(real):
    imp = importar_diario(_bruto_euler(real), p_atm_bar=P_ATM_BAR)
    assert not imp.bloqueada
    assert len(imp.dados) == len(real)
    assert imp.dados["estado_vapor"].eq("superaquecido").all()
    assert imp.dados["p_vapor_bar_abs"].notna().all()
    assert imp.dados["t_vapor_c"].between(530, 545).all()


def test_fixture_nao_e_usado_para_inventar_eficiencia_global(real):
    """A ausência de combustível/feedwater é uma limitação do dado, não valor zero."""
    colunas = set(real.columns)
    requeridas_para_balanco_completo = {
        "fuel_mass",
        "fuel_pci",
        "feedwater_temperature",
    }
    assert requeridas_para_balanco_completo.isdisjoint(colunas)


def test_euler_se_abstem_do_balanco_completo_com_telemetria_real_incompleta(real):
    pacote = importar_pacote({"diario": _bruto_euler(real)}, p_atm_bar=P_ATM_BAR)
    assert pacote.origens_de_dado() == {"publico"}
    assert not pacote.sintetico

    caps = {c.id: c for c in avaliar(pacote)}
    assert caps["registros"].habilitada
    assert caps["energia_vapor"].situacao == "bloqueada"
    assert any("totalizador" in m.lower() for m in caps["energia_vapor"].motivos)
    assert any("água de alimentação" in m.lower() for m in caps["energia_vapor"].motivos)
    assert caps["eficiencia_direta"].situacao == "bloqueada"


def test_if97_confere_com_entalpias_publicadas_pelo_bee():
    """Benchmark externo; não compara eficiência porque BEE usa GCV e EULER usa PCI."""
    caso = json.loads(BEE.read_text(encoding="utf-8"))["published"]
    p_abs = caso["steam_pressure_kgf_cm2_g"] * 0.980665 + P_ATM_BAR
    h_steam_kcal_kg = h_vapor_mj_kg(p_abs, "saturado_seco") * 1000 / 4.1868
    h_fw_kcal_kg = h_agua_mj_kg(p_abs, caso["feedwater_temperature_c"]) * 1000 / 4.1868

    assert h_steam_kcal_kg == pytest.approx(caso["steam_enthalpy_kcal_kg"], rel=0.015)
    assert h_fw_kcal_kg == pytest.approx(caso["feedwater_enthalpy_kcal_kg"], rel=0.015)
