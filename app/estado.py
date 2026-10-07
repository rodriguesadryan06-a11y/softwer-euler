"""Estado compartilhado entre as telas: arquivos enviados, configuração do local e dados importados.

Resultados derivados (investigação, relatório gerado) são guardados junto com a
**assinatura** dos dados que os produziram (arquivos + altitude). Uma tela só mostra um
resultado guardado se a assinatura bater com os dados em uso: trocar os arquivos ou a
altitude nunca deixa um resultado antigo aparecer como se fosse dos dados novos.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

from euler.io import Pacote, fontes_de_arquivos, importar_pacote
from euler.vapor import p_atm_por_altitude_bar

RAIZ = Path(__file__).resolve().parents[1]


@st.cache_data(show_spinner="Importando…")
def _importar(arquivos: tuple[tuple[str, bytes], ...], p_atm_bar: float | None) -> Pacote:
    fontes, avisos = fontes_de_arquivos(dict(arquivos))
    pacote = importar_pacote(fontes, p_atm_bar=p_atm_bar)
    pacote.avisos_gerais += avisos
    return pacote


def ler_pasta(pasta: Path) -> dict[str, bytes]:
    """Lê os CSVs de uma pasta do repositório como se tivessem sido enviados."""
    return {p.name: p.read_bytes() for p in sorted(pasta.glob("*.csv"))}


def definir_arquivos(arquivos: dict[str, bytes], rotulo: str, sinteticos: bool = False) -> None:
    """Troca os dados da sessão. `sinteticos`: exemplos do próprio projeto (marcados como tal)."""
    for chave in ("persistencia", "persistencia_erro", "persistencia_aviso", "saude_incerteza"):
        st.session_state.pop(chave, None)
    st.session_state["arquivos"] = tuple(sorted(arquivos.items()))
    st.session_state["rotulo_dados"] = rotulo
    st.session_state["dados_sinteticos"] = sinteticos
    esquecer_resultados()
    for chave in list(st.session_state):
        if chave in (
            "periodos_escolhidos",
            "periodo_ref",
            "periodo_comp",
            "periodo_ref_inicio",
            "periodo_ref_fim",
            "periodo_comp_inicio",
            "periodo_comp_fim",
        ) or chave.startswith("fin_recuperacao_"):
            st.session_state.pop(chave, None)


def limpar_dados() -> None:
    """Esvazia só esta sessão. Não apaga arquivos do PC nem de outras sessões.

    O contador recria os controles de envio e altitude para não recuperar entradas antigas.
    Caches internos não são uma exclusão segura: reinicie o app para encerrar sua memória.
    """
    for chave in list(st.session_state):
        if chave in (
            "arquivos",
            "rotulo_dados",
            "dados_sinteticos",
            "altitude_m",
            "investigacao",
            "relatorio_gerado",
            "periodos_escolhidos",
            "periodo_ref",
            "periodo_comp",
            "periodo_ref_inicio",
            "periodo_ref_fim",
            "periodo_comp_inicio",
            "periodo_comp_fim",
            "saude_incerteza",
            "persistencia",
            "persistencia_erro",
            "persistencia_aviso",
        ) or chave.startswith(("fin_recuperacao_", "envio_", "altitude_envio_")):
            st.session_state.pop(chave, None)
    st.session_state["importacao_geracao"] = st.session_state.get("importacao_geracao", 0) + 1


def importar_novos(arquivos: dict[str, bytes], altitude: float | None) -> None:
    """Substitui o conjunto inteiro e usa somente a altitude informada para o novo local."""
    definir_arquivos(arquivos, f"{len(arquivos)} arquivo(s) enviado(s)", sinteticos=False)
    st.session_state["altitude_m"] = altitude


def dados_sinteticos() -> bool:
    """True quando os dados em uso são sintéticos: um exemplo do projeto, ou arquivos em que
    toda linha com origem declarada diz `sintetico`."""
    if not st.session_state.get("arquivos"):
        return False
    if st.session_state.get("dados_sinteticos"):
        return True
    p = pacote()
    return p is not None and p.sintetico


def assinatura() -> str | None:
    """Identifica os dados em uso (conteúdo dos arquivos + altitude); None sem dados."""
    arquivos = st.session_state.get("arquivos")
    if not arquivos:
        return None
    h = hashlib.sha256(repr(st.session_state.get("altitude_m")).encode())
    ctx = st.session_state.get("persistencia", {})
    h.update(repr((ctx.get("planta_id"), ctx.get("importacao_id"))).encode())
    # Uma edição no motor também invalida os resultados guardados da sessão.
    for caminho in sorted((RAIZ / "euler").rglob("*.py")):
        h.update(caminho.relative_to(RAIZ).as_posix().encode())
        h.update(caminho.read_bytes().replace(b"\r\n", b"\n"))
    for nome, dados in arquivos:
        h.update(nome.encode())
        h.update(dados)
    return h.hexdigest()[:16]


def esquecer_resultados() -> None:
    """Descarta investigação e relatório guardados (dados trocados ou comparação inválida)."""
    st.session_state.pop("investigacao", None)
    st.session_state.pop("relatorio_gerado", None)


def guardar_investigacao(j: dict) -> None:
    st.session_state["investigacao"] = {"assinatura": assinatura(), "json": j}
    from armazenamento import guardar_analise

    guardar_analise(j)


def investigacao_atual() -> tuple[dict | None, str]:
    """(JSON da investigação, motivo). JSON None se não houver investigação destes dados.

    motivo: "" (há investigação), "nenhuma" ou "dados_mudaram".
    """
    guardada = st.session_state.get("investigacao")
    if guardada is None:
        return None, "nenhuma"
    if guardada["assinatura"] != assinatura():
        return None, "dados_mudaram"
    return guardada["json"], ""


@st.cache_data(show_spinner="Preparando a análise…", max_entries=32)
def _analisar(assinatura_dados, ref, comp, _pacote):
    from euler.investigacao import investigar

    return investigar(_pacote, ref, comp)


def investigacao_ou_padrao(pacote: Pacote) -> dict | None:
    """Investigação guardada destes dados; senão, a comparação padrão (ou a escolhida na tela
    Investigação): primeira metade dos períodos entre estoques contra os dois seguintes.
    None quando a comparação não está habilitada."""
    from euler.capacidades import avaliar
    from euler.periodos import periodos_entre_estoques

    j, _ = investigacao_atual()
    if j is not None:
        return j
    caps = {c.id: c for c in avaliar(pacote)}
    periodos = periodos_entre_estoques(pacote)
    if not caps["comparacao"].habilitada or len(periodos) < 2:
        return None
    n = len(periodos)
    meio = max(1, n // 2)
    escolha = st.session_state.get("periodos_escolhidos")
    if escolha and escolha["assinatura"] == assinatura():
        a, b = escolha["ref"], escolha["comp"]
    else:
        a, b = (0, meio - 1), (meio, min(n - 1, meio + 1))
    if max(*a, *b) >= n or not (a[1] < b[0] or b[1] < a[0]):
        return None
    ref = (periodos[a[0]][0], periodos[a[1]][1])
    comp = (periodos[b[0]][0], periodos[b[1]][1])
    j = _analisar(assinatura(), ref, comp, pacote)
    guardar_investigacao(j)
    return j


ALTITUDE_DEMO_M = 1000.0


CASOS_DEMO = {
    # ato 1: os mesmos registros, com a incerteza de todos os instrumentos (D62)
    True: (
        "caso_demo_completo",
        "caso de demonstração · ato 1, completo (caldeira sintética de 20 t/h, 8 semanas)",
    ),
    # ato 2: sem a incerteza de quatro instrumentos; a EULER explica por que não conclui (D53)
    False: (
        "caso_demo",
        "caso de demonstração · ato 2, dados insuficientes (a mesma caldeira sintética)",
    ),
}


def usar_caso_demo(completo: bool = False) -> None:
    """Carrega um dos dois atos do caso de demonstração sintético e a altitude dele."""
    pasta, rotulo = CASOS_DEMO[completo]
    definir_arquivos(ler_pasta(RAIZ / "demo" / pasta), rotulo, sinteticos=True)
    st.session_state["altitude_m"] = ALTITUDE_DEMO_M


def altitude_m() -> float | None:
    return st.session_state.get("altitude_m")


def p_atm_bar() -> float | None:
    alt = altitude_m()
    return None if alt is None else p_atm_por_altitude_bar(alt)


def pacote() -> Pacote | None:
    """Dados importados na sessão (ou None se nada foi enviado)."""
    arquivos = st.session_state.get("arquivos")
    if not arquivos:
        return None
    return _importar(arquivos, p_atm_bar())


def rotulo_dados() -> str:
    return st.session_state.get("rotulo_dados", "")


def sem_dados() -> None:
    """Tela que depende de dados, sem dados: importar os da fábrica ou carregar o demo."""
    st.info("Nenhum dado importado ainda.", icon=":material/upload_file:")
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        if st.button(
            "Ato 1 · caso completo", type="primary", icon=":material/play_circle:", key="ato1_vazio"
        ):
            usar_caso_demo(completo=True)
            st.rerun()
        if st.button(
            "Ato 2 · dados insuficientes", icon=":material/play_circle:", key="ato2_vazio"
        ):
            usar_caso_demo(completo=False)
            st.rerun()
        st.page_link(
            "paginas/importar.py", label="Ir para Importar dados", icon=":material/arrow_forward:"
        )


def exigir_pacote() -> Pacote | None:
    """Para telas que dependem de dados: devolve o pacote ou mostra como importar.

    Não usa st.stop(), para o rodapé de segurança sempre aparecer.
    """
    p = pacote()
    if p is None:
        sem_dados()
        return None
    selo = " · :orange-badge[:material/science: DADOS SINTÉTICOS]" if dados_sinteticos() else ""
    import armazenamento

    st.caption(
        f":material/hourglass_top: **Análise temporária** · dados desta sessão: "
        f"**{rotulo_dados()}**{selo} · {armazenamento.situacao()}"
    )
    return p
