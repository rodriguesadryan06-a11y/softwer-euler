"""Escolha de datas por clique: limites de estoque, navegação e isolamento dos dados."""

import pytest
from test_app import abrir_com_demo


def _escolher(at, tipo, inicio, fim):
    at.selectbox(key=f"periodo_{tipo}_inicio").set_value(inicio).run()
    assert not at.exception, at.exception
    at.selectbox(key=f"periodo_{tipo}_fim").set_value(fim).run()
    assert not at.exception, at.exception


def _intervalo(at, tipo):
    return tuple(at.selectbox(key=f"periodo_{tipo}_{limite}").value for limite in ("inicio", "fim"))


def test_datas_por_clique_atualizam_analise_e_sobrevivem_a_navegacao():
    at = abrir_com_demo("investigacao.py")
    assert not at.select_slider
    assert at.selectbox(key="periodo_ref_inicio").options[0] == "03/08/2026 07:30"
    assert at.selectbox(key="periodo_comp_fim").options[-1] == "28/09/2026 07:30"
    _escolher(at, "ref", 1, 2)
    _escolher(at, "comp", 5, 7)
    j = at.session_state["investigacao"]["json"]
    assert j["periodos"]["referencia"]["rotulo"] == "10/08/2026 07:30 a 24/08/2026 07:30"
    assert j["periodos"]["comparacao"]["rotulo"] == "07/09/2026 07:30 a 28/09/2026 07:30"
    at.run()
    assert _intervalo(at, "ref") == (1, 2)
    assert _intervalo(at, "comp") == (5, 7)
    at.switch_page("paginas/relatorio.py").run()
    assert any("07/09/2026 07:30 a 28/09/2026 07:30" in c.value for c in at.caption)
    at.switch_page("paginas/investigacao.py").run()
    assert _intervalo(at, "ref") == (1, 2)
    assert _intervalo(at, "comp") == (5, 7)
    _escolher(at, "comp", 6, 6)
    assert at.session_state["periodos_escolhidos"]["comp"] == (6, 6)


def test_inicio_novo_limita_o_fim_e_sobreposicao_descarta_resultado():
    at = abrir_com_demo("investigacao.py")
    at.selectbox(key="periodo_comp_inicio").set_value(7).run()
    assert not at.exception, at.exception
    assert _intervalo(at, "comp") == (7, 7)
    assert at.selectbox(key="periodo_comp_fim").options == ["28/09/2026 07:30"]
    at.selectbox(key="periodo_ref_fim").set_value(7).run()
    assert any("se sobrepõem" in w.value for w in at.warning)
    assert "investigacao" not in at.session_state
    at.selectbox(key="periodo_ref_fim").set_value(3).run()
    assert not at.exception, at.exception
    assert "investigacao" in at.session_state


def test_mudar_dados_com_controles_na_tela_reinicia_datas():
    at = abrir_com_demo("investigacao.py")
    _escolher(at, "comp", 7, 7)
    assinatura = at.session_state["periodos_escolhidos"]["assinatura"]
    # Mesmas datas, outro conjunto: o estado visual também precisa ser reiniciado.
    at.session_state["arquivos"] = tuple(
        (nome, dados.replace(b"sintetico", b"sintetico "))
        for nome, dados in at.session_state["arquivos"]
    )
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["periodos_escolhidos"]["assinatura"] != assinatura
    assert _intervalo(at, "ref") == (0, 3)
    assert _intervalo(at, "comp") == (4, 5)


@pytest.mark.parametrize("referencia", [(-1, 3), (0, 99), (3, 1), (None, 3)])
def test_escolha_salva_invalida_nao_cria_controle_fora_dos_limites(referencia):
    at = abrir_com_demo("investigacao.py")
    salvo = at.session_state["periodos_escolhidos"]
    at.session_state["periodos_escolhidos"] = {**salvo, "ref": referencia}
    at.run()
    assert not at.exception, at.exception
    assert _intervalo(at, "ref") == (0, 3)
    assert _intervalo(at, "comp") == (4, 5)
