"""Testes de fumaça do app: cada tela abre sem erro e mostra o rodapé de segurança."""

import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from euler.textos import RODAPE_SEGURANCA

APP = Path(__file__).resolve().parents[1] / "app"
PAGINAS = sorted(p.name for p in (APP / "paginas").glob("*.py"))


def escolher_periodo(at, tipo, intervalo):
    """Interage com início/fim sem alterar as expectativas dos testes de análise."""
    at.selectbox(key=f"periodo_{tipo}_inicio").set_value(intervalo[0]).run()
    at.selectbox(key=f"periodo_{tipo}_fim").set_value(intervalo[1]).run()
    return at


def intervalo_escolhido(at, tipo):
    return tuple(at.selectbox(key=f"periodo_{tipo}_{limite}").value for limite in ("inicio", "fim"))


def abrir(pagina: str | None = None) -> AppTest:
    at = AppTest.from_file(str(APP / "main.py"), default_timeout=30).run()
    if pagina:
        at.switch_page(f"paginas/{pagina}").run()
    return at


def test_tela_inicial_abre_com_rodape():
    at = abrir()
    assert not at.exception
    assert any(t.value == "EULER" for t in at.title)
    assert any(c.value == RODAPE_SEGURANCA for c in at.caption)


@pytest.mark.parametrize("pagina", PAGINAS)
def test_toda_pagina_abre_sem_erro_e_com_rodape(pagina):
    at = abrir(pagina)
    assert not at.exception, at.exception
    assert any(c.value == RODAPE_SEGURANCA for c in at.caption)


def test_calculadora_mostra_caso_de_referencia_g01():
    at = abrir("calculadora.py")
    valores = {m.label: m.value for m in at.metric}
    assert valores["Perda nos gases"] == "11,77 % do PCI"
    assert valores["Razão de ar λ"] == "1,611"
    assert valores["PCI úmido"] == "10,12 MJ/kg"
    assert any("Simulação" in w.value for w in at.warning)


def test_calculadora_bloqueia_com_motivo():
    at = abrir("calculadora.py")
    # gases a 60 °C com combustível a 70% de umidade: abaixo do orvalho (≈71 °C)
    at.slider[0].set_value(60)
    at.slider[2].set_value(70).run()
    assert not at.metric
    assert any("bloqueado" in e.value for e in at.error)


def test_nenhuma_tela_tem_texto_solto_que_o_streamlit_mostraria():
    """Falha real: um texto solto depois de uma constante (como se fosse docstring) aparecia
    na tela do Relatório, porque o Streamlit mostra toda expressão solta da página ("magic").
    Só a docstring do módulo pode ficar solta."""
    for arquivo in [APP / "main.py", *sorted((APP / "paginas").glob("*.py"))]:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        soltos = [
            no.lineno
            for no in arvore.body[1:]
            if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant)
        ]
        assert not soltos, f"{arquivo.name}: texto solto nas linhas {soltos}"


def test_nenhuma_tela_usa_st_stop_que_esconderia_o_rodape():
    for arquivo in [*(APP / "paginas").glob("*.py"), APP / "estado.py", APP / "main.py"]:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        chamadas = [
            n
            for n in ast.walk(arvore)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "stop"
        ]
        assert not chamadas, arquivo.name


def clicar(at: AppTest, inicio_do_rotulo: str) -> AppTest:
    next(b for b in at.button if b.label.startswith(inicio_do_rotulo)).click().run()
    return at


def test_importar_exemplo_com_problemas_mostra_avisos():
    at = clicar(abrir("importar.py"), "Exemplo com problemas")
    assert not at.exception
    valores = {m.label: m.value for m in at.metric}
    assert valores["Tabelas importadas"] == "5"
    assert int(valores["Avisos de atenção"]) >= 15
    assert any(c.value == RODAPE_SEGURANCA for c in at.caption)


def abrir_com_demo(pagina: str) -> AppTest:
    at = clicar(abrir("importar.py"), "Ato 2 · dados insuficientes")
    at.switch_page(f"paginas/{pagina}").run()
    return at


def test_extrato_com_caso_de_demonstracao():
    at = abrir_com_demo("extrato.py")
    assert not at.exception, at.exception
    assert any("mais barato por tonelada nem sempre" in m.value for m in at.markdown)
    assert any(i.value.startswith("F3 tem o menor preço por tonelada") for i in at.info)
    assert any(c.value == RODAPE_SEGURANCA for c in at.caption)
    assert [m.label for m in at.metric] == [
        "Compras registradas",
        "Custo médio da energia",
        "Lotes com custo por energia",
    ]
    assert any(e.label == "Detalhes por fornecedor" for e in at.expander)
    assert any("Como ler estes valores" == e.label for e in at.expander)
    at.radio[0].set_value("Por tonelada · R$/t").run()
    assert not at.exception, at.exception


def test_extrato_sem_amostras_preserva_compras_e_nao_inventa_custo():
    at = abrir_com_demo("extrato.py")
    at.session_state["arquivos"] = tuple(
        (nome, conteudo)
        for nome, conteudo in at.session_state["arquivos"]
        if nome != "amostras.csv"
    )
    at.run()
    assert not at.exception, at.exception
    valores = {m.label: m.value for m in at.metric}
    assert valores["Compras registradas"] != "—"
    assert valores["Custo médio da energia"] == "—"
    assert valores["Lotes com custo por energia"].startswith("0 de")
    assert any("Ainda não é possível comparar" in i.value for i in at.info)
    at.radio[0].set_value("Por tonelada · R$/t").run()
    assert not at.exception, at.exception


def test_extrato_sem_dados_orienta_a_importar():
    at = abrir("extrato.py")
    assert not at.exception
    assert any("Nenhum dado importado" in i.value for i in at.info)


def test_dados_e_limites_com_demo_bloqueia_incerteza_e_extensoes_sem_medicao():
    at = abrir_com_demo("limites.py")
    assert not at.exception, at.exception
    valores = {m.label: m.value for m in at.metric}
    # Incerteza da eficiência e extensões de purga/UA, cujas medições não estão no demo.
    assert valores["Bloqueadas"] == "3"
    assert any(e.label == "Novas análises físicas · em revisão" for e in at.expander)
    assert any("Não calculável" in i.value for i in at.info)


def test_dados_e_limites_com_modelos_mostra_bloqueios():
    at = clicar(abrir("importar.py"), "Modelos")
    at.switch_page("paginas/limites.py").run()
    assert not at.exception
    assert int({m.label: m.value for m in at.metric}["Bloqueadas"]) > 0
    assert any("Por quê" in m.value for m in at.markdown)


def test_investigacao_com_demo_mostra_o_que_falta_para_concluir():
    at = abrir_com_demo("investigacao.py")
    assert not at.exception, at.exception
    # Auditoria A3: sem a incerteza do método de umidade, a EULER se abstém e diz o que cadastrar
    assert any("Não dá para concluir" in w.value for w in at.warning)
    assert any("Mais calor saindo pela chaminé" in m.value for m in at.markdown)
    assert any("Registrar no cadastro de instrumentos" in i.value for i in at.info)
    assert any(c.value == RODAPE_SEGURANCA for c in at.caption)


def test_investigacao_semana_sem_vapor_abstem():
    at = abrir_com_demo("investigacao.py")
    escolher_periodo(at, "comp", (6, 6))  # semana 7: medidor de vapor fora
    assert not at.exception, at.exception
    assert any(w.value.startswith("Não dá para saber se o consumo") for w in at.warning)


def test_relatorio_sem_dados_manda_importar():
    at = abrir("relatorio.py")
    assert not at.exception
    assert any("Nenhum dado importado" in i.value for i in at.info)


def test_relatorio_com_dados_mas_sem_investigacao_orienta():
    at = clicar(abrir("importar.py"), "Ato 2 · dados insuficientes")
    at.switch_page("paginas/relatorio.py").run()
    assert not at.exception
    assert any("Investigação" in i.value for i in at.info)


# --- revisão de uso para a demonstração (Etapa 7): resultados antigos nunca aparecem
# como se fossem dos dados novos


def test_relatorio_nao_usa_investigacao_de_dados_anteriores():
    """Falha real: depois de investigar o demo e trocar para os Modelos, a tela Relatório
    ainda oferecia a comparação do demo."""
    at = abrir_com_demo("investigacao.py")
    at.switch_page("paginas/importar.py").run()
    clicar(at, "Modelos")
    at.switch_page("paginas/relatorio.py").run()
    assert not at.exception
    assert not any("Comparação em uso" in c.value for c in at.caption)
    assert any("bloqueada" in i.value for i in at.info)  # Modelos não têm dois períodos


def test_relatorio_avisa_quando_a_altitude_mudou_depois_da_investigacao():
    at = abrir_com_demo("investigacao.py")
    at.switch_page("paginas/importar.py").run()
    at.session_state["altitude_m"] = 500.0  # mudança explícita do cadastro em uso
    at.switch_page("paginas/relatorio.py").run()
    assert not at.exception
    assert any("dados mudaram" in w.value for w in at.warning)
    assert not any("Comparação em uso" in c.value for c in at.caption)


def test_relatorio_segue_os_periodos_escolhidos():
    at = abrir_com_demo("investigacao.py")
    escolher_periodo(at, "comp", (6, 6))  # semana 7
    at.switch_page("paginas/relatorio.py").run()
    assert any("14/09/2026 07:30 a 21/09/2026 07:30" in c.value for c in at.caption)


def test_relatorio_continua_na_tela_depois_de_outra_interacao():
    """Baixar o arquivo recarrega a página: o relatório gerado não pode sumir."""
    at = abrir_com_demo("investigacao.py")
    at.switch_page("paginas/relatorio.py").run()
    clicar(at, "Gerar relatório")
    assert len(at.get("download_button")) >= 1
    at.run()  # nova execução, sem clicar em "Gerar relatório"
    assert not at.exception
    assert len(at.get("download_button")) >= 1


def test_barra_lateral_diz_quando_os_dados_sao_sinteticos():
    at = abrir()
    assert any("sem dados carregados" in c.value for c in at.sidebar.caption)
    at = abrir_com_demo("limites.py")
    assert any("dados sintéticos" in c.value for c in at.sidebar.caption)
    assert any("DADOS SINTÉTICOS" in c.value for c in at.caption)


def test_relatorio_depois_da_investigacao_gera_html():
    at = abrir_com_demo("investigacao.py")
    at.switch_page("paginas/relatorio.py").run()
    clicar(at, "Gerar relatório")
    assert not at.exception, at.exception
    assert any(c.value == RODAPE_SEGURANCA for c in at.caption)


def test_investigacao_mostra_fator_que_mudou_no_sentido_contrario():
    """Explicações concorrentes (matriz V-E1) na tela real: o fator oposto aparece no bloco
    2 com o rótulo próprio, junto da frase de fechamento (antes ele sumia da tela)."""
    from construtor_caso import Periodo, montar
    from test_validacao_combustivel_incerteza import _referencia_lab

    perda = 100 * _referencia_lab()(230, 8, 0.36)[0]
    pacote, _ = montar([Periodo(11.773, umidade=0.40), Periodo(perda, t_gases_c=230, umidade=0.36)])
    at = abrir()
    at.session_state["arquivos"] = tuple(
        sorted((f"{nome}.csv", dados) for nome, dados in pacote._arquivos_teste.items())
    )
    at.session_state["rotulo_dados"] = "caso de teste: explicações concorrentes"
    at.session_state["altitude_m"] = 0.0
    at.switch_page("paginas/investigacao.py").run()
    assert not at.exception, at.exception
    assert any("Mudou no sentido contrário" in m.value for m in at.markdown)
    assert any("fecham dentro da incerteza" in c.value for c in at.caption)


def test_escolha_de_periodos_sobrevive_a_ida_e_volta_entre_telas():
    """Falha real: escolher a semana 7, ir ao Relatório e voltar trocava a comparação em
    silêncio de volta ao padrão (semanas 5–6), e o relatório mudava junto."""
    at = abrir_com_demo("investigacao.py")
    escolher_periodo(at, "comp", (6, 6))
    at.switch_page("paginas/relatorio.py").run()
    at.switch_page("paginas/investigacao.py").run()
    assert intervalo_escolhido(at, "comp") == (6, 6)
    escolher_periodo(at, "comp", (7, 7))  # mover de novo continua funcionando
    escolher_periodo(at, "comp", (5, 7))
    assert intervalo_escolhido(at, "comp") == (5, 7)
    at.switch_page("paginas/relatorio.py").run()
    legendas = [c.value for c in at.caption if "Comparação em uso" in c.value]
    assert legendas and "**07/09/2026 07:30 a 28/09/2026 07:30** (comparação)" in legendas[0]


def test_escolha_de_periodos_volta_ao_padrao_com_dados_novos():
    at = abrir_com_demo("investigacao.py")
    escolher_periodo(at, "comp", (6, 6))
    at.switch_page("paginas/importar.py").run()
    clicar(at, "Ato 2 · dados insuficientes")  # recarregar os dados também é "dados novos"
    at.number_input[0].set_value(900.0).run()
    at.switch_page("paginas/investigacao.py").run()
    assert intervalo_escolhido(at, "comp") == (4, 5)


def test_dados_e_limites_resume_os_avisos_de_qualidade():
    """O botão de demonstração leva direto a Dados e limites: os avisos de qualidade (lacuna,
    totalizador reiniciado, registros tardios) precisam aparecer ali também."""
    at = abrir_com_demo("limites.py")
    texto = " ".join(m.value for m in at.markdown)
    assert "Qualidade dos registros:" in texto and "4 avisos de atenção" in texto
    assert "Sem leituras entre 12/09/2026" in texto and "Totalizador voltou" in texto


def test_investigacao_resume_o_resultado_no_topo_sem_perder_os_quatro_estados():
    """Visual novo (D59): resumo no topo e tabela com a diferença e a incerteza dela, vindas
    do JSON. Os quatro estados da detecção continuam distintos e o condicional diz o que falta."""
    at = abrir_com_demo("investigacao.py")
    assert not at.exception, at.exception
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Consumo por tonelada de vapor"] == "0,353 t/t"
    assert metricas["Valor em jogo (estimado)"].endswith("26.992")
    assert any(
        i.value.startswith("**Próxima verificação, em detalhe:** Registrar") for i in at.info
    )
    resumo = next(w.value for w in at.warning if "Não dá para concluir" in w.value)
    assert resumo.startswith("O consumo por tonelada de vapor subiu 10,1%.")
    assert "Próxima verificação: " in resumo
    tabela = at.table[0].value.set_index("Indicador")
    temperatura = tabela.loc["Temperatura dos gases"]
    assert temperatura["Diferença"] == "+31,9 °C (± 3,3)"
    assert temperatura["Mudou de forma detectável?"] == ":blue-badge[Sim]"
    umidade = tabela.loc["Umidade do combustível recebido"]
    assert umidade["Diferença"] == "+3,2 p.p. (incerteza incompleta)"
    assert "falta cadastrar a incerteza" in umidade["Mudou de forma detectável?"]
    assert tabela.loc["O₂ nos gases", "Mudou de forma detectável?"].startswith(":gray-badge[Não]")


def test_investigacao_sem_vapor_nao_mostra_numero_de_consumo_nem_valor():
    """Semana 7 (sem medidor de vapor): o resumo não inventa consumo nem valor em jogo."""
    at = abrir_com_demo("investigacao.py")
    escolher_periodo(at, "comp", (6, 6))
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Consumo por tonelada de vapor"] == "—"
    assert metricas["Valor em jogo"] == "não estimado"


def test_o_que_falta_saber_agrupa_sem_perder_itens():
    """Bloco 4 na tela: incertezas a cadastrar num grupo, o resto em outro, todos os itens."""
    from euler.investigacao import SUFIXO_CADASTRAR

    at = abrir_com_demo("investigacao.py")
    falta = at.session_state["investigacao"]["json"]["o_que_falta"]
    texto = " ".join(m.value for m in at.markdown)
    assert "**Completar o cadastro de instrumentos**" in texto
    assert "**Medir, registrar ou conferir**" in texto
    assert any(f.endswith(SUFIXO_CADASTRAR) for f in falta)
    for f in falta:
        item = f.removesuffix(SUFIXO_CADASTRAR)
        assert item[0].upper() + item[1:] in texto, item


def test_tela_sem_dados_oferece_carregar_o_demo():
    at = abrir("investigacao.py")
    assert any("Nenhum dado importado" in i.value for i in at.info)
    clicar(at, "Ato 2 · dados insuficientes")
    assert not at.exception, at.exception
    assert any("Não dá para concluir" in w.value for w in at.warning)


def test_investigacao_guardada_nao_serve_para_outra_altitude():
    """A investigação fica guardada por dados e períodos; mudar a altitude muda os dados
    (pressão absoluta) e a conta tem de ser refeita, não reaproveitada."""

    def energia_por_kg(at):
        j = at.session_state["investigacao"]["json"]
        return next(
            c["referencia"]
            for c in j["o_que_mudou"]["indicadores"]
            if c["nome"] == "energia por kg de vapor"
        )

    at = abrir_com_demo("investigacao.py")
    com_1000_m = energia_por_kg(at)
    at.switch_page("paginas/importar.py").run()
    at.session_state["altitude_m"] = 0.0  # mudança explícita do cadastro em uso
    at.switch_page("paginas/investigacao.py").run()
    assert not at.exception, at.exception
    assert energia_por_kg(at) != com_1000_m


def test_lancador_do_windows_abre_o_app():
    lancador = (APP.parent / "ABRIR-EULER.cmd").read_bytes()
    assert b"\r\n" in lancador
    assert b'"%~dp0scripts\\abrir_local.py" %*' in lancador
    assert b'cd /d "%~dp0"' in lancador


def test_saude_investigar_esta_mudanca_escolhe_os_periodos():
    """D65: o botão troca uma comparação já escolhida pelos períodos da mudança."""
    at = abrir_com_demo("investigacao.py")
    escolher_periodo(at, "comp", (7, 7))
    assert intervalo_escolhido(at, "comp") == (7, 7)
    at.switch_page("paginas/saude.py").run()
    assert not at.exception, at.exception
    at.button(key="investigar_mudanca").click().run()
    assert not at.exception, at.exception
    assert intervalo_escolhido(at, "ref") == (0, 3)
    assert intervalo_escolhido(at, "comp") == (4, 5)


def test_saude_sem_periodos_suficientes_nao_tem_botao():
    """Com os modelos (uma linha de cada), o selo é "Não dá para dizer" e não há mudança."""
    at = clicar(abrir("importar.py"), "Modelos (1 linha de exemplo)")
    at.switch_page("paginas/saude.py").run()
    assert not at.exception, at.exception
    assert any("Não dá para dizer" in m.value for m in at.markdown)
    assert not [b for b in at.button if b.key == "investigar_mudanca"]


def test_limites_tabela_por_periodo_resumida_com_detalhes():
    """D66: a tabela mostra só período, eficiência, consumo por t de vapor e situação; o
    resto (vapor, combustível, pátio, perda nos gases, motivo) fica em "ver detalhes"."""
    at = abrir_com_demo("limites.py")
    assert not at.exception, at.exception
    resumo, detalhes = at.table[0].value, at.table[1].value
    assert list(resumo.columns) == ["Período", "Eficiência", "Consumo por t de vapor", "Situação"]
    linha = resumo.set_index("Período").loc["14/09 a 21/09"]
    assert linha["Consumo por t de vapor"] == "✕"
    assert "Não dá para concluir" in linha["Situação"]
    # ato 2: falta a incerteza de quatro instrumentos, então a eficiência fica com limites
    assert "Com limites" in resumo.set_index("Período").loc["03/08 a 10/08", "Situação"]
    assert {"Vapor (t)", "Eficiência conforme o pátio", "Por que não dá"} <= set(detalhes.columns)
    assert any(e.label == "Ver detalhes de cada período" for e in at.expander)
