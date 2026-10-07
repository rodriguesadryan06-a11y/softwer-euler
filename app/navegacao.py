"""Menu compacto (D105): cinco seções no menu lateral e as telas de cada seção como abas.

Nenhuma tela foi removida: as 17 rotas continuam registradas, os links antigos abrem e cada
tela pertence a exatamente uma seção. O menu lateral mostra só as seções; no topo da tela,
as abas levam às telas irmãs da seção aberta.
"""

# (seção, ícone, ((caminho, rótulo da aba, ícone), ...)); a primeira tela abre a seção
SECOES = (
    ("Início", "home", (("paginas/inicio.py", "Início", "home"),)),
    (
        "Minha planta",
        "space_dashboard",
        (
            ("paginas/painel.py", "Painel", "space_dashboard"),
            ("paginas/acompanhamento.py", "Dados", "upload"),
            ("paginas/fechamentos.py", "Fechamentos", "event_available"),
            ("paginas/acoes.py", "Ações", "task_alt"),
            ("paginas/plantas.py", "Histórico", "database"),
        ),
    ),
    (
        "Análise",
        "monitor_heart",
        (
            ("paginas/saude.py", "Saúde da caldeira", "monitor_heart"),
            ("paginas/investigacao.py", "Investigar", "troubleshoot"),
            ("paginas/oportunidades.py", "Oportunidades", "flag"),
            ("paginas/limites.py", "Qualidade e limites", "rule"),
            ("paginas/relatorio.py", "Relatório", "description"),
            ("paginas/importar.py", "Arquivo avulso", "upload_file"),
        ),
    ),
    (
        "Financeiro",
        "payments",
        (
            ("paginas/financeiro.py", "Conta do período", "payments"),
            ("paginas/extrato.py", "Fornecedores", "receipt_long"),
        ),
    ),
    (
        "Validação",
        "science",
        (
            ("paginas/dados_publicos.py", "Testes com dados reais", "science"),
            ("paginas/diagnostico.py", "Diagnóstico de evidências", "fact_check"),
            ("paginas/calculadora.py", "Calculadora de referência", "calculate"),
        ),
    ),
)


def todas_as_paginas() -> tuple:
    """Todas as rotas, na ordem do menu, para registrar no `st.navigation`."""
    return tuple(tela for _, _, telas in SECOES for tela in telas)


def secao_de(caminho: str) -> tuple:
    """A seção a que a tela pertence (cada tela está em exatamente uma)."""
    return next(s for s in SECOES if any(t[0] == caminho for t in s[2]))


def menu_lateral(st, atual: str) -> None:
    """Cinco entradas. A seção aberta aponta para a tela atual, para ficar destacada."""
    with st.sidebar:
        for nome, icone, telas in SECOES:
            destino = atual if any(t[0] == atual for t in telas) else telas[0][0]
            st.page_link(destino, label=nome, icon=f":material/{icone}:")


def abas_da_secao(st, atual: str) -> None:
    """Abas no topo da tela com as telas irmãs da seção aberta (nada aparece no Início)."""
    _, _, telas = secao_de(atual)
    if len(telas) < 2:
        return
    with st.container(horizontal=True, gap="small", key="euler-abas"):
        for caminho, rotulo, icone in telas:
            st.page_link(caminho, label=rotulo, icon=f":material/{icone}:", width="content")
