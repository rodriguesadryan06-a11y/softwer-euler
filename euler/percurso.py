"""Percurso da planta em cinco passos (D102, proposta).

Enviar registros → conferir a conta → investigar → registrar ação → verificar resultado.

Para o equipamento escolhido, diz em que pé está cada passo e qual é o próximo, lendo só o
que já está gravado no armazém da planta (importações, fechamentos, investigações,
intervenções e avaliações). Não calcula física nem dinheiro novo e não decide nada pela
equipe: aponta o passo pendente e onde fazê-lo.

Estados: "feito" (nada pendente neste passo), "andamento" (há algo aberto e acompanhado),
"pendente" (há algo para fazer agora) e "bloqueado" (depende de um passo anterior).
"""

import pandas as pd

from euler.acompanhamento import intervencoes, investigacoes, ultima_avaliacao
from euler.armazem import Armazem
from euler.fechamento import fechamentos_vigentes, periodos_pendentes, referencia_vigente

PASSOS = (
    ("registros", "Enviar registros", "dados"),
    ("conta", "Conferir a conta", "fechamentos"),
    ("investigar", "Investigar", "acoes"),
    ("acao", "Registrar ação", "acoes"),
    ("resultado", "Verificar resultado", "acoes"),
)


def _data(x) -> str:
    return pd.Timestamp(x).strftime("%d/%m/%Y")


def _tem_o_que_investigar(f: dict) -> bool:
    n = f["resultado"]["nucleo"]
    return f["resultado"]["situacao"] == "acima" or any(
        o["prioridade"] in ("alta", "media") for o in n["oportunidades"]
    )


def percurso(a: Armazem, equip_id: str, agora=None) -> list[dict]:
    """Lista os cinco passos com estado, frase e destino (tela onde o passo é feito).

    Entrada: armazém aberto da planta e o equipamento. Saída: uma lista na ordem do
    percurso; cada item tem `id`, `titulo`, `estado`, `frase` e `destino`
    (`dados`, `fechamentos` ou `acoes`). O primeiro item "pendente" é o próximo passo.
    `agora` só serve para testes (data de hoje na cobertura dos registros).
    """
    cob = a.cobertura(equip_id, agora=agora)
    fs = fechamentos_vigentes(a, equip_id)
    ultimo = fs[-1] if fs else None
    invs = investigacoes(a, equip_id)
    abertas = [x for x in invs if x["estado"] != "encerrada"]
    acoes = intervencoes(a, equip_id)
    passos = {}

    # 1 · registros
    if not cob["importacoes"]:
        passos["registros"] = ("pendente", "Nenhum registro enviado para este equipamento.")
    elif cob["conflitos_pendentes"]:
        passos["registros"] = (
            "pendente",
            f"{cob['conflitos_pendentes']} conflito(s) de importação esperando decisão.",
        )
    elif cob["estado"] != "atualizado":
        passos["registros"] = ("pendente", cob["frase"])
    else:
        passos["registros"] = (
            "feito",
            f"{cob['importacoes']} envio(s); último em {_data(cob['ultima_importacao'])}. "
            + cob["frase"],
        )

    # 2 · conta
    if not cob["importacoes"]:
        passos["conta"] = ("bloqueado", "Depende dos registros.")
    elif referencia_vigente(a, equip_id) is None:
        passos["conta"] = ("pendente", "Defina a referência para fechar o primeiro período.")
    else:
        pend = periodos_pendentes(a, equip_id)
        prontos = [p for p in pend if p.get("valido", True)]
        if prontos:
            passos["conta"] = (
                "pendente",
                f"{len(prontos)} período(s) com dados completos ainda sem fechamento.",
            )
        elif ultimo is None:
            passos["conta"] = ("pendente", "Nenhum período fechado ainda.")
        else:
            n = ultimo["resultado"]["nucleo"]["periodo"]
            passos["conta"] = (
                "feito",
                f"Último fechamento: {_data(n['inicio'])} a {_data(n['fim'])}. "
                + ultimo["resultado"]["situacao_frase"],
            )

    # 3 · investigar
    if ultimo is None:
        passos["investigar"] = ("bloqueado", "Depende do primeiro fechamento.")
    else:
        ligadas = {
            e["dados"].get("fechamento_id") for inv in invs for e in inv["eventos"] if e["dados"]
        }
        if _tem_o_que_investigar(ultimo) and ultimo["id"] not in ligadas:
            passos["investigar"] = (
                "pendente",
                "O último fechamento tem verificação a fazer e ainda não virou investigação.",
            )
        elif abertas:
            passos["investigar"] = ("andamento", f"{len(abertas)} investigação(ões) aberta(s).")
        else:
            passos["investigar"] = ("feito", "Nada aberto para investigar neste momento.")

    # 4 · ação
    com_acao = {x["investigacao_id"] for x in acoes if x["investigacao_id"] is not None}
    sem_acao = [x for x in abertas if x["estado"] == "em_investigacao" and x["id"] not in com_acao]
    if sem_acao:
        passos["acao"] = (
            "pendente",
            (
                f"{len(sem_acao)} investigação(ões) sem ação registrada: registre o que a "
                "equipe verificou ou fez."
            ),
        )
    elif acoes:
        passos["acao"] = (
            "feito",
            f"{len(acoes)} ação(ões) registrada(s); última em {_data(acoes[-1]['data'])}.",
        )
    elif abertas:
        passos["acao"] = ("andamento", "Investigações aguardando dados ou verificação.")
    else:
        passos["acao"] = ("bloqueado", "Depende de uma investigação aberta.")

    # 5 · resultado: "não avaliável" não conclui a etapa (D110)
    avaliacoes = {x["id"]: ultima_avaliacao(a, x["id"]) for x in acoes}
    sem_avaliacao = [x for x in acoes if avaliacoes[x["id"]] is None]
    nao_avaliaveis = [
        x
        for x in acoes
        if avaliacoes[x["id"]] is not None
        and avaliacoes[x["id"]]["resultado"]["resultado"] == "nao_avaliavel"
    ]
    if sem_avaliacao or nao_avaliaveis:
        partes = []
        if sem_avaliacao:
            partes.append(f"{len(sem_avaliacao)} ação(ões) ainda sem avaliação do resultado")
        if nao_avaliaveis:
            partes.append(
                f'{len(nao_avaliaveis)} ação(ões) com avaliação "não avaliável" '
                "(reavaliar quando houver dados)"
            )
        passos["resultado"] = ("pendente", "; ".join(partes) + ".")
    elif acoes:
        passos["resultado"] = ("feito", "Todas as ações registradas já foram avaliadas.")
    else:
        passos["resultado"] = ("bloqueado", "Depende de uma ação registrada.")

    return [
        {"id": k, "titulo": t, "estado": passos[k][0], "frase": passos[k][1], "destino": d}
        for k, t, d in PASSOS
    ]


def proximo_passo(itens: list[dict]) -> dict | None:
    """O primeiro passo pendente do percurso, ou None quando nada está pendente."""
    return next((x for x in itens if x["estado"] == "pendente"), None)
