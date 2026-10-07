"""Tela Investigação: o consumo mudou? O que os dados sustentam? O que verificar? (T13).

Organização: no topo, resultado, próxima verificação e números principais; abaixo,
detalhes e evidências em seções recolhidas. Os textos vêm prontos do
JSON da investigação: a tela só arruma, não calcula nem reescreve conclusões.
"""

import json
from html import escape

import estado
import graficos
import pandas as pd
import streamlit as st
from componentes import cabecalho, cartao, md, proximo_passo, secao
from formatacao import SERIES, STATUS, diferenca, selo_deteccao, valor_formatado

from euler.capacidades import avaliar
from euler.formato import num, plural
from euler.investigacao import SUFIXO_CADASTRAR, investigar
from euler.periodos import periodos_entre_estoques
from euler.textos import PERGUNTA_CENTRAL

cabecalho("Investigação", PERGUNTA_CENTRAL, "Analisar um período")


@st.cache_data(show_spinner="Investigando os dois períodos…", max_entries=64)
def _investigar(assinatura: str, ref, comp, _pacote) -> dict:
    """Investigação guardada por dados e períodos: voltar a uma comparação já vista não
    recalcula. O pacote fica fora da chave; a assinatura (arquivos + altitude) o identifica."""
    return investigar(_pacote, ref, comp)


def _o_que_falta(falta: list[str]) -> None:
    """Bloco 4 agrupado: incertezas a cadastrar e o que medir ou registrar (mesmos itens)."""
    if not falta:
        st.caption("Nada essencial faltando para esta comparação.")
        return

    def item(texto: str) -> str:
        return f"- {md(texto[0].upper() + texto[1:])}"

    cadastrar = [f.removesuffix(SUFIXO_CADASTRAR) for f in falta if f.endswith(SUFIXO_CADASTRAR)]
    outros = [f for f in falta if not f.endswith(SUFIXO_CADASTRAR)]
    if cadastrar:
        with cartao("falta-cadastrar"):
            st.markdown(
                ":material/edit_note: **Completar o cadastro de instrumentos** · "
                f"{plural(len(cadastrar), 'incerteza', 'incertezas')}, cada uma com o tipo da "
                "incerteza"
            )
            st.markdown("\n".join(item(c) for c in cadastrar))
    if outros:
        with cartao("falta-medir"):
            st.markdown(
                ":material/straighten: **Medir, registrar ou conferir** · "
                f"{plural(len(outros), 'item', 'itens')}"
            )
            st.markdown("\n".join(item(o) for o in outros))


def _linha_do_tempo(periodos, ref, comp) -> None:
    """Faixa com todos os períodos: os da referência e os da comparação em destaque."""
    celulas = []
    for i, (inicio, fim) in enumerate(periodos):
        classe = "ref" if ref[0] <= i <= ref[1] else "comp" if comp[0] <= i <= comp[1] else ""
        celulas.append(
            f'<div class="p {classe}" title="{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}">'
            f"{inicio:%d/%m}</div>"
        )

    def resumo(a, b) -> str:
        inicio, fim = periodos[a][0], periodos[b][1]
        dias = round((fim - inicio).total_seconds() / 86400)
        return f"{inicio:%d/%m} a {fim:%d/%m} · {plural(dias, 'dia', 'dias')}"

    st.html(
        f'<div class="euler-tempo">{"".join(celulas)}</div>'
        '<div class="euler-tempo-legenda">'
        '<span><span class="q ref">'
        f"</span><b>Referência</b> · {escape(resumo(*ref))}</span>"
        '<span><span class="q comp">'
        f"</span><b>Comparação</b> · {escape(resumo(*comp))}</span></div>"
    )


def _escolher_periodos(periodos):
    """Períodos de referência e de comparação.

    Datas selecionáveis são limites de estoque medidos, sem interpolar registros.
    A escolha persiste entre telas e é reiniciada quando a assinatura dos dados muda.
    """
    n = len(periodos)
    ref_fim = max(1, n // 2)
    comp_fim = min(n, ref_fim + 2)
    padrao = {"ref": (0, ref_fim - 1), "comp": (min(ref_fim, n - 1), comp_fim - 1)}
    salvo = st.session_state.get("periodos_escolhidos")

    def intervalo_valido(valor):
        return (
            isinstance(valor, (list, tuple))
            and len(valor) == 2
            and all(isinstance(i, int) for i in valor)
            and 0 <= valor[0] <= valor[1] < n
        )

    valido = (
        isinstance(salvo, dict)
        and salvo.get("assinatura") == estado.assinatura()
        and all(intervalo_valido(salvo.get(tipo)) for tipo in ("ref", "comp"))
    )
    inicial = salvo if valido else padrao
    if not valido:
        for tipo in ("ref", "comp"):
            for limite in ("inicio", "fim"):
                st.session_state.pop(f"periodo_{tipo}_{limite}", None)

    def selecionar(coluna, tipo, titulo):
        with coluna:
            st.markdown(f"**{titulo}**")
            inicio = st.selectbox(
                "Início",
                options=list(range(n)),
                index=inicial[tipo][0],
                key=f"periodo_{tipo}_inicio",
                format_func=lambda i: periodos[i][0].strftime("%d/%m/%Y %H:%M"),
            )
            chave_fim = f"periodo_{tipo}_fim"
            fim_anterior = st.session_state.get(chave_fim, inicial[tipo][1])
            ajustado = fim_anterior < inicio
            if ajustado:
                st.session_state[chave_fim] = inicio
            fim = st.selectbox(
                "Fim",
                options=list(range(inicio, n)),
                index=max(inicio, inicial[tipo][1]) - inicio,
                key=chave_fim,
                format_func=lambda i: periodos[i][1].strftime("%d/%m/%Y %H:%M"),
            )
            if ajustado:
                st.caption("O fim foi ajustado para a primeira medição após o início escolhido.")
            return inicio, fim

    with cartao("periodos"):
        st.markdown(":material/date_range: **Períodos comparados**")
        st.caption("Escolha as datas de início e fim. As opções seguem as medições de estoque.")
        c1, c2 = st.columns(2, gap="large")
        ref = selecionar(c1, "ref", "Referência · como era")
        comp = selecionar(c2, "comp", "Comparação · como ficou")
        _linha_do_tempo(periodos, ref, comp)
    st.session_state["periodos_escolhidos"] = {
        "assinatura": estado.assinatura(),
        "ref": tuple(ref),
        "comp": tuple(comp),
    }
    return (periodos[ref[0]][0], periodos[ref[1]][1]), (periodos[comp[0]][0], periodos[comp[1]][1])


def _grafico(pacote, ref, comp) -> None:
    """Série diária escolhida pelo usuário, com os dois períodos em faixas de fundo."""
    diario = pacote.dados("diario")
    if diario is None:
        return
    disponiveis = [c for c in SERIES if c in diario and diario[c].notna().any()]
    if not disponiveis:
        return
    coluna = st.segmented_control(
        "Ver no gráfico",
        disponiveis,
        default=disponiveis[0],
        required=True,
        format_func=lambda c: SERIES[c][0],
        key="grafico_serie",
    )
    coluna = coluna or disponiveis[0]
    _, titulo, unidade, formato = SERIES[coluna]
    d = diario.dropna(subset=[coluna, "instante_observado"])
    d = d[d["regime"].fillna("estavel") != "parada"]
    dias = d.groupby(d["instante_observado"].dt.tz_localize(None).dt.normalize())[coluna].mean()
    df = pd.DataFrame({"dia": dias.index, "valor": dias.values.astype(float)})
    st.altair_chart(
        graficos.serie_diaria_com_periodos(
            df,
            f"{titulo} ({unidade}, média do dia)",
            formato,
            [(ref[0], ref[1], "Referência"), (comp[0], comp[1], "Comparação")],
        ),
        width="stretch",
    )


def _hipoteses(lista, titulo_vazio: str) -> None:
    if not lista:
        st.caption(titulo_vazio)
    for h in lista:
        rotulo, cor, icone = STATUS[h["status"]]
        with st.container(border=True):
            st.markdown(f":{cor}-badge[{icone} {rotulo}]")
            st.markdown(f"**{h['titulo']}**")
            st.markdown(md(h["porque"]))
            efeito = h["efeito"]["consumo_pct"]
            if efeito is not None and h["status"] in ("sustentada", "possivel"):
                st.caption(
                    f"Efeito estimado no consumo: {'+' if efeito >= 0 else ''}{num(efeito, 1)}%"
                )
            st.caption(f"Como verificar: {h['verificacao']}")


def _indicadores(j) -> None:
    linhas = []
    for c in j["o_que_mudou"]["indicadores"]:
        if c["referencia"] is None and c["comparacao"] is None:
            continue
        linhas.append(
            {
                "Indicador": c["nome"][0].upper() + c["nome"][1:],
                "Referência": valor_formatado(c["referencia"], c["unidade"]),
                "Comparação": valor_formatado(c["comparacao"], c["unidade"]),
                "Diferença": diferenca(c),
                "Mudou de forma detectável?": selo_deteccao(c),
            }
        )
    # tabela simples: quebra o texto (a coluna da detecção tem frases longas)
    st.table(pd.DataFrame(linhas), hide_index=True, border="horizontal")
    st.caption(
        "Diferença = comparação − referência; entre parênteses, a incerteza da diferença. "
        "p.p. = pontos percentuais."
    )


def _numeros_principais(j) -> None:
    """Três indicadores do topo: consumo, valor em jogo e situação das explicações."""
    c1, c2, c3 = st.columns(3)
    consumo = j["o_que_mudou"].get("consumo_especifico")
    with c1, cartao("kpi-consumo"):
        if consumo and consumo["variacao"] is not None and consumo["referencia"]:
            variacao = 100 * consumo["variacao"] / consumo["referencia"]
            st.metric(
                "Consumo por tonelada de vapor",
                f"{num(consumo['comparacao'], 3)} t/t",
                f"{'+' if variacao >= 0 else ''}{num(variacao, 1)}% sobre "
                f"{num(consumo['referencia'], 3)} t/t",
                delta_color="off",
            )
            st.markdown(f"Mudou de forma detectável? {selo_deteccao(consumo)}")
        else:
            st.metric("Consumo por tonelada de vapor", "—")
            st.caption("Não pode ser calculado neste período (ver o motivo na conclusão).")
    valor = j["valor_em_jogo"]
    with c2, cartao("kpi-valor"):
        if valor:
            st.metric(
                "Valor em jogo (estimado)",
                md(f"R$ {num(valor['valor_brl'], 0)}"),
                help="No período de comparação, em relação ao consumo da referência.",
            )
            incerteza = (
                f"Incerteza: ± R$ {num(valor['incerteza_brl'], 0)}. "
                if valor["incerteza_brl"] is not None
                else ""
            )
            st.caption(md(incerteza + valor["base"]))
        else:
            st.metric("Valor em jogo", "não estimado")
            st.caption(md(j["valor_em_jogo_motivo"]))
    hips = j["hipoteses"]
    contagem = {s: sum(h["status"] == s for h in hips) for s in STATUS}
    with c3, cartao("kpi-explicacoes"):
        compativeis = contagem["sustentada"]
        st.metric(
            "Explicações compatíveis com os dados",
            compativeis,
        )
        partes = [
            plural(contagem["possivel"] + contagem["nao_avaliavel"], "em aberto", "em aberto"),
            plural(contagem["descartada"], "enfraquecida", "enfraquecidas"),
        ]
        if contagem["oposta"]:
            partes.append(
                plural(contagem["oposta"], "no sentido contrário", "no sentido contrário")
            )
        st.caption(" · ".join(partes) + ". Compatível não é causa comprovada.")


def mostrar(pacote) -> None:
    caps = {c.id: c for c in avaliar(pacote)}
    if not caps["comparacao"].habilitada:
        estado.esquecer_resultados()  # nada de relatório de uma comparação que não existe
        st.warning("**Investigação bloqueada.** " + " ".join(caps["comparacao"].motivos))
        st.markdown("Para liberar: " + " ".join(caps["comparacao"].o_que_fazer))
        return
    periodos = periodos_entre_estoques(pacote)
    ref, comp = _escolher_periodos(periodos)
    if not (ref[1] <= comp[0] or comp[1] <= ref[0]):
        estado.esquecer_resultados()
        st.warning("Os dois períodos se sobrepõem. Escolha períodos separados.")
        return

    j = _investigar(estado.assinatura(), ref, comp, pacote)
    estado.guardar_investigacao(j)
    from blocos.diagnostico import renderizar as renderizar_diagnostico

    # ---------------------------------------------------------------- resultado em resumo
    secao("Resultado")
    # até três frases curtas (D63): o consumo; o que explica e o que foi descartado; a
    # próxima verificação. A conclusão completa abre a aba 2.
    resumo = "  \n".join(md(f) for f in j["resumo"]["frases"])
    if j["conclusao"]["abstencao"]:
        st.warning(resumo, icon=":material/pan_tool:")
    else:
        st.success(resumo, icon=":material/fact_check:")
        st.caption(
            '"Compatível com os dados" não é causa comprovada: cada explicação precisa da '
            "verificação indicada."
        )
    _numeros_principais(j)
    st.page_link(
        "paginas/financeiro.py",
        label="Ver impacto em reais e simular recuperação",
        icon=":material/payments:",
    )
    prox = j["proxima_verificacao"]
    st.info(
        f"**Próxima verificação, em detalhe:** {md(prox['acao'])}  \n{md(prox['porque'])}",
        icon=":material/search:",
    )

    # ---------------------------------------------------------------- detalhes em abas
    hips = j["hipoteses"]
    sustentadas = [h for h in hips if h["status"] == "sustentada"]
    opostas = [h for h in hips if h["status"] == "oposta"]
    abertas = [h for h in hips if h["status"] in ("possivel", "nao_avaliavel")]
    secao("Detalhes")
    with st.expander("O que mudou · gráfico e indicadores"):
        st.markdown(f"**{md(j['o_que_mudou']['frase'])}**")
        if j["o_que_mudou"]["custo_vapor"]:
            st.markdown(md(j["o_que_mudou"]["custo_vapor"]["frase"]))
        _grafico(pacote, ref, comp)
        with st.expander("Ver todos os indicadores e suas incertezas"):
            _indicadores(j)

    with st.expander(f"O que os dados sustentam ({len(sustentadas) + len(opostas)})"):
        st.markdown(f"**Conclusão:** {md(j['conclusao']['texto'])}")
        _hipoteses(sustentadas, "Nenhuma explicação é sustentada pelos dados.")
        if opostas:
            _hipoteses(opostas, "")
        fechamento = j["o_que_mudou"].get("fechamento")
        if fechamento:
            st.caption(md(fechamento["frase"]))
            if fechamento.get("frase_com_condicionais"):
                st.caption(md(fechamento["frase_com_condicionais"]))
        st.caption(
            '"Compatível com os dados" não é causa comprovada: cada explicação precisa da '
            "verificação indicada."
        )
        descartadas = [h for h in hips if h["status"] == "descartada"]
        if descartadas:
            with st.expander(f"Hipóteses enfraquecidas e por quê ({len(descartadas)})"):
                _hipoteses(descartadas, "")

    with st.expander(f"Outras explicações possíveis ({len(abertas)})"):
        _hipoteses(abertas, "Nenhuma outra explicação continua em aberto.")

    with st.expander(f"Dados que faltam para concluir ({len(j['o_que_falta'])})"):
        _o_que_falta(j["o_que_falta"])
        st.caption(md(j["independencia"]["nota"]))

    with st.expander("Qualidade das evidências e rastreabilidade"):
        renderizar_diagnostico(j["diagnostico_evidencias"], completo=False)
        st.page_link("paginas/diagnostico.py", label="Ver diagnóstico completo e rastreabilidade")

    with st.container(horizontal=True, vertical_alignment="center"):
        st.page_link(
            "paginas/relatorio.py",
            label="Gerar o relatório desta comparação",
            icon=":material/description:",
        )
    with st.expander("Detalhes técnicos da investigação (JSON)"):
        texto = json.dumps(j, ensure_ascii=False, indent=2)
        st.download_button(
            "Baixar o JSON", texto, file_name="investigacao_euler.json", mime="application/json"
        )
        st.json(j, expanded=False)
    proximo_passo("paginas/financeiro.py", "Financeiro")


pacote = estado.exigir_pacote()
if pacote is not None:
    mostrar(pacote)
