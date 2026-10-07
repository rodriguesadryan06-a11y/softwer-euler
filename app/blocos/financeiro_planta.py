"""Conta salva por planta: lê o fechamento, sem recalcular preços nem misturar a sessão."""

import pandas as pd
import streamlit as st
from acompanhamento_ui import brl, faixa_situacao, periodo, planta_e_equipamento
from blocos.conclusao_financeira import renderizar as renderizar_conclusao
from blocos.entrega import renderizar as renderizar_entrega
from blocos.linha_do_tempo import renderizar as renderizar_linha_do_tempo
from componentes import incerteza_explicada, md

from euler.armazem import ORIGEM_DA_CLASSE
from euler.conta import conclusao_financeira
from euler.fechamento import fechamentos_vigentes
from euler.formato import num
from euler.painel import painel, texto_fechamento


def _massa(v):
    return "Não informada" if v is None else f"{num(v, 1)} t"


def conta_salva(f: dict, origem: str | None = None) -> None:
    """Mostra o núcleo auditável de um fechamento; todos os valores já vieram do motor."""
    r = f["resultado"]
    n = r["nucleo"]
    c = n["explicacao_conta"]
    p = n["politica_custo"]
    st.markdown(f"### Conta do período · {periodo(n['periodo'])}")
    st.caption(
        f"Referência v{n['referencia']['versao']} · {periodo(n['referencia'])}. "
        "Valores preservados no fechamento; preços e registros novos não reescrevem esta conta."
    )
    faixa_situacao(r["situacao"], (c.get("desvio") or {}).get("frase") or r["situacao_frase"])
    if c.get("disponivel"):
        dias = {
            k: (pd.Timestamp(x["fim"]) - pd.Timestamp(x["inicio"])).total_seconds() / 86400
            for k, x in (("referencia", n["referencia"]), ("comparacao", n["periodo"]))
        }
        renderizar_conclusao(
            conclusao_financeira(c, n["oportunidades"], dias), chave=f"fin-fech-{f['id']}"
        )
        incerteza_explicada(c["desvio"].get("incerteza"), recolhido=True)
    else:
        st.info(c.get("motivo") or "Comparação financeira ainda não disponível.")
    st.markdown(md(f"**Próxima verificação:** {n['proxima_verificacao']['acao']}"))
    st.caption(md(f"Política de custo: {p['descricao']}"))
    preco = p.get("preco_brl_t")
    st.caption(
        f"Preço atribuído: {brl(preco)}/t · moeda BRL. "
        + (f"Origem: {p['origem']}. " if p.get("origem") else "")
        if preco is not None
        else "Preço atribuído: não determinado."
    )
    if p.get("motivo"):
        st.warning(md(p["motivo"]))

    v = c.get("variacao") or {}
    if v.get("disponivel"):
        with st.expander("Por que a conta mudou · parcelas do fechamento"):
            st.caption(
                "Decomposição contábil sob as premissas da referência; não comprova causas físicas."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Parcela": x["titulo"],
                            "Valor": brl(x["custo_brl"])
                            if x["custo_brl"] is not None
                            else "Não separada do desvio",
                            "Base": x["base"],
                        }
                        for x in v["componentes"]
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
            for premissa in c.get("premissas", []):
                st.caption(md(premissa))

    cp = n["conta_do_periodo"]
    with st.expander("Compras, estoque e consumo deste período"):
        st.caption(
            "Estoque inicial + recebimentos − estoque final = consumo. Compra não é pagamento."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {"Movimento": "Estoque inicial", "Quantidade": _massa(cp["estoque_inicial_t"])},
                    {
                        "Movimento": "+ Recebimentos registrados",
                        "Quantidade": _massa(cp["recebido_t"]),
                    },
                    {"Movimento": "− Estoque final", "Quantidade": _massa(cp["estoque_final_t"])},
                    {"Movimento": "= Consumo calculado", "Quantidade": _massa(cp["consumido_t"])},
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        a, b = st.columns(2)
        parcial = cp.get("lotes_sem_valor", 0) > 0
        a.metric(
            "Valor parcial das notas" if parcial else "Valor das notas registradas",
            brl(cp["valor_notas_brl"]),
        )
        b.metric("Custo atribuído ao consumo", brl(cp["custo_atribuido_brl"]))
        if parcial:
            st.warning(
                f"{cp['lotes_sem_valor']} recebimento(s) sem preço. O valor das notas está incompleto."
            )
        if cp.get("motivo_consumo"):
            st.info(cp["motivo_consumo"])
        st.caption(cp["nota_pagamento"])

    with st.expander("Oportunidades a verificar · não somar ao desvio"):
        st.caption(
            "Parcela evitável: não apurada. Impactos associados não são promessa de recuperação."
        )
        ops = [o for o in n["oportunidades"] if o["prioridade"] in ("alta", "media")]
        for o in ops:
            st.markdown(md(f"**{o['titulo']}** · {o['verificacao']}"))
        if not ops:
            st.caption("Nenhuma oportunidade priorizada neste fechamento.")
        for nota in n["sobreposicao"]:
            st.caption(md(nota))

    with st.expander("Origem da conta e relatório"):
        st.caption(
            f"Fechamento #{f['id']} · revisão dos dados {f['revisao_dados']} · "
            f"núcleo {f['resultado_sha'][:16]} · código {f['versao_euler']}"
        )
        st.download_button(
            "Baixar este fechamento",
            texto_fechamento(f, origem),
            f"fechamento-{f['id']}.md",
            "text/markdown",
        )


def mostrar() -> None:
    """Consulta sem escritas: seleciona planta, equipamento e período já fechado."""
    with planta_e_equipamento(passo=("conta",)) as ctx:
        if ctx is None:
            return
        _, planta, a, eq = ctx
        fs = fechamentos_vigentes(a, eq["id"])
        if not fs:
            st.info(
                "Ainda não há conta fechada para este equipamento. Defina a referência e produza o primeiro fechamento."
            )
            st.page_link(
                "paginas/fechamentos.py",
                label="Preparar o primeiro fechamento",
                icon=":material/event_available:",
            )
            return
        renderizar_linha_do_tempo(a, eq["id"])
        st.divider()
        por_id = {f["id"]: f for f in fs}
        ident = st.selectbox(
            "Fechamento salvo",
            list(por_id)[::-1],
            format_func=lambda i: f"#{i} · {periodo(por_id[i]['resultado']['nucleo']['periodo'])}",
            key=f"fin_fech_{planta['id']}_{eq['id']}",
        )
        conta_salva(por_id[ident], ORIGEM_DA_CLASSE.get(planta["classe"]))
        renderizar_entrega(a, eq, ident)
        ver = painel(a, eq["id"])["verificado"]
    st.markdown("### Resultados das ações · histórico do equipamento")
    st.caption("Histórico completo disponível hoje; não se limita ao período do fechamento acima.")
    st.metric(
        "Economia verificada no histórico",
        brl(ver["total_brl"]) if ver["total_brl"] is not None else "Não apurada",
    )
    st.caption(ver["nota"])
    if ver["excluidas_por_sobreposicao"]:
        st.warning(
            "Há avaliações com períodos sobrepostos. Elas foram excluídas da soma para evitar dupla contagem."
        )
    if ver["itens"]:
        with st.expander("Ver ações, períodos e valores verificados"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Ação": x["descricao"],
                            "Período": periodo(x["periodo"]),
                            "Valor": brl(x["valor_brl"]),
                        }
                        for x in ver["itens"]
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    st.page_link(
        "paginas/acoes.py", label="Acompanhar verificações e ações", icon=":material/task_alt:"
    )
    st.page_link(
        "paginas/fechamentos.py",
        label="Gerenciar referência e fechamentos",
        icon=":material/event_available:",
    )
