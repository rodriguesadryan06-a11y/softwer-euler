"""Peças de tela reaproveitadas por todas as páginas do app (identidade visual EULER).

Tema escuro e marca minimalista (D61, pedido do Adryan): fundo grafite, barra lateral mais
escura, interface monocromática e cor só onde informa. Só apresentação: nenhuma conta física
aqui. O estilo usa as classes que o Streamlit dá aos contêineres com `key`
(`st-key-<chave>`) e alguns `data-testid`; a versão do Streamlit está travada em
`pyproject.toml` (<2).
"""

from html import escape
from pathlib import Path

import streamlit as st

from euler.textos import RODAPE_SEGURANCA

IMAGENS = Path(__file__).resolve().parent / "imagens"
LOGO = IMAGENS / "euler_logo.svg"
MARCA = IMAGENS / "euler_marca.svg"
ICONE = IMAGENS / "euler_icone.svg"

# Cores dos dois períodos comparados (as mesmas nas faixas do gráfico e na linha do tempo):
# referência em azul-ardósia, comparação em âmbar, as duas escuras para o fundo grafite.
COR_REFERENCIA = "#2A3646"
COR_COMPARACAO = "#45321F"

ESTILO = f"""<style>
:root {{
  --euler-fundo: #212121;
  --euler-cartao: #262626;
  --euler-lateral: #171717;
  --euler-texto: #ECECEC;
  --euler-suave: #A3A3A3;
  --euler-fraco: #A3A3A3;
  --euler-linha: #363636;
  --euler-ref: {COR_REFERENCIA};
  --euler-ref-texto: #C7D5EA;
  --euler-ref-borda: #3E4E66;
  --euler-comp: {COR_COMPARACAO};
  --euler-comp-texto: #F2C08F;
  --euler-comp-borda: #6A4A2C;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
.stMainBlockContainer {{ max-width: 1200px; padding-top: 2.4rem; padding-bottom: 3rem; }}
/* Hierarquia compacta; informações complementares ficam em expansores. */
.stMainBlockContainer h2 {{ font-size: 1.35rem; letter-spacing: -.015em; }}
[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
.st-key-cartao-saude-selo {{ padding: 1.5rem; border-left: 3px solid var(--euler-ref-texto); }}
.st-key-cartao-saude-selo [data-testid="stMetric"] {{ background: transparent; }}
.st-key-cartao-saude-selo [data-testid="stMetricValue"] {{ font-size: 1.55rem; }}
[data-testid="stExpander"] details {{ background: transparent; }}
a:focus-visible, button:focus-visible, input:focus-visible {{
  outline: 2px solid var(--euler-ref-texto); outline-offset: 3px; }}
@media(max-width:640px) {{
  .stMainBlockContainer {{ padding: 3.4rem 1rem 2rem; }} /* espaço para o botão do menu */
  .st-key-cartao-saude-selo {{ padding: 1rem; }}
  .st-key-euler-abertura {{ padding: 1.25rem !important; }}
}}
[data-testid="stSidebarContent"] [data-testid="stCaptionContainer"] {{ color: var(--euler-fraco); }}

/* Botões: o principal é claro com texto escuro (o Streamlit pintaria o texto de branco) */
[data-testid="stBaseButton-primary"] {{ color: #171717; font-weight: 600; }}
[data-testid="stBaseButton-primary"]:hover {{ background: #FFFFFF; border-color: #FFFFFF;
  color: #000000; }}
[data-testid="stBaseButton-primary"] p {{ color: inherit; }}
[data-testid="stBaseButton-secondary"]:hover {{ border-color: #6B6B6B; color: #FFFFFF; }}

/* Abas da seção (telas irmãs) logo acima do cabeçalho */
.st-key-euler-abas {{ margin-bottom: .4rem; row-gap: .15rem; }}

/* Cabeçalho de cada tela */
.st-key-euler-cabecalho {{ gap: .2rem; padding-bottom: 1rem; margin-bottom: .35rem;
  border-bottom: 1px solid var(--euler-linha); }}
.st-key-euler-cabecalho h1 {{ padding: .1rem 0 .35rem; letter-spacing: -.01em; }}
.st-key-euler-cabecalho [data-testid="stMarkdownContainer"] p {{ color: var(--euler-suave);
  font-size: 1.04rem; max-width: 62rem; }}
.euler-sobrelinha {{ text-transform: uppercase; letter-spacing: .12em; font-size: .72rem;
  font-weight: 600; color: var(--euler-fraco); }}

/* Cartões (contêineres com key "cartao-…") e indicadores */
[class*="st-key-cartao"] {{ background: var(--euler-cartao); }}
/* cartões lado a lado com a mesma altura (indicadores, passos, estágios) */
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{ height: 100%; }}
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-cartao-kpi"]),
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-cartao-passo"]),
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-cartao-estagio"]),
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-cartao-exemplo"]) {{ flex: 1 1 auto; }}
[class*="st-key-cartao-kpi"], [class*="st-key-cartao-passo"],
[class*="st-key-cartao-estagio"], [class*="st-key-cartao-exemplo"] {{ flex: 1 1 auto; }}
[class*="st-key-cartao-passo"] {{ justify-content: space-between; }}
[data-testid="stMetric"] {{ background: var(--euler-cartao); }}
[data-testid="stMetricLabel"] p {{ color: var(--euler-suave); font-weight: 500; }}
.euler-secao {{ text-transform: uppercase; letter-spacing: .12em; font-size: .74rem;
  font-weight: 600; color: var(--euler-fraco); margin: .4rem 0 -.2rem; }}

/* Abertura da tela inicial */
.st-key-euler-abertura {{ background:
  radial-gradient(120% 140% at 0% 0%, rgba(168, 199, 250, .07) 0%, rgba(168, 199, 250, 0) 55%),
  var(--euler-lateral); border: 1px solid #2C2C2C; border-radius: 14px;
  padding: 2.4rem 2.6rem 2.2rem; gap: .6rem; }}
.st-key-euler-abertura h1 {{ color: #FFFFFF; font-size: 2.9rem; font-weight: 500;
  letter-spacing: .2em; padding: 0; }}
.st-key-euler-abertura h3 {{ color: var(--euler-texto); font-weight: 500; max-width: 46rem; }}
.st-key-euler-abertura p, .st-key-euler-abertura li {{ color: var(--euler-suave);
  font-size: 1.05rem; max-width: 50rem; }}
.st-key-euler-abertura [data-testid="stBaseButton-primary"] p {{ color: #171717;
  font-size: 1rem; }}
.st-key-euler-abertura [data-testid="stPageLink"] a {{ border: 1px solid #3A3A3A;
  border-radius: .45rem; padding: .32rem .9rem; }}
.st-key-euler-abertura [data-testid="stPageLink"] a p,
.st-key-euler-abertura [data-testid="stPageLink"] a span {{ color: var(--euler-texto);
  font-size: 1rem; }}

/* Botão "Próximo passo" no fim das telas do fluxo */
.st-key-euler-proximo [data-testid="stPageLink"] a {{ border: 1px solid #4A4A4A;
  border-radius: .45rem; padding: .35rem 1rem; background: var(--euler-cartao); }}
.st-key-euler-proximo [data-testid="stPageLink"] a:hover {{ border-color: #8A8A8A; }}
.st-key-euler-proximo [data-testid="stPageLink"] a p {{ color: var(--euler-texto);
  font-weight: 600; }}

/* Envio de arquivos: o componente do Streamlit vem em inglês ("Upload", "200MB per file").
   O texto original fica com tamanho zero e o português entra no lugar. */
[data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"] p {{
  font-size: 0; }}
[data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"] p::after {{
  content: "Escolher arquivos"; font-size: .875rem; }}
[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] * {{ white-space: normal;
  overflow: visible; text-overflow: clip; }}
[data-testid="stFileUploaderDropzoneInstructions"] span {{ font-size: 0; }}
[data-testid="stFileUploaderDropzoneInstructions"] span::after {{
  content: "ou arraste para cá · CSV ou planilha .xlsx"; font-size: .82rem; }}

/* Linha do tempo dos períodos comparados (tela Investigação) */
.euler-tempo {{ display: flex; gap: 4px; margin: .2rem 0 .3rem; }}
.euler-tempo .p {{ flex: 1; text-align: center; font-size: .78rem; padding: .45rem 0;
  border-radius: 5px; background: #2A2A2A; color: var(--euler-fraco);
  border: 1px solid #333333; font-variant-numeric: tabular-nums; }}
.euler-tempo .p.ref {{ background: var(--euler-ref); color: var(--euler-ref-texto);
  border-color: var(--euler-ref-borda); font-weight: 600; }}
.euler-tempo .p.comp {{ background: var(--euler-comp); color: var(--euler-comp-texto);
  border-color: var(--euler-comp-borda); font-weight: 600; }}
.euler-tempo-legenda {{ display: flex; flex-wrap: wrap; gap: 1.4rem; font-size: .9rem;
  color: var(--euler-suave); }}
.euler-tempo-legenda b {{ color: var(--euler-texto); font-weight: 600; }}
.euler-tempo-legenda span.q {{ display: inline-block; width: .8rem; height: .8rem;
  border-radius: 3px; margin-right: .4rem; vertical-align: -1px; }}
.euler-tempo-legenda span.q.ref {{ background: var(--euler-ref);
  border: 1px solid var(--euler-ref-borda); }}
.euler-tempo-legenda span.q.comp {{ background: var(--euler-comp);
  border: 1px solid var(--euler-comp-borda); }}
</style>"""


def aplicar_estilo() -> None:
    """Injeta o estilo EULER (uma vez por execução, antes da tela)."""
    st.html(ESTILO)


def cabecalho(titulo: str, resumo: str = "", sobrelinha: str = "") -> None:
    """Cabeçalho padrão: sobrelinha (ex.: "Analisar um período"), título e uma frase de resumo."""
    with st.container(key="euler-cabecalho"):
        if sobrelinha:
            st.html(f'<div class="euler-sobrelinha">{escape(sobrelinha)}</div>')
        st.title(titulo, anchor=False)
        if resumo:
            st.markdown(resumo)


def cartao(chave: str):
    """Contêiner com borda e fundo branco (chave única na tela)."""
    return st.container(border=True, key=f"cartao-{chave}")


def secao(texto: str) -> None:
    """Rótulo pequeno de seção, em maiúsculas (ex.: "Resultado")."""
    st.html(f'<div class="euler-secao">{escape(texto)}</div>')


def proximo_passo(pagina: str, rotulo: str) -> None:
    """Botão para a próxima tela do fluxo, alinhado à direita."""
    with st.container(key="euler-proximo", horizontal=True, horizontal_alignment="right"):
        st.page_link(
            pagina,
            label=f"Próximo: {rotulo}",
            icon=":material/arrow_forward:",
            icon_position="right",
        )


def rodape() -> None:
    """Mostra o rodapé de segurança (obrigatório em todas as telas)."""
    st.divider()
    st.caption(RODAPE_SEGURANCA)


def md(texto: str) -> str:
    """Protege o "$" para o Markdown do Streamlit não confundir "R$ … R$" com fórmula."""
    return texto.replace("$", r"\$")


def incerteza_explicada(inc: dict | None, *, recolhido: bool = False) -> None:
    """De onde vem a faixa do desvio e o que a estreitaria (D97): texto do motor, sem conta nova."""
    if not inc:
        return
    titulo = "Por que a faixa é larga e o que a estreita"

    def corpo():
        if inc.get("frase_origem"):
            st.markdown(md(inc["frase_origem"]))
        for chave in ("condicional", "melhor"):
            if inc.get(chave):
                st.markdown(md(f"- {inc[chave]['frase']}"))
        st.caption(inc["nota"])

    if recolhido:
        with st.expander(titulo):
            corpo()
    else:
        with st.container(border=True):
            st.markdown(f"**{titulo}**")
            corpo()
