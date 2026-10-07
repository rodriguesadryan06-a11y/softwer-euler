"""Dados das telas "Acompanhar a planta" para a prévia interativa (scripts/gerar_previa.py).

Repete com o motor o que o botão "Criar planta de demonstração (sintética)" faz no app (mesma
caldeira, mesma referência de agosto, primeiro fechamento) e guarda o que as telas mostram:
os três fechamentos possíveis, a investigação aberta a partir de cada um e a avaliação de uma
ação para cada data. A página não recalcula nada: só escolhe o resultado já calculado e
registra, na própria página, o que o visitante faz (evidência, ação, encerramento).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pandas as pd

from euler.acompanhamento import (
    ESTADOS,
    RESULTADOS,
    TIPOS_INTERVENCAO,
    TRANSICOES,
    abrir_do_fechamento,
    avaliar_intervencao,
    registrar_intervencao,
)
from euler.armazem import POLITICAS_CUSTO
from euler.conta import conclusao_financeira
from euler.evidencias import ROTULOS
from euler.fechamento import (
    TIPOS_REFERENCIA,
    criar_referencia,
    fechamentos,
    periodos_pendentes,
    produzir_fechamento,
    referencia_vigente,
)
from euler.formato import num
from euler.io.esquemas import TABELAS
from euler.linha_do_tempo import linha_do_tempo
from euler.painel import CATEGORIAS, CRITERIOS
from euler.periodos import periodos_entre_estoques
from euler.persistencia import Repositorio

RAIZ = Path(__file__).resolve().parents[1]
DEMO = RAIZ / "demo" / "caso_demo_completo"
EQ = "CALD-DEMO-01"
AUTOR = "__AUTOR__"  # a página troca pelo nome que o visitante digitar
FUSO = "America/Sao_Paulo"
SITUACOES = {
    "nova": "Novos",
    "igual": "Já gravados (ignorados)",
    "conflito": "Conflitos",
    "rejeitada": "Recusados",
    "repetida_no_arquivo": "Repetidos no arquivo",
    "tardia": "Novos em período já coberto",
}


def brl(v) -> str:
    return "—" if v is None else ("−" if v < 0 else "") + f"R$ {num(abs(v), 0)}"


def data(x) -> str:
    return "—" if not x else f"{pd.Timestamp(x):%d/%m/%Y}"


def periodo(p: dict) -> str:
    return f"{data(p['inicio'])} a {data(p['fim'])}"


def _dias(p: dict) -> float:
    return (pd.Timestamp(p["fim"]) - pd.Timestamp(p["inicio"])).total_seconds() / 86400


# campos da linha do tempo (D103) que a prévia usa; valores do motor, sem conta nova
CAMPOS_LT = (
    "dias", "vapor_t", "consumo_t_t", "custo_brl", "esperado_brl", "desvio_brl", "faixa_brl",
    "estado", "custo_por_t_vapor_brl", "custo_por_dia_brl", "desvio_por_t_vapor_brl",
    "faixa_por_t_vapor_brl", "referencia_versao", "qualidade", "qualidade_motivo",
)  # fmt: skip


def _fechamento(f: dict) -> dict:
    """O que a tela Fechamentos mostra de um fechamento (mesmos textos da tela)."""
    r = f["resultado"]
    n = r["nucleo"]
    conta = n["explicacao_conta"]
    desvio = conta.get("desvio") or {}
    cp = n["conta_do_periodo"]
    ce = n["custo_por_energia"]
    pol = n["politica_custo"]
    ops = [o for o in n["oportunidades"] if o["prioridade"] in ("alta", "media")]
    variacao = None
    if conta.get("disponivel") and conta["variacao"].get("disponivel"):
        variacao = [
            [
                x["titulo"],
                x["pergunta"],
                brl(x["custo_brl"]) if x["custo_brl"] is not None else "no desvio",
            ]
            for x in conta["variacao"]["componentes"]
        ]
    return {
        "id": f["id"],
        "inicio": n["periodo"]["inicio"],
        "fim": n["periodo"]["fim"],
        "periodo": periodo(n["periodo"]),
        "situacao": r["situacao"],
        "situacao_frase": r["situacao_frase"],
        "frase": desvio.get("frase") or r["situacao_frase"],
        # quadro único da conclusão (D101): o mesmo objeto que o app mostra
        "quadro": conclusao_financeira(
            conta,
            n["oportunidades"],
            {"referencia": _dias(n["referencia"]), "comparacao": _dias(n["periodo"])},
        ),
        "metricas": [
            brl(conta["consumido"]["custo_brl"]),
            brl(conta["esperado"]["custo_brl"]),
            brl(desvio["custo_brl"]),
        ]
        if conta.get("disponivel")
        else None,
        "politica": (
            "Desvio monetizado não é oportunidade comprovada nem economia verificada. Política de "
            f"custo: {pol['descricao']}" + (f" ({pol['motivo']})" if pol.get("motivo") else "")
        ),
        "mudanca": r["comparacao_anterior"]["frase"],
        "persistencia": r["contexto"].get("persistencia"),
        "proxima": n["proxima_verificacao"]["acao"],
        "forca": "Força da evidência: "
        + " · ".join(
            f"{ROTULOS.get(k, k).lower()} {v.lower()}" for k, v in n["evidencias"].items()
        ),
        "conta_periodo": [
            ["Recebido (notas)", f"{num(cp['recebido_t'], 1)} t", brl(cp["valor_notas_brl"])],
            ["Estoque inicial", f"{num(cp['estoque_inicial_t'], 1)} t", "—"],
            ["Estoque final", f"{num(cp['estoque_final_t'], 1)} t", "—"],
            ["Consumido (E9)", f"{num(cp['consumido_t'], 1)} t", brl(cp["custo_atribuido_brl"])],
            ["Despesa ou pagamento do período", "—", "não informado"],
        ],
        "nota_pagamento": cp["nota_pagamento"],
        "energia": f"Custo por energia: R$ {num(ce['periodo_brl_gj'])}/GJ (base PCI úmido dos lotes)."
        if ce["periodo_brl_gj"] is not None
        else ce["motivo"],
        "variacao": variacao,
        "nao_ajustado": list((conta.get("esperado") or {}).get("nao_ajustado", []))
        if variacao
        else [],
        "oportunidades": [
            f"**{o['titulo']}** · evidência {o['evidencia'].lower()} · {brl(o['impacto_brl'])} "
            f"associado (não somar) · {o['verificacao']}"
            for o in ops
        ],
        "sobreposicao": list(n.get("sobreposicao", [])),
        "rastro": (
            f"Dados da revisão {f['revisao_dados']} · conjunto {f['conjunto_sha'][:16]} · "
            f"núcleo {f['resultado_sha'][:16]} · código {f['versao_euler']} · referência "
            f"v{n['referencia']['versao']}"
        ),
        "ref_versao": n["referencia"]["versao"],
        "ref_id": n["referencia"]["id"],
        "desvio_brl": desvio.get("custo_brl"),
        "incerteza": desvio.get("incerteza"),
        # para a fila do Painel (mesmas regras de euler/painel.py)
        "desvio_pct": desvio.get("pct_do_esperado"),
        "desvio_faixa": desvio.get("faixa_brl"),
        "ops": [
            {
                "id": o["id"],
                "titulo": o["titulo"],
                "evidencia": o["evidencia"],
                "prioridade": o["prioridade"],
                "complexidade": o["complexidade"] or "não classificada",
                "impacto_brl": o["impacto_brl"],
                "faixa_brl": o["faixa_brl"],
                "verificacao": o["verificacao"],
            }
            for o in ops
        ],
    }


def _pendentes(a) -> list[dict]:
    return [
        {
            "rotulo": f"{p['inicio']:%d/%m} a {p['fim']:%d/%m}",
            "valido": bool(p["valido"]),
            "motivo": p.get("motivo"),
        }
        for p in periodos_pendentes(a, EQ)
    ]


def _investigacao(inv: dict) -> dict:
    d = inv["dados"]
    return {
        "chave": inv["chave_grupo"],
        "titulo": inv["titulo"],
        "estado": inv["estado"],
        "desvio": d.get("desvio"),
        "proxima_verificacao": d.get("proxima_verificacao"),
        "hipoteses": [
            {
                "titulo": h["titulo"],
                "evidencia": h["evidencia"],
                "impacto_brl": h.get("impacto_brl"),
                "verificacao": h["verificacao"],
            }
            for h in d.get("hipoteses", [])
        ],
        "limitacoes": d.get("limitacoes", []),
    }


def _avaliacao(r: dict) -> dict:
    """Só o que a tela mostra da avaliação, mais as datas para as regras da página."""
    dif = r.get("diferenca_observada")
    return {
        "resultado": r["resultado"],
        "frase": r["frase"],
        "dif": None
        if not dif
        else {
            "periodo": periodo(dif["periodo_depois"]),
            "antes": num(dif["consumo_antes_t_t"], 3),
            "depois": num(dif["consumo_depois_t_t"], 3),
            "desvio": brl(dif["desvio_brl"]),
            "fim": dif["periodo_depois"]["fim"],
        },
        "melhoria": r.get("melhoria_associada"),
        "economia": r.get("economia_verificada"),
        "motivos": (r.get("comparabilidade") or {}).get("motivos", []),
        "excluidos": r.get("periodos_excluidos", []),
        "faltam": r.get("faltam", []),
        "ref_fim": (r.get("referencia") or {}).get("fim"),
    }


def _copia(origem: Path) -> Path:
    destino = Path(tempfile.mkdtemp()) / "r"
    shutil.copytree(origem, destino)
    return destino


def dados_acompanhamento() -> dict:
    raiz = Path(tempfile.mkdtemp()) / "r"
    repo = Repositorio(raiz)
    planta = repo.criar_planta("Demonstração · caldeira sintética", classe="sintetico")
    pid = planta["id"]
    a = repo.armazem(pid)
    try:
        a.criar_equipamento(
            EQ, "Caldeira de demonstração", EQ, config={"altitude_m": 1000.0}, autor=AUTOR
        )
        arquivos = {p.name: p.read_bytes() for p in sorted(DEMO.glob("*.csv"))}
        previa = a.previa(EQ, arquivos)
        contagem = [
            [TABELAS[t].titulo if t in TABELAS else t, *(c.get(k, 0) for k in SITUACOES)]
            for t, c in previa.contagem().items()
        ]
        resumo = a.confirmar(previa, autor=AUTOR)
        s = periodos_entre_estoques(a.pacote(EQ))
        criar_referencia(
            a, EQ, s[0][0], s[3][1], "inicial",
            "Agosto: quatro semanas de operação normal (demonstração)", AUTOR,
        )  # fmt: skip
        produzir_fechamento(a, EQ, AUTOR)
        cfg = a.equipamento(EQ)["config"]
        cob = a.cobertura(EQ)
        ref = referencia_vigente(a, EQ)
        eventos = [
            {
                "quando": e["quando"],
                "o_que": f"{e['entidade']} {e['entidade_id']}",
                "acao": e["tipo"],
            }
            for e in reversed(a.eventos(EQ, limite=500))
        ]
        pendentes = [_pendentes(a)]
        while pendentes[-1]:
            produzir_fechamento(a, EQ, AUTOR)
            pendentes.append(_pendentes(a))
        lista = [_fechamento(f) for f in fechamentos(a, EQ)]
        # linha do tempo (D103): valores de cada fechamento e a leitura da série até ele
        for item, p in zip(lista, linha_do_tempo(a, EQ)["periodos"], strict=True):
            item["lt"] = {k: p[k] for k in CAMPOS_LT}
            item["padrao"] = linha_do_tempo(a, EQ, ate_fechamento=item["id"])["padrao"]
    finally:
        a.fechar()

    abrir = []
    for f in lista:
        b = Repositorio(_copia(raiz)).armazem(pid)
        try:
            abrir.append({"ok": True, **_investigacao(abrir_do_fechamento(b, f["id"], AUTOR))})
        except Exception as e:  # noqa: BLE001 — a recusa do motor vira a mensagem da tela
            abrir.append({"ok": False, "erro": str(e)})
        finally:
            b.fechar()

    # avaliação de uma ação em cada data (o resultado depende só da data: dados e referência
    # são os mesmos); um dia depois do fim dos dados mostra o caso sem período posterior
    avaliacoes = {}
    dias = pd.date_range("2026-08-03", "2026-09-29", freq="D")
    for dia in dias:
        b = Repositorio(_copia(raiz)).armazem(pid)
        try:
            it = registrar_intervencao(
                b, EQ, dia.tz_localize(FUSO), "limpeza", "Ação de teste", AUTOR
            )
            avaliacoes[f"{dia:%Y-%m-%d}"] = _avaliacao(
                avaliar_intervencao(b, it["id"], AUTOR)["resultado"]
            )
        finally:
            b.fechar()
    print(f"  acompanhamento: {len(lista)} fechamentos, {len(avaliacoes)} datas de ação")
    diario = cob["tabelas"].get("diario") or {}
    return {
        "planta": planta["nome"],
        "equipamento": {"id": EQ, "nome": "Caldeira de demonstração", "caldeira_id": EQ},
        "config": [
            ["Altitude do local", f"{num(cfg['altitude_m'], 0)} m"],
            [
                "Avisar desatualização depois de",
                f"{cfg['dias_para_desatualizado']} dias sem dados",
            ],
            ["Política de custo do combustível consumido", POLITICAS_CUSTO[cfg["politica_custo"]]],
            [
                "Períodos completos exigidos depois de uma ação para verificar economia",
                str(cfg["periodos_minimos_pos_intervencao"]),
            ],
        ],
        "limite_dias": cfg["dias_para_desatualizado"],
        "diario": [diario.get("inicio"), diario.get("fim")],
        "importacao": {
            "colunas": ["Tabela", *SITUACOES.values()],
            "contagem": contagem,
            "novas": resumo["novas"],
            "corrigidas": resumo.get("corrigidas"),
            "conflitos": resumo["conflitos_pendentes"],
        },
        "referencia": {
            "versao": ref["versao"],
            "periodo": periodo(ref),
            "tipo": TIPOS_REFERENCIA[ref["tipo"]],
            "consumo": num(ref["dados"].get("consumo_t_t"), 3),
            "motivo": ref["motivo"],
        },
        "eventos": eventos,
        "pendentes": pendentes,
        "fechamentos": lista,
        "abrir": abrir,
        "avaliacoes": avaliacoes,
        "estados": ESTADOS,
        "transicoes": {k: sorted(v) for k, v in TRANSICOES.items()},
        "resultados": RESULTADOS,
        "tipos": TIPOS_INTERVENCAO,
        "categorias": CATEGORIAS,
        "criterios": CRITERIOS,
        "rotulos_evidencia": {k: v for k, v in ROTULOS.items()},
    }


def _dh(x) -> str:
    return "—" if not x else f"{pd.Timestamp(x).tz_convert(FUSO):%d/%m %H:%M}"


def dados_mensais() -> dict:
    """Painel novo e fechamento do mês (D111–D114) na mesma planta de demonstração.

    Calculado pelo motor numa planta à parte: meses e cobertura, prévia de setembro (sem
    gravar), fechamento aprovado do mês, os totais do mês, a frase "por que a conta mudou"
    do último trecho, as condições comparadas e o dia a dia dos últimos 30 dias.
    """
    from euler.dia_a_dia import dia_a_dia
    from euler.mensal import fechar_mes, meses, previa_do_mes, resumo_do_mes

    outubro = pd.Timestamp("2026-10-07T12:00:00-03:00")
    repo = Repositorio(Path(tempfile.mkdtemp()) / "r")
    planta = repo.criar_planta("Demonstração · caldeira sintética", classe="sintetico")
    a = repo.armazem(planta["id"])
    try:
        a.criar_equipamento(
            EQ, "Caldeira de demonstração", EQ, config={"altitude_m": 1000.0}, autor=AUTOR
        )
        a.confirmar(
            a.previa(EQ, {p.name: p.read_bytes() for p in sorted(DEMO.glob("*.csv"))}), autor=AUTOR
        )
        s = periodos_entre_estoques(a.pacote(EQ))
        criar_referencia(a, EQ, s[0][0], s[3][1], "inicial", "Agosto (demonstração)", AUTOR)
        lista = []
        for m in meses(a, EQ, outubro):
            lista.append(
                {
                    "mes": m["mes"],
                    "rotulo": m["rotulo"],
                    "estado": m["estado"],
                    "estado_rotulo": m["estado_rotulo"],
                    "frase": m["frase"],
                    "cobertura": m["cobertura"]["frases"],
                    "trechos": [
                        {
                            "periodo": f"{_dh(t['inicio'])} a {_dh(t['fim'])}",
                            "valido": t["valido"],
                            "motivo": t["motivo"],
                            "periodos": t["periodos"],
                        }
                        for t in m["trechos"]
                    ],
                }
            )
        prev = previa_do_mes(a, EQ, "2026-09", outubro)
        previas = [
            {
                "periodo": f"{_dh(p['inicio'])} a {_dh(p['fim'])}",
                "frase": p["frase"] if p["valido"] else p["motivo"],
                "situacao": p["situacao"],
                "consumido": brl((p.get("conta") or {}).get("consumido", {}).get("custo_brl"))
                if (p.get("conta") or {}).get("disponivel")
                else "—",
                "diferenca": brl((p.get("conta") or {}).get("desvio", {}).get("custo_brl"))
                if (p.get("conta") or {}).get("disponivel")
                else "—",
            }
            for p in prev["previas"]
        ]
        fs = fechar_mes(a, EQ, "2026-09", AUTOR, outubro)
        resumo = resumo_do_mes(a, EQ, "2026-09")
        ultimo = fs[-1]["resultado"]
        n = ultimo["nucleo"]
        dias = {
            k: (pd.Timestamp(p["fim"]) - pd.Timestamp(p["inicio"])).total_seconds() / 86400
            for k, p in (("referencia", n["referencia"]), ("comparacao", n["periodo"]))
        }
        q = conclusao_financeira(n["explicacao_conta"], n["oportunidades"], dias)
        cond = ultimo.get("condicoes") or {}
        dd = dia_a_dia(a.pacote(EQ), referencia_vigente(a, EQ))
    finally:
        a.fechar()
    return {
        "meses": lista,
        "previas": previas,
        "resumo": {
            "rotulo": resumo["rotulo"],
            "consumido": brl(resumo["consumido_brl"]),
            "esperado": brl(resumo["esperado_brl"]),
            "diferenca": brl(resumo["diferenca_brl"]),
            "combustivel_t": num(resumo["combustivel_t"], 0)
            if resumo["combustivel_t"] is not None
            else None,
            "trechos": [
                {
                    "periodo": f"{data(t['inicio'])} a {data(t['fim'])}",
                    "situacao": t["situacao"],
                    "frase": t["frase"] or t["motivo"],
                }
                for t in resumo["trechos"]
            ],
        },
        "ultimo_trecho": periodo(n["periodo"]),
        "ajustado_por": (q.get("esperado") or {}).get("ajustado_por", []),
        "ponte": (q.get("ponte") or {}).get("resposta"),
        "condicoes": {"frases": cond.get("frases", []), "nao_ajustado": cond.get("nao_ajustado")},
        "ainda_no_desvio": (q.get("evitavel") or {}).get("ainda_no_desvio", []),
        "dia": {
            "serie": [
                {
                    "dia": f"{pd.Timestamp(r['dia']):%d/%m}",
                    **{
                        k: r.get(k) for k in ("vazao_t_h", "t_gases_c", "o2_seco_pct", "recebido_t")
                    },
                }
                for r in dd["serie"]
            ],
            "faixas": dd["faixas"],
            "quadros": dd["quadros"],
            "ultimo_dia": f"{pd.Timestamp(dd['ultimo_dia']):%d/%m/%Y}"
            if dd["ultimo_dia"]
            else None,
            "frases": dd["frases"],
        },
    }
