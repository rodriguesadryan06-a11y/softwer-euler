"""Envio real de bytes pelo formulário, com confirmação antes da troca da sessão."""

import io
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest


class Arquivo(io.BytesIO):
    name = "diario.csv"


def clicar(at, rotulo):
    next(b for b in at.button if b.label == rotulo).click().run()
    assert not at.exception, at.exception


def test_guia_confirma_previa_e_invalida_quando_conteudo_muda(tmp_path, monkeypatch):
    monkeypatch.setenv("EULER_DADOS_DIR", str(tmp_path / "dados"))
    arquivo = Arquivo(
        b"caldeira_id,instante_observado,vazao_vapor_t_h,origem_dado\nB1,2026-10-01 08:00,2,publico\n"
    )
    enviados = [arquivo]
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: enviados)
    app = Path(__file__).resolve().parents[1] / "app/main.py"
    at = AppTest.from_file(str(app), default_timeout=90).run()
    at.switch_page("paginas/importar.py").run()
    assert not at.exception, at.exception
    assert next(b for b in at.button if b.label == "Importar os arquivos enviados").disabled
    next(c for c in at.checkbox if c.label.startswith("Conferi as colunas")).check().run()
    clicar(at, "Preparar prévia")
    assert any(e.label == "O que estes dados permitem analisar" for e in at.expander)
    assert not next(b for b in at.button if b.label == "Importar os arquivos enviados").disabled
    clicar(at, "Importar os arquivos enviados")
    salvos = dict(at.session_state["arquivos"])
    assert "euler_importacao.json" in salvos
    assert salvos["original_01.bin"] == arquivo.getvalue()
    # Mesmo nome e outro conteúdo: não reaproveitar a confirmação nem a prévia.
    enviados[:] = [Arquivo(arquivo.getvalue().replace(b",2,publico", b",3,publico"))]
    at.run()
    assert not at.exception, at.exception
    assert next(b for b in at.button if b.label == "Importar os arquivos enviados").disabled
    assert dict(at.session_state["arquivos"]) == salvos


def test_planilha_de_fabrica_com_titulo_entra_pela_tela(tmp_path, monkeypatch):
    """Excel com título em cima, Data e Hora separadas e unidades de fábrica (D106)."""
    from test_planilha_real import planilha_da_fabrica

    class Planilha(io.BytesIO):
        name = "caldeira.xlsx"

    monkeypatch.setenv("EULER_DADOS_DIR", str(tmp_path / "dados"))
    # bytes gerados uma vez: o Excel grava a hora de criação, e outro conteúdo desfaz a confirmação
    conteudo = planilha_da_fabrica()
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: [Planilha(conteudo)])
    app = Path(__file__).resolve().parents[1] / "app/main.py"
    at = AppTest.from_file(str(app), default_timeout=90).run()
    at.switch_page("paginas/importar.py").run()
    assert not at.exception, at.exception
    assert [n.value for n in at.number_input if n.label.startswith("Linha do cabeçalho")] == [4, 1]
    assert any(c.label.startswith("Juntar “Data” + “Hora”") and c.value for c in at.checkbox)
    for s in at.selectbox:
        if s.label == "Origem de todos os registros desta tabela":
            s.set_value("sintetico")
        elif s.label == "O que todas as linhas representam?":
            s.set_value("recebimento")
    next(t for t in at.text_input if t.label.startswith("Código da caldeira")).input("CALD-1")
    at.run()
    assert any("O que a EULER entendeu" in m.value for m in at.markdown)
    next(c for c in at.checkbox if c.label.startswith("Conferi as colunas")).check().run()
    clicar(at, "Preparar prévia")
    clicar(at, "Importar os arquivos enviados")
    salvos = dict(at.session_state["arquivos"])
    assert {"diario.csv", "combustivel.csv", "euler_importacao.json"} <= set(salvos)
    assert b"9.80665" in salvos["diario.csv"] or b"8.33565" in salvos["diario.csv"]


def test_mes_por_aba_e_cabecalho_duplo_pela_tela(tmp_path, monkeypatch):
    """Um mês por aba e cabeçalho em duas linhas (D107): a tela junta as abas e o
    manifesto guarda o que foi sugerido e o que a pessoa ajustou (T16)."""
    from test_planilha_real import planilha_mes_por_aba

    from app.importacao_guiada import ajustes_do_lote

    class Planilha(io.BytesIO):
        name = "mensal.xlsx"

    monkeypatch.setenv("EULER_DADOS_DIR", str(tmp_path / "dados"))
    conteudo = planilha_mes_por_aba()
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: [Planilha(conteudo)])
    app = Path(__file__).resolve().parents[1] / "app/main.py"
    at = AppTest.from_file(str(app), default_timeout=90).run()
    at.switch_page("paginas/importar.py").run()
    assert not at.exception, at.exception
    duplos = [c.value for c in at.checkbox if c.label.startswith("Cabeçalho em duas linhas")]
    assert duplos == [True, True, False, False]
    assert any("2 fontes vão para" in i.value for i in at.info)
    tipos = [s.value for s in at.selectbox if s.label == "O que todas as linhas representam?"]
    assert tipos == ["recebimento", "estoque"]  # pelo nome das abas
    for s in at.selectbox:
        if s.label == "Origem de todos os registros desta tabela":
            s.set_value("sintetico")
    for t in at.text_input:
        if t.label.startswith("Código da caldeira"):
            t.input("CALD-1")
    at.run()
    next(c for c in at.checkbox if c.label.startswith("Conferi as colunas")).check().run()
    clicar(at, "Preparar prévia")
    clicar(at, "Importar os arquivos enviados")
    salvos = dict(at.session_state["arquivos"])
    # nesta tela avulsa não há planta: origem (4 abas) e caldeira (2 abas) são declaradas
    assert ajustes_do_lote(salvos) == {
        "tabela": 0,
        "cabecalho": 0,
        "data_hora": 0,
        "colunas": 0,
        "unidades": 0,
        "valores_unicos": 6,
        "total": 6,
        "fontes": 4,
    }
    assert salvos["diario.csv"].count(b"\n") == 5  # cabeçalho + 2 linhas de agosto + 2 de setembro
