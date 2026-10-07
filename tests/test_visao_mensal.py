"""O mês escolhido não pode receber números de outro mês."""

from visao_mensal import fechamentos_do_mes, mes_em_foco, orientacao_do_mes


def test_foco_preserva_mes_com_pendencia_e_nao_o_mais_favoravel():
    planos = [
        {"mes": "2026-08", "estado": "fechado"},
        {"mes": "2026-09", "estado": "pronto"},
        {"mes": "2026-10", "estado": "em_andamento"},
    ]
    assert mes_em_foco(planos)["mes"] == "2026-09"
    assert mes_em_foco([]) is None


def test_filtro_nao_substitui_mes_sem_conta_por_mes_anterior():
    fs = [
        {"id": 1, "fim": "2026-09-01T00:00:00-03:00", "resultado": {}},
        {"id": 2, "fim": "2026-09-21T08:00:00-03:00", "resultado": {"mes": "2026-09"}},
    ]
    assert [f["id"] for f in fechamentos_do_mes(fs, "2026-08")] == [1]
    assert [f["id"] for f in fechamentos_do_mes(fs, "2026-09")] == [2]
    assert fechamentos_do_mes(fs, "2026-10") == []


def test_mes_aprovado_nao_pede_aprovacao_de_novo_e_revisao_tem_motivo():
    assert "aprov" not in orientacao_do_mes("fechado")[0].lower()
    assert "motivo" in orientacao_do_mes("revisar")[1].lower()
    assert "prévia" in orientacao_do_mes("pronto")[1].lower()
