"""Tela Importar dados: envio dos arquivos e lista de avisos de qualidade (T03, T05)."""

import armazenamento as arm
import estado
import streamlit as st
from componentes import cabecalho, cartao, proximo_passo
from importacao_guiada import assinatura_envio, guia_importacao

from euler.capacidades import avaliar
from euler.formato import num
from euler.io import fontes_de_arquivos, importar_pacote
from euler.io.esquemas import TABELAS
from euler.io.modelos import ARQUIVO_PLANILHA

COR_GRAVIDADE = {"Erro": "red", "Atenção": "orange", "Informação": "gray"}

cabecalho(
    "Importar dados",
    "Carregue os registros disponíveis. A EULER mostra o que pode analisar e o que ainda falta.",
    "Analisar um período",
)

if st.session_state.get("arquivos"):
    with st.container(border=True):
        st.markdown("**Dados em uso:** " + estado.rotulo_dados())
        st.caption(
            "Uma nova importação substitui todo o conjunto atual. Não mistura com a demonstração."
        )
        st.button(
            "Limpar dados e começar de novo",
            key="limpar_dados",
            icon=":material/restart_alt:",
            on_click=estado.limpar_dados,
        )
        st.caption("Limpa esta sessão. Arquivos e versões salvas no banco permanecem intactos.")

st.page_link(
    "paginas/plantas.py",
    label="Reabrir dados salvos ou cadastrar uma planta",
    icon=":material/database:",
)

with st.expander("Como preparar os dados de uma empresa"):
    st.markdown(
        "1. **Envie sua própria planilha** e confirme a correspondência das colunas e unidades, "
        "ou baixe o modelo pronto. Títulos acima do cabeçalho, Data e Hora em colunas "
        "separadas e unidades como kgf/cm², °F ou t/h são reconhecidos; confira as sugestões.\n"
        "2. **Apague as linhas sintéticas de exemplo** de todas as abas. Preencha só os registros reais disponíveis.\n"
        "3. Use uma **caldeira por análise**, com identificação, datas e horários coerentes. "
        "Na coluna de origem dos registros, indique que os dados são reais. "
        "Mantenha estimativas identificadas como tal; não transforme valores desconhecidos em zero.\n"
        "4. Informe a altitude do local e envie a planilha ou selecione todos os CSVs do novo conjunto.\n"
        "5. Prepare a prévia, confira os avisos e confirme a importação. Depois abra **Saúde da caldeira** "
        "ou **Dados e limites**. Não é preciso preencher todos os campos para começar."
    )
    st.caption(
        "O guia ajuda a associar nomes e converter unidades compatíveis. "
        "Não transforme preço por tonelada em preço total sem os registros necessários."
    )
    with st.expander("Detalhes técnicos · origem dos registros"):
        st.markdown("Na planilha, preencha a coluna `origem_dado` com `real` nos registros reais.")

geracao = st.session_state.get("importacao_geracao", 0)
local, envio = st.columns([1, 2], gap="medium")
with local, cartao("local"):
    st.markdown("**1. Local da caldeira**")
    altitude = st.number_input(
        "Altitude do local (m)",
        min_value=-500.0,
        max_value=5000.0,
        value=None,
        key=f"altitude_envio_{geracao}",
        step=10.0,
        placeholder="ex.: 1100",
        help="Usada para converter a pressão do manômetro em pressão absoluta.",
    )
    st.caption("Local dos novos arquivos. A altitude da demonstração não é reutilizada.")
    if altitude is None:
        st.caption(
            "Sem altitude, a conversão de pressão manométrica fica limitada. "
            "Pressão já informada como absoluta segue suas próprias verificações."
        )
    else:
        st.caption(
            f"Pressão atmosférica: **{num(estado.p_atm_por_altitude_bar(altitude), 3)} bar** "
            "(estimado pela altitude, atmosfera padrão)."
        )

with envio, cartao("arquivos"):
    st.markdown("**2. Arquivos da fábrica**")
    enviados = st.file_uploader(
        "Arquivos (CSV ou planilha .xlsx)",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=f"envio_{geracao}",
    )
    ctx = arm.contexto()
    salvar_no_banco = False
    autor_importacao, motivo_importacao = "", ""
    if ctx:
        salvar_no_banco = st.checkbox(
            f"Salvar nova versão em {ctx['planta_nome']}", value=True, key="salvar_importacao_banco"
        )
        if salvar_no_banco:
            autor_importacao = st.text_input(
                "Responsável pela importação", value=ctx.get("autor", "")
            )
            motivo_importacao = st.text_input(
                "Motivo da nova versão", placeholder="Ex.: novo período ou correção de origem"
            )
            st.caption(
                "Envie o conjunto completo. As versões anteriores serão preservadas; não há união automática de linhas."
            )
    else:
        st.caption("A importação fica na sessão até você salvá-la em Plantas e histórico.")
    arquivos = None
    if enviados:
        if len({f.name for f in enviados}) != len(enviados):
            st.error("Há arquivos com o mesmo nome. Renomeie antes de importar.")
        else:
            brutos = {f.name: f.getvalue() for f in enviados}
            guiado = st.toggle("Adaptar minha planilha (nomes de colunas e unidades)", value=True)
            try:
                arquivos, _ = (
                    guia_importacao(brutos, chave="importacao_avulsa") if guiado else (brutos, {})
                )
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    assinatura = assinatura_envio(arquivos, {"altitude": altitude}) if arquivos else None
    if st.button("Preparar prévia", disabled=not arquivos):
        try:
            fontes, avisos = fontes_de_arquivos(arquivos)
            previa = importar_pacote(
                fontes,
                p_atm_bar=None if altitude is None else estado.p_atm_por_altitude_bar(altitude),
            )
            previa.avisos_gerais += avisos
            st.session_state["importar_previa_guiada"] = (assinatura, previa)
        except (ValueError, OSError) as exc:
            st.error(f"Não foi possível ler os arquivos: {exc}")
    preparada = st.session_state.get("importar_previa_guiada")
    pronta = preparada is not None and assinatura is not None and preparada[0] == assinatura
    if pronta:
        previa = preparada[1]
        avisos = previa.tabela_avisos()
        erros = sum(a.gravidade == "erro" for a in previa.avisos)
        repetidas = sum("duplic" in a.tipo for a in previa.avisos)
        c1, c2, c3 = st.columns(3)
        c1.metric("Tabelas reconhecidas", len(previa.importacoes))
        c2.metric("Erros para revisar", erros)
        c3.metric("Avisos de duplicidade", repetidas)
        if erros:
            st.warning("Tabelas com erros ficam bloqueadas. Corrija o arquivo para utilizá-las.")
        with st.expander("O que estes dados permitem analisar", expanded=True):
            for cap in avaliar(previa):
                estado_cap = {
                    "habilitada": "Disponível",
                    "parcial": "Parcial",
                    "bloqueada": "Faltam dados",
                }[cap.situacao]
                st.markdown(f"**{cap.nome}** · {estado_cap}")
                if cap.motivos:
                    st.caption(" ".join(cap.motivos[:2]))
        with st.expander("Conferir qualidade e primeiras linhas"):
            relevantes = avisos[avisos["Gravidade"] != "Informação"]
            if not relevantes.empty:
                st.dataframe(relevantes, hide_index=True, width="stretch")
            for nome, imp in previa.importacoes.items():
                st.caption(TABELAS[nome].titulo)
                st.dataframe(imp.dados.head(5), hide_index=True, width="stretch")
        pronta = any(not imp.bloqueada for imp in previa.importacoes.values())
    with st.container(horizontal=True, gap="small"):
        if st.button("Importar os arquivos enviados", type="primary", disabled=not pronta):
            if len({f.name for f in enviados}) != len(enviados):
                st.error(
                    "Há arquivos com o mesmo nome. Renomeie antes de importar para não perder registros."
                )
            else:
                try:
                    if salvar_no_banco:
                        arm.importar_na_planta(
                            arquivos, altitude, autor=autor_importacao, motivo=motivo_importacao
                        )
                    else:
                        estado.importar_novos(arquivos, altitude)
                    st.rerun()
                except arm.ERROS as exc:
                    st.error(f"Importação não concluída: {exc}. Os dados ativos foram preservados.")
        st.download_button(
            "Baixar a planilha modelo (.xlsx)",
            ARQUIVO_PLANILHA.read_bytes(),
            file_name=ARQUIVO_PLANILHA.name,
            icon=":material/download:",
        )
    with st.expander("Detalhes técnicos: nomes dos arquivos e das colunas"):
        st.markdown(
            "Os nomes abaixo são o formato recomendado. CSVs com outro nome podem ser "
            "reconhecidos pelo cabeçalho quando não houver ambiguidade. Colunas e unidades "
            "completas no contrato de dados "
            "(`docs/dados/contrato_dados.md`)."
        )
        st.dataframe(
            [
                {
                    "Registro": t.titulo,
                    "Arquivo": t.arquivo,
                    "Colunas obrigatórias": ", ".join(c.nome for c in t.colunas if c.obrigatoria),
                }
                for t in TABELAS.values()
            ],
            hide_index=True,
            width="stretch",
        )

with st.expander("Experimentar com dados sintéticos"):
    exemplos = st.columns(4, gap="small")
    with exemplos[0], cartao("exemplo-ato1"):
        st.markdown(":material/play_circle: **Ato 1 · caso completo**")
        st.caption(
            "Caldeira de 20 t/h a cavaco, 8 semanas, 3 fornecedores, instrumentos com incerteza cadastrada: a EULER conclui."
        )
        if st.button("Ato 1 · caso completo", width="stretch", key="importar_ato1"):
            estado.usar_caso_demo(completo=True)
            st.rerun()
    with exemplos[1], cartao("exemplo-ato2"):
        st.markdown(":material/play_circle: **Ato 2 · dados insuficientes**")
        st.caption(
            "A mesma caldeira, sem a incerteza de quatro instrumentos: a EULER explica por que não conclui."
        )
        if st.button("Ato 2 · dados insuficientes", width="stretch", key="importar_ato2"):
            estado.usar_caso_demo(completo=False)
            st.rerun()
    with exemplos[2], cartao("exemplo-modelos"):
        st.markdown(":material/table_view: **Modelos**")
        st.caption("Uma linha de exemplo por arquivo: mostra o formato e o que fica bloqueado.")
        if st.button("Modelos (1 linha de exemplo)", width="stretch"):
            estado.definir_arquivos(
                estado.ler_pasta(estado.RAIZ / "templates"),
                "modelos de exemplo (sintéticos)",
                sinteticos=True,
            )
    with exemplos[3], cartao("exemplo-problemas"):
        st.markdown(":material/report: **Exemplo com problemas**")
        st.caption(
            "Erros de propósito (unidades trocadas, lacunas, duplicatas) para ver os avisos."
        )
        if st.button("Exemplo com problemas (sintético)", width="stretch"):
            estado.definir_arquivos(
                estado.ler_pasta(estado.RAIZ / "demo" / "qualidade"),
                "exemplo com problemas de propósito (sintético)",
                sinteticos=True,
            )


def mostrar_resultado(pacote) -> None:
    st.markdown(f"### Resultado da importação · {estado.rotulo_dados()}")
    avisos = pacote.tabela_avisos()
    contagem = avisos["Gravidade"].value_counts()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tabelas importadas", len(pacote.importacoes), border=True)
    m2.metric("Erros", int(contagem.get("Erro", 0)), border=True)
    m3.metric("Avisos de atenção", int(contagem.get("Atenção", 0)), border=True)
    m4.metric("Informações", int(contagem.get("Informação", 0)), border=True)

    linhas = []
    for nome, tabela in TABELAS.items():
        imp = pacote.importacoes.get(nome)
        if imp is None:
            situacao, n = "não enviada", "—"
        elif imp.bloqueada:
            situacao, n = "bloqueada (ver erros)", str(len(imp.original))
        else:
            situacao, n = "importada", str(len(imp.dados))
        linhas.append({"Registro": tabela.titulo, "Linhas": n, "Situação": situacao})
    with st.expander("Ver registros importados e tabelas ausentes"):
        st.dataframe(linhas, hide_index=True, width="stretch")

    st.markdown("#### Avisos de qualidade")
    if avisos.empty:
        st.success("Nenhum problema encontrado.")
    else:
        with st.expander(
            f"Revisar {len(avisos)} avisos de qualidade", expanded=bool(contagem.get("Erro", 0))
        ):
            filtro = st.pills(
                "Mostrar",
                ["Erro", "Atenção", "Informação"],
                default=["Erro", "Atenção"],
                selection_mode="multi",
            )
            visiveis = avisos[avisos["Gravidade"].isin(filtro)][
                ["Gravidade", "Tabela", "Linha", "Aviso"]
            ]
            visiveis = visiveis.astype({"Linha": "string"}).fillna({"Linha": "—"})
            if len(visiveis) <= 80:
                # tabela simples: quebra o texto, mostra a frase inteira e a gravidade em selo
                visiveis["Gravidade"] = visiveis["Gravidade"].map(
                    lambda g: f":{COR_GRAVIDADE.get(g, 'gray')}-badge[{g}]"
                )
                st.table(visiveis, hide_index=True, border="horizontal")
            else:
                st.dataframe(visiveis, hide_index=True, width="stretch")
            st.caption(
                "**Erro:** a tabela não pôde ser usada. **Atenção:** pode afetar as análises. "
                "**Informação:** registro do que foi interpretado. Os números de linha são os do arquivo "
                "(cabeçalho = linha 1)."
            )

    with st.expander("Detalhes técnicos: os dados como a EULER entendeu"):
        nomes = list(pacote.importacoes)
        for aba, nome in zip(st.tabs([TABELAS[n].titulo for n in nomes]), nomes, strict=True):
            with aba:
                st.dataframe(pacote.importacoes[nome].dados, hide_index=True, width="stretch")


pacote = estado.pacote()
if pacote is not None:
    mostrar_resultado(pacote)
    proximo_passo("paginas/saude.py", "Saúde da caldeira")
