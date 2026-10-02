"""Tela Dados e limites: o que dá e o que não dá para concluir, e por quê (T11)."""

import estado
import pandas as pd
import streamlit as st
from componentes import cabecalho, cartao, proximo_passo
from formatacao import COLUNAS_RESUMO, SITUACAO_PERIODO, linhas_por_periodo

from euler.capacidades import avaliar
from euler.fluxos import balanco_por_vazoes
from euler.formato import plural
from euler.periodos import periodos_entre_estoques
from euler.planta import mapear_planta
from euler.tipos import AnaliseBloqueada

cabecalho(
    "Dados e limites",
    "A EULER começa perguntando **o que esta planta tem?** e escolhe a rota física compatível "
    "com os sinais disponíveis. Quando uma pergunta exige algo que a planta não mede, ela usa "
    "outra rota quando existe; se não existe, mostra exatamente o limite sem inventar dados.",
    "Passo 3 de 6",
)

ICONE = {
    "habilitada": ":material/check_circle:",
    "parcial": ":material/contrast:",
    "bloqueada": ":material/block:",
}
ROTULO = {"habilitada": "Dá para concluir", "parcial": "Dá, com limites", "bloqueada": "Bloqueada"}


def qualidade(pacote) -> None:
    """Resumo dos avisos de qualidade (a lista completa fica em Importar dados)."""
    avisos = pacote.tabela_avisos()
    n = avisos["Gravidade"].value_counts()
    with cartao("qualidade"):
        st.markdown(
            ":material/fact_check: **Qualidade dos registros:** "
            f"{plural(int(n.get('Erro', 0)), 'erro', 'erros')} · "
            f"{plural(int(n.get('Atenção', 0)), 'aviso de atenção', 'avisos de atenção')} · "
            f"{plural(int(n.get('Informação', 0)), 'informação', 'informações')}. "
            "Nada foi corrigido nem preenchido em silêncio."
        )
        atencao = avisos[avisos["Gravidade"].isin(["Erro", "Atenção"])]
        if len(atencao):
            st.markdown(
                "\n".join(f"- {linha.Tabela}: {linha.Aviso}" for linha in atencao.itertuples())
            )
        st.page_link(
            "paginas/importar.py",
            label="Ver todos os avisos em Importar dados",
            icon=":material/list_alt:",
        )


def _capacidade_completa(c) -> None:
    """Análise bloqueada ou com limites: mostra por quê e o que fazer para liberar."""
    with cartao(f"cap-{c.id}"):
        cabeca, situacao = st.columns([4, 1])
        cabeca.markdown(f"**{c.nome}**  \n{c.pergunta}")
        cor = "red" if c.situacao == "bloqueada" else "orange"
        situacao.markdown(f":{cor}-badge[{ICONE[c.situacao]} {ROTULO[c.situacao]}]")
        if c.motivos:
            st.markdown("**Por quê:**\n" + "\n".join(f"- {m}" for m in c.motivos))
        if c.o_que_fazer:
            st.markdown("**Para liberar:**\n" + "\n".join(f"- {o}" for o in c.o_que_fazer))


def mapa_adaptativo(pacote) -> None:
    """Mostra as rotas que nascem dos dados disponíveis, antes da lista rígida histórica."""
    perfil = mapear_planta(pacote)
    st.markdown("### O que esta planta tem?")
    st.caption(
        "O motor monta a investigação a partir dos sinais observados. Uma rota disponível "
        "não significa causa comprovada; significa apenas que aquela pergunta física já pode "
        "ser tratada com os dados existentes."
    )
    sinais, rotas, parciais = st.columns(3)
    sinais.metric("Sinais reconhecidos", len(perfil.sinais), border=True)
    rotas.metric("Rotas físicas disponíveis", len(perfil.disponiveis), border=True)
    parciais.metric(
        "Rotas parciais",
        sum(r.situacao == "parcial" for r in perfil.rotas),
        border=True,
    )

    disponiveis = [r for r in perfil.rotas if r.situacao == "disponivel"]
    if disponiveis:
        with cartao("rotas-disponiveis"):
            st.markdown("**Já dá para trabalhar com:**")
            for rota in disponiveis:
                usando = ", ".join(rota.usando) if rota.usando else "dados já observados"
                st.markdown(
                    f"- **{rota.nome}** · rota: *{rota.alternativa}*  \n"
                    f"  {rota.pergunta}  \n"
                    f"  :gray[Usando: {usando}]"
                )

    # Se a planta já entrega vazões dos dois lados, calcula uma rota independente do pátio.
    rota_eta = perfil.rota("eficiencia_direta")
    diario = pacote.dados("diario")
    if (
        diario is not None
        and rota_eta.situacao == "disponivel"
        and rota_eta.alternativa == "historiador por vazões"
    ):
        try:
            b = balanco_por_vazoes(diario)
            st.markdown("#### Balanço disponível pelo historiador")
            m1, m2, m3 = st.columns(3)
            m1.metric("Eficiência combustível → vapor", f"{100*b.eficiencia:.1f}%", border=True)
            m2.metric("Cobertura comum", f"{100*b.cobertura:.0f}%", border=True)
            m3.metric("Intervalos usados", b.intervalos_usados, border=True)
            st.caption(b.nota)
        except AnaliseBloqueada as erro:
            st.info(f"A rota por vazões existe, mas este recorte ainda não fecha: {erro.motivo}")

    incompletas = [r for r in perfil.rotas if r.situacao == "parcial"]
    if incompletas:
        with st.expander("Rotas que ficam disponíveis com pouco dado adicional"):
            for rota in incompletas:
                st.markdown(
                    f"**{rota.nome}** · melhor rota atual: *{rota.alternativa}*  \n"
                    f"Já temos: {', '.join(rota.usando) or '—'}  \n"
                    f"Falta: {', '.join(rota.faltam) or '—'}"
                )


def mostrar(pacote) -> None:
    mapa_adaptativo(pacote)
    caps = avaliar(pacote)
    contagem = {s: sum(c.situacao == s for c in caps) for s in ROTULO}
    m1, m2, m3 = st.columns(3)
    m1.metric("Análises liberadas", contagem["habilitada"], border=True)
    m2.metric("Com limites", contagem["parcial"], border=True)
    m3.metric("Bloqueadas", contagem["bloqueada"], border=True)
    qualidade(pacote)

    atencao = [c for c in caps if c.situacao != "habilitada"]
    if atencao:
        st.markdown("### Precisa de dados para concluir")
        for c in atencao:
            _capacidade_completa(c)

    liberadas = [c for c in caps if c.situacao == "habilitada"]
    if liberadas:
        st.markdown("### Liberadas com estes dados")
        with cartao("liberadas"):
            metade = (len(liberadas) + 1) // 2
            for coluna, grupo in zip(
                st.columns(2, gap="large"), (liberadas[:metade], liberadas[metade:]), strict=True
            ):
                coluna.markdown(
                    "\n\n".join(
                        f":green[{ICONE['habilitada']}] **{c.nome}**  \n:gray[{c.pergunta}]"
                        for c in grupo
                    )
                )

    with st.expander("Detalhes técnicos: equações e decisões de cada análise"):
        st.markdown(
            "Itens E (equações) de `docs/fisica_para_revisao.md` e propostas D de "
            "`docs/decisoes.md`, todos em revisão.\n\n"
            + "\n".join(f"- {c.nome}: {c.referencia}" for c in caps if c.referencia)
        )

    periodos = periodos_entre_estoques(pacote)
    if periodos:
        st.caption(
            f"{plural(len(periodos), 'período', 'períodos')} entre medições de estoque, de "
            f"{periodos[0][0]:%d/%m/%Y} a {periodos[-1][1]:%d/%m/%Y}."
        )


@st.cache_data(show_spinner="Calculando período a período…", max_entries=16)
def _linhas_por_periodo(assinatura: str, _pacote) -> list[dict]:
    """Guardada pela assinatura dos dados (arquivos + altitude): voltar a esta tela não
    recalcula as semanas."""
    return linhas_por_periodo(_pacote)


def por_periodo(pacote) -> None:
    periodos = periodos_entre_estoques(pacote)
    if not periodos:
        return
    st.markdown("### Período a período")
    st.caption(
        "Cada linha vai de uma medição de estoque à seguinte. **Com limites**: falta a "
        "incerteza de algum instrumento ou a perda nos gases; **Não dá para concluir**: falta a "
        "eficiência ou o consumo. O motivo de cada um está em “Ver detalhes de cada período”."
    )
    linhas = _linhas_por_periodo(estado.assinatura(), pacote)
    resumo = pd.DataFrame(linhas)[list(COLUNAS_RESUMO)]
    resumo["Situação"] = resumo["Situação"].map(
        lambda s: f":{SITUACAO_PERIODO.get(s, 'gray')}-badge[{s}]"
    )
    st.table(resumo, hide_index=True, border="horizontal")
    with st.expander("Ver detalhes de cada período"):
        detalhes = pd.DataFrame(linhas).drop(columns=["Eficiência", "Situação"])
        # tabela simples: quebra o texto e mostra o motivo inteiro
        st.table(detalhes, hide_index=True, border="horizontal")
        st.markdown(
            "**Como ler as colunas de eficiência.** A **eficiência direta** supõe que o "
            "combustível queimado tem a qualidade do recebido no período. A coluna "
            "**Eficiência conforme o pátio** mostra os limites possíveis conforme o uso do pátio "
            "(quanto maior o estoque perto do consumido, mais larga a faixa). São cenários de "
            "contabilidade do pátio, não intervalo de confiança nem desempenho validado: um "
            "limite acima de 100% menos a perda nos gases calculada para o mesmo período (mesma "
            "fronteira e base PCI) é incompatível com ela e só mostra quanto o pátio pode pesar "
            "no resultado. Os limites não são cortados."
        )


pacote = estado.exigir_pacote()
if pacote is not None:
    mostrar(pacote)
    por_periodo(pacote)
    proximo_passo("paginas/investigacao.py", "4. Investigação")
