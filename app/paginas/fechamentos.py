"""Fechamentos: referência versionada e fechamento recorrente de custo e desempenho (D93)."""

import json

import pandas as pd
import streamlit as st
from acompanhamento_ui import (
    autor,
    brl,
    chave_form,
    data,
    executar,
    exigir_autor,
    faixa_situacao,
    periodo,
    planta_e_equipamento,
    recarregar,
)
from componentes import cabecalho, incerteza_explicada, md

from euler.acompanhamento import ESTADOS, abrir_do_fechamento
from euler.armazem import ORIGEM_DA_CLASSE
from euler.entrega import entrega_do_fechamento, texto_entrega
from euler.evidencias import ROTULOS
from euler.fechamento import (
    TIPOS_REFERENCIA,
    criar_referencia,
    fechamento,
    fechamentos,
    p_atm,
    periodos_pendentes,
    produzir_fechamento,
    referencia_vigente,
    referencias,
    reproduzir,
)
from euler.formato import num
from euler.painel import texto_fechamento
from euler.periodos import periodos_entre_estoques


def bloco_referencia(a, equip, nome_autor) -> bool:
    ref = referencia_vigente(a, equip)
    if ref is not None:
        d = ref["dados"]
        st.markdown(
            f"**Referência v{ref['versao']}** · {periodo(ref)} · {TIPOS_REFERENCIA[ref['tipo']]} "
            f"· {num(d.get('consumo_t_t'), 3)} t de combustível por t de vapor"
        )
        if d.get("absorve_piora_pct"):
            st.warning(
                f"Esta referência absorveu uma piora de {num(d['absorve_piora_pct'], 1)}% em "
                f"relação à anterior, como mudança estrutural: {ref['motivo']}"
            )
    with st.expander(
        "Definir nova versão da referência" if ref else "Definir a referência", expanded=ref is None
    ):
        periodos = periodos_entre_estoques(a.pacote(equip, p_atm_bar=p_atm(a, equip)))
        if len(periodos) < 1:
            st.caption("Sem períodos completos entre medições de estoque.")
            return ref is not None
        rotulos = [f"{p[0]:%d/%m/%Y} a {p[1]:%d/%m/%Y}" for p in periodos]
        i, j = st.select_slider(
            "Períodos da referência",
            options=list(range(len(periodos))),
            value=(0, min(1, len(periodos) - 1)),
            format_func=lambda k: rotulos[k],
            key=chave_form("ref_periodos"),
        )
        tipos = ["inicial"] if ref is None else ["estrutural", "correcao_de_dados"]
        tipo = st.selectbox("Tipo", tipos, format_func=TIPOS_REFERENCIA.get)
        motivo = st.text_input("Motivo (fica no histórico)", key=chave_form("ref_motivo"))
        confirmar = (
            st.checkbox(
                "Confirmo que é uma mudança estrutural documentada, mesmo que o novo período seja pior",
                key=chave_form("ref_confirma"),
            )
            if ref is not None
            else False
        )
        if st.button("Registrar referência") and exigir_autor(nome_autor):
            executar(
                lambda: criar_referencia(
                    a,
                    equip,
                    periodos[i][0],
                    periodos[j][1],
                    tipo,
                    motivo,
                    nome_autor,
                    confirmar_absorcao=confirmar,
                ),
                "Referência registrada.",
                recarregar_tela=True,
            )
        if ref is not None:
            st.caption(
                "Versões anteriores nunca mudam; fechamentos antigos continuam reproduzíveis."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Versão": r["versao"],
                            "Período": periodo(r),
                            "Tipo": r["tipo"],
                            "Motivo": r["motivo"],
                            "Por": r["autor"],
                            "Em": data(r["criada_em"]),
                        }
                        for r in referencias(a, equip)
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    return ref is not None


def mostrar_fechamento(a, f, nome_autor) -> None:
    r = f["resultado"]
    n = r["nucleo"]
    conta = n["explicacao_conta"]
    st.markdown(f"### Fechamento #{f['id']} · {periodo(n['periodo'])}")
    faixa_situacao(r["situacao"], (conta.get("desvio") or {}).get("frase") or r["situacao_frase"])
    if conta.get("disponivel"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Custo do consumo observado", brl(conta["consumido"]["custo_brl"]), border=True)
        c2.metric(
            "Custo esperado (referência ajustada)", brl(conta["esperado"]["custo_brl"]), border=True
        )
        c3.metric("Desvio monetizado", brl(conta["desvio"]["custo_brl"]), border=True)
        st.caption(
            "Desvio monetizado não é oportunidade comprovada nem economia verificada. Política de "
            f"custo: {n['politica_custo']['descricao']}"
            + (f" ({n['politica_custo']['motivo']})" if n["politica_custo"].get("motivo") else "")
        )
        incerteza_explicada((conta.get("desvio") or {}).get("incerteza"), recolhido=True)
    st.markdown(
        md(f"**O que mudou desde o fechamento anterior:** {r['comparacao_anterior']['frase']}")
    )
    if r["contexto"].get("persistencia"):
        st.markdown(md(f"**Persistência:** {r['contexto']['persistencia']}"))
    st.markdown(md(f"**Próxima verificação:** {n['proxima_verificacao']['acao']}"))
    st.caption(
        "Força da evidência: "
        + " · ".join(f"{ROTULOS.get(k, k).lower()} {v.lower()}" for k, v in n["evidencias"].items())
    )
    if st.button("Abrir investigação deste desvio", key=f"inv_{f['id']}") and exigir_autor(
        nome_autor
    ):
        inv = executar(
            lambda: abrir_do_fechamento(a, f["id"], nome_autor), "Investigação atualizada."
        )
        if inv:
            st.session_state["acoes_inv_sel"] = inv["id"]
            st.success(f"Investigação #{inv['id']}: {inv['titulo']} ({ESTADOS[inv['estado']]}).")
            st.page_link(
                "paginas/acoes.py",
                label="Abrir em Investigações e ações",
                icon=":material/task_alt:",
            )
    with st.expander("Conta do período: compra, estoque, consumo e custo"):
        cp = n["conta_do_periodo"]
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Item": "Recebido (notas)",
                        "Quantidade": f"{num(cp['recebido_t'], 1)} t",
                        "Valor": brl(cp["valor_notas_brl"]),
                    },
                    {
                        "Item": "Estoque inicial",
                        "Quantidade": f"{num(cp['estoque_inicial_t'], 1)} t",
                        "Valor": "—",
                    },
                    {
                        "Item": "Estoque final",
                        "Quantidade": f"{num(cp['estoque_final_t'], 1)} t",
                        "Valor": "—",
                    },
                    {
                        "Item": "Consumido (E9)",
                        "Quantidade": f"{num(cp['consumido_t'], 1)} t",
                        "Valor": brl(cp["custo_atribuido_brl"]),
                    },
                    {
                        "Item": "Despesa ou pagamento do período",
                        "Quantidade": "—",
                        "Valor": "não informado",
                    },
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(cp["nota_pagamento"])
        ce = n["custo_por_energia"]
        st.caption(
            f"Custo por energia: R$ {num(ce['periodo_brl_gj'])}/GJ (base PCI úmido dos lotes)."
            if ce["periodo_brl_gj"] is not None
            else ce["motivo"]
        )
    if conta.get("disponivel") and conta["variacao"].get("disponivel"):
        with st.expander("Por que a conta mudou: produção, condição do vapor, qualidade, preço"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Parcela": x["titulo"],
                            "Pergunta": x["pergunta"],
                            "Valor": brl(x["custo_brl"])
                            if x["custo_brl"] is not None
                            else "no desvio",
                        }
                        for x in conta["variacao"]["componentes"]
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
            for x in conta["esperado"]["nao_ajustado"]:
                st.caption(x)
    with st.expander("O que investigar e ações anteriores"):
        for o in n["oportunidades"]:
            if o["prioridade"] in ("alta", "media"):
                st.markdown(
                    md(
                        f"- **{o['titulo']}** · evidência {o['evidencia'].lower()} · {brl(o['impacto_brl'])} associado (não somar) · {o['verificacao']}"
                    )
                )
        for x in n["sobreposicao"]:
            st.caption(x)
        for x in r["contexto"]["acoes"]:
            st.markdown(md(f"- Ação #{x['id']} ({data(x['data'])}) {x['descricao']}: {x['frase']}"))
        if not r["contexto"]["acoes"]:
            st.caption("Nenhuma ação registrada até este fechamento.")
    with st.expander("Rastreabilidade e reprodução"):
        st.caption(
            f"Dados da revisão {f['revisao_dados']} · conjunto {f['conjunto_sha'][:16]} · "
            f"núcleo {f['resultado_sha'][:16]} · código {f['versao_euler']} · referência "
            f"v{n['referencia']['versao']} · por {f['autor']} em {data(f['criado_em'])}"
        )
        refs = referencias(a, f["equipamento_id"])
        alvo = st.selectbox(
            "Reproduzir com a referência",
            [x["id"] for x in refs],
            index=[x["id"] for x in refs].index(f["referencia_id"]),
            format_func=lambda i: f"v{next(x['versao'] for x in refs if x['id'] == i)}",
            key=f"rep_ref_{f['id']}",
        )
        if st.button("Reproduzir", key=f"rep_{f['id']}"):
            rep = executar(lambda: reproduzir(a, f["id"], alvo))
            if rep:
                (st.success if rep["identico"] else st.info)(rep["frase"])
        c1, c2, c3 = st.columns(3)
        c1.download_button(
            "Baixar relatório",
            texto_fechamento(f, ORIGEM_DA_CLASSE.get(a.info["classe"])),
            f"fechamento-{f['id']}.md",
            "text/markdown",
        )
        c3.download_button(
            "Baixar a entrega do fechamento",
            texto_entrega(
                entrega_do_fechamento(a, f["equipamento_id"], f["id"]),
                a.equipamento(f["equipamento_id"]).get("nome"),
            ),
            f"entrega-fechamento-{f['id']}.md",
            "text/markdown",
            help="Resumo para a gestão: conta e o que mudou, pendências, verificações e ações "
            "em andamento e resultados já demonstrados.",
        )
        c2.download_button(
            "Baixar dados (JSON)",
            json.dumps(f, ensure_ascii=False, indent=1, default=str),
            f"fechamento-{f['id']}.json",
            "application/json",
        )


def mostrar() -> None:
    nome_autor = autor()
    with planta_e_equipamento(passo=("conta",)) as ctx:
        if ctx is not None:
            _, _, a, eq = ctx
            conteudo(a, eq["id"], nome_autor)


def conteudo(a, equip, nome_autor) -> None:
    cob = a.cobertura(equip)
    if cob["estado"] != "atualizado":
        st.warning(cob["frase"])
    if not bloco_referencia(a, equip, nome_autor):
        return
    pend = periodos_pendentes(a, equip)
    if pend:
        validos = sum(p["valido"] for p in pend)
        st.markdown(
            f"**{len(pend)} período(s) novo(s) para fechar** ({validos} com vapor e combustível conhecidos)."
        )
        for p in pend:
            if not p["valido"]:
                st.caption(f"{p['inicio']:%d/%m} a {p['fim']:%d/%m}: {p['motivo']}")
        if st.button("Produzir fechamento", type="primary") and exigir_autor(nome_autor):
            with st.spinner("Calculando o fechamento…"):
                f = executar(lambda: produzir_fechamento(a, equip, nome_autor))
            if f:
                st.session_state["acomp_fech"] = f["id"]
                recarregar(f"Fechamento #{f['id']} gravado.")
    else:
        st.caption(
            "Nenhum período novo desde o último fechamento: importe dados novos para continuar."
        )
    lista = fechamentos(a, equip)
    if not lista:
        return
    ids = [f["id"] for f in lista]
    atual = st.session_state.get("acomp_fech")
    escolhido = atual if atual in ids else ids[-1]
    mostrar_fechamento(a, fechamento(a, escolhido), nome_autor)
    st.markdown("### Histórico de fechamentos")
    st.caption("Todos os períodos ficam: favoráveis, desfavoráveis e inconclusivos.")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "#": f["id"],
                    "Período": periodo(f),
                    "Situação": f["resultado"]["situacao_frase"],
                    "Desvio": brl(
                        (f["resultado"]["nucleo"]["explicacao_conta"].get("desvio") or {}).get(
                            "custo_brl"
                        )
                    ),
                    "Referência": f"v{f['resultado']['nucleo']['referencia']['versao']}",
                    "Em": data(f["criado_em"]),
                }
                for f in reversed(lista)
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    if len(ids) < 2:
        return
    ver = st.selectbox(
        "Ver outro fechamento",
        ids[::-1],
        index=ids[::-1].index(escolhido),
        format_func=lambda i: f"#{i}",
    )
    if ver != escolhido:
        st.session_state["acomp_fech"] = ver
        st.rerun()


cabecalho(
    "Fechamentos",
    "Quanto custou, quanto seria esperado e o que mudou — a cada período, com histórico.",
    "Acompanhar a planta",
)
mostrar()
