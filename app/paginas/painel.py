"""Painel: visão executiva do acompanhamento (D95).

O que mudou, o que olhar primeiro, o que está em andamento e o que já foi verificado. Lê os
registros persistidos; não estima nada. Oportunidades não confirmadas não são somadas e a
economia verificada não é contada duas vezes.
"""

import armazenamento as arm
import pandas as pd
import streamlit as st
from acompanhamento_ui import brl, data, faixa_situacao, periodo, planta_e_equipamento
from blocos.percurso import renderizar as renderizar_percurso
from componentes import cabecalho, md

from euler.fechamento import periodos_pendentes, previa_do_proximo_fechamento, versao_codigo
from euler.formato import num
from euler.painel import CRITERIOS, fila_de_atencao, painel

CORES = {
    "desvio_persistente": "red",
    "acao_sem_verificacao": "orange",
    "desvio_novo": "orange",
    "investigacao_aberta": "blue",
    "oportunidade": "violet",
    "dados": "gray",
}
SITUACAO_CURTA = {
    "acima": "desvio estabelecido",
    "nao_estabelecido": "desvio não estabelecido",
    "abaixo": "abaixo da referência",
    "sem_faixa": "sem faixa de incerteza",
}
ROTULO_CRITERIO = {
    "persistencia_fechamentos": "fechamentos seguidos acima",
    "magnitude_pct": "% do esperado",
    "faixa_brl": "faixa",
    "avaliacao": "avaliação",
    "ocorrencias": "ocorrências",
    "responsavel": "responsável",
    "estado": "situação",
    "evidencia": "evidência",
    "prioridade_investigacao": "prioridade da investigação",
    "complexidade_verificacao": "complexidade da verificação",
}


def valor_criterio(v) -> str:
    if isinstance(v, list):
        return f"{brl(v[0])} a {brl(v[1])}"
    if isinstance(v, float):
        return num(v, 1)
    texto = str(v)
    return texto.lower() if texto.isupper() else texto


def item_fila(i: dict) -> None:
    with st.container(border=True):
        st.badge(i["categoria_rotulo"], color=CORES[i["categoria"]])
        valor = i["valor_brl"]
        criterios = i["criterios"] or {}
        extra = ""
        if valor is not None and i["categoria"] == "oportunidade":
            extra = f" · {brl(valor)} associado (não somar)"
        elif valor is not None:
            situacao = criterios.get("situacao_do_desvio")
            extra = f" · desvio de {brl(valor)}" + (
                f" ({SITUACAO_CURTA[situacao]})" if situacao in SITUACAO_CURTA else ""
            )
        st.markdown(md(f"**{i['ordem']}. {i['titulo']}**{extra}"))
        if i.get("proxima_acao"):
            st.caption(md(f"Próximo passo: {i['proxima_acao']}"))
        visiveis = {
            k: v
            for k, v in criterios.items()
            if v not in (None, "", []) and k != "situacao_do_desvio"
        }
        if visiveis:
            st.caption(
                md(
                    " · ".join(
                        f"{ROTULO_CRITERIO.get(k, k.replace('_', ' '))}: {valor_criterio(v)}"
                        for k, v in visiveis.items()
                    )
                )
            )


@st.cache_data(show_spinner="Calculando a prévia do período novo…", max_entries=16)
def _previa(raiz: str, planta_id: str, equip_id: str, marco: tuple) -> dict | None:
    """Prévia do próximo fechamento (D108); `marco` muda quando os dados ou o histórico mudam."""
    a = arm.repositorio().armazem(planta_id)
    try:
        return previa_do_proximo_fechamento(a, equip_id)
    finally:
        a.fechar()


def aviso_dados_novos(prev: dict) -> None:
    """Dados novos desde o último fechamento: prévia rotulada, nunca gravada."""
    with st.container(border=True, key="painel-previa"):
        st.badge("Prévia · ainda não fechado", icon=":material/preview:", color="gray")
        if "motivo" in prev:
            st.markdown(md(f"**Há período completo ainda não fechado.** {prev['motivo']}"))
        else:
            st.markdown(
                md(f"**Período completo ainda não fechado: {periodo(prev)}.** {prev['frase']}")
            )
        st.caption(
            "A prévia usa a mesma conta do fechamento, mas não é gravada nem entra no "
            "histórico. Para registrar o resultado, feche o período."
        )
        st.page_link(
            "paginas/fechamentos.py", label="Fechar o período", icon=":material/event_available:"
        )


def mostrar() -> None:
    prev = None
    with planta_e_equipamento() as ctx:
        if ctx is None:
            return
        repo, planta, a, eq = ctx
        renderizar_percurso(a, eq["id"])
        p = painel(a, eq["id"])
        fila = fila_de_atencao(a, eq["id"])
        if p["ultimo_fechamento"] is not None and periodos_pendentes(a, eq["id"]):
            marco = (a.revisao, p["ultimo_fechamento"].get("id"), versao_codigo())
            prev = _previa(str(repo.raiz), planta["id"], eq["id"], marco)
    cob = p["cobertura"]
    if cob["estado"] != "atualizado":
        st.warning(cob["frase"], icon=":material/update:")
    u = p["ultimo_fechamento"]
    if u is None:
        st.info(
            "Ainda não há fechamento deste equipamento. Defina a referência e feche o primeiro "
            "período para o painel ganhar conteúdo."
        )
        st.page_link(
            "paginas/fechamentos.py", label="Ir para Fechamentos", icon=":material/event_available:"
        )
    else:
        st.markdown(
            f"#### Último fechamento · {periodo(u['periodo'])} · referência v{u['referencia_versao']}"
        )
        faixa_situacao(u["situacao"], u["frase"] or u["situacao_frase"])
        st.markdown(md(f"**O que mudou:** {u['mudanca']}"))
        if u.get("persistencia"):
            st.markdown(md(f"**Persistência:** {u['persistencia']}"))
    if prev:
        aviso_dados_novos(prev)
    inv = p["investigacoes"]
    acoes = p["acoes"]
    ver = p["verificado"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Investigações abertas", inv["abertas"], border=True)
    c2.metric("Encerradas", inv["encerradas"], border=True)
    c3.metric("Ações acompanhadas", len(acoes), border=True)
    c4.metric(
        "Economia verificada",
        brl(ver["total_brl"]) if ver["total_brl"] is not None else "nenhuma",
        border=True,
        help="Só entra aqui o resultado de ação avaliada pelo protocolo de verificação.",
    )
    l1, l2, l3 = st.columns(3)
    l1.page_link("paginas/acompanhamento.py", label="Atualizar dados", icon=":material/upload:")
    l2.page_link("paginas/fechamentos.py", label="Fechamentos", icon=":material/event_available:")
    l3.page_link("paginas/acoes.py", label="Investigações e ações", icon=":material/task_alt:")
    st.markdown("### O que olhar primeiro")
    if not fila:
        st.caption("Nada pendente: sem desvio estabelecido, ação sem verificação ou dado faltando.")
    for i in fila[:3]:
        item_fila(i)
    if len(fila) > 3:
        with st.expander(f"Outros itens para acompanhar ({len(fila) - 3})"):
            for i in fila[3:]:
                item_fila(i)
    if any(i["categoria"] == "oportunidade" for i in fila):
        st.caption(
            "Oportunidades aparecem uma a uma, sem soma: podem representar a mesma perda e "
            "nenhuma é ganho antes de verificada."
        )
    with st.expander("Como a ordem é definida"):
        st.caption(CRITERIOS)
    if ver["itens"]:
        st.markdown("### Resultados verificados")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Ação": f"#{v['intervencao_id']} · {v['descricao']}",
                        "Período avaliado": periodo(v["periodo"]),
                        "Economia verificada": brl(v["valor_brl"]),
                        "Faixa": f"{brl(v['faixa_brl'][0])} a {brl(v['faixa_brl'][1])}",
                        "Benefício líquido": brl(v["beneficio_liquido_brl"]),
                        "Na soma": "não (janela sobreposta)"
                        if v["intervencao_id"] in ver["excluidas_por_sobreposicao"]
                        else "sim",
                    }
                    for v in ver["itens"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        if ver["beneficio_liquido_brl"] is not None:
            st.markdown(md(f"**Benefício líquido somado:** {brl(ver['beneficio_liquido_brl'])}"))
        st.caption(ver["nota"])
    na_fila = {i["titulo"] for i in fila}
    outras = [o for o in p["oportunidades_nao_confirmadas"] if o["titulo"] not in na_fila]
    if outras:
        with st.expander(f"Outras oportunidades ainda não confirmadas ({len(outras)})"):
            st.caption("Uma a uma, sem soma: podem representar a mesma perda.")
            for o in outras:
                st.markdown(
                    md(
                        f"- **{o['titulo']}** · evidência {o['evidencia'].lower()} · "
                        f"{brl(o['impacto_brl'])} associado"
                    )
                )
    if acoes:
        with st.expander(f"Ações acompanhadas ({len(acoes)})"):
            for x in acoes:
                st.markdown(md(f"- {data(x['data'])} · {x['descricao']}: {x['frase']}"))
    if p["pendencias"]:
        with st.expander(f"Pendências dos registros ({len(p['pendencias'])})"):
            for x in p["pendencias"]:
                st.markdown(md(f"- {x}"))
    st.caption(
        "Desvio monetizado não é economia; oportunidade não confirmada não é ganho; só a "
        "economia verificada pelo protocolo entra como resultado. O benefício é das ações da planta."
    )


cabecalho(
    "Painel",
    "O que mudou, o que olhar primeiro e o que já foi verificado.",
    "Acompanhar a planta",
)
mostrar()
