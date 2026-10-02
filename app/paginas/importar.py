"""Tela Importar dados: envio dos arquivos e lista de avisos de qualidade (T03, T05)."""

import estado
import streamlit as st
from componentes import cabecalho, cartao, proximo_passo

from euler.formato import num, plural
from euler.io.esquemas import TABELAS
from euler.io.modelos import ARQUIVO_PLANILHA

COR_GRAVIDADE = {"Erro": "red", "Atenção": "orange", "Informação": "gray"}

cabecalho(
    "Importar dados",
    "Envie o que a planta já tem: historiador, diário, combustível, amostras, eventos ou "
    "instrumentos. A EULER reconhece as grandezas disponíveis, monta as rotas físicas possíveis "
    "e mostra o que ainda não dá para concluir. Nomes padrão ajudam, mas um CSV com cabeçalho "
    "inequívoco também pode ser reconhecido. Nada é corrigido nem preenchido sem avisar.",
    "Passo 1 de 6",
)

local, envio = st.columns([1, 2], gap="medium")
with local, cartao("local"):
    st.markdown("**1. Local da caldeira**")
    altitude = st.number_input(
        "Altitude do local (m)",
        min_value=-500.0,
        max_value=5000.0,
        value=st.session_state.get("altitude_m"),
        step=10.0,
        placeholder="ex.: 1100",
        help="Usada para converter a pressão do manômetro em pressão absoluta.",
    )
    st.session_state["altitude_m"] = altitude
    if altitude is None:
        st.caption("Sem altitude, a pressão absoluta do vapor não é calculada.")
    else:
        st.caption(
            f"Pressão atmosférica: **{num(estado.p_atm_bar(), 3)} bar** "
            "(estimado pela altitude, atmosfera padrão)."
        )

with envio, cartao("arquivos"):
    st.markdown("**2. Arquivos da fábrica**")
    enviados = st.file_uploader(
        "Arquivos (CSV ou planilha .xlsx)",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    with st.container(horizontal=True, gap="small"):
        if st.button("Importar os arquivos enviados", type="primary", disabled=not enviados):
            estado.definir_arquivos(
                {f.name: f.getvalue() for f in enviados},
                plural(len(enviados), "arquivo enviado", "arquivos enviados"),
            )
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
            "(`docs/contrato_dados.md`)."
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

st.markdown("##### Ou comece com um exemplo sintético")
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
    st.caption("Erros de propósito (unidades trocadas, lacunas, duplicatas) para ver os avisos.")
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
    st.dataframe(linhas, hide_index=True, width="stretch")

    st.markdown("#### Avisos de qualidade")
    if avisos.empty:
        st.success("Nenhum problema encontrado.")
    else:
        filtro = st.pills(
            "Mostrar",
            ["Erro", "Atenção", "Informação"],
            default=["Erro", "Atenção", "Informação"],
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
    proximo_passo("paginas/saude.py", "2. Saúde da caldeira")
