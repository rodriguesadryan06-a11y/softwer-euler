"""Painel principal (D114): o acompanhamento em uma tela, para o cliente ver como está.

De cima para baixo: planta, equipamento, até quando há dados e a situação do mês; o dia a
dia (últimos 7 dias contra o comum na referência, com dois gráficos simples); as cinco
respostas do trabalho do mês; e, depois, o histórico. Só apresenta números já calculados
pelo motor; ausente aparece como ausente.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from acompanhamento_ui import brl, data, periodo
from componentes import md
from graficos import CORES, TINTA_SECUNDARIA, _configurar

from euler.condicoes import condicoes_comparadas
from euler.conta import FRASE_INCONCLUSIVO, conclusao_financeira, motivo_inconclusivo
from euler.formato import num
from euler.mensal import ESTADOS_MES

COR_MES = {
    "referencia": "gray",
    "sem_periodo": "gray",
    "em_andamento": "blue",
    "aguarda_anterior": "orange",
    "pronto": "green",
    "fechado": "violet",
    "revisar": "red",
}
# estado do desvio: sempre com ícone e nome, a cor só apoia
ESTADO = {
    "acima": (":material/trending_up:", "Acima do esperado (estabelecido)", "orange"),
    "abaixo": (":material/trending_down:", "Abaixo do esperado (estabelecido)", "blue"),
    "nao_estabelecido": (":material/remove:", "Diferença não estabelecida", "gray"),
    "sem_faixa": (":material/help:", "Sem faixa de incerteza", "gray"),
    None: (":material/block:", "Sem conta", "gray"),
}


def _dias(f: dict) -> dict:
    n = f["resultado"]["nucleo"]
    return {
        k: (pd.Timestamp(p["fim"]) - pd.Timestamp(p["inicio"])).total_seconds() / 86400
        for k, p in (("referencia", n["referencia"]), ("comparacao", n["periodo"]))
    }


# ------------------------------------------------------------ topo


def topo(planta: dict, eq: dict, cob: dict, plano: dict | None) -> None:
    diario = cob["tabelas"].get("diario") or {}
    with st.container(border=True, key="painel-topo"):
        c1, c2, c3 = st.columns([1.4, 1, 1.2])
        c1.markdown(md(f"**{planta['nome']}**  \n{eq['nome']} · {eq['caldeira_id']}"))
        icone = ":material/check_circle:" if cob["estado"] == "atualizado" else ":material/update:"
        dias = cob.get("dias_desde_ultima_leitura")
        c2.markdown(
            md(
                f"{icone} **Dados até {data(diario.get('fim'))}**  \n"
                + (f"última leitura há {dias} dia(s)" if dias is not None else "sem leituras")
            )
        )
        if plano:
            c3.markdown(md(f"**Mês: {plano['rotulo']}**"))
            c3.badge(ESTADOS_MES[plano["estado"]], color=COR_MES[plano["estado"]])
        if cob["estado"] != "atualizado":
            st.caption(md(f":material/update: {cob['frase']}"))


# ------------------------------------------------------------ dia a dia


def _grafico_diario(serie, campo, titulo, unidade, faixa, casas, barras: bool) -> None:
    df = pd.DataFrame(serie)
    if df.empty or campo not in df or df[campo].notna().sum() == 0:
        st.caption(f"{titulo}: sem leituras no período mostrado.")
        return
    df = df[["dia", campo]].copy()
    df["dia"] = pd.to_datetime(df["dia"], utc=True).dt.tz_convert("America/Sao_Paulo")
    df["dia"] = df["dia"].dt.tz_localize(None)
    df["texto"] = [
        "sem valor (dia parcial)" if pd.isna(v) else f"{num(v, casas)} {unidade}" for v in df[campo]
    ]
    x = alt.X("dia:T", title=None, axis=alt.Axis(format="%d/%m", tickCount=6, grid=False))
    dicas = [
        alt.Tooltip("dia:T", title="Dia", format="%d/%m/%Y"),
        alt.Tooltip("texto:N", title=titulo),
    ]
    camadas = []
    if faixa:
        camadas.append(
            alt.Chart(pd.DataFrame({"lo": [faixa[0]], "hi": [faixa[1]]}))
            .mark_rect(color=TINTA_SECUNDARIA, opacity=0.16)
            .encode(y="lo:Q", y2="hi:Q")
        )
    y = alt.Y(
        f"{campo}:Q",
        title=unidade,
        scale=alt.Scale(zero=barras),
        axis=alt.Axis(tickCount=4, format=",.0f" if casas == 0 else ",.1f"),
    )
    base = alt.Chart(df).encode(x=x, tooltip=dicas)
    if barras:
        camadas.append(
            base.mark_bar(
                color=CORES[0], width=7, cornerRadiusTopLeft=2, cornerRadiusTopRight=2
            ).encode(y=y)
        )
    else:
        camadas.append(base.mark_line(color=CORES[0], strokeWidth=2, invalid=None).encode(y=y))
        camadas.append(base.mark_point(color=CORES[0], filled=True, size=36).encode(y=y))
    # alvo de dica maior que a marca: o dia inteiro
    camadas.append(base.mark_rule(opacity=0, strokeWidth=12).encode(y=y))
    st.altair_chart(
        _configurar(alt.layer(*camadas).properties(height=170, title=titulo)), width="stretch"
    )


def dia_a_dia_bloco(d: dict) -> None:
    st.markdown("### Dia a dia")
    if not d["quadros"]:
        st.caption("Sem leituras do diário para mostrar.")
        return
    st.caption(
        f"Últimos 7 dias com registro (até {data(d['ultimo_dia'])}), comparados com o que era "
        "comum na referência. Combustível consumido só se conhece no fechamento, entre "
        "medições de estoque."
    )
    colunas = st.columns(len(d["quadros"]))
    for col, q in zip(colunas, d["quadros"], strict=True):
        valor = "—" if q["media_7d"] is None else f"{num(q['media_7d'], q['casas'])} {q['unidade']}"
        col.metric(q["nome"], valor, border=True)
        icone = ":material/warning:" if q["fora_da_faixa"] else ":material/check:"
        if q["fora_da_faixa"] is None:
            icone = ":material/info:"
        col.caption(md(f"{icone} {q['frase']}"))
    g1, g2 = st.columns(2)
    with g1:
        _grafico_diario(
            d["serie"],
            "vazao_t_h",
            "Vapor · vazão média do dia",
            "t/h",
            d["faixas"].get("vazao_t_h"),
            1,
            barras=True,
        )
    with g2:
        _grafico_diario(
            d["serie"],
            "t_gases_c",
            "Temperatura dos gases · média do dia",
            "°C",
            d["faixas"].get("t_gases_c"),
            0,
            barras=False,
        )
    st.caption(
        "Faixa cinza: do 10º ao 90º percentil dos dias da referência (o comum na base de "
        "comparação, não um limite de projeto). " + " ".join(d["frases"])
    )


# ------------------------------------------------------------ cinco respostas


def _cartao(chave: str, pergunta: str):
    caixa = st.container(border=True, key=f"resposta-{chave}")
    caixa.markdown(md(f"**{pergunta}**"))
    return caixa


def cinco_respostas(f: dict | None, resumo: dict | None, pacote, fila: list, p: dict) -> None:
    st.markdown("### O mês em cinco respostas")
    if f is None:
        st.info(
            "Este mês ainda não tem fechamento registrado. Os valores ficam em branco "
            "até haver uma conta; consulte a prévia e os dados necessários em **Fechamentos**."
        )
        for col, rotulo in zip(
            st.columns(3), ("Consumido", "Esperado", "Diferença estimada"), strict=True
        ):
            col.metric(rotulo, "—")
        st.page_link(
            "paginas/fechamentos.py", label="Ir para Fechamentos", icon=":material/event_available:"
        )
        return
    r = f["resultado"]
    n = r["nucleo"]
    conta = n["explicacao_conta"]
    q = conclusao_financeira(conta, n["oportunidades"], _dias(f))
    alvo = (
        f"{resumo['rotulo'].capitalize()} ({len(resumo['trechos'])} trecho(s))"
        if resumo
        else f"Fechamento de {periodo(n['periodo'])}"
    )
    st.caption(
        md(f"{alvo} · referência v{n['referencia']['versao']} · {n['politica_custo']['descricao']}")
    )
    c1, c2, c3 = st.columns(3)

    # 1. quanto custou
    with c1:
        caixa = _cartao("custou", "1 · Quanto custou o combustível consumido?")
        if resumo:
            caixa.metric("Nos trechos registrados", brl(resumo["consumido_brl"]))
            caixa.caption(
                f"{num(resumo['combustivel_t'], 0)} t queimadas"
                if resumo["combustivel_t"] is not None
                else "Quantidade não somada: algum trecho sem conta."
            )
            if resumo["lacunas"]:
                caixa.caption(
                    md(
                        ":material/block: "
                        + "; ".join(
                            f"{data(t['inicio'])} a {data(t['fim'])} sem conta"
                            for t in resumo["lacunas"]
                        )
                        + "."
                    )
                )
        elif q.get("disponivel"):
            caixa.metric("No período", brl(q["consumido"]["custo_brl"]))
            caixa.caption(
                f"{num(q['consumido']['combustivel_t'], 0)} t a "
                f"{brl(q['consumido']['preco_brl_t'])}/t"
            )
        else:
            caixa.metric("No período", "—")
            caixa.caption(q.get("motivo") or "Conta indisponível.")

    # 2. quanto seria esperado + por que a conta mudou
    with c2:
        caixa = _cartao("esperado", "2 · Quanto seria esperado nas condições comparadas?")
        if resumo:
            caixa.metric("Nos trechos registrados", brl(resumo["esperado_brl"]))
        else:
            caixa.metric(
                "No período", brl(q["esperado"]["custo_brl"]) if q.get("disponivel") else "—"
            )
        if q.get("disponivel"):
            caixa.caption("Ajustado por " + ", ".join(q["esperado"]["ajustado_por"]) + ".")

    # 3. diferença estabelecida e dúvidas
    with c3:
        caixa = _cartao("diferenca", "3 · Qual é a diferença estimada e o que falta saber?")
        if resumo:
            caixa.metric("No mês (soma dos trechos)", brl(resumo["diferenca_brl"]))
            caixa.caption(
                "Soma monetária dos trechos; a evidência é avaliada em cada trecho. "
                "Não representa perda recuperável ou economia verificada."
            )
            for t in resumo["trechos"]:
                icone, rotulo, _ = ESTADO.get(t["situacao"], ESTADO[None])
                caixa.caption(md(f"{icone} {data(t['inicio'])} a {data(t['fim'])}: {rotulo}"))
        elif q.get("disponivel"):
            caixa.metric("No período", brl(q["sem_explicacao"]["custo_brl"]))
            icone, rotulo, _ = ESTADO.get(q["estado"], ESTADO[None])
            caixa.caption(md(f"{icone} {rotulo}"))
        des = conta.get("desvio") or {}
        motivo = motivo_inconclusivo(des)
        if motivo:
            quando = f"No trecho de {periodo(n['periodo'])}" if resumo else "Por quê"
            caixa.caption(md(f"{quando}: {FRASE_INCONCLUSIVO[motivo]}."))
        cond = r.get("condicoes") or condicoes_comparadas(
            pacote,
            n["referencia"]["inicio"],
            n["referencia"]["fim"],
            n["periodo"]["inicio"],
            n["periodo"]["fim"],
        )
        with caixa.expander("Condições comparadas e o que ficou no desvio"):
            for frase in cond["frases"]:
                st.markdown(md(f"- {frase}"))
            st.caption(cond["nao_ajustado"])
            for x in (q.get("evitavel") or {}).get("ainda_no_desvio", []):
                st.caption(md(f"- {x}"))

    ponte = q.get("ponte") or {} if q.get("disponivel") else {}
    if ponte.get("resposta"):
        with st.container(border=True, key="resposta-ponte"):
            st.markdown(
                md(f"**Por que a conta mudou** · {periodo(n['periodo'])}  \n{ponte['resposta']}")
            )
            if ponte.get("dias") and ponte["dias"].get("referencia") != ponte["dias"].get(
                "comparacao"
            ):
                st.caption(
                    "Períodos com durações diferentes: para comparar o ritmo, veja o custo por "
                    "tonelada de vapor no histórico."
                )
    c4, c5 = st.columns(2)
    # 4. próxima verificação
    with c4:
        caixa = _cartao(
            "verificacao", "4 · Qual é a próxima verificação, quem faz e em que pé está?"
        )
        if not fila:
            caixa.markdown(
                "Nada pendente: sem desvio estabelecido, ação sem verificação ou dado faltando."
            )
        for i in fila[:2]:
            criterios = i.get("criterios") or {}
            quem = criterios.get("responsavel") or "responsável ainda não definido"
            estado = criterios.get("estado") or "não aberta como investigação"
            caixa.markdown(md(f"**{i['titulo']}**"))
            if i.get("proxima_acao"):
                caixa.caption(md(f"Próximo passo: {i['proxima_acao']}"))
            caixa.caption(md(f"Quem: {quem} · Situação: {estado}"))
        caixa.page_link(
            "paginas/acoes.py", label="Investigações e ações", icon=":material/task_alt:"
        )

    # 5. o que aconteceu depois das ações
    with c5:
        caixa = _cartao("acoes", "5 · O que aconteceu depois das ações anteriores?")
        if not p["acoes"]:
            caixa.markdown("Nenhuma ação registrada ainda.")
        for x in p["acoes"][-3:][::-1]:
            caixa.markdown(md(f"**{data(x['data'])} · {x['descricao']}**"))
            caixa.caption(md(x["frase"]))
        ver = p["verificado"]
        caixa.caption(
            "Economia verificada pelo protocolo: "
            + (brl(ver["total_brl"]) if ver["total_brl"] is not None else "nenhuma até agora")
            + "."
        )
