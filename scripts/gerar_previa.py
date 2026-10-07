"""Gera a prévia interativa do app EULER (uma página HTML que abre sem o Streamlit).

A página mostra as telas com o visual do app e os resultados **calculados pelo motor** para os
dois atos do caso de demonstração sintético (D62): nada é recalculado nem inventado no
navegador. As telas de "Acompanhar a planta" usam a planta de demonstração calculada em
scripts/previa_acompanhamento.py; o que o visitante registra fica só no navegador dele.
Telas novas da página: scripts/previa_telas_novas.js. A investigação é calculada para as combinações de períodos que a prévia oferece
(referência começando em 03/08 e comparação depois dela, mais o antes × depois da limpeza).

Uso:
    python scripts/gerar_previa.py                 # demo/previa/index.html
    python scripts/gerar_previa.py saida.html

A página é o conteúdo do corpo (sem <html>/<head>), pronta para publicar como Artifact;
para abrir direto no navegador, ela também funciona assim.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))
sys.path.insert(0, str(RAIZ / "scripts"))

import pandas as pd
from formatacao import (
    COLUNAS_RESUMO,
    COR_SAUDE,
    SELO_SAUDE,
    SERIES,
    SITUACAO_PERIODO,
    SITUACAO_SAUDE,
    STATUS,
    diferenca,
    linhas_por_periodo,
    partes_do_selo,
    texto_consumo,
    valor_formatado,
    variacao_referencia,
)
from graficos import CORES
from previa_acompanhamento import dados_acompanhamento, dados_mensais
from previa_publicos import dados_publicos

from euler.capacidades import avaliar
from euler.combustivel import (
    extrato_por_fornecedor,
    extrato_semanal,
    frase_tonelada_vs_energia,
)
from euler.conta import conclusao_financeira
from euler.formato import num, pct, plural
from euler.investigacao import SUFIXO_CADASTRAR, investigar
from euler.io import importar_pasta
from euler.io.esquemas import TABELAS
from euler.periodos import periodos_entre_estoques
from euler.relatorio import gerar_html
from euler.saude import avaliar_saude
from euler.textos import (
    AVISO_PROTOTIPO,
    ESTAGIOS_MODELO,
    FRASE_PRODUTO,
    PERGUNTA_CENTRAL,
    RODAPE_SEGURANCA,
)
from euler.vapor import p_atm_por_altitude_bar

MODELO = RAIZ / "scripts" / "previa_modelo.html"
ALTITUDE_DEMO_M = 1000.0
# os mesmos dois atos da tela inicial do app (app/estado.py, CASOS_DEMO)
ATOS = {
    "1": ("caso_demo_completo", "caso de demonstração · ato 1, completo (caldeira sintética de 20 t/h, 8 semanas)"),
    "2": ("caso_demo", "caso de demonstração · ato 2, dados insuficientes (a mesma caldeira sintética)"),
}  # fmt: skip
REF_FIM_MAX = 3  # a referência termina entre a semana 1 e a 4


def _versao() -> str:
    saida = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True,
        check=False,
    )  # fmt: skip
    return saida.stdout.strip() or "desconhecida"


def _importacao(pacote) -> dict:
    avisos = pacote.tabela_avisos()
    contagem = avisos["Gravidade"].value_counts()
    tabelas = []
    for nome, tabela in TABELAS.items():
        imp = pacote.importacoes.get(nome)
        if imp is None:
            situacao, n = "não enviada", "—"
        elif imp.bloqueada:
            situacao, n = "bloqueada (ver erros)", str(len(imp.original))
        else:
            situacao, n = "importada", str(len(imp.dados))
        tabelas.append([tabela.titulo, n, situacao])
    linhas = avisos.astype({"Linha": "string"}).fillna({"Linha": "—"})
    return {
        "contagem": {g: int(contagem.get(g, 0)) for g in ("Erro", "Atenção", "Informação")},
        "n_tabelas": len(pacote.importacoes),
        "tabelas": tabelas,
        "arquivos": [
            [t.titulo, t.arquivo, ", ".join(c.nome for c in t.colunas if c.obrigatoria)]
            for t in TABELAS.values()
        ],
        "avisos": [[r.Gravidade, r.Tabela, str(r.Linha), r.Aviso] for r in linhas.itertuples()],
    }


def _capacidades(pacote) -> list[dict]:
    return [
        {
            "nome": c.nome,
            "pergunta": c.pergunta,
            "situacao": c.situacao,
            "motivos": list(c.motivos),
            "o_que_fazer": list(c.o_que_fazer),
            "referencia": c.referencia,
        }
        for c in avaliar(pacote)
    ]


def _series(pacote) -> dict:
    diario = pacote.dados("diario")
    saida = {}
    for coluna, (botao, titulo, unidade, formato) in SERIES.items():
        if coluna not in diario or not diario[coluna].notna().any():
            continue
        d = diario.dropna(subset=[coluna, "instante_observado"])
        d = d[d["regime"].fillna("estavel") != "parada"]
        dias = d.groupby(d["instante_observado"].dt.tz_localize(None).dt.normalize())[coluna].mean()
        saida[coluna] = {
            "botao": botao,
            "titulo": f"{titulo} ({unidade}, média do dia)",
            "unidade": unidade,
            "casas": int(formato[1]),
            "pontos": [[f"{dia:%Y-%m-%d}", round(float(v), 3)] for dia, v in dias.items()],
        }
    return saida


def _extrato(pacote) -> dict:
    combustivel, amostras = pacote.dados("combustivel"), pacote.dados("amostras")
    extrato = extrato_por_fornecedor(combustivel, amostras)
    lotes, forn = extrato.lotes, extrato.fornecedores
    determinados = lotes[lotes["situacao"] == "determinada"]
    com_custo = determinados.dropna(subset=["brl_gj"])
    fornecedores = sorted(combustivel["fornecedor_id"].dropna().unique())
    semanal = extrato_semanal(lotes)
    alertas = extrato.alertas_umidade
    resumo_alertas = []
    for f, g in alertas.groupby("fornecedor_id"):
        acima = int((g["alerta_direcao"] == "acima").sum())
        abaixo = len(g) - acima
        partes = [f"{acima} acima" if acima else "", f"{abaixo} abaixo" if abaixo else ""]
        resumo_alertas.append([f, f"{' e '.join(x for x in partes if x)} da faixa"])
    nao_det = extrato.lotes_nao_determinados
    datas = combustivel[combustivel["tipo"] == "recebimento"]["data"]
    return {
        "periodo": f"{datas.min():%d/%m/%Y} a {datas.max():%d/%m/%Y}",
        "frase": frase_tonelada_vs_energia(forn),
        "metricas": [
            [
                "Energia entregue (lotes determinados)",
                f"{num(determinados['energia_gj'].sum(), 0)} GJ",
            ],
            [
                "Custo médio da energia",
                f"R$ {num(com_custo['preco_brl'].sum() / com_custo['energia_gj'].sum())}/GJ",
            ],
            ["Lotes com energia determinada", f"{len(determinados)} de {len(lotes)}"],
        ],
        "cores": {f: CORES[i] for i, f in enumerate(fornecedores[: len(CORES)])},
        "barras": [
            {
                "f": r.fornecedor_id,
                "t": float(r.brl_t),
                "gj": float(r.brl_gj),
                "rt": f"R$ {num(r.brl_t)}/t",
                "rgj": f"R$ {num(r.brl_gj)}/GJ",
            }
            for r in forn.dropna(subset=["brl_t", "brl_gj"]).itertuples()
        ],
        "tabela": [
            [
                f"{r.posicao_energia}º" if pd.notna(r.posicao_energia) else "—",
                r.fornecedor_id,
                str(r.lotes),
                num(r.massa_t, 1),
                num(r.brl_t),
                pct(r.umidade_media),
                f"{pct(r.umidade_referencia)} → {pct(r.umidade_recente)}",
                num(r.energia_gj, 0),
                num(r.brl_gj),
                str(r.alertas_umidade),
            ]
            for r in forn.itertuples()
        ],
        "semanal": [
            [
                r.fornecedor_id,
                f"{r.semana:%Y-%m-%d}",
                round(float(r.umidade_media), 4),
                int(r.lotes),
            ]
            for r in semanal.itertuples()
        ],
        "n_alertas": len(alertas),
        "alertas": resumo_alertas,
        "nao_determinados": [
            [
                f"{r.data:%d/%m/%Y %H:%M}",
                r.fornecedor_id,
                r.lote_id,
                num(r.massa_kg / 1000 if pd.notna(r.massa_kg) else None, 1),
                r.motivo,
            ]
            for r in nao_det.itertuples()
        ],
    }


# ------------------------------------------------------------ Financeiro e Oportunidades
ESTADOS_DESVIO = {
    "acima": ("Acima do esperado", "alerta"),
    "abaixo": ("Abaixo do esperado", "total"),
    "nao_estabelecido": ("Não ficou bem estabelecido", ""),
    "sem_faixa": ("Faixa não determinada", ""),
}
NIVEL = {"INSUFICIENTE": "Insuficiente", "FRACA": "Fraca", "MODERADA": "Moderada", "FORTE": "Forte"}
COMPLEXIDADE = {"baixa": "Baixa", "media": "Média", "alta": "Alta", None: "Não classificada"}


def _rs(v) -> str:
    return "—" if v is None else ("−" if v < 0 else "") + f"R$ {num(abs(v), 0)}"


def _t(v) -> str:
    return "—" if v is None else ("−" if v < 0 else "") + f"{num(abs(v), 1)} t"


def _cab_periodos(j: dict) -> tuple[str, dict]:
    p = j["periodos"]
    datas = {k: (pd.Timestamp(v["inicio"]), pd.Timestamp(v["fim"])) for k, v in p.items()}
    dias = {k: (b - a).total_seconds() / 86400 for k, (a, b) in datas.items()}
    (ci, cf), (ri, rf) = datas["comparacao"], datas["referencia"]
    return (
        f"Período analisado: {ci:%d/%m/%Y} a {cf:%d/%m/%Y} · Referência: {ri:%d/%m/%Y} a {rf:%d/%m/%Y}",
        dias,
    )


def _financeiro(j: dict) -> dict:
    """O que a tela Financeiro mostra (app/paginas/financeiro.py), já em texto."""
    cab, dias = _cab_periodos(j)
    c = j.get("explicacao_conta") or {}
    if not c.get("disponivel"):
        return {"cab": cab, "motivo": c.get("motivo") or j["o_que_mudou"]["frase"]}
    d, e = c["desvio"], c["esperado"]
    rotulo, classe = ESTADOS_DESVIO[d["estado"]]
    faixa = d["faixa_brl"]
    v = c["variacao"]
    vj = j.get("valor_em_jogo")
    separacao = None
    if vj and v["disponivel"]:
        b = {x["id"]: x["custo_brl"] for x in v["componentes"]}
        separacao = (
            f"Na Investigação, o valor em jogo é {_rs(vj['valor_brl'])}: consumo acima da "
            "referência para o mesmo vapor. Aqui ele se divide em condição do vapor "
            f"({_rs(b['condicao_vapor'])}), qualidade do combustível ({_rs(b['qualidade'])}) e "
            f"desvio não explicado ({_rs(b['nao_explicado'])})."
        )
    motivo = c["evitavel"]["motivo"].removeprefix("Parcela evitável não apurada: ")
    premissas = [f"**{x['titulo']}:** {x['base']}" for x in v["componentes"]]
    premissas += list(e["nao_ajustado"])
    if d["cenarios_preco_brl"]:
        a, b = d["cenarios_preco_brl"]
        premissas.append(
            "Cenários de preço (menor e maior preço por tonelada dos lotes do período): "
            f"desvio de {_rs(a)} a {_rs(b)}."
        )
    if d["cenarios_qualidade_brl"]:
        a, b = d["cenarios_qualidade_brl"]
        premissas.append(
            "Cenários do pátio (combustível queimado = recebido ou o mais antigo do estoque): "
            f"desvio de {_rs(a)} a {_rs(b)}."
        )
    return {
        "cab": cab,
        "frase": d["frase"],
        # quadro único da conclusão (D101), o mesmo objeto da tela do app
        "quadro": conclusao_financeira(
            c, (j.get("oportunidades") or {}).get("oportunidades", ()), dias
        ),
        "cartoes": [
            [
                "Combustível consumido",
                _rs(c["consumido"]["custo_brl"]),
                f"{_t(c['consumido']['combustivel_t'])} queimadas no período, ao preço médio dos recebimentos.",
                "total",
            ],
            [
                "Esperado nas mesmas condições",
                _rs(e["custo_brl"]),
                f"{_t(e['combustivel_t'])}: consumo por tonelada de vapor da referência, ajustado por: "
                + ", ".join(e["ajustado_por"])
                + ".",
                "",
            ],
            [
                f"Desvio ainda não explicado · {rotulo.lower()}",
                _rs(d["custo_brl"]),
                f"{_t(d['combustivel_t'])} ({num(d['pct_do_esperado'], 1)}% do esperado)"
                + (
                    f". Faixa das medições: {_rs(faixa[0])} a {_rs(faixa[1])}."
                    if faixa
                    else ". Faixa não determinada."
                ),
                classe,
            ],
        ],
        "evitavel": motivo[:1].upper() + motivo[1:],
        "verificacao": c["evitavel"]["verificacao"],
        "porque": j["proxima_verificacao"]["porque"],
        "variacao": (
            f"Conta da referência ({num(dias['referencia'], 0)} dias) {_rs(v['custo_referencia_brl'])} "
            f"→ conta do período ({num(dias['comparacao'], 0)} dias) {_rs(v['custo_brl'])}: variação "
            f"de {_rs(v['variacao_brl'])}. As parcelas somam exatamente a variação."
            if v["disponivel"]
            else v["motivo"]
        ),
        "parcelas": [
            [
                x["titulo"],
                x["pergunta"],
                _t(x["combustivel_t"]) if x["separado"] or x["id"] == "preco" else "no desvio",
                _rs(x["custo_brl"])
                if x["custo_brl"] is not None
                else ("no desvio" if not x["separado"] else "—"),
            ]
            for x in v["componentes"]
        ],
        "separacao": separacao,
        "premissas": premissas,
        "notas": list(c["premissas"]),
        "incerteza": d.get("incerteza"),
    }


def _oportunidades(j: dict) -> dict:
    """O que a tela Oportunidades mostra (app/paginas/oportunidades.py), já em texto."""
    cab, _ = _cab_periodos(j)
    o = j.get("oportunidades")
    if o is None:
        return {
            "cab": cab,
            "vazio": "Refaça a investigação para ver as oportunidades desta versão.",
        }
    r = o["resumo"]
    assoc = r["associado"]

    def cartao(x):
        i, v = x["impacto"], x["verificacao"]
        legenda = []
        if i["combustivel_t"] is not None:
            legenda.append(f"{num(i['combustivel_t'], 1)} t de combustível no período")
        if i["faixa_brl"]:
            legenda.append(f"faixa {_rs(i['faixa_brl'][0])} a {_rs(i['faixa_brl'][1])}")
        detalhes = []
        if v["distingue"]:
            detalhes.append(f"Distingue: {v['distingue']}.")
        if v["etapa_seguinte"]:
            detalhes.append(v["etapa_seguinte"])
        detalhes.append(f"{x['natureza_rotulo']}. Intervenção: {x['intervencao']['motivo']}")
        return {
            "ordem": x["ordem"],
            "titulo": x["titulo"],
            "prioridade": [x["prioridade_rotulo"], "blue" if x["prioridade"] == "alta" else "gray"],
            "impacto": _rs(i["custo_brl"]),
            "custo": i["custo_brl"],
            "faixa": i["faixa_brl"],
            "legenda": legenda,
            "motivo": i.get("motivo") if i["custo_brl"] is None else None,
            "evidencia": [NIVEL[x["evidencia"]["nivel"]], x["evidencia"]["motivo"]],
            "complexidade": [
                COMPLEXIDADE[v["complexidade"]],
                ("Sem parada. " if v["exige_parada"] is False else "")
                + (f"{v['recurso'][:1].upper()}{v['recurso'][1:]}." if v["recurso"] else "")
                + f" Fonte: {v['origem_complexidade']}.",
            ],
            "acao": v["acao"],
            "detalhes": detalhes,
        }

    ativos = [x for x in o["oportunidades"] if x["prioridade"] in ("alta", "media")]
    outros = [x for x in o["oportunidades"] if x not in ativos]
    return {
        "cab": cab,
        "frase": r["frase"],
        "dias": assoc["dias"],
        "assoc": {
            "rotulo": f"Associado ao desvio no período ({num(assoc['dias'], 0)} dias)"
            if assoc["dias"]
            else "No período",
            "valor": _rs(assoc["custo_brl"]),
            "custo": assoc["custo_brl"],
            "legenda": (
                f"Incerteza ±{_rs(assoc['incerteza_brl'])} (k = 2). "
                if assoc["incerteza_brl"] is not None
                else ""
            )
            + assoc["base"],
        },
        "primeira": r["primeira"],
        "sobreposicao": list(o["sobreposicao"]),
        "ativos": [cartao(x) for x in ativos],
        "outros": [[x["titulo"], x["prioridade_rotulo"], " ".join(x["porque"])] for x in outros],
        "intervencao": o["intervencao"]["motivo"],
        "cadeia": " → ".join(("✓ " if c["disponivel"] else "○ ") + c["etapa"] for c in o["cadeia"]),
        "objetivos": list(o["regras"]["objetivos"]),
        "propostos": list(o["regras"]["propostos"]),
    }


def _compras(pacote) -> dict | None:
    """Compras registradas (fim da tela Financeiro): todos os recebimentos carregados."""
    from financeiro import nao_negativo

    combustivel = pacote.dados("combustivel")
    receb = combustivel[combustivel["tipo"] == "recebimento"].copy()
    if receb.empty:
        return None
    receb["valor_valido"] = receb["preco_brl"].map(nao_negativo)
    validos = receb.dropna(subset=["valor_valido"])
    grupos = (
        validos.assign(fornecedor=validos["fornecedor_id"].fillna("Sem identificação"))
        .groupby("fornecedor")["valor_valido"]
        .sum()
        .sort_values(ascending=False)
    )
    return {
        "periodo": f"{receb['data'].min():%d/%m/%Y} a {receb['data'].max():%d/%m/%Y}",
        "rotulo": "Valor dos recebimentos"
        if len(validos) == len(receb)
        else "Valor parcial dos recebimentos",
        "total": f"R$ {num(float(validos['valor_valido'].sum()), 2)}"
        if len(validos)
        else "Não calculado",
        "contagem": f"{len(validos)} de {len(receb)} recebimentos com preço.",
        "grupos": [[f, float(v), f"R$ {num(float(v), 0)}"] for f, v in grupos.items()],
    }


def _hipotese(h: dict) -> dict:
    rotulo, cor, _ = STATUS[h["status"]]
    efeito = h["efeito"]["consumo_pct"]
    return {
        "status": h["status"],
        "rotulo": rotulo,
        "cor": cor,
        "titulo": h["titulo"],
        "porque": h["porque"],
        "efeito": (
            f"Efeito estimado no consumo: {'+' if efeito >= 0 else ''}{num(efeito, 1)}%"
            if efeito is not None and h["status"] in ("sustentada", "possivel")
            else ""
        ),
        "verificacao": h["verificacao"],
    }


def _investigacao(j: dict) -> dict:
    """O que a tela Investigação mostra para uma comparação (mesmas regras da tela)."""
    om = j["o_que_mudou"]
    consumo = om.get("consumo_especifico")
    if consumo and consumo["variacao"] is not None and consumo["referencia"]:
        variacao = 100 * consumo["variacao"] / consumo["referencia"]
        kpi_consumo = {
            "valor": f"{num(consumo['comparacao'], 3)} t/t",
            "delta": f"{'+' if variacao >= 0 else ''}{num(variacao, 1)}% sobre "
            f"{num(consumo['referencia'], 3)} t/t",
            "sobe": variacao >= 0,
            "selo": partes_do_selo(consumo),
        }
    else:
        kpi_consumo = None
    valor = j["valor_em_jogo"]
    if valor:
        incerteza = (
            f"Incerteza: ± R$ {num(valor['incerteza_brl'], 0)}. "
            if valor["incerteza_brl"] is not None
            else ""
        )
        kpi_valor = {
            "valor": f"R$ {num(valor['valor_brl'], 0)}",
            "legenda": incerteza + valor["base"],
        }
    else:
        kpi_valor = {"valor": None, "legenda": j["valor_em_jogo_motivo"]}
    hips = j["hipoteses"]
    contagem = {s: sum(h["status"] == s for h in hips) for s in STATUS}
    partes = [
        plural(contagem["possivel"] + contagem["nao_avaliavel"], "em aberto", "em aberto"),
        plural(contagem["descartada"], "descartada", "descartadas"),
    ]
    if contagem["oposta"]:
        partes.append(plural(contagem["oposta"], "no sentido contrário", "no sentido contrário"))
    indicadores = [
        {
            "nome": c["nome"][0].upper() + c["nome"][1:],
            "ref": valor_formatado(c["referencia"], c["unidade"]),
            "comp": valor_formatado(c["comparacao"], c["unidade"]),
            "dif": diferenca(c),
            "selo": partes_do_selo(c),
        }
        for c in om["indicadores"]
        if not (c["referencia"] is None and c["comparacao"] is None)
    ]
    fechamento = om.get("fechamento") or {}
    falta = j["o_que_falta"]
    return {
        "rotulo_ref": j["periodos"]["referencia"]["rotulo"],
        "rotulo_comp": j["periodos"]["comparacao"]["rotulo"],
        "conclusao": j["conclusao"],
        "proxima": j["proxima_verificacao"],
        "kpi_consumo": kpi_consumo,
        "kpi_valor": kpi_valor,
        "kpi_expl": {
            "n": contagem["sustentada"],
            "legenda": " · ".join(partes) + ". Compatível não é causa comprovada.",
        },
        "frase": om["frase"],
        "custo": om["custo_vapor"]["frase"] if om["custo_vapor"] else None,
        "indicadores": indicadores,
        "sustentadas": [_hipotese(h) for h in hips if h["status"] == "sustentada"],
        "opostas": [_hipotese(h) for h in hips if h["status"] == "oposta"],
        "abertas": [_hipotese(h) for h in hips if h["status"] in ("possivel", "nao_avaliavel")],
        "descartadas": [_hipotese(h) for h in hips if h["status"] == "descartada"],
        "fechamento": [x for x in (fechamento.get("frase"), fechamento.get("frase_com_condicionais")) if x],
        "falta_cadastrar": [f.removesuffix(SUFIXO_CADASTRAR) for f in falta if f.endswith(SUFIXO_CADASTRAR)],
        "falta_outros": [f for f in falta if not f.endswith(SUFIXO_CADASTRAR)],
        "resumo": j["resumo"]["frases"],
        "independencia": j["independencia"]["nota"],
        "relatorio": gerar_html(j),
        "fin": _financeiro(j),
        "op": _oportunidades(j),
    }  # fmt: skip


def _saude(pacote) -> dict:
    """O que a tela Saúde da caldeira mostra (mesmas regras e textos da tela, D65)."""
    s = avaliar_saude(pacote)
    cor, rotulo = SELO_SAUDE[s.selo]
    kpi_mud = None
    if s.mudanca is not None and s.comparacao_mudanca is not None:
        c = s.comparacao_mudanca
        v = 100 * c.delta / c.referencia
        kpi_mud = {
            "valor": f"{num(c.comparacao, 3)} t/t",
            "delta": f"{'+' if v >= 0 else '−'}{num(abs(v), 1)}%",
            "sobe": v >= 0,
        }
    return {
        "selo": [cor, rotulo],
        "sobe": kpi_mud["sobe"] if kpi_mud else None,
        "frase": s.frase,
        "ref": list(s.referencia) if s.referencia else None,
        "mudanca": list(s.mudanca) if s.mudanca else None,
        "kpi_ref": None
        if s.consumo_referencia is None
        else f"{num(s.consumo_referencia.valor, 3)} t/t",
        "kpi_mud": kpi_mud,
        "valor_ref": None if s.consumo_referencia is None else s.consumo_referencia.valor,
        "periodos": [
            {
                "valor": None if p.consumo is None else p.consumo.valor,
                "u": None if p.consumo is None else p.consumo.incerteza,
                "texto": texto_consumo(p),
                "variacao": variacao_referencia(p),
                "situacao": [COR_SAUDE.get(p.estado, "gray"), SITUACAO_SAUDE[p.estado]],
                "motivo": "" if p.consumo is not None else (p.motivo or ""),
            }
            for p in s.periodos
        ],
        "eventos": [
            {
                "iso": f"{e['instante']:%Y-%m-%dT%H:%M}",
                "quando": f"{e['instante']:%d/%m %H:%M}",
                "dia": f"{e['instante']:%d/%m}",
                "tipo": e["tipo"],
                "descricao": e["descricao"],
            }
            for e in s.eventos
        ],
    }


def _por_periodo(pacote) -> dict:
    linhas = linhas_por_periodo(pacote)
    detalhe = [c for c in linhas[0] if c not in ("Eficiência", "Situação")] if linhas else []
    return {
        "resumo": [[l[c] for c in COLUNAS_RESUMO] for l in linhas],
        "cores": SITUACAO_PERIODO,
        "colunas_resumo": list(COLUNAS_RESUMO),
        "colunas_detalhe": detalhe,
        "detalhe": [[l[c] for c in detalhe] for l in linhas],
    }


def _ato(pasta: str, rotulo: str) -> dict:
    """Tudo o que as telas mostram para um ato do caso de demonstração."""
    pacote = importar_pasta(
        RAIZ / "demo" / pasta, p_atm_bar=p_atm_por_altitude_bar(ALTITUDE_DEMO_M)
    )
    periodos = periodos_entre_estoques(pacote)
    n = len(periodos)
    # referência começando em 03/08 (todas as comparações depois dela) e, à parte, a
    # intervenção do demo: semanas antes da limpeza de 21/09 × a semana depois dela
    escolhas = [
        (0, r, a, b) for r in range(REF_FIM_MAX + 1) for a in range(r + 1, n) for b in range(a, n)
    ]
    escolhas += [(4, 5, 7, 7), (4, 4, 7, 7), (5, 5, 7, 7)]
    combos = {}
    for r0, r, a, b in escolhas:
        ref = (periodos[r0][0], periodos[r][1])
        comp = (periodos[a][0], periodos[b][1])
        combos[f"{r0}-{r}|{a}-{b}"] = _investigacao(investigar(pacote, ref, comp))
    print(f"  {pasta}: {len(combos)} comparações", flush=True)
    avisos = pacote.tabela_avisos()
    atencao = avisos[avisos["Gravidade"].isin(["Erro", "Atenção"])]
    return {
        "rotulo_dados": rotulo,
        "periodos": [
            {
                "ini": f"{a:%d/%m}",
                "fim": f"{b:%d/%m}",
                "ini_iso": f"{a:%Y-%m-%dT%H:%M}",
                "fim_iso": f"{b:%Y-%m-%dT%H:%M}",
                "dias": round((b - a).total_seconds() / 86400),
            }
            for a, b in periodos
        ],
        "importacao": _importacao(pacote),
        "qualidade": [f"{r.Tabela}: {r.Aviso}" for r in atencao.itertuples()],
        "capacidades": _capacidades(pacote),
        "por_periodo": _por_periodo(pacote),
        "saude": _saude(pacote),
        "series": _series(pacote),
        "extrato": _extrato(pacote),
        "compras": _compras(pacote),
        "combos": combos,
    }


def dados_da_previa() -> dict:
    return {
        "versao": _versao(),
        "textos": {
            "frase": FRASE_PRODUTO,
            "pergunta": PERGUNTA_CENTRAL,
            "aviso": AVISO_PROTOTIPO,
            "rodape": RODAPE_SEGURANCA,
            "estagios": [list(e) for e in ESTAGIOS_MODELO],
        },
        "atos": {ato: _ato(pasta, rotulo) for ato, (pasta, rotulo) in ATOS.items()},
        "acomp": dados_acompanhamento(),
        "mensal": dados_mensais(),
        "publicos": dados_publicos(),
        "padrao": [0, 3, 4, 5],
    }


def gerar(destino: Path) -> Path:
    dados = dados_da_previa()
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    texto = texto.replace("</", "<\\/")  # o JSON vai dentro de <script>
    telas = (RAIZ / "scripts" / "previa_telas_novas.js").read_text(encoding="utf-8")
    html = (
        MODELO.read_text(encoding="utf-8")
        .replace("/*TELAS_NOVAS*/", telas)
        .replace("/*DADOS*/{}", texto)
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino


if __name__ == "__main__":
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "demo" / "previa" / "index.html"
    print(gerar(saida))
