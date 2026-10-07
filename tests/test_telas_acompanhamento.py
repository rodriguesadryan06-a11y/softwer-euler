"""Ciclo completo pelas telas de acompanhamento, com a planta de demonstração (sintética).

Planta → dados → referência → fechamento → investigação → evidência → ação → avaliação →
encerramento → painel; mais preço e custo de atendimento. Tudo pela interface, no mesmo banco.
"""

import datetime as dt
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from euler.acompanhamento import custos_servico, intervencoes, investigacoes
from euler.fechamento import fechamentos, precos
from euler.persistencia import Repositorio

APP = Path(__file__).resolve().parents[1] / "app"
PAGINAS = (
    "paginas/painel.py",
    "paginas/acompanhamento.py",
    "paginas/fechamentos.py",
    "paginas/acoes.py",
)


@pytest.fixture
def raiz(tmp_path, monkeypatch):
    r = tmp_path / "dados"
    monkeypatch.setenv("EULER_DADOS_DIR", str(r))
    return r


def abrir(pagina: str) -> AppTest:
    at = AppTest.from_file(str(APP / "main.py"), default_timeout=120).run()
    at.switch_page(pagina).run()
    assert not at.exception, at.exception
    return at


def ir(at: AppTest, pagina: str) -> None:
    at.switch_page(pagina).run()
    assert not at.exception, at.exception


def clicar(at: AppTest, rotulo: str) -> None:
    next(b for b in at.button if b.label == rotulo).click().run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]


def campo(lista, rotulo: str):
    return next(x for x in lista if x.label == rotulo)


def textos(at: AppTest) -> str:
    return "\n".join(
        str(x.value)
        for grupo in (at.markdown, at.success, at.info, at.warning, at.caption)
        for x in grupo
    )


@pytest.mark.parametrize("pagina", PAGINAS)
def test_telas_abrem_sem_planta_e_indicam_o_caminho(raiz, pagina):
    at = abrir(pagina)
    if pagina == "paginas/acompanhamento.py":
        assert any(b.label == "Criar planta de demonstração (sintética)" for b in at.button)
    else:
        assert "Nenhuma planta cadastrada" in textos(at)


def test_ciclo_completo_pelas_telas_com_a_planta_de_demonstracao(raiz):
    at = abrir("paginas/acompanhamento.py")
    # sem nome, nada é gravado
    clicar(at, "Criar planta de demonstração (sintética)")
    assert not Repositorio(raiz).listar_plantas()
    assert any("Informe seu nome" in w.value for w in at.warning)

    at.text_input(key="acomp_autor").set_value("Teste de interface").run()
    clicar(at, "Criar planta de demonstração (sintética)")
    assert "Planta de demonstração criada" in textos(at)
    repo = Repositorio(raiz)
    (planta,) = repo.listar_plantas()
    assert planta["classe"] == "sintetico"

    # painel: último fechamento e oportunidade sem soma
    ir(at, "paginas/painel.py")
    t = textos(at)
    # Painel novo (D114): topo, dia a dia e as cinco respostas; detalhes sob demanda
    assert "Dados até 28/09/2026" in t
    assert "Dia a dia" in t and "dentro do comum na referência" in t
    assert any(m.label == "Vapor (vazão média)" for m in at.metric)
    for pergunta in (
        "1 · Quanto custou o combustível consumido?",
        "2 · Quanto seria esperado nas condições comparadas?",
        "3 · Qual diferença ficou estabelecida e o que falta saber?",
        "4 · Qual é a próxima verificação, quem faz e em que pé está?",
        "5 · O que aconteceu depois das ações anteriores?",
    ):
        assert pergunta in t
    assert "Por que a conta mudou" in t
    assert any(m.label == "Economia verificada" and m.value == "nenhuma" for m in at.metric)
    # período completo depois do fechamento: prévia rotulada, sem gravar (D108)
    assert "Prévia · ainda não fechado" in t
    assert "Período completo ainda não fechado: 14/09/2026 a 21/09/2026" in t

    # o nome digitado continua valendo em outra tela
    ir(at, "paginas/fechamentos.py")
    assert at.text_input(key="acomp_autor").value == "Teste de interface"
    assert "Fechamento #1" in textos(at)
    clicar(at, "Abrir investigação deste desvio")
    assert at.session_state["acoes_inv_sel"] == 1

    # investigação: evidência, ação ligada, avaliação, encerramento
    ir(at, "paginas/acoes.py")
    assert "#1 ·" in textos(at)
    campo(at.text_area, "O que foi verificado ou medido").set_value(
        "Umidade da lenha medida na pilha (amostra sintética)"
    )
    clicar(at, "Adicionar evidência")
    assert "Evidência registrada" in textos(at)
    # o formulário volta limpo depois de gravar
    assert campo(at.text_area, "O que foi verificado ou medido").value == ""

    # a primeira ficha de ação é a da investigação aberta (fica ligada a ela)
    campo(at.date_input, "Data da ação").set_value(dt.date(2026, 9, 1))
    campo(at.text_input, "O que foi feito").set_value("Lenha coberta na pilha")
    clicar(at, "Registrar ação")
    assert "Ação registrada" in textos(at)

    clicar(at, "Avaliar agora")
    assert "Avaliação registrada" in textos(at)
    assert any(m.label == "Ações registradas" and m.value == "1" for m in at.metric)

    campo(at.text_input, "Motivo do encerramento").set_value(
        "Umidade dentro do usual; demonstração"
    )
    clicar(at, "Encerrar investigação")
    assert "Investigação encerrada" in textos(at)

    # custo de atendimento
    campo(at.date_input, "Data").set_value(dt.date(2026, 9, 2))
    campo(at.number_input, "Valor (R$)").set_value(350.0)
    campo(at.text_input, "Descrição").set_value("Análise de umidade (sintética)")
    campo(at.text_input, "Origem (nota, contrato)").set_value("orçamento sintético")
    clicar(at, "Registrar custo")

    # tabela de preços
    ir(at, "paginas/acompanhamento.py")
    campo(at.text_input, "Combustível").set_value("lenha")
    campo(at.number_input, "Preço (R$/t)").set_value(180.0)
    campo(at.date_input, "Válido de").set_value(dt.date(2026, 8, 1))
    campo(at.text_input, "Origem (contrato, nota, cotação)").set_value("contrato sintético")
    clicar(at, "Registrar preço")

    ir(at, "paginas/painel.py")
    assert any(m.label == "Encerradas" and m.value == "1" for m in at.metric)

    a = repo.armazem(planta["id"])
    try:
        eq = a.equipamentos()[0]["id"]
        assert len(fechamentos(a, eq)) == 1
        (inv,) = investigacoes(a, eq)
        assert inv["estado"] == "encerrada"
        assert any(e["tipo"] == "evidencia" for e in inv["eventos"])
        (acao,) = intervencoes(a, eq)
        assert acao["investigacao_id"] == inv["id"]
        assert custos_servico(a, eq)[0]["valor_brl"] == 350.0
        assert precos(a, eq)[0]["preco_brl_t"] == 180.0
    finally:
        a.fechar()


def test_atendimento_da_caldeira_no_historico(raiz):
    """Registro de atendimento (T16): caminho até o 1º fechamento e horas da equipe."""
    at = abrir("paginas/acompanhamento.py")
    at.text_input(key="acomp_autor").set_value("Equipe EULER").run()
    clicar(at, "Criar planta de demonstração (sintética)")
    t = textos(at)
    assert "Do primeiro envio ao primeiro fechamento" in t
    # a demonstração é importada sem a tela de conferência: sem medição, não zero
    assert any(m.label == "Tempo na tela de envio" and m.value == "sem medição" for m in at.metric)
    assert "1 envio(s) até o primeiro fechamento; 0 com medição da tela" in t
    assert "Nenhuma hora lançada ainda" in t
    campo(at.date_input, "Dia").set_value(dt.date(2026, 9, 2))
    campo(at.selectbox, "Tarefa").set_value("planilha")
    campo(at.number_input, "Minutos").set_value(40)
    clicar(at, "Lançar atendimento")
    assert "Atendimento lançado" in textos(at)
    assert any(b.label == "Baixar atendimento.csv" for b in at.get("download_button"))
    repo = Repositorio(raiz)
    (planta,) = repo.listar_plantas()
    a = repo.armazem(planta["id"])
    try:
        from euler.atendimento import atendimentos_registrados

        (r,) = atendimentos_registrados(a, a.equipamentos()[0]["id"])
        assert (r["dia"], r["tarefa"], r["minutos"], r["autor"]) == (
            "2026-09-02",
            "planilha",
            40.0,
            "Equipe EULER",
        )
    finally:
        a.fechar()


def test_fechamento_do_mes_pela_tela(raiz):
    """Fechamento mensal (D111): o mês mostra cobertura e lacuna e é aprovado pela tela."""
    at = abrir("paginas/acompanhamento.py")
    at.text_input(key="acomp_autor").set_value("Teste de interface").run()
    clicar(at, "Criar planta de demonstração (sintética)")
    ir(at, "paginas/fechamentos.py")
    t = textos(at)
    assert "Fechamento do mês" in t
    assert at.selectbox(key="fech_mes_sel").value == "2026-09"
    assert "Pronto para fechar" in t
    assert "Lacuna de 14/09 07:30 a 21/09 07:30" in t
    assert "não completa o consumo pelo calendário" in t
    clicar(at, "Aprovar fechamento do mês")
    assert "Fechamento de setembro/2026 aprovado: 2 trecho(s) gravado(s)" in textos(at)
    repo = Repositorio(raiz)
    (planta,) = repo.listar_plantas()
    a = repo.armazem(planta["id"])
    try:
        fs = fechamentos(a, a.equipamentos()[0]["id"])
        assert [f["resultado"].get("mes") for f in fs] == [None, "2026-09", "2026-09"]
    finally:
        a.fechar()
