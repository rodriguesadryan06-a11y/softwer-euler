"""Fechamento mensal (D111): mês, cobertura, prévia, aprovação, ordem e revisão.

Planta de demonstração (sintética): agosto é a referência; setembro tem uma semana sem
vapor conhecido (o totalizador reiniciou), que vira lacuna registrada.
"""

from pathlib import Path

import pandas as pd
import pytest

from euler.armazem import ErroArmazem
from euler.fechamento import (
    criar_referencia,
    fechamentos,
    fechamentos_vigentes,
    produzir_fechamento,
    revisoes,
)
from euler.linha_do_tempo import linha_do_tempo
from euler.mensal import (
    chave_do_mes,
    fechar_mes,
    meses,
    plano_do_mes,
    previa_do_mes,
    resumo_do_mes,
    revisar_mes,
)
from euler.periodos import periodos_entre_estoques
from euler.persistencia import Repositorio

RAIZ = Path(__file__).resolve().parents[1]
DEMO = RAIZ / "demo" / "caso_demo_completo"
EQ = "CALD-DEMO-01"
OUTUBRO = pd.Timestamp("2026-10-07T12:00:00-03:00")


def _planta(tmp_path, fim_referencia: int = 3):
    repo = Repositorio(tmp_path)
    planta = repo.criar_planta("Mensal (sintético)", classe="sintetico")
    a = repo.armazem(planta["id"])
    a.criar_equipamento(EQ, "Caldeira A", EQ, config={"altitude_m": 1000.0}, autor="Teste")
    arquivos = {p.name: p.read_bytes() for p in DEMO.glob("*.csv")}
    a.confirmar(a.previa(EQ, arquivos), autor="Teste")
    s = periodos_entre_estoques(a.pacote(EQ))
    criar_referencia(a, EQ, s[0][0], s[fim_referencia][1], "inicial", "Base", "Teste")
    return a, arquivos


@pytest.mark.parametrize(
    ("instante", "mes"),
    [
        ("2026-09-14T07:30:00-03:00", "2026-09"),
        ("2026-10-01T00:00:00-03:00", "2026-09"),  # termina à 0h do dia 1: mês anterior
        ("2026-10-01T00:00:01-03:00", "2026-10"),
        ("2026-10-01T02:00:00+00:00", "2026-09"),  # 23h de 30/09 no horário da planta
    ],
)
def test_cada_periodo_pertence_ao_mes_em_que_termina(instante, mes):
    assert chave_do_mes(instante) == mes


def test_mes_a_mes_com_previa_aprovacao_e_revisao(tmp_path):
    a, arquivos = _planta(tmp_path)
    try:
        planos = {m["mes"]: m for m in meses(a, EQ, OUTUBRO)}
        assert planos["2026-08"]["estado"] == "referencia"
        assert planos["2026-10"]["estado"] == "em_andamento"
        set_ = planos["2026-09"]
        assert set_["estado"] == "pronto"
        assert [(t["valido"], t["periodos"]) for t in set_["trechos"]] == [
            (True, 2),
            (False, 1),
            (True, 1),
        ]
        cob = set_["cobertura"]
        assert cob["dias_de_outro_mes"] == pytest.approx(0.6875)  # 31/08 07:30 → 01/09
        assert cob["dias_para_o_mes_seguinte"] == pytest.approx(2.6875)  # 28/09 07:30 → 01/10
        assert cob["dias_com_conta"] == pytest.approx(13.3125 + 7)  # a lacuna não tem conta
        frases = " ".join(cob["frases"])
        assert "não completa o consumo pelo calendário" in frases
        assert "Lacuna de 14/09 07:30 a 21/09 07:30" in frases

        # mês ainda em andamento: só prévia
        with pytest.raises(ErroArmazem, match="ainda não terminou"):
            fechar_mes(a, EQ, "2026-09", "Teste", agora=pd.Timestamp("2026-09-29T12:00-03:00"))

        # prévia não grava nada e bate com o fechamento aprovado
        antes = (a.revisao, len(fechamentos(a, EQ)), len(a.eventos(EQ, limite=100_000)))
        prev = previa_do_mes(a, EQ, "2026-09", OUTUBRO)
        assert (a.revisao, len(fechamentos(a, EQ)), len(a.eventos(EQ, limite=100_000))) == antes
        fs = fechar_mes(a, EQ, "2026-09", "Teste", OUTUBRO)
        assert [f["resultado"]["mes"] for f in fs] == ["2026-09"] * 3
        assert [p["situacao"] for p in prev["previas"]] == [f["resultado"]["situacao"] for f in fs]
        assert fs[1]["resultado"]["situacao"] is None  # a lacuna fica registrada, sem conta
        assert plano_do_mes(a, EQ, "2026-09", OUTUBRO)["estado"] == "fechado"
        resumo = resumo_do_mes(a, EQ, "2026-09", OUTUBRO)
        assert resumo["estado"] == "fechado"
        assert resumo["completo"] is False  # aprovado não quer dizer sem lacuna
        assert resumo["trechos_com_valor"] == 2
        assert resumo["periodos_pendentes"] == 0
        assert resumo["cobertura"]["dias_com_conta"] == pytest.approx(20.3125)
        assert resumo["cobertura"]["dias_com_valor"] == pytest.approx(20.3125)
        assert resumo["cobertura"]["dias_do_mes"] == 30
        for t, f in zip(resumo["trechos"], fs, strict=True):
            assert t["autor"] == "Teste"
            assert t["criado_em"] == f["criado_em"]
            assert t["revisao_dados"] == f["revisao_dados"]
            assert t["referencia_versao"] == 1
            assert t["revisa"] is None
        assert resumo["lacunas"][0]["motivo"]
        assert resumo["motivos"]
        valor_original = resumo["consumido_brl"]
        with pytest.raises(ErroArmazem, match="fechados"):
            fechar_mes(a, EQ, "2026-09", "Teste", OUTUBRO)

        # correção de um recebimento de 22/09 depois da aprovação: o mês pede revisão
        comb = pd.read_csv(DEMO / "combustivel.csv", dtype=str, keep_default_na=False)
        comb.loc[comb["lote_id"] == "L-0195", "massa_kg"] = "28460"
        corrigido = {**arquivos, "combustivel.csv": comb.to_csv(index=False).encode()}
        a.confirmar(a.previa(EQ, corrigido), "Teste", "correcao", "Nota fiscal corrigida")
        plano = plano_do_mes(a, EQ, "2026-09", OUTUBRO)
        assert plano["estado"] == "revisar"
        assert plano["a_revisar"] == [fs[2]["id"]]  # só o trecho de 21/09 a 28/09
        pendente = resumo_do_mes(a, EQ, "2026-09", OUTUBRO)
        assert pendente["estado"] == "revisar"
        assert pendente["a_revisar"] == [fs[2]["id"]]
        assert pendente["consumido_brl"] == valor_original  # não recalcula em silêncio
        with pytest.raises(ErroArmazem, match="motivo"):
            revisar_mes(a, EQ, "2026-09", "Teste", " ", OUTUBRO)
        (novo,) = revisar_mes(a, EQ, "2026-09", "Teste", "Nota fiscal corrigida", OUTUBRO)
        assert novo["resultado"]["revisa"] == fs[2]["id"]
        assert novo["resultado"]["motivo_revisao"] == "Nota fiscal corrigida"
        assert revisoes(a, EQ) == {fs[2]["id"]: novo["id"]}
        # a versão antiga fica no histórico, fora da lista em vigor e da linha do tempo
        assert [f["id"] for f in fechamentos(a, EQ)] == [
            fs[0]["id"],
            fs[1]["id"],
            fs[2]["id"],
            novo["id"],
        ]
        assert [f["id"] for f in fechamentos_vigentes(a, EQ)] == [
            fs[0]["id"],
            fs[1]["id"],
            novo["id"],
        ]
        assert len(linha_do_tempo(a, EQ)["periodos"]) == 3
        assert plano_do_mes(a, EQ, "2026-09", OUTUBRO)["estado"] == "fechado"
        revisado = resumo_do_mes(a, EQ, "2026-09", OUTUBRO)
        assert revisado["trechos"][-1]["revisa"] == fs[2]["id"]
        assert revisado["trechos"][-1]["motivo_revisao"] == "Nota fiscal corrigida"
        assert revisado["trechos"][-1]["criado_em"] == novo["criado_em"]
        assert revisado["fechamentos"] == [fs[0]["id"], fs[1]["id"], novo["id"]]
        assert revisado["consumido_brl"] == sum(
            f["resultado"]["nucleo"]["explicacao_conta"]["consumido"]["custo_brl"]
            for f in (fs[0], novo)
        )
    finally:
        a.fechar()


def test_meses_sao_fechados_na_ordem(tmp_path):
    """Referência só até 17/08: o fim de agosto fica aberto e setembro espera."""
    a, _ = _planta(tmp_path, fim_referencia=1)
    try:
        assert plano_do_mes(a, EQ, "2026-08", OUTUBRO)["estado"] == "pronto"
        setembro = plano_do_mes(a, EQ, "2026-09", OUTUBRO)
        assert setembro["estado"] == "aguarda_anterior"
        with pytest.raises(ErroArmazem, match="na ordem"):
            fechar_mes(a, EQ, "2026-09", "Teste", OUTUBRO)
    finally:
        a.fechar()


def test_resumo_sem_preco_preserva_ausencia_e_explica_o_motivo(tmp_path):
    a, _ = _planta(tmp_path)
    try:
        a.configurar(EQ, {"politica_custo": "tabela_de_precos"}, autor="Teste")
        fechar_mes(a, EQ, "2026-09", "Teste", OUTUBRO)
        resumo = resumo_do_mes(a, EQ, "2026-09", OUTUBRO)
        assert resumo["consumido_brl"] is None
        assert resumo["esperado_brl"] is None
        assert resumo["diferenca_brl"] is None
        assert resumo["combustivel_t"] > 0
        assert resumo["trechos_com_valor"] == 0
        assert resumo["completo"] is False
        assert resumo["cobertura"]["dias_com_valor"] == 0  # cobertura, não custo
        assert resumo["cobertura"]["dias_com_conta"] > 0
        for trecho in resumo["trechos"]:
            assert trecho["valoracao_disponivel"] is False
            if trecho["conta_disponivel"]:
                assert "Nenhum preço da tabela" in trecho["motivo"]
        assert any("Nenhum preço da tabela" in m for m in resumo["motivos"])
    finally:
        a.fechar()


def test_resumo_de_mes_parcial_nao_se_apresenta_como_completo(tmp_path):
    a, _ = _planta(tmp_path)
    try:
        assert resumo_do_mes(a, EQ, "2026-09", OUTUBRO) is None
        periodos = periodos_entre_estoques(a.pacote(EQ))
        f = produzir_fechamento(a, EQ, "Operador", periodos[4][0], periodos[5][1], mes="2026-09")
        resumo = resumo_do_mes(a, EQ, "2026-09", OUTUBRO)
        assert resumo["estado"] == "pronto"
        assert resumo["completo"] is False
        assert resumo["periodos_pendentes"] == 2
        assert resumo["trechos_com_valor"] == 1
        assert resumo["cobertura"]["dias_com_conta"] == pytest.approx(13.3125)
        assert resumo["cobertura"]["dias_com_valor"] == pytest.approx(13.3125)
        assert (
            resumo["consumido_brl"]
            == (f["resultado"]["nucleo"]["explicacao_conta"]["consumido"]["custo_brl"])
        )
        assert any("sem aprovação" in m for m in resumo["motivos"])
    finally:
        a.fechar()
