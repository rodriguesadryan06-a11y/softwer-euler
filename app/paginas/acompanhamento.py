"""Atualizar dados: planta, equipamento e entrada incremental no mesmo banco (D92).

Envio → prévia → confirmação numa tela só. Os arquivos originais e os registros normalizados
entram na mesma transação; nada se duplica e nada é substituído em silêncio.
"""

import time
from pathlib import Path

import armazenamento as arm
import pandas as pd
import streamlit as st
from acompanhamento_ui import (
    autor,
    chave_form,
    data,
    executar,
    exigir_autor,
    mostrar_aviso,
    planta_e_equipamento,
    recarregar,
)
from componentes import cabecalho, md
from importacao_guiada import ajustes_do_lote, assinatura_envio, guia_importacao

from euler.armazem import CLASSES, POLITICAS_CUSTO, TAREFAS_ATENDIMENTO, cabecalho_csv
from euler.atendimento import (
    atendimentos_registrados,
    csv_atendimento,
    minutos_por_mes,
    registro_atendimento,
)
from euler.fechamento import (
    criar_referencia,
    precos,
    produzir_fechamento,
    registrar_preco,
)
from euler.io.esquemas import TABELAS
from euler.painel import indicadores_internos
from euler.periodos import periodos_entre_estoques

SITUACOES = {
    "nova": "Novos",
    "igual": "Já gravados (ignorados)",
    "conflito": "Conflitos",
    "rejeitada": "Recusados",
    "repetida_no_arquivo": "Repetidos no arquivo",
    "tardia": "Novos em período já coberto",
}
COLUNAS_CONTRATO = sorted({c.nome for t in TABELAS.values() for c in t.colunas})
DEMO = Path(__file__).resolve().parents[2] / "demo" / "caso_demo_completo"
FONTES = ("Enviar arquivos novos", "Usar versão já salva em Plantas e histórico")


def titulo_tabela(t: str) -> str:
    return TABELAS[t].titulo if t in TABELAS else t


def criar_demo(repo, nome_autor: str):
    """Planta sintética com o ato 1: equipamento, dados, referência e primeiro fechamento."""
    planta = repo.criar_planta("Demonstração · caldeira sintética", classe="sintetico")
    a = repo.armazem(planta["id"])
    try:
        a.criar_equipamento(
            "CALD-DEMO-01", "Caldeira de demonstração", "CALD-DEMO-01",
            config={"altitude_m": 1000.0}, autor=nome_autor,
        )  # fmt: skip
        arquivos = {p.name: p.read_bytes() for p in sorted(DEMO.glob("*.csv"))}
        a.confirmar(a.previa("CALD-DEMO-01", arquivos), autor=nome_autor)
        s = periodos_entre_estoques(a.pacote("CALD-DEMO-01"))
        criar_referencia(
            a, "CALD-DEMO-01", s[0][0], s[3][1], "inicial",
            "Agosto: quatro semanas de operação normal (demonstração)", nome_autor,
        )  # fmt: skip
        produzir_fechamento(a, "CALD-DEMO-01", nome_autor)
    finally:
        a.fechar()
    return planta


def cadastrar_planta(repo, nome_autor: str, aberto: bool) -> None:
    with st.expander("Cadastrar uma planta", expanded=aberto):
        with st.form(chave_form("nova_planta_acomp")):
            nome = st.text_input("Nome da planta", max_chars=160)
            classe = st.radio(
                "Origem dos dados", list(CLASSES), format_func=CLASSES.get, horizontal=True
            )
            autorizacao = st.text_input(
                "Autorização (obrigatória para dados de cliente: quem autorizou e quando)"
            )
            if st.form_submit_button("Criar planta"):
                p = executar(
                    lambda: repo.criar_planta(nome, classe=classe, autorizacao=autorizacao or None)
                )
                if p:
                    st.session_state["acomp_planta_atual"] = p["id"]
                    recarregar("Planta criada. Agora cadastre o equipamento.")
        st.divider()
        st.caption("Para conhecer o fluxo sem dados reais:")
        if st.button(
            "Criar planta de demonstração (sintética)", icon=":material/science:"
        ) and exigir_autor(nome_autor):
            with st.spinner(
                "Importando 8 semanas, definindo a referência e fechando o primeiro período…"
            ):
                p = executar(lambda: criar_demo(repo, nome_autor))
            if p:
                st.session_state["acomp_planta_atual"] = p["id"]
                st.session_state["acomp_equip_atual"] = "CALD-DEMO-01"
                recarregar(
                    "Planta de demonstração criada, com referência e primeiro fechamento. "
                    "Veja o resultado em **Painel** e **Fechamentos**."
                )


def cadastrar_equipamento(a, nome_autor: str, aberto: bool) -> None:
    with st.expander("Cadastrar equipamento", expanded=aberto), st.form("acomp_equip"):
        c1, c2 = st.columns(2)
        codigo = c1.text_input("Identificador interno", key="equip_id")
        nome = c2.text_input("Nome do equipamento", key="equip_nome")
        c3, c4 = st.columns(2)
        caldeira = c3.text_input(
            "Código da caldeira no diário (caldeira_id)", key="equip_caldeira_id"
        )
        altitude = c4.number_input("Altitude do local (m)", value=None, key="equip_altitude")
        if st.form_submit_button("Cadastrar equipamento"):
            r = executar(
                lambda: a.criar_equipamento(
                    codigo.strip(), nome.strip(), caldeira.strip() or None,
                    config={"altitude_m": altitude}, autor=nome_autor,
                ),
                "Equipamento cadastrado.",
            )  # fmt: skip
            if r:
                st.session_state["acomp_equip_atual"] = r["id"]
                recarregar("Equipamento cadastrado. Agora envie os dados na aba **Novos dados**.")


def mapeamento(brutos: dict[str, bytes], salvo: dict) -> dict:
    """Colunas fora do modelo: o usuário diz a que coluna do contrato cada uma corresponde."""
    fora = sorted(
        {
            c
            for n, b in brutos.items()
            if n.lower().endswith(".csv")
            for c in cabecalho_csv(b)
            if c not in COLUNAS_CONTRATO
        }
    )
    mapa = {}
    if not fora:
        return mapa
    with st.expander(f"Colunas com outro nome ({len(fora)})", expanded=not salvo):
        st.caption(
            "Diga a que coluna do modelo cada uma corresponde; deixe em branco para ignorar. "
            "Renomear não converte unidade."
        )
        opcoes = ["", *COLUNAS_CONTRATO]
        for c in fora:
            escolha = st.selectbox(c, opcoes, index=opcoes.index(salvo.get(c, "")), key=f"map_{c}")
            if escolha:
                mapa[c] = escolha
    return mapa


def novos_dados(repo, planta, a, eq, nome_autor: str) -> None:
    versoes = repo.listar_importacoes(planta["id"])
    tipo = st.radio("Origem dos arquivos", FONTES, horizontal=True, key="acomp_fonte_tipo")
    importacao_id = None
    if tipo == FONTES[0]:
        enviados = st.file_uploader(
            "Arquivos da planta (CSV ou Excel)",
            type=["csv", "xlsx"],
            accept_multiple_files=True,
            key=chave_form(f"up_{planta['id']}_{eq['id']}"),
        )
        if enviados and len({f.name for f in enviados}) != len(enviados):
            st.error("Há arquivos com nomes repetidos. Renomeie antes de enviar.")
            return
        brutos = {f.name: f.getvalue() for f in enviados or []}
    else:
        if not versoes:
            st.info("Nenhuma versão salva nesta planta.")
            return
        v = st.selectbox(
            "Versão salva", versoes, format_func=lambda x: f"{x['rotulo']} · {data(x['criado_em'])}"
        )
        importacao_id = v["id"]
        brutos = repo.carregar_importacao(planta["id"], v["id"])["arquivos"]
    if not brutos:
        st.caption("Envie os arquivos. Nada é gravado antes da sua confirmação.")
        return
    # Registro de atendimento (T16): relógio da tela, do arquivo recebido à confirmação.
    inicio = st.session_state.setdefault(
        f"acomp_inicio_{eq['id']}_{assinatura_envio(brutos, {})[:16]}", time.time()
    )
    fonte = st.text_input(
        "Nome da fonte (ex.: supervisório, planilha do turno)",
        value="Importação de arquivos",
        key="acomp_fonte_nome",
        help="O mapeamento de colunas fica salvo por fonte e equipamento.",
    ).strip()
    salvo = a.perfil(eq["id"], fonte) or {}
    guiado = tipo == FONTES[0] and st.toggle(
        "Adaptar minha planilha (nomes de colunas e unidades)",
        value=True,
        key="acomp_guia_ativo",
    )
    if guiado:
        try:
            lote, mapa = guia_importacao(
                brutos,
                chave=f"acomp_{planta['id']}_{eq['id']}",
                salvo=salvo,
                origem={
                    "sintetico": "sintetico",
                    "publico": "publico",
                    "cliente_autorizado": "real",
                }.get(planta["classe"]),
                caldeira=eq.get("caldeira_id"),
            )
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            return
        if lote is None:
            return
        brutos = lote
    else:
        mapa = mapeamento(brutos, salvo)
    salvar_perfil = st.checkbox(
        "Guardar o mapeamento para esta fonte", value=bool(mapa and not salvo)
    )
    chave = (
        planta["id"],
        eq["id"],
        importacao_id,
        assinatura_envio(brutos, mapa),
        fonte,
        tuple(sorted(mapa.items())),
    )
    if st.button("Preparar prévia", type="primary"):
        previa = executar(
            lambda: a.previa(
                eq["id"],
                brutos,
                fonte=fonte or None,
                mapeamento={} if guiado else mapa,
            )
        )
        if previa and guiado:
            # O lote já está adaptado; o perfil guarda apenas as escolhas de cabeçalho.
            # As unidades são confirmadas em cada envio e rastreadas no manifesto.
            previa.mapeamento = mapa
        st.session_state["acomp_previa"] = (chave, previa) if previa else None
    preparada = st.session_state.get("acomp_previa")
    if not preparada or preparada[0] != chave:
        return
    previa = preparada[1]
    st.dataframe(
        pd.DataFrame(
            [
                {"Tabela": titulo_tabela(t), **{SITUACOES[k]: v for k, v in c.items()}}
                for t, c in previa.contagem().items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Registros já gravados não se duplicam. Valores diferentes ficam pendentes de decisão."
    )
    for t, motivos in previa.tabelas_bloqueadas.items():
        st.error(f"{titulo_tabela(t)}: tabela recusada. " + " ".join(motivos))
    for av in previa.avisos:
        if av.tipo == "unidade_incompativel":
            st.warning(av.mensagem)
    recusadas = [x for x in previa.linhas if x.situacao == "rejeitada"]
    if recusadas:
        with st.expander(f"Recusados ({len(recusadas)})"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Tabela": titulo_tabela(x.tabela), "Linha": x.linha, "Motivo": x.motivo}
                        for x in recusadas[:500]
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    conflitos = [x for x in previa.linhas if x.situacao == "conflito"]
    if conflitos:
        with st.expander(f"Conflitos com dados já gravados ({len(conflitos)})", expanded=True):
            for x in conflitos[:50]:
                st.markdown(
                    md(
                        f"- {titulo_tabela(x.tabela)}, linha {x.linha}: "
                        + "; ".join(
                            f"{k}: {v['atual']} → {v['novo']}" for k, v in x.diferencas.items()
                        )
                    )
                )
    atencao = [
        av for av in previa.avisos if av.gravidade != "info" and av.tipo != "unidade_incompativel"
    ]
    if atencao:
        with st.expander(f"Avisos de qualidade ({len(atencao)})"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Tabela": titulo_tabela(av.tabela),
                            "Linha": av.linha,
                            "Aviso": av.mensagem,
                        }
                        for av in atencao
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    c1, c2 = st.columns([1, 1])

    def atendimento() -> dict:
        return {
            "segundos_na_tela": time.time() - inicio,
            "ajustes": ajustes_do_lote(brutos) if guiado else None,
        }

    if c1.button("Confirmar registros novos", type="primary") and exigir_autor(nome_autor):
        r = executar(
            lambda: a.confirmar(
                previa,
                autor=nome_autor,
                salvar_perfil=salvar_perfil,
                importacao_id=importacao_id,
                atendimento=atendimento(),
            ),
        )
        if r:
            st.session_state.pop("acomp_previa", None)
            recarregar(
                f"Importação gravada: {r['novas']} registros novos"
                + (
                    f"; {r['conflitos_pendentes']} conflito(s) aguardam decisão na aba Conflitos"
                    if r["conflitos_pendentes"]
                    else ""
                )
                + ". Os arquivos originais ficaram guardados."
            )
    with c2.popover("Confirmar como correção"):
        st.caption("Os valores diferentes viram nova versão; o original fica no histórico.")
        motivo = st.text_input("Motivo da correção", key="acomp_motivo_correcao")
        if st.button("Gravar correções") and exigir_autor(nome_autor):
            r = executar(
                lambda: a.confirmar(
                    previa, nome_autor, "correcao", motivo, salvar_perfil=salvar_perfil,
                    importacao_id=importacao_id, atendimento=atendimento(),
                ),
            )  # fmt: skip
            if r:
                st.session_state.pop("acomp_previa", None)
                recarregar("Correções gravadas; os valores anteriores ficam no histórico.")


def conflitos(a, eq, nome_autor: str) -> None:
    pend = a.conflitos(eq["id"])
    if not pend:
        st.caption("Nenhum conflito pendente.")
        return
    for c in pend:
        with st.container(border=True):
            st.markdown(f"**{titulo_tabela(c['tabela'])}** · {c['chave']}")
            for k, novo in c["proposto"].items():
                atual = (c["atual"] or {}).get(k)
                if atual != novo:
                    st.write(f"{k}: {atual} (gravado) → {novo} (novo arquivo)")
            motivo = st.text_input("Motivo da decisão", key=f"motivo_conf_{c['id']}")
            x, y = st.columns(2)
            for col, aceitar, rotulo, ok in (
                (x, True, "Aceitar o novo valor", "Nova versão gravada."),
                (y, False, "Manter o gravado", "Decisão registrada."),
            ):
                if col.button(rotulo, key=f"{int(aceitar)}_{c['id']}") and exigir_autor(nome_autor):
                    executar(
                        lambda c=c, m=motivo, ac=aceitar: a.resolver_conflito(
                            c["id"], ac, nome_autor, m
                        ),
                        ok,
                        recarregar_tela=True,
                    )


def configuracao(a, eq, nome_autor: str) -> None:
    cfg = eq["config"]
    with st.form(chave_form("acomp_config")):
        c1, c2 = st.columns(2)
        alt = c1.number_input(
            "Altitude do local (m)",
            # altitude gravada como inteiro (ex.: 1000) não pode quebrar o campo decimal
            value=None if cfg["altitude_m"] is None else float(cfg["altitude_m"]),
            step=10.0,
        )
        dias = c2.number_input(
            "Avisar desatualização depois de (dias sem dados)",
            min_value=1,
            value=int(cfg["dias_para_desatualizado"]),
        )
        politicas = list(POLITICAS_CUSTO)
        politica = st.selectbox(
            "Política de custo do combustível consumido",
            politicas,
            index=politicas.index(cfg["politica_custo"]),
            format_func=POLITICAS_CUSTO.get,
        )
        minimo = st.number_input(
            "Períodos completos exigidos depois de uma ação para verificar economia",
            value=int(cfg["periodos_minimos_pos_intervencao"]),
            min_value=1,
        )
        if st.form_submit_button("Salvar configuração") and exigir_autor(nome_autor):
            executar(
                lambda: a.configurar(
                    eq["id"],
                    {
                        "altitude_m": alt,
                        "dias_para_desatualizado": int(dias),
                        "politica_custo": politica,
                        "periodos_minimos_pos_intervencao": int(minimo),
                    },
                    nome_autor,
                ),
                "Configuração salva (o valor anterior fica no histórico).",
                recarregar_tela=True,
            )
    st.caption(
        "Configuração por equipamento, sem mudar código. Fechamentos antigos guardam a que usaram."
    )
    st.markdown("**Tabela de preços**")
    lista = precos(a, eq["id"])
    if lista:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Combustível": p["combustivel"],
                        "Fornecedor": p["fornecedor"] or "—",
                        "R$/t": p["preco_brl_t"],
                        "Adicional R$/t": p["custo_adicional_brl_t"],
                        "Adicional": p["custo_adicional_desc"] or "—",
                        "De": data(p["valido_de"]),
                        "Até": data(p["valido_ate"]),
                        "Origem": p["origem"],
                    }
                    for p in lista
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with st.form(chave_form("novo_preco")):
        c1, c2, c3 = st.columns(3)
        comb = c1.text_input("Combustível")
        forn = c2.text_input("Fornecedor (opcional)")
        preco = c3.number_input("Preço (R$/t)", min_value=0.0, value=None)
        c4, c5, c6 = st.columns(3)
        de = c4.date_input("Válido de", value=None, format="DD/MM/YYYY")
        ate = c5.date_input("Válido até (opcional)", value=None, format="DD/MM/YYYY")
        origem = c6.text_input("Origem (contrato, nota, cotação)")
        c7, c8 = st.columns(2)
        adicional = c7.number_input("Custo adicional (R$/t, opcional)", min_value=0.0, value=None)
        desc = c8.text_input("Descrição do adicional (ex.: frete)")
        if st.form_submit_button("Registrar preço") and exigir_autor(nome_autor):
            fuso = "America/Sao_Paulo"
            executar(
                lambda: registrar_preco(
                    a, eq["id"], comb, preco, pd.Timestamp(de).tz_localize(fuso), origem, nome_autor,
                    valido_ate=None if ate is None else pd.Timestamp(ate).tz_localize(fuso),
                    fornecedor=forn or None, custo_adicional_brl_t=adicional,
                    custo_adicional_desc=desc or None,
                ),
                "Preço registrado.",
                recarregar_tela=True,
            )  # fmt: skip
    st.caption(
        "Usada só com a política 'tabela de preços'. Mais de um preço vigente no mesmo período "
        "deixa o custo ausente até haver regra de rateio; nada é escolhido em silêncio."
    )


def historico(a, eq, planta, nome_autor: str) -> None:
    lotes = a.importacoes(eq["id"])
    if lotes:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Quando": data(x["recebido_em"]),
                        "Quem": x["autor"],
                        "Fonte": x["fonte"] or "—",
                        "Modo": "correção" if x["modo"] == "correcao" else "incremental",
                        "Novos": x["resumo"].get("novas"),
                        "Corrigidos": x["resumo"].get("corrigidas"),
                        "Conflitos": x["resumo"].get("conflitos_pendentes"),
                    }
                    for x in lotes
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("Nenhuma importação neste equipamento ainda.")
    with st.expander("Todas as alterações (auditoria)"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Quando": data(e["quando"]),
                        "O quê": f"{e['entidade']} {e['entidade_id']}",
                        "Ação": e["tipo"],
                        "Quem": e["autor"] or "—",
                    }
                    for e in a.eventos(eq["id"], limite=500)
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with st.expander("Atendimento desta caldeira (uso interno, só nesta instalação)"):
        atendimento_interno(a, eq, planta, nome_autor)


def _duracao(segundos: float | None) -> str:
    if segundos is None:
        return "sem medição"
    if segundos < 60:
        return "menos de 1 min"
    if segundos < 3600:
        return f"{segundos / 60:.0f} min"
    return f"{segundos / 3600:.1f} h"


def atendimento_interno(a, eq, planta, nome_autor: str) -> None:
    """Registro de atendimento (T16): o caminho até o 1º fechamento e as horas da equipe."""
    r = registro_atendimento(a, eq["id"])
    st.markdown("**Do primeiro envio ao primeiro fechamento** · medido nos registros")
    c1, c2, c3 = st.columns(3)
    horas = r["horas_ate_primeiro_fechamento"]
    c1.metric(
        "Calendário",
        "sem fechamento" if horas is None else _duracao(horas * 3600),
        help="Do primeiro lote importado ao primeiro fechamento, incluindo esperas fora da EULER.",
    )
    c2.metric(
        "Tempo na tela de envio",
        _duracao(r["segundos_na_tela"]),
        help="Do arquivo recebido à confirmação, somado nos envios medidos (inclui pausas).",
    )
    c3.metric(
        "Ajustes feitos à mão",
        "sem medição" if r["ajustes"] is None else str(r["ajustes"]),
        help="Campos que a pessoa precisou mudar ou preencher na conferência da planilha.",
    )
    st.caption(
        f"{r['envios_ate_fechamento']} envio(s) até o primeiro fechamento; "
        f"{r['envios_medidos']} com medição da tela"
        + (
            f", {r['envios_sem_medicao']} sem medição (anteriores ao registro ou automáticos)."
            if r["envios_sem_medicao"]
            else "."
        )
    )
    st.markdown("**Horas da equipe com este cliente** · lançadas por quem atendeu")
    with st.form(chave_form(f"atendimento_{eq['id']}")):
        c1, c2, c3 = st.columns([1, 2, 1])
        dia = c1.date_input("Dia", format="DD/MM/YYYY")
        tarefa = c2.selectbox(
            "Tarefa", list(TAREFAS_ATENDIMENTO), format_func=TAREFAS_ATENDIMENTO.get
        )
        minutos = c3.number_input("Minutos", min_value=1, max_value=1440, value=None, step=5)
        nota = st.text_input("Nota (opcional)", max_chars=500)
        if st.form_submit_button("Lançar atendimento") and exigir_autor(nome_autor):
            executar(
                lambda: a.registrar_atendimento(
                    eq["id"], dia.isoformat() if dia else "", tarefa, minutos, nome_autor, nota
                ),
                "Atendimento lançado.",
                recarregar_tela=True,
            )
    registros = atendimentos_registrados(a, eq["id"])
    if registros:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Mês": mes,
                        "Horas": round(m["minutos"] / 60, 2),
                        **{
                            TAREFAS_ATENDIMENTO[t]: round(v / 60, 2)
                            for t, v in m["por_tarefa"].items()
                        },
                    }
                    for mes, m in minutos_por_mes(registros).items()
                ]
            ).fillna(0),
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Baixar atendimento.csv",
            csv_atendimento(planta["nome"], eq["id"], registros),
            file_name=f"atendimento_{eq['id']}.csv",
            mime="text/csv",
        )
    else:
        st.caption("Nenhuma hora lançada ainda: sem lançamento, o total fica sem dado (não zero).")
    st.caption("Contagens dos registros (nada é coletado à parte nem enviado):")
    st.json(indicadores_internos(a, eq["id"]), expanded=False)


def mostrar() -> None:
    nome_autor = autor()
    mostrar_aviso()
    repo = arm.repositorio()
    tem_plantas = bool(repo.listar_plantas())
    cadastrar_planta(repo, nome_autor, aberto=not tem_plantas)
    if not tem_plantas:
        return
    with planta_e_equipamento(exigir_equipamento=False, passo=("registros",)) as ctx:
        if ctx is None:
            return
        repo, planta, a, eq = ctx
        cadastrar_equipamento(a, nome_autor, aberto=eq is None)
        if eq is None:
            return
        cob = a.cobertura(eq["id"])
        if cob["estado"] == "atualizado":
            st.caption(f":material/check_circle: {cob['frase']}")
        else:
            st.warning(cob["frase"], icon=":material/update:")
        diario = cob["tabelas"].get("diario") or {}
        c1, c2, c3 = st.columns(3)
        c1.metric("Diário desde", data(diario.get("inicio")))
        c2.metric("até", data(diario.get("fim")))
        c3.metric("Última importação", data(cob["ultima_importacao"]))
        pendentes = st.container()  # espaço fixo (ver mostrar_aviso)
        if cob["conflitos_pendentes"]:
            pendentes.warning(
                f"{cob['conflitos_pendentes']} conflito(s) aguardam decisão na aba **Conflitos**.",
                icon=":material/rule:",
            )
        # rótulos fixos: a aba escolhida continua aberta depois de gravar
        abas = st.tabs(
            ["Novos dados", "Conflitos", "Configuração e preços", "Histórico"], key="acomp_aba"
        )
        with abas[0]:
            novos_dados(repo, planta, a, eq, nome_autor)
        with abas[1]:
            conflitos(a, eq, nome_autor)
        with abas[2]:
            configuracao(a, eq, nome_autor)
        with abas[3]:
            historico(a, eq, planta, nome_autor)
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.page_link(
                "paginas/fechamentos.py",
                label="Fechar o período",
                icon=":material/event_available:",
            )
            st.caption("Próximo passo do acompanhamento: custo, desvio e o que mudou.")
        with c2:
            if st.button("Analisar série acumulada", icon=":material/troubleshoot:") and executar(
                lambda: arm.abrir_serie(planta, a, eq["id"], autor=nome_autor)
            ):
                st.success("Série carregada: abra Investigação, Saúde ou Financeiro para analisar.")
            st.caption("Leva os registros desta revisão para as telas de análise de um período.")


cabecalho(
    "Atualizar dados",
    "Acrescente os dados novos da planta: nada se duplica e nada é substituído em silêncio.",
    "Acompanhar a planta",
)
try:
    mostrar()
except arm.ERROS as exc:
    st.error(f"Operação não concluída: {exc}")
