"""A navegação compacta não pode deixar telas ou links existentes inacessíveis (D105)."""

import ast
from pathlib import Path

from navegacao import SECOES, secao_de, todas_as_paginas
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"


def test_menu_compacto_preserva_todas_as_rotas_sem_duplicar():
    caminhos = [p[0] for p in todas_as_paginas()]
    assert len(SECOES) <= 5
    assert len(caminhos) == len(set(caminhos))
    assert set(caminhos) == {f"paginas/{p.name}" for p in (APP / "paginas").glob("*.py")}
    # cada tela pertence a exatamente uma seção, e a primeira tela abre a seção
    for nome, _, telas in SECOES:
        assert telas, nome
        for caminho, _, _ in telas:
            assert secao_de(caminho)[0] == nome
    assert SECOES[0][2][0][0] == "paginas/inicio.py"


def test_links_entre_telas_continuam_registrados():
    rotas = {p[0] for p in todas_as_paginas()}
    for arquivo in APP.rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr in {"page_link", "switch_page"}
                and no.args
                and isinstance(no.args[0], ast.Constant)
                and isinstance(no.args[0].value, str)
                and no.args[0].value.startswith("paginas/")
            ):
                assert no.args[0].value in rotas, (arquivo, no.args[0].value)


def _rotulos(elementos):
    return [e.proto.label for e in elementos]


def test_inicio_tem_menu_curto_e_acesso_aos_dados_reais(tmp_path, monkeypatch):
    monkeypatch.setenv("EULER_DADOS_DIR", str(tmp_path / "dados"))
    at = AppTest.from_file(str(APP / "main.py"), default_timeout=90).run()
    assert not at.exception, at.exception
    assert any(t.value == "EULER" for t in at.title)
    menu = _rotulos(at.sidebar.get("page_link"))
    assert menu[: len(SECOES)] == [s[0] for s in SECOES]
    assert not any(e.label == "Mais ferramentas" for e in at.sidebar.expander)
    assert any(
        e.label == "Sobre a demonstração e os limites" and not e.proto.expanded for e in at.expander
    )
    assert at.button(key="ato1")
    assert at.button(key="ato2")
    assert any("660 dias" in m.value for m in at.markdown)


def test_cada_secao_mostra_as_telas_irmas_como_abas(tmp_path, monkeypatch):
    monkeypatch.setenv("EULER_DADOS_DIR", str(tmp_path / "dados"))
    at = AppTest.from_file(str(APP / "main.py"), default_timeout=90).run()
    for nome, _, telas in SECOES:
        if len(telas) < 2:
            continue
        caminho = telas[-1][0]
        at.switch_page(caminho).run()
        assert not at.exception, (caminho, at.exception)
        abas = [e for e in at.main.get("page_link") if e.proto.label in {t[1] for t in telas}]
        assert _rotulos(abas)[: len(telas)] == [t[1] for t in telas], nome
        # no menu lateral, a seção aberta aponta para a tela atual (fica destacada)
        menu = {e.proto.label: e.proto.page for e in at.sidebar.get("page_link")}
        assert menu[nome].endswith(Path(caminho).stem), (nome, menu[nome])
