"""Tela Saúde da caldeira: consumo por tonelada de vapor período a período (D65).

Logo depois de carregar os dados: o consumo de cada período entre medições de estoque, os
eventos registrados e um selo (mudou, estável ou não dá para dizer). Os números vêm de
`euler.saude`, que usa as mesmas contas da Investigação; a tela só arruma.
"""

import estado
import pandas as pd
import streamlit as st
from componentes import cabecalho, cartao, proximo_passo
from formatacao import variacao_referencia
from saude_visual import ROTULOS, consumo_kg, explicacao, grafico, indicadores

from euler.formato import num
from euler.saude import avaliar_saude

cabecalho(
    "Saúde da caldeira",
    "O consumo mudou? Veja o que merece atenção e por onde começar.",
    "Analisar um período",
)


@st.cache_data(show_spinner="Calculando o consumo período a período…", max_entries=16)
def _saude(assinatura: str, _pacote):
    """Guardada pela assinatura dos dados: voltar a esta tela não recalcula."""
    return avaliar_saude(_pacote)


def investigar(s) -> None:
    """Leva os períodos da mudança para a Investigação, já escolhidos."""
    st.session_state["periodos_escolhidos"] = {
        "assinatura": estado.assinatura(),
        "ref": s.referencia,
        "comp": s.mudanca,
    }
    # os controles da Investigação usam esta escolha como valor inicial
    for chave in (
        "periodo_ref",
        "periodo_comp",
        "periodo_ref_inicio",
        "periodo_ref_fim",
        "periodo_comp_inicio",
        "periodo_comp_fim",
    ):
        st.session_state.pop(chave, None)
    st.switch_page("paginas/investigacao.py")


def _eventos(s) -> None:
    if not s.eventos:
        st.caption("Nenhum evento registrado (limpeza, manutenção, troca de fornecedor…).")
        return
    st.markdown(
        "\n".join(
            f"{i}. **{e['instante']:%d/%m %H:%M}** · {e['tipo']}: {e['descricao']}"
            for i, e in enumerate(s.eventos, start=1)
        )
    )


def _tabela(s) -> None:
    linhas = [
        {
            "Período": f"{p.inicio:%d/%m} a {p.fim:%d/%m}",
            "Consumo (kg/t de vapor)": consumo_kg(p),
            "Em relação à referência": variacao_referencia(p),
            "Situação": ROTULOS[p.estado],
            "Limite da análise": p.motivo
            or (
                "Incerteza insuficiente ou comparação condicional"
                if p.estado == "nao_da_para_dizer" and p.consumo is not None
                else "—"
            ),
        }
        for p in s.periodos
    ]
    st.table(pd.DataFrame(linhas), hide_index=True, border="horizontal")


def _comparacao_por_carga(s) -> None:
    """Exibe a referência por carga já calculada pelo motor, sem alterar o selo."""
    with st.expander("Comparação por carga · análise complementar"):
        st.markdown(
            "**A produção de vapor ajuda a explicar a mudança de consumo?** Esta camada "
            "compara o combustível com uma referência ajustada à produção de vapor. "
            "O resultado é complementar: o selo acima continua usando a comparação "
            "com a incerteza das medições."
        )
        modelo = getattr(s, "baseline_carga", None)
        if modelo is None:
            st.info(
                "Não há uma referência por carga calculável com estes dados. O ajuste "
                "exige pelo menos três períodos de referência explicitamente estáveis, "
                "com consumo de combustível e vapor válidos e mais de uma carga observada."
            )
            return
        st.caption(
            f"Referência estimada com {modelo.n} períodos. Faixa observada: "
            f"{num(modelo.carga_min_t_h, 2)} a {num(modelo.carga_max_t_h, 2)} t/h de vapor. "
            "O motor não usa essa relação fora da faixa observada."
        )
        residuos = getattr(s, "residuos_carga", {})
        linhas = []
        for p in s.periodos:
            if p.estado == "referencia":
                continue
            valor = residuos.get(p.indice)
            linhas.append(
                {
                    "Período": f"{p.inicio:%d/%m} a {p.fim:%d/%m}",
                    "Desvio normalizado · estimado": (
                        "Não calculável" if valor is None else num(valor, 2)
                    ),
                }
            )
        if linhas:
            st.table(pd.DataFrame(linhas), hide_index=True, border="horizontal")
        st.caption(
            "O desvio é expresso em desvios-padrão de previsão, sem unidade: positivo "
            "significa consumo acima da referência por carga; negativo, abaixo. "
            "Não é probabilidade nem prova de uma causa. Sem regime estável, dados "
            "válidos, carga dentro da faixa ou dispersão estimável, o valor não é calculado. "
            "Esta camada ainda não inclui as incertezas instrumentais separadamente "
            "e está em revisão física."
        )


def mostrar(pacote) -> None:
    s = _saude(estado.assinatura(), pacote)
    titulo, resumo = explicacao(s)
    cor = {"mudou": "orange", "estavel": "blue"}.get(s.selo, "gray")
    with cartao("saude-selo"):
        st.markdown(f":{cor}-badge[CONSUMO DE COMBUSTÍVEL]")
        st.markdown(f"## {titulo}")
        st.write(resumo)
        if s.periodos:
            indicadores(s)
        with st.container(horizontal=True, gap="medium"):
            if s.mudanca is not None:
                if st.button(
                    "Investigar esta mudança",
                    type="primary",
                    icon=":material/troubleshoot:",
                    key="investigar_mudanca",
                ):
                    investigar(s)
            else:
                st.page_link(
                    "paginas/limites.py",
                    label="Ver o que os dados permitem",
                    icon=":material/rule:",
                )
            st.page_link(
                "paginas/financeiro.py", label="Ver impacto financeiro", icon=":material/payments:"
            )
    st.caption("Este painel acompanha consumo; não avalia a segurança da caldeira.")
    if s.periodos:
        grafico(s)
        with st.expander("Ver dados de cada período · valores e limites"):
            _tabela(s)
            st.caption(
                "Consumo = combustível queimado ÷ vapor produzido. "
                "Valores estimados a partir das medições; ± indica incerteza expandida (k = 2)."
            )
    with st.expander(f"Eventos registrados · {len(s.eventos)}"):
        _eventos(s)
        st.caption("Proximidade no tempo não comprova que um evento causou a mudança.")
    if s.periodos:
        _comparacao_por_carga(s)
    with st.expander("Como interpretar esta análise"):
        st.markdown(
            "- **Mudança detectada:** diferença maior que a incerteza declarada. Pode ser aumento ou redução.\n"
            "- **Sem mudança detectável:** os dados não distinguem a diferença da incerteza; não é prova de eficiência.\n"
            "- **Sem conclusão:** faltam medições ou incertezas, ou a comparação depende de condições adicionais.\n"
            "- **Referência:** primeira metade do histórico entre medições de estoque. "
            "É uma comparação histórica, não uma meta de eficiência ideal.\n"
            "- **Contexto:** carga, umidade e condições do vapor podem alterar o consumo. "
            "A relação kg/t, sozinha, não isola esses efeitos nem comprova desperdício."
        )
        st.page_link(
            "paginas/limites.py", label="Consultar dados e limites", icon=":material/rule:"
        )


pacote = estado.exigir_pacote()
if pacote is not None:
    mostrar(pacote)
    proximo_passo("paginas/limites.py", "Dados e limites")
