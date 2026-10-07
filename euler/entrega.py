"""Entrega recorrente de cada fechamento (D104, proposta).

Um documento curto por fechamento, para a gestão da planta, com quatro partes:
1. a conta do período (quadro da conclusão, D101) e o que mudou desde o fechamento anterior;
2. as pendências relevantes;
3. as verificações e ações em andamento;
4. os resultados já demonstrados (só avaliações registradas e economia verificada, D94/D95).

Tudo é lido dos registros gravados; nada é estimado aqui. A conta vem preservada do
fechamento; pendências, verificações e resultados são os do momento em que a entrega é
gerada, e o documento diz a data. A EULER recomenda verificações e não comanda a caldeira.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from euler.acompanhamento import ESTADOS, intervencoes, investigacoes, ultima_avaliacao
from euler.armazem import ORIGEM_DA_CLASSE, Armazem
from euler.conta import conclusao_financeira
from euler.fechamento import fechamento, fechamentos_vigentes, periodos_pendentes
from euler.formato import num
from euler.linha_do_tempo import linha_do_tempo
from euler.painel import painel, selo_origem

SEGURANCA = (
    "A EULER investiga e recomenda verificações; não comanda a caldeira. Qualquer ajuste "
    "operacional é avaliado e decidido pelos responsáveis técnicos da planta."
)


def _dias(p: dict) -> float:
    return (pd.Timestamp(p["fim"]) - pd.Timestamp(p["inicio"])).total_seconds() / 86400


def entrega_do_fechamento(
    a: Armazem, equip_id: str, fechamento_id: int | None = None, agora=None
) -> dict | None:
    """Monta a entrega de um fechamento (padrão: o mais recente do equipamento).

    Entrada: armazém aberto, equipamento, id do fechamento (opcional) e o instante da
    geração (padrão: agora, UTC). Saída: dict com `fechamento_id`, `periodo`, `gerada_em`,
    `conta` (quadro da conclusão), `mudou`, `serie` (leitura da linha do tempo até este
    fechamento), `qualidade`, `pendencias`, `verificacoes`, `acoes_em_andamento`,
    `resultados` e `seguranca`; None quando ainda não há fechamento. Valores ausentes
    ficam None; nada é preenchido nem somado além do que o painel já soma (D95).
    """
    if fechamento_id is None:
        lista = fechamentos_vigentes(a, equip_id)
        if not lista:
            return None
        f = lista[-1]
    else:
        f = fechamento(a, fechamento_id)
        if f["equipamento_id"] != equip_id:
            raise ValueError("O fechamento escolhido é de outro equipamento.")
    agora = agora or datetime.now(UTC)
    r = f["resultado"]
    n = r["nucleo"]
    c = n["explicacao_conta"]
    dias = {"referencia": _dias(n["referencia"]), "comparacao": _dias(n["periodo"])}
    lt = linha_do_tempo(a, equip_id, ate_fechamento=f["id"])
    este = lt["periodos"][-1]
    pn = painel(a, equip_id)

    cob = pn["cobertura"]
    pendencias = [cob["frase"]] if cob["estado"] != "atualizado" else []
    if cob["conflitos_pendentes"]:
        pendencias.append(f"{cob['conflitos_pendentes']} conflito(s) de importação para decidir.")
    novos = [p for p in periodos_pendentes(a, equip_id) if p["valido"]]
    if novos:
        pendencias.append(f"{len(novos)} período(s) com dados completos ainda sem fechamento.")
    if este["qualidade"] != "completa":
        pendencias.append(
            f"Conta deste fechamento: {este['qualidade']} ({este['qualidade_motivo']})"
        )

    verificacoes = [
        {
            "titulo": x["titulo"],
            "estado": ESTADOS[x["estado"]],
            "responsavel": x["responsavel"] or "não informado",
            "proxima": (x["dados"].get("proxima_verificacao") or {}).get("acao"),
        }
        for x in investigacoes(a, equip_id, abertas=True)
    ]
    em_andamento, avaliadas = [], []
    for it in intervencoes(a, equip_id):
        av = ultima_avaliacao(a, it["id"])
        item = {"data": it["data"], "descricao": it["descricao"]}
        if av is None or av["resultado"]["resultado"] == "nao_avaliavel":
            em_andamento.append(
                {
                    **item,
                    "situacao": "ainda não avaliada"
                    if av is None
                    else "avaliação sem conclusão: " + av["resultado"]["frase"],
                }
            )
        else:
            avaliadas.append({**item, "frase": av["resultado"]["frase"]})
    ver = pn["verificado"]
    return {
        "fechamento_id": f["id"],
        "equipamento_id": equip_id,
        "periodo": n["periodo"],
        "referencia_versao": n["referencia"]["versao"],
        "gerada_em": pd.Timestamp(agora).isoformat(),
        "situacao_frase": r["situacao_frase"],
        "conta": conclusao_financeira(c, n["oportunidades"], dias),
        "mudou": r["comparacao_anterior"]["frase"],
        "serie": lt["padrao"],
        "qualidade": {"rotulo": este["qualidade"], "motivo": este["qualidade_motivo"]},
        "pendencias": pendencias,
        "verificacoes": verificacoes,
        "acoes_em_andamento": em_andamento,
        "resultados": {
            "avaliadas": avaliadas,
            "economia_verificada_brl": ver["total_brl"],
            "itens_verificados": ver["itens"],
            "excluidas_por_sobreposicao": ver["excluidas_por_sobreposicao"],
            "nota": ver["nota"],
        },
        "nucleo_sha": r["nucleo_sha"],
        "revisao_dados": f["revisao_dados"],
        "versao_euler": f["versao_euler"],
        "origem_dados": r.get("origem_dados") or ORIGEM_DA_CLASSE.get(a.info["classe"]),
        "seguranca": SEGURANCA,
    }


def _brl(v, sinal: bool = False) -> str:
    if v is None:
        return "—"
    s = "−" if v < 0 else ("+" if sinal and v > 0 else "")
    return f"{s}R$ {num(abs(v), 0)}"


def _faixa(f) -> str:
    return "não determinada" if not f else f"{_brl(f[0])} a {_brl(f[1])}"


def _data(x) -> str:
    return f"{pd.Timestamp(x):%d/%m/%Y}"


ESTADO_DESVIO = {
    "acima": "acima do esperado, além da incerteza",
    "abaixo": "abaixo do esperado, além da incerteza",
    "nao_estabelecido": "dentro da incerteza: não estabelecida",
    "sem_faixa": "sem faixa de incerteza",
}


def _conta_md(q: dict) -> list[str]:
    if not q.get("disponivel"):
        return [q.get("motivo") or "Conta indisponível.", ""]
    c, e, s = q["consumido"], q["esperado"], q["sem_explicacao"]
    preco = (
        f"{num(c['combustivel_t'], 1)} t × R$ {num(c['preco_brl_t'], 2)}/t"
        if c.get("preco_brl_t") is not None
        else f"{num(c['combustivel_t'], 1)} t"
    )
    linhas = [
        f"**{q['frase']}**",
        "",
        "| A conta do período | Valor | Como foi obtido |",
        "|---|---:|---|",
        (
            f"| Custo do combustível consumido | {_brl(c['custo_brl'])} | {preco} · consumo pelos "
            "estoques e recebimentos |"
        ),
        (
            f"| Esperado nas condições analisadas | {_brl(e['custo_brl'])} | referência ajustada por "
            f"{', '.join(e['ajustado_por'])} |"
        ),
        (
            f"| **Diferença sem explicação** | **{_brl(s['custo_brl'], True)}** | faixa das medições: "
            f"{_faixa(s['faixa_brl'])} · {ESTADO_DESVIO[s['estado']]} |"
        ),
        "",
    ]
    p = q["ponte"]
    if p["disponivel"]:
        linhas += [
            (
                f"Por que o custo mudou em relação à referência: {_brl(p['referencia_brl'])} → "
                f"{_brl(p['periodo_brl'])}, variação de {_brl(p['variacao_brl'], True)}."
            ),
            "",
            "| Parcela | Valor |",
            "|---|---:|",
        ]
        linhas += [
            f"| {g['titulo']}{' · ' + g['nota'] if g.get('nota') else ''} | "
            f"{_brl(g['custo_brl'], True) if g['custo_brl'] is not None else 'não separado'} |"
            for g in p["grupos"]
        ]
        linhas += [
            "",
            "Explicado quer dizer atribuído a um fator medido, não inevitável.",
            "",
        ]
    else:
        linhas += [f"Comparação com a referência: {p['motivo']}", ""]
    ev = q["evitavel"]
    linhas += [f"**{ev['situacao']}.** O que falta verificar:", ""]
    itens = list(ev["antes"]) + [
        f"**{x['titulo']}**"
        + (
            f" · impacto associado {_brl(x['impacto_brl'])}"
            if x.get("impacto_brl") is not None
            else ""
        )
        + f". {x['acao']}"
        + (f" Separa: {x['distingue']}." if x.get("distingue") else "")
        for x in ev["verificacoes"]
    ]
    linhas += [f"{i}. {t}" for i, t in enumerate(itens, 1)] or ["Nenhuma verificação priorizada."]
    linhas += ["", ev["condicao"], ""]
    return linhas


def texto_entrega(e: dict, nome_equipamento: str | None = None) -> str:
    """A entrega em Markdown, gerada do mesmo dict que a tela mostra."""
    nome = nome_equipamento or e["equipamento_id"]
    linhas = [
        f"# Entrega do fechamento #{e['fechamento_id']} · {nome}",
        "",
        *selo_origem(e.get("origem_dados")),
        (
            f"Período: {_data(e['periodo']['inicio'])} a {_data(e['periodo']['fim'])} · referência "
            f"v{e['referencia_versao']} · entrega gerada em {_data(e['gerada_em'])}."
        ),
        "",
        (
            "A conta é a preservada no fechamento. Pendências, verificações e resultados são os "
            "registrados até a data da entrega."
        ),
        "",
        "## 1. A conta do período",
        "",
        *_conta_md(e["conta"]),
        "## 2. O que mudou",
        "",
        e["mudou"],
        "",
        *[f"- {x}" for x in e["serie"]],
        "",
        "## 3. Pendências relevantes",
        "",
        *([f"- {x}" for x in e["pendencias"]] or ["Nenhuma pendência registrada."]),
        "",
        "## 4. Verificações e ações em andamento",
        "",
    ]
    for v in e["verificacoes"]:
        linhas.append(
            f"- Verificação: {v['titulo']} · estado: {v['estado'].lower()} · "
            f"responsável: {v['responsavel']}"
            + (f" · próximo passo: {v['proxima']}" if v["proxima"] else "")
        )
    for x in e["acoes_em_andamento"]:
        linhas.append(f"- Ação em {_data(x['data'])}: {x['descricao']} · {x['situacao']}")
    if not e["verificacoes"] and not e["acoes_em_andamento"]:
        linhas.append("Nenhuma verificação ou ação em andamento.")
    res = e["resultados"]
    linhas += ["", "## 5. Resultados já demonstrados", ""]
    linhas += [f"- {_data(x['data'])} · {x['descricao']}: {x['frase']}" for x in res["avaliadas"]]
    if not res["avaliadas"]:
        linhas.append("Nenhuma ação avaliada até esta entrega.")
    linhas += [
        "",
        "Economia verificada no histórico: "
        + (
            _brl(res["economia_verificada_brl"])
            if res["economia_verificada_brl"] is not None
            else "não apurada (nenhuma avaliação cumpriu o protocolo)"
        )
        + ".",
        "",
        res["nota"],
        "",
        "---",
        e["seguranca"],
        "",
        (
            f"Núcleo reproduzível: {e['nucleo_sha'][:16]} · dados da revisão {e['revisao_dados']} · "
            f"código {e['versao_euler']}."
        ),
    ]
    return "\n".join(linhas)
