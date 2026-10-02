"""Arquitetura adaptativa: a EULER trabalha com o que a planta realmente mede."""

from __future__ import annotations

import pandas as pd
import pytest

from euler.fluxos import balanco_por_vazoes
from euler.io import fontes_de_arquivos, importar_pacote
from euler.io.diario import importar_diario
from euler.planta import mapear_planta


def _diario(**extras) -> pd.DataFrame:
    base = {
        "linha": [2, 3, 4],
        "caldeira_id": ["C1", "C1", "C1"],
        "instante_observado": [
            "2026-10-01T08:00:00-03:00",
            "2026-10-01T09:00:00-03:00",
            "2026-10-01T10:00:00-03:00",
        ],
        "regime": ["estavel", "estavel", "estavel"],
        "origem_dado": ["real", "real", "real"],
    }
    base.update(extras)
    return pd.DataFrame(base)


def test_aliases_unitarios_entram_sem_apagar_original():
    bruto = _diario(
        steam_pressure_bar_g=[9.0, 9.0, 9.0],
        steam_temperature_c=[250.0, 250.0, 250.0],
        steam_flow_t_h=[10.0, 10.0, 10.0],
        feedwater_temperature_c=[80.0, 80.0, 80.0],
        fuel_flow_kg_h=[2000.0, 2000.0, 2000.0],
        fuel_pci_mj_kg=[15.0, 15.0, 15.0],
    )
    imp = importar_diario(bruto, p_atm_bar=1.01325)
    assert not imp.bloqueada
    assert imp.dados["vazao_vapor_t_h"].eq(10.0).all()
    assert imp.dados["vazao_combustivel_kg_h"].eq(2000.0).all()
    assert imp.dados["pci_combustivel_mj_kg"].eq(15.0).all()
    assert "steam_flow_t_h" in imp.original.columns
    assert any(a.tipo == "alias_coluna" for a in imp.avisos)


def test_mapa_nao_exige_banco_de_dados_completo_para_ser_util():
    pacote = importar_pacote(
        {
            "diario": _diario(
                t_gases_c=[180.0, 190.0, 205.0],
                o2_seco_pct=[7.0, 7.2, 7.4],
            )
        },
        p_atm_bar=1.01325,
    )
    perfil = mapear_planta(pacote)
    assert perfil.rota("tendencias").situacao == "disponivel"
    assert perfil.rota("perda_gases").situacao == "parcial"
    assert perfil.rota("eficiencia_direta").situacao != "disponivel"


def test_p_e_t_do_vapor_abrem_rota_termica_mesmo_sem_patio():
    pacote = importar_pacote(
        {
            "diario": _diario(
                p_vapor_bar_man=[9.0, 9.0, 9.0],
                t_vapor_c=[250.0, 251.0, 249.0],
                vazao_vapor_t_h=[10.0, 10.2, 9.8],
            )
        },
        p_atm_bar=1.01325,
    )
    perfil = mapear_planta(pacote)
    assert perfil.rota("estado_vapor").situacao == "disponivel"
    assert perfil.rota("entalpia_vapor").situacao == "disponivel"
    assert perfil.rota("energia_combustivel").situacao == "indisponivel"


def test_balanco_por_vazoes_fecha_sem_estoque_e_sem_totalizador():
    imp = importar_diario(
        _diario(
            p_vapor_bar_man=[9.0, 9.0, 9.0],
            estado_vapor=["superaquecido", "superaquecido", "superaquecido"],
            t_vapor_c=[250.0, 250.0, 250.0],
            t_agua_alim_c=[80.0, 80.0, 80.0],
            vazao_vapor_t_h=[10.0, 10.0, 10.0],
            vazao_combustivel_kg_h=[2000.0, 2000.0, 2000.0],
            pci_combustivel_mj_kg=[15.0, 15.0, 15.0],
        ),
        p_atm_bar=1.01325,
    )
    b = balanco_por_vazoes(imp.dados)
    assert b.cobertura == pytest.approx(1.0)
    assert b.intervalos_usados == 2
    assert 0.70 < b.eficiencia < 0.95
    assert b.energia_vapor_gj > 0
    assert b.energia_combustivel_gj > b.energia_vapor_gj


def test_balanco_por_vazoes_nao_atravessa_lacuna_grande():
    bruto = _diario(
        p_vapor_bar_man=[9.0, 9.0, 9.0],
        estado_vapor=["superaquecido", "superaquecido", "superaquecido"],
        t_vapor_c=[250.0, 250.0, 250.0],
        t_agua_alim_c=[80.0, 80.0, 80.0],
        vazao_vapor_t_h=[10.0, 10.0, 10.0],
        vazao_combustivel_kg_h=[2000.0, 2000.0, 2000.0],
        pci_combustivel_mj_kg=[15.0, 15.0, 15.0],
    )
    bruto.loc[2, "instante_observado"] = "2026-10-02T09:00:00-03:00"
    imp = importar_diario(bruto, p_atm_bar=1.01325)
    with pytest.raises(Exception, match="Cobertura comum insuficiente|Nenhum intervalo"):
        balanco_por_vazoes(imp.dados, cobertura_minima=0.8)


def test_nome_do_arquivo_nao_precisa_ser_padrao_quando_o_cabecalho_e_inequivoco():
    conteudo = (
        "boiler_id,timestamp,steam_pressure_bar_g,steam_temperature_c,steam_flow_t_h\n"
        "B1,2026-10-01T08:00:00-03:00,9,250,10\n"
    ).encode()
    fontes, avisos = fontes_de_arquivos({"historian_export_october.csv": conteudo})
    assert set(fontes) == {"diario"}
    assert any(a.tipo == "arquivo_inferido" for a in avisos)
