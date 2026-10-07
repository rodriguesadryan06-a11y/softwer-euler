"""Painel do serviço, fila de atenção, relatório do fechamento e indicadores internos (D95).

Tudo é lido dos registros persistidos; nada é estimado aqui. Regras:
- a fila de atenção usa categorias explícitas, sem nota nem pesos;
- ocorrências repetidas da mesma investigação são agrupadas, nunca escondidas;
- só entra no total verificado a economia de avaliações que cumpriram o protocolo, uma
  por intervenção (a mais recente), e janelas sobrepostas nunca somam duas vezes;
- oportunidades não confirmadas aparecem uma a uma, sem soma;
- o benefício é da ação da planta, não da EULER; preço de assinatura não entra em cálculo.
"""

from __future__ import annotations

import pandas as pd

from euler.acompanhamento import (
    ESTADOS,
    RESULTADOS,
    custos_servico,
    intervencoes,
    investigacoes,
    ultima_avaliacao,
)
from euler.armazem import Armazem
from euler.fechamento import fechamentos_vigentes, referencia_vigente
from euler.formato import num

CATEGORIAS = {
    "desvio_persistente": "Desvio acima da referência em fechamentos seguidos",
    "acao_sem_verificacao": "Ação registrada aguardando verificação",
    "desvio_novo": "Desvio acima da referência no último fechamento",
    "investigacao_aberta": "Investigação aberta",
    "oportunidade": "Oportunidade a investigar (ainda não confirmada)",
    "dados": "Dados ou decisões pendentes",
}
ORDEM = list(CATEGORIAS)
CRITERIOS = (
    "Ordem por categoria: desvio persistente; ação aguardando verificação; desvio novo; "
    "investigação aberta; oportunidade; pendência de dados. Dentro da categoria, maior "
    "valor em reais primeiro (ausente vai depois). Persistência = fechamentos seguidos com "
    "a mesma referência e consumo acima dela, fora da incerteza. Sem nota nem pesos (D95)."
)


def _brl(v) -> str:
    return "—" if v is None else ("−" if v < 0 else "") + f"R$ {num(abs(v), 0)}"


def _persistencia(fs: list[dict]) -> int:
    """Fechamentos seguidos, do mais recente para trás, acima da mesma referência."""
    n = 0
    ref = None
    for f in reversed(fs):
        if ref is not None and f["referencia_id"] != ref:
            break
        ref = f["referencia_id"]
        if f["resultado"]["situacao"] != "acima":
            break
        n += 1
    return n


def fila_de_atencao(a: Armazem, equip_id: str) -> list[dict]:
    """O que olhar primeiro, com os critérios de cada item à vista."""
    itens = []
    fs = fechamentos_vigentes(a, equip_id)
    ultimo = fs[-1] if fs else None
    persist = _persistencia(fs)
    abertas = investigacoes(a, equip_id, abertas=True)
    chaves_abertas = {x["chave_grupo"] for x in abertas}
    if ultimo is not None and ultimo["resultado"]["situacao"] == "acima":
        desvio = ultimo["resultado"]["nucleo"]["explicacao_conta"]["desvio"]
        itens.append(
            {
                "categoria": "desvio_persistente" if persist >= 2 else "desvio_novo",
                "titulo": f"Consumo acima da referência ajustada ({num(desvio['pct_do_esperado'], 1)}%)",
                "valor_brl": desvio["custo_brl"],
                "criterios": {
                    "persistencia_fechamentos": persist,
                    "magnitude_pct": desvio["pct_do_esperado"],
                    "faixa_brl": desvio["faixa_brl"],
                },
                "proxima_acao": ultimo["resultado"]["nucleo"]["proxima_verificacao"]["acao"],
                "fechamento_id": ultimo["id"],
            }
        )
    for it in intervencoes(a, equip_id):
        av = ultima_avaliacao(a, it["id"])
        if av is None or av["resultado"]["resultado"] == "nao_avaliavel":
            itens.append(
                {
                    "categoria": "acao_sem_verificacao",
                    "titulo": f"Verificar o resultado: {it['descricao']} ({pd.Timestamp(it['data']):%d/%m/%Y})",
                    "valor_brl": None,
                    "criterios": {
                        "avaliacao": "nenhuma" if av is None else av["resultado"]["frase"]
                    },
                    "proxima_acao": (
                        "Avaliar a ação quando houver período completo depois dela."
                        if av is None
                        else "Completar os dados que faltam e avaliar de novo."
                    ),
                    "intervencao_id": it["id"],
                }
            )
    for x in abertas:
        ocorr = sum(e["tipo"] in ("criada", "ocorrencia") for e in x["eventos"])
        itens.append(
            {
                "categoria": "investigacao_aberta",
                "titulo": f"{x['titulo']} · {ESTADOS[x['estado']]}",
                "valor_brl": (x["dados"].get("desvio") or {}).get("custo_brl"),
                "criterios": {
                    "ocorrencias": ocorr,
                    "situacao_do_desvio": (x["dados"].get("desvio") or {}).get("situacao"),
                    "responsavel": x["responsavel"] or "não informado",
                    "estado": ESTADOS[x["estado"]],
                },
                "proxima_acao": (x["dados"].get("proxima_verificacao") or {}).get("acao"),
                "investigacao_id": x["id"],
            }
        )
    if ultimo is not None:
        for o in ultimo["resultado"]["nucleo"]["oportunidades"]:
            if o["prioridade"] not in ("alta", "media"):
                continue
            if f"{equip_id}:{o['id']}" in chaves_abertas:
                continue  # já está numa investigação aberta (agrupado lá)
            itens.append(
                {
                    "categoria": "oportunidade",
                    "titulo": o["titulo"],
                    "valor_brl": o["impacto_brl"],
                    "criterios": {
                        "evidencia": o["evidencia"],
                        "prioridade_investigacao": o["prioridade"],
                        "complexidade_verificacao": o["complexidade"] or "não classificada",
                        "faixa_brl": o["faixa_brl"],
                    },
                    "proxima_acao": o["verificacao"],
                }
            )
    cob = a.cobertura(equip_id)
    if cob["estado"] != "atualizado":
        itens.append(
            {
                "categoria": "dados",
                "titulo": cob["frase"],
                "valor_brl": None,
                "criterios": {},
                "proxima_acao": "Importar os dados mais recentes da planta.",
            }
        )
    if cob["conflitos_pendentes"]:
        itens.append(
            {
                "categoria": "dados",
                "titulo": f"{cob['conflitos_pendentes']} conflito(s) de importação aguardando decisão",
                "valor_brl": None,
                "criterios": {},
                "proxima_acao": "Decidir cada conflito (aceitar como correção ou recusar).",
            }
        )
    if referencia_vigente(a, equip_id) is None:
        itens.append(
            {
                "categoria": "dados",
                "titulo": "Referência do equipamento não definida",
                "valor_brl": None,
                "criterios": {},
                "proxima_acao": "Definir a referência.",
            }
        )
    itens.sort(
        key=lambda i: (
            ORDEM.index(i["categoria"]),
            (0, -i["valor_brl"]) if i["valor_brl"] is not None else (1, 0.0),
            i["titulo"],
        )
    )
    for n, i in enumerate(itens, 1):
        i["ordem"] = n
        i["categoria_rotulo"] = CATEGORIAS[i["categoria"]]
    return itens


def _janelas_sobrepostas(itens: list[dict]) -> set[int]:
    sobrepostas = set()
    for i, x in enumerate(itens):
        for y in itens[i + 1 :]:
            a0, a1 = pd.Timestamp(x["periodo"]["inicio"]), pd.Timestamp(x["periodo"]["fim"])
            b0, b1 = pd.Timestamp(y["periodo"]["inicio"]), pd.Timestamp(y["periodo"]["fim"])
            if a0 < b1 and b0 < a1:
                sobrepostas |= {x["intervencao_id"], y["intervencao_id"]}
    return sobrepostas


def painel(a: Armazem, equip_id: str) -> dict:
    """Visão executiva do acompanhamento: o que mudou, o que está aberto, o que foi
    verificado e o que ainda falta. Cada número diz de onde vem."""
    fs = fechamentos_vigentes(a, equip_id)
    ultimo = fs[-1] if fs else None
    todas = investigacoes(a, equip_id)
    abertas = [x for x in todas if x["estado"] != "encerrada"]
    encerradas = [x for x in todas if x["estado"] == "encerrada"]
    acoes = []
    verificadas = []
    for it in intervencoes(a, equip_id):
        av = ultima_avaliacao(a, it["id"])
        r = None if av is None else av["resultado"]
        acoes.append(
            {
                "id": it["id"],
                "data": it["data"],
                "descricao": it["descricao"],
                "resultado": None if r is None else r["resultado"],
                "frase": "Ainda não avaliada." if r is None else r["frase"],
            }
        )
        ev = None if r is None else r.get("economia_verificada")
        if ev and ev.get("valor_brl") is not None:
            verificadas.append(
                {
                    "intervencao_id": it["id"],
                    "descricao": it["descricao"],
                    "valor_brl": ev["valor_brl"],
                    "faixa_brl": ev["faixa_brl"],
                    "periodo": ev["periodo"],
                    "beneficio_liquido_brl": ev.get("beneficio_liquido_brl"),
                    "custos_considerados_brl": ev.get("custos_considerados_brl"),
                }
            )
    sobrepostas = _janelas_sobrepostas(verificadas)
    somaveis = [v for v in verificadas if v["intervencao_id"] not in sobrepostas]
    total = sum(v["valor_brl"] for v in somaveis) if somaveis else None
    liquidos = [v["beneficio_liquido_brl"] for v in somaveis]
    custos_extra = custos_servico(a, equip_id)
    resumo_custos = sum(c["valor_brl"] for c in custos_extra) if custos_extra else None
    oportunidades = (
        []
        if ultimo is None
        else [
            o
            for o in ultimo["resultado"]["nucleo"]["oportunidades"]
            if o["prioridade"] in ("alta", "media")
        ]
    )
    cob = a.cobertura(equip_id)
    pendencias = [cob["frase"]] if cob["estado"] != "atualizado" else []
    if cob["conflitos_pendentes"]:
        pendencias.append(f"{cob['conflitos_pendentes']} conflito(s) de importação para decidir.")
    pendencias += [
        f"Investigação aguardando dados: {x['titulo']}"
        for x in abertas
        if x["estado"] == "aguardando_dados"
    ]
    pendencias += [f"Ação sem avaliação: {x['descricao']}" for x in acoes if x["resultado"] is None]
    return {
        "ultimo_fechamento": None
        if ultimo is None
        else {
            "id": ultimo["id"],
            "periodo": ultimo["resultado"]["nucleo"]["periodo"],
            "situacao": ultimo["resultado"]["situacao"],
            "situacao_frase": ultimo["resultado"]["situacao_frase"],
            "frase": (ultimo["resultado"]["nucleo"]["explicacao_conta"].get("desvio") or {}).get(
                "frase"
            ),
            "mudanca": ultimo["resultado"]["comparacao_anterior"]["frase"],
            "persistencia": ultimo["resultado"]["contexto"].get("persistencia"),
            "referencia_versao": ultimo["resultado"]["nucleo"]["referencia"]["versao"],
        },
        "fechamentos": len(fs),
        "investigacoes": {
            "abertas": len(abertas),
            "por_estado": {
                ESTADOS[k]: sum(x["estado"] == k for x in abertas)
                for k in ESTADOS
                if k != "encerrada"
            },
            "encerradas": len(encerradas),
            "por_resultado": {
                RESULTADOS[k]: sum((x["dados"].get("resultado") == k) for x in encerradas)
                for k in RESULTADOS
            },
        },
        "acoes": acoes,
        "verificado": {
            "itens": verificadas,
            "total_brl": total,
            "excluidas_por_sobreposicao": sorted(sobrepostas),
            "beneficio_liquido_brl": sum(liquidos) if somaveis and None not in liquidos else None,
            "nota": (
                "Soma só economias verificadas pelo protocolo, uma por intervenção, sem janelas "
                "sobrepostas. É benefício das ações da planta (equipe, fornecedores, projetos), "
                "não um valor atribuído à EULER. Horas de trabalho não entram como dinheiro."
            ),
        },
        "custos_servico_informados_brl": resumo_custos,
        "oportunidades_nao_confirmadas": oportunidades,
        "pendencias": pendencias,
        "cobertura": cob,
    }


SELO_ORIGEM = {
    "sintetico": "> **DADOS SINTÉTICOS** · não representam uma planta real.",
    "publico": "> **DADOS PÚBLICOS** · de fonte pública, não de um cliente.",
}


def selo_origem(origem: str | None) -> list[str]:
    """Linhas do selo de origem dos dados para os relatórios exportados (D110)."""
    return [SELO_ORIGEM[origem], ""] if origem in SELO_ORIGEM else []


def texto_fechamento(f: dict, origem: str | None = None) -> str:
    """Relatório em Markdown gerado do mesmo objeto que a tela mostra.

    `origem`: origem dos dados da planta ("sintetico", "publico", "real"), para fechamentos
    gravados antes de o resultado guardar a origem; a gravada no fechamento tem prioridade.
    """
    r = f["resultado"]
    n = r["nucleo"]
    conta = n["explicacao_conta"]
    cp = n["conta_do_periodo"]
    linhas = [
        f"# Fechamento #{f['id']} · {f['equipamento_id']}",
        "",
        *selo_origem(r.get("origem_dados") or origem),
        (
            f"Período: {pd.Timestamp(n['periodo']['inicio']):%d/%m/%Y} a "
            f"{pd.Timestamp(n['periodo']['fim']):%d/%m/%Y} · referência v{n['referencia']['versao']} "
            f"({n['referencia']['tipo']}) · política de custo: {n['politica_custo']['descricao']}"
        ),
        "",
        f"**{r['situacao_frase']}**",
        "",
    ]
    if conta.get("disponivel"):
        d = conta["desvio"]
        linhas += [
            d["frase"],
            "",
            "| | Combustível | Custo |",
            "|---|---|---|",
            f"| Consumido | {num(conta['consumido']['combustivel_t'], 1)} t | {_brl(conta['consumido']['custo_brl'])} |",
            f"| Esperado (referência ajustada) | {num(conta['esperado']['combustivel_t'], 1)} t | {_brl(conta['esperado']['custo_brl'])} |",
            f"| Desvio monetizado | {num(d['combustivel_t'], 1)} t | {_brl(d['custo_brl'])} |",
            "",
        ]
        v = conta["variacao"]
        if v.get("disponivel"):
            linhas += ["## Por que a conta mudou", "", "| Parcela | Valor |", "|---|---|"]
            linhas += [
                f"| {x['titulo']} | {_brl(x['custo_brl']) if x['custo_brl'] is not None else 'no desvio'} |"
                for x in v["componentes"]
            ]
            linhas.append("")
    else:
        linhas += [conta.get("motivo") or "Conta indisponível.", ""]
    notas = f"notas: {_brl(cp['valor_notas_brl'])}"
    if cp.get("lotes_sem_valor", 0):
        notas = (
            f"notas, valor parcial: {_brl(cp['valor_notas_brl'])}; "
            f"{cp['lotes_sem_valor']} lote(s) sem valor informado"
        )
    linhas += [
        "## Conta do período",
        "",
        f"- Recebido: {num(cp['recebido_t'], 1)} t em {cp['recebido_lotes']} lotes ({notas})",
        f"- Estoque: {num(cp['estoque_inicial_t'], 1)} t → {num(cp['estoque_final_t'], 1)} t",
        f"- Consumido: {num(cp['consumido_t'], 1)} t · custo atribuído: {_brl(cp['custo_atribuido_brl'])}",
        f"- {cp['nota_pagamento']}",
        "",
        "## O que mudou desde o fechamento anterior",
        "",
        r["comparacao_anterior"]["frase"],
        "",
        "## O que investigar",
        "",
    ]
    for o in n["oportunidades"]:
        if o["prioridade"] in ("alta", "media"):
            linhas.append(
                f"- {o['titulo']} (evidência {o['evidencia'].lower()}): {o['verificacao']}"
            )
    linhas += ["", "## Ações anteriores", ""]
    for x in r["contexto"]["acoes"] or [{"descricao": "Nenhuma ação registrada.", "frase": ""}]:
        linhas.append(f"- {x['descricao']}: {x['frase']}")
    if r["contexto"].get("persistencia"):
        linhas += ["", r["contexto"]["persistencia"]]
    linhas += [
        "",
        "---",
        (
            f"Núcleo reproduzível: {r['nucleo_sha'][:16]} · dados da revisão {f['revisao_dados']} · "
            f"código {f['versao_euler']}. Desvio monetizado não é economia recuperável nem verificada."
        ),
    ]
    return "\n".join(linhas)


def indicadores_internos(a: Armazem, equip_id: str) -> dict:
    """Esforço de atendimento, calculado só dos registros já existentes (nada é coletado à
    parte). Para uso interno da equipe EULER, fora das telas do cliente."""
    lotes = a.importacoes(equip_id)
    contagens = [x["resumo"]["contagem"] for x in lotes]
    total = {k: 0 for k in ("nova", "igual", "conflito", "rejeitada")}
    for c in contagens:
        for t in c.values():
            for k in total:
                total[k] += t.get(k, 0)
    perfis = a.perfis(equip_id)
    eventos = a.eventos(equip_id, limite=100000)
    return {
        "importacoes": len(lotes),
        "linhas": total,
        "perfis_salvos": len(perfis),
        "usos_de_perfil": sum(p["usos"] for p in perfis),
        "correcoes": sum(e["tipo"] == "correcao" for e in eventos),
        "conflitos_decididos": sum(e["entidade"] == "conflito" for e in eventos),
        "fechamentos": len(fechamentos_vigentes(a, equip_id)),
    }
