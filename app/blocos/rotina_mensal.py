"""Orientação mensal e memória da planta, usando somente resultados já registrados."""

import pandas as pd
import streamlit as st
from acompanhamento_ui import brl, data
from componentes import md
from visao_mensal import orientacao_do_mes

from euler.formato import num
from euler.mensal import resumo_do_mes


def rotina(plano: dict) -> None:
    titulo, instrucao = orientacao_do_mes(plano["estado"])
    with st.container(border=True):
        st.markdown(md(f"**Seu próximo passo · {titulo}**"))
        st.caption(instrucao)
        if plano["estado"] in ("pronto", "revisar", "aguarda_anterior"):
            destino, rotulo = "fechamentos", "Conferir fechamento"
        elif plano["estado"] == "fechado":
            destino, rotulo = "acoes", "Acompanhar verificações"
        else:
            destino, rotulo = "acompanhamento", "Atualizar dados"
        st.page_link(f"paginas/{destino}.py", label=rotulo, icon=":material/arrow_forward:")


def registro_do_mes(resumo: dict) -> None:
    """Identifica autoria informada e cobertura; aprovação não valida a causa física."""
    cob = resumo.get("cobertura", {})
    autores = sorted({t.get("autor") or "Não informado" for t in resumo["trechos"]})
    datas = [t["criado_em"] for t in resumo["trechos"] if t.get("criado_em")]
    st.caption(
        md(
            f"Registros aprovados por: {', '.join(autores)} · "
            f"último registro em {data(max(datas)) if datas else '—'}."
        )
    )
    if not resumo["completo"]:
        st.warning(
            "Conta parcial · há dados faltantes, períodos sem aprovação ou revisão pendente. "
            "Os valores não representam todo o mês."
        )
    if cob:
        st.caption(
            f"Cobertura dos registros aprovados: {num(cob['dias_com_conta'], 1)} dias "
            f"com conta no calendário do mês. "
            "Os períodos seguem as medições de estoque, sem completar dias ausentes."
        )
    motivos = resumo.get("motivos", [])
    if motivos:
        st.caption(md(motivos[0]))
    with st.expander("Ver cobertura, motivos e versões dos registros"):
        for motivo in motivos[1:]:
            st.caption(md(motivo))
        for frase in cob.get("frases", []):
            st.caption(md(frase))
        for t in resumo["trechos"]:
            st.markdown(
                md(
                    f"**#{t['fechamento_id']} · {data(t['inicio'])} a {data(t['fim'])}**  \n"
                    f"{t.get('autor') or 'Autoria não informada'} · {data(t.get('criado_em'))} · "
                    f"revisão dos dados {t.get('revisao_dados', '—')}"
                )
            )
            if t.get("revisa"):
                st.caption(
                    md(
                        f"Revisa #{t['revisa']}: {t.get('motivo_revisao') or 'motivo não informado'}"
                    )
                )
        st.caption(
            "Nome informado no registro; não é assinatura digital nem autenticação. "
            "Aprovar a conta não confirma a causa do desvio ou uma economia."
        )


def historico(a, equip: str, planos: list[dict]) -> None:
    st.markdown("### Histórico mensal da caldeira")
    com_registro = [p for p in planos if p["fechamentos"]]
    if not com_registro:
        st.caption("O primeiro fechamento inicia a memória mensal da planta.")
        return
    fechados = sum(p["estado"] == "fechado" for p in com_registro)
    st.caption(
        f"{len(com_registro)} mês(es) com registros · {fechados} fechado(s) · "
        "valores vigentes, sem somar novamente versões substituídas."
    )
    linhas = []
    for p in reversed(com_registro):
        r = resumo_do_mes(a, equip, p["mes"], plano=p)
        if r is None:
            continue
        autores = sorted({t.get("autor") or "Não informado" for t in r["trechos"]})
        datas = [t["criado_em"] for t in r["trechos"] if t.get("criado_em")]
        linhas.append(
            {
                "Mês": r["rotulo"],
                "Situação": p["estado_rotulo"],
                "Conta": "Completa nos períodos registrados"
                if r["completo"]
                else "Parcial / conferir motivos",
                "Consumido": brl(r["consumido_brl"]),
                "Esperado": brl(r["esperado_brl"]),
                "Diferença estimada": brl(r["diferenca_brl"]),
                "Registrado por": ", ".join(autores),
                "Último registro": data(max(datas)) if datas else "—",
            }
        )
    df = pd.DataFrame(linhas)
    st.dataframe(df, hide_index=True, width="stretch")
    st.caption(
        "Diferença estimada não é economia. Coberturas e condições podem variar entre meses; "
        "o histórico permite conferir essas diferenças, não prova melhora por si só."
    )
    st.download_button(
        "Baixar histórico mensal",
        df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="euler_historico_mensal.csv",
        mime="text/csv",
        icon=":material/download:",
    )
