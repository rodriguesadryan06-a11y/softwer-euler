"""Linha do tempo financeira dos fechamentos (D103, proposta).

Reúne, período a período, o que cada fechamento gravado já calculou: consumo, vapor,
custo, esperado, desvio com faixa, duração, qualidade da conta e as ações registradas
no período. Ajuda a responder "o problema apareceu agora, está se repetindo ou melhorou
depois da ação?" sem criar número novo:

- comparações entre períodos usam valores por tonelada de vapor e por dia, porque
  produção e duração mudam de um fechamento para outro;
- um desvio só conta como "acima" quando o fechamento o estabeleceu (faixa fora de zero);
- se a versão da referência muda entre fechamentos, os desvios não são diretamente
  comparáveis e a leitura avisa;
- "melhorou depois da ação" só vem da avaliação registrada da ação (D94), nunca da simples
  queda entre dois fechamentos.
"""

import pandas as pd

from euler.acompanhamento import intervencoes, ultima_avaliacao
from euler.armazem import Armazem
from euler.conta import FRASE_INCONCLUSIVO, motivo_inconclusivo
from euler.fechamento import fechamento, fechamentos_vigentes


def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t if t.tzinfo else t.tz_localize("UTC")


def _qualidade(f: dict) -> tuple[str, str]:
    """Rótulo curto e motivo da qualidade da conta de um fechamento."""
    n = f["resultado"]["nucleo"]
    c = n["explicacao_conta"]
    cp = n["conta_do_periodo"]
    if not c.get("disponivel"):
        return "conta indisponível", c.get("motivo") or "Conta indisponível."
    if (c.get("consumido") or {}).get("preco_brl_t") is None:
        return (
            "sem preço",
            "Sem preço do combustível no período: a conta fica em toneladas, sem valor em reais.",
        )
    if cp.get("lotes_sem_valor"):
        return "preço incompleto", f"{cp['lotes_sem_valor']} recebimento(s) sem preço."
    if c["desvio"]["estado"] == "sem_faixa":
        return "sem faixa", "Falta a incerteza de algum instrumento para a faixa do desvio."
    return "completa", "Conta com preço e faixa de incerteza."


def linha_do_tempo(a: Armazem, equip_id: str, ate_fechamento: int | None = None) -> dict:
    """Fechamentos do equipamento em ordem, com valores comparáveis e a leitura da série.

    Entrada: armazém aberto e equipamento. Saída: `periodos` (um por fechamento, com dias,
    vapor_t, combustivel_t, custo_brl, esperado_brl, desvio_brl, faixa_brl, estado,
    consumo_t_t, custo_por_t_vapor_brl, custo_por_dia_brl, desvio_por_t_vapor_brl,
    faixa_por_t_vapor_brl, referencia_versao, qualidade e acoes do período) e `leitura`
    (frases sobre o padrão da série, com as ressalvas; `padrao` é a mesma leitura sem as
    linhas das ações). Com `ate_fechamento`, a série para nesse fechamento (a leitura fica
    como era na data dele, sem olhar para frente).
    Valores ausentes ficam None; nada é preenchido.
    """
    fs = fechamentos_vigentes(a, equip_id)
    if ate_fechamento is not None:
        alvo = fechamento(a, ate_fechamento)
        fs = sorted(
            [f for f in fs if f["id"] != alvo["id"] and _ts(f["fim"]) <= _ts(alvo["fim"])] + [alvo],
            key=lambda f: (_ts(f["fim"]), f["id"]),
        )
    acoes = intervencoes(a, equip_id)
    periodos = []
    for f in fs:
        n = f["resultado"]["nucleo"]
        c = n["explicacao_conta"]
        e = c.get("entradas") or {}
        ini, fim = _ts(n["periodo"]["inicio"]), _ts(n["periodo"]["fim"])
        dias = (fim - ini).total_seconds() / 86400
        disp = bool(c.get("disponivel"))
        custo = c["consumido"]["custo_brl"] if disp else None
        vapor = e.get("vapor_t")
        desvio = c["desvio"]["custo_brl"] if disp else None
        faixa = c["desvio"]["faixa_brl"] if disp else None
        rotulo, motivo = _qualidade(f)
        no_periodo = [x for x in acoes if ini < _ts(x["data"]) <= fim]
        periodos.append(
            {
                "fechamento_id": f["id"],
                "inicio": ini.isoformat(),
                "fim": fim.isoformat(),
                "dias": dias,
                "vapor_t": vapor,
                "combustivel_t": c["consumido"]["combustivel_t"] if disp else None,
                "consumo_t_t": n["consumo_especifico"].get("periodo_t_t"),
                "custo_brl": custo,
                "esperado_brl": c["esperado"]["custo_brl"] if disp else None,
                "desvio_brl": desvio,
                "faixa_brl": faixa,
                "estado": c["desvio"]["estado"] if disp else None,
                "motivo_inconclusivo": motivo_inconclusivo(c["desvio"]) if disp else None,
                "custo_por_t_vapor_brl": custo / vapor if custo is not None and vapor else None,
                "custo_por_dia_brl": custo / dias if custo is not None and dias > 0 else None,
                "desvio_por_t_vapor_brl": desvio / vapor if desvio is not None and vapor else None,
                "faixa_por_t_vapor_brl": [x / vapor for x in faixa] if faixa and vapor else None,
                "referencia_versao": n["referencia"]["versao"],
                "qualidade": rotulo,
                "qualidade_motivo": motivo,
                "acoes": [
                    {
                        "id": x["id"],
                        "data": x["data"],
                        "descricao": x["descricao"],
                        "avaliacao": (ultima_avaliacao(a, x["id"]) or {})
                        .get("resultado", {})
                        .get("frase"),
                    }
                    for x in no_periodo
                ],
            }
        )
    return {
        "periodos": periodos,
        "leitura": _leitura(periodos),
        "padrao": _leitura(periodos, com_acoes=False),
    }


def _leitura(ps: list[dict], com_acoes: bool = True) -> list[str]:
    if not ps:
        return ["Ainda não há fechamento: a linha do tempo começa no primeiro período fechado."]
    frases = []
    acima = [p["estado"] == "acima" for p in ps]
    seguidos = 0
    for x in reversed(acima):
        if not x:
            break
        seguidos += 1
    if seguidos >= 2:
        frases.append(
            f"Está se repetindo: desvio acima do esperado, além da incerteza, nos últimos "
            f"{seguidos} fechamentos."
        )
    elif seguidos == 1 and len(ps) > 1:
        frases.append(
            "Apareceu agora: o último fechamento tem desvio acima do esperado, além da "
            "incerteza; o anterior não tinha."
        )
    elif seguidos == 1:
        frases.append("Primeiro fechamento, com desvio acima do esperado além da incerteza.")
    else:
        ultimo = ps[-1]
        frases.append(
            {
                None: "O último fechamento não tem conta disponível ("
                + ultimo["qualidade_motivo"].rstrip(".")
                + "): não dá para dizer se o desvio continua.",
                "sem_faixa": "O último fechamento não tem faixa de incerteza: o desvio não "
                "pode ser classificado.",
                "abaixo": "O último fechamento ficou abaixo do esperado, além da incerteza. "
                "Isso não é economia verificada.",
                "nao_estabelecido": "Nenhum desvio estabelecido no último fechamento: "
                + FRASE_INCONCLUSIVO[ultimo.get("motivo_inconclusivo") or "faixa_inclui_zero"]
                + ".",
            }[ultimo["estado"]]
        )
    for p in ps if com_acoes else ():
        for x in p["acoes"]:
            frases.append(
                f"Ação em {pd.Timestamp(x['data']).strftime('%d/%m/%Y')} ({x['descricao']}): "
                + (x["avaliacao"] or "ainda não avaliada; a melhora só é afirmada pela avaliação.")
            )
    if len({p["referencia_versao"] for p in ps}) > 1:
        frases.append(
            "A referência mudou de versão ao longo da série: desvios de versões diferentes "
            "não são diretamente comparáveis."
        )
    dias = [p["dias"] for p in ps]
    if max(dias) > 1.5 * min(dias):
        frases.append(
            "Os períodos têm durações diferentes: compare custo por tonelada de vapor ou por "
            "dia, não o total."
        )
    incompletos = [p for p in ps if p["qualidade"] != "completa"]
    if incompletos:
        frases.append(
            f"{len(incompletos)} fechamento(s) com conta incompleta "
            f"({', '.join(sorted({p['qualidade'] for p in incompletos}))}): leia esses "
            "períodos com cautela."
        )
    return frases
