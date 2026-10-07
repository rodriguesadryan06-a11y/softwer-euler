"""Fechamento mensal (D111): mês escolhido, cobertura dos dados, prévia, aprovação e revisão.

O consumo só é conhecido entre duas medições de estoque (E9). Por isso o mês nunca é
"completado" pelo calendário:

- cada período entre medições de estoque pertence a um único mês, o mês em que termina
  (nada é contado duas vezes nem fica sem mês);
- o fechamento do mês cobre esses períodos inteiros; os dias depois da última medição
  do mês ficam para o mês seguinte, e a tela diz isso;
- períodos com vapor e combustível conhecidos e seguidos formam um trecho com uma conta;
  período sem vapor ou combustível conhecido vira uma lacuna registrada, com o motivo;
- um mês só é aprovado depois de terminar e depois dos meses anteriores (sem pular
  períodos); a prévia nunca é gravada;
- se os registros de um mês fechado mudarem depois, o mês pede revisão: a revisão grava
  uma nova versão de cada trecho afetado, com motivo; a versão antiga fica no histórico.

Os períodos dentro da referência não são fechados: são a base de comparação.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from euler.armazem import Armazem, ErroArmazem
from euler.condicoes import condicoes_comparadas
from euler.fechamento import (
    _nucleo,
    _ts,
    dados_mudaram,
    fechamentos_vigentes,
    frase_situacao,
    p_atm,
    produzir_fechamento,
    referencia_vigente,
    validade_periodos,
)
from euler.formato import num
from euler.periodos import periodos_entre_estoques

FUSO = "America/Sao_Paulo"
MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
ESTADOS_MES = {
    "referencia": "Base de comparação (referência)",
    "sem_periodo": "Sem período completo",
    "em_andamento": "Mês em andamento",
    "aguarda_anterior": "Aguarda o mês anterior",
    "pronto": "Pronto para fechar",
    "fechado": "Fechado",
    "revisar": "Dados mudaram: revisar",
}


def _limites(chave: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Início do mês e início do mês seguinte, no fuso da planta."""
    inicio = pd.Timestamp(f"{chave}-01").tz_localize(FUSO)
    return inicio, inicio + pd.offsets.MonthBegin(1)


def chave_do_mes(instante) -> str:
    """Mês ("AAAA-MM") ao qual pertence o período que termina em `instante`.

    Um período que termina exatamente à 0h do dia 1 pertence ao mês anterior.
    """
    t = _ts(instante).tz_convert(FUSO) - pd.Timedelta(microseconds=1)
    return f"{t.year:04d}-{t.month:02d}"


def rotulo_mes(chave: str) -> str:
    ano, mes = chave.split("-")
    return f"{MESES[int(mes) - 1]}/{ano}"


def _dias(inicio, fim) -> float:
    return max((_ts(fim) - _ts(inicio)).total_seconds() / 86400, 0.0)


def _fmt(t) -> str:
    return _ts(t).tz_convert(FUSO).strftime("%d/%m %H:%M")


def _cobre(f: dict, p: tuple) -> bool:
    return _ts(f["inicio"]) <= _ts(p[0]) and _ts(p[1]) <= _ts(f["fim"])


def _trechos(itens: list[dict]) -> list[list[dict]]:
    """Períodos válidos seguidos formam um trecho; cada período inválido fica sozinho."""
    trechos: list[list[dict]] = []
    for x in itens:
        anterior = trechos[-1] if trechos else None
        if (
            x["valido"]
            and anterior
            and anterior[-1]["valido"]
            and _ts(anterior[-1]["fim"]) == _ts(x["inicio"])
        ):
            anterior.append(x)
        else:
            trechos.append([x])
    return trechos


def _contexto(a: Armazem, equip_id: str) -> dict:
    """O que todos os meses compartilham (lido uma vez)."""
    pacote = a.pacote(equip_id, p_atm_bar=p_atm(a, equip_id))
    return {
        "pacote": pacote,
        "ref": referencia_vigente(a, equip_id),
        "vigentes": fechamentos_vigentes(a, equip_id),
        "todos": periodos_entre_estoques(pacote),
        "mudou": {},
    }


def plano_do_mes(a: Armazem, equip_id: str, chave: str, agora=None, _ctx=None) -> dict:
    """O que o fechamento do mês cobre, o que fica de fora e em que situação ele está.

    Saída: `mes`, `rotulo`, `estado` (ver ESTADOS_MES), `frase`, `janela` (início e fim dos
    períodos do mês, ou None), `periodos` (cada um com inicio, fim, valido, motivo e
    `situacao`: "referencia", "fechado" (com `fechamento_id`) ou "aberto"), `trechos`
    abertos a fechar, `lacunas` (períodos sem vapor ou combustível conhecidos),
    `cobertura` (dias do calendário, dias com conta, dias de outros meses incluídos e dias
    do mês que ficam para o mês seguinte, com as frases), `fechamentos` em vigor do mês e
    `a_revisar` (fechamentos do mês cujos registros mudaram depois de gravados).
    """
    agora = _ts(agora or datetime.now(UTC))
    ini_mes, fim_mes = _limites(chave)
    ctx = _ctx or _contexto(a, equip_id)
    pacote, ref, vigentes, todos = ctx["pacote"], ctx["ref"], ctx["vigentes"], ctx["todos"]
    do_mes = [p for p in todos if ini_mes < _ts(p[1]) <= fim_mes]
    itens = validade_periodos(pacote, do_mes)
    for x in itens:
        dono = next((f for f in vigentes if _cobre(f, (x["inicio"], x["fim"]))), None)
        if ref is not None and _ts(x["fim"]) <= _ts(ref["fim"]):
            x["situacao"] = "referencia"
        elif dono is not None:
            x["situacao"], x["fechamento_id"] = "fechado", dono["id"]
        else:
            x["situacao"] = "aberto"
    abertos = [x for x in itens if x["situacao"] == "aberto"]
    do_mes_fechados = {x["fechamento_id"] for x in itens if x["situacao"] == "fechado"}
    fech_mes = [f for f in vigentes if f["id"] in do_mes_fechados]
    for f in fech_mes:
        if f["id"] not in ctx["mudou"]:
            ctx["mudou"][f["id"]] = dados_mudaram(a, equip_id, f)
    a_revisar = [f for f in fech_mes if ctx["mudou"][f["id"]]]

    # cobertura: nada é completado pelo calendário
    dias_mes = _dias(ini_mes, fim_mes)
    janela = (itens[0]["inicio"], itens[-1]["fim"]) if itens else None
    com_conta = sum(
        _dias(max(_ts(x["inicio"]), ini_mes), min(_ts(x["fim"]), fim_mes))
        for x in itens
        if x["valido"] and x["situacao"] != "referencia"
    )
    frases = []
    antes = _dias(janela[0], ini_mes) if janela and _ts(janela[0]) < ini_mes else 0.0
    depois_ini = _ts(janela[1]) if janela else ini_mes
    depois = (
        _dias(depois_ini, min(fim_mes, max(agora, depois_ini)))
        if janela and depois_ini < fim_mes
        else 0.0
    )
    if antes:
        frases.append(
            f"Começa em {_fmt(janela[0])}, na medição de estoque anterior ao mês: "
            f"{num(antes, 1)} dia(s) do mês anterior entram aqui, porque o período só termina neste mês."
        )
    if depois:
        frases.append(
            f"De {_fmt(depois_ini)} em diante não há medição de estoque neste mês: esses "
            f"{num(depois, 1)} dia(s) entram no fechamento seguinte. A EULER não completa o "
            "consumo pelo calendário."
        )
    if not itens:
        frases.append(
            "Nenhum período entre medições de estoque termina neste mês: sem medição de "
            "estoque, o consumo do mês não é conhecido."
        )
    lacunas = [x for x in itens if not x["valido"] and x["situacao"] != "referencia"]
    for x in lacunas:
        frases.append(f"Lacuna de {_fmt(x['inicio'])} a {_fmt(x['fim'])}: {x['motivo']}")

    # estado
    anteriores_abertos = []
    if ref is not None:
        anteriores_abertos = [
            p
            for p in todos
            if _ts(p[1]) <= ini_mes
            and _ts(p[1]) > _ts(ref["fim"])
            and not any(_cobre(f, p) for f in vigentes)
        ]
    if itens and all(x["situacao"] == "referencia" for x in itens):
        estado = "referencia"
        frases = []
    elif not itens:
        estado = "em_andamento" if agora < fim_mes else "sem_periodo"
    elif a_revisar:
        estado = "revisar"
    elif not abertos:
        estado = "fechado"
    elif agora < fim_mes:
        estado = "em_andamento"
    elif anteriores_abertos:
        estado = "aguarda_anterior"
    elif ref is None:
        estado = "sem_periodo"
    else:
        estado = "pronto"
    frase = {
        "referencia": "Os períodos deste mês fazem parte da referência (base de comparação).",
        "sem_periodo": (
            "Defina a referência antes do primeiro fechamento."
            if itens and ref is None
            else "Sem período completo entre medições de estoque neste mês."
        ),
        "em_andamento": (
            "O mês ainda não terminou: a prévia pode ser vista, a aprovação fica para depois "
            "do fim do mês."
            if itens
            else "O mês ainda não terminou e nenhum período entre medições de estoque "
            "terminou nele."
        ),
        "aguarda_anterior": (
            "Há período anterior ainda sem fechamento: feche os meses na ordem, para nenhum "
            "período ficar de fora."
        ),
        "pronto": (
            f"{len(abertos)} período(s) completo(s) para fechar"
            + (
                f", em {len(_trechos(abertos))} trecho(s), "
                f"{sum(not x['valido'] for x in abertos)} deles sem conta (lacuna)."
                if any(not x["valido"] for x in abertos)
                else "."
            )
        ),
        "fechado": "Todos os períodos do mês estão fechados.",
        "revisar": (
            f"Os registros de {len(a_revisar)} fechamento(s) deste mês mudaram depois da "
            "aprovação: revise com o motivo."
        ),
    }[estado]
    return {
        "mes": chave,
        "rotulo": rotulo_mes(chave),
        "estado": estado,
        "estado_rotulo": ESTADOS_MES[estado],
        "frase": frase,
        "janela": None if janela is None else [_ts(j).isoformat() for j in janela],
        "periodos": [
            {**x, "inicio": _ts(x["inicio"]).isoformat(), "fim": _ts(x["fim"]).isoformat()}
            for x in itens
        ],
        "trechos": [
            {
                "inicio": _ts(t[0]["inicio"]).isoformat(),
                "fim": _ts(t[-1]["fim"]).isoformat(),
                "valido": t[0]["valido"],
                "motivo": t[0]["motivo"],
                "periodos": len(t),
            }
            for t in _trechos(abertos)
        ],
        "lacunas": [
            {
                "inicio": _ts(x["inicio"]).isoformat(),
                "fim": _ts(x["fim"]).isoformat(),
                "motivo": x["motivo"],
            }
            for x in lacunas
        ],
        "cobertura": {
            "dias_do_mes": dias_mes,
            "dias_com_conta": com_conta,
            "dias_de_outro_mes": antes,
            "dias_para_o_mes_seguinte": depois,
            "frases": frases,
        },
        "fechamentos": [f["id"] for f in fech_mes],
        "a_revisar": [f["id"] for f in a_revisar],
    }


def meses(a: Armazem, equip_id: str, agora=None) -> list[dict]:
    """Planos de todos os meses com período entre medições de estoque, do mais antigo ao
    mais novo, mais o mês corrente (para mostrar o que está em andamento)."""
    agora = _ts(agora or datetime.now(UTC))
    ctx = _contexto(a, equip_id)
    chaves = {chave_do_mes(p[1]) for p in ctx["todos"]}
    if chaves:
        chaves.add(chave_do_mes(agora))
    return [plano_do_mes(a, equip_id, c, agora, ctx) for c in sorted(chaves)]


def previa_do_mes(a: Armazem, equip_id: str, chave: str, agora=None) -> dict:
    """Prévia do mês sem gravar nada: a conta de cada trecho aberto, como o fechamento a
    faria agora. Lacunas aparecem com o motivo, sem conta."""
    plano = plano_do_mes(a, equip_id, chave, agora)
    ref = referencia_vigente(a, equip_id)
    if ref is None or not plano["trechos"]:
        return {**plano, "previas": []}
    revisao = a.revisao
    pacote = a.pacote(equip_id, revisao=revisao, p_atm_bar=p_atm(a, equip_id))
    politica = a.equipamento(equip_id)["config"]["politica_custo"]
    previas = []
    for t in plano["trechos"]:
        if not t["valido"]:
            previas.append({**t, "situacao": None, "frase": f"Lacuna: {t['motivo']}"})
            continue
        n = _nucleo(a, equip_id, pacote, ref, _ts(t["inicio"]), _ts(t["fim"]), politica)
        c = n["explicacao_conta"]
        previas.append(
            {
                **t,
                "situacao": c["desvio"]["estado"] if c.get("disponivel") else None,
                "frase": frase_situacao(n),
                "conta": c,
                "condicoes": condicoes_comparadas(
                    pacote, ref["inicio"], ref["fim"], _ts(t["inicio"]), _ts(t["fim"])
                ),
            }
        )
    return {**plano, "previas": previas, "revisao_dados": revisao}


def fechar_mes(a: Armazem, equip_id: str, chave: str, autor: str, agora=None) -> list[dict]:
    """Aprova o fechamento do mês: grava um fechamento por trecho aberto (lacunas
    inclusive, para ficarem registradas). Recusa mês em andamento, mês com período anterior
    em aberto, mês sem período e mês já fechado."""
    plano = plano_do_mes(a, equip_id, chave, agora)
    if plano["estado"] != "pronto":
        raise ErroArmazem(f"{plano['rotulo'].capitalize()}: {plano['frase']}")
    return [
        produzir_fechamento(a, equip_id, autor, t["inicio"], t["fim"], mes=chave)
        for t in plano["trechos"]
    ]


def revisar_mes(
    a: Armazem, equip_id: str, chave: str, autor: str, motivo: str, agora=None
) -> list[dict]:
    """Grava uma nova versão de cada fechamento do mês cujos registros mudaram, com o
    motivo; a versão anterior fica no histórico, ligada à nova."""
    if not (motivo or "").strip():
        raise ErroArmazem("A revisão do mês exige motivo.")
    plano = plano_do_mes(a, equip_id, chave, agora)
    if not plano["a_revisar"]:
        raise ErroArmazem(
            f"{plano['rotulo'].capitalize()}: nenhum registro mudou depois do fechamento."
        )
    return [
        produzir_fechamento(a, equip_id, autor, revisa=fid, motivo=motivo, mes=chave)
        for fid in plano["a_revisar"]
    ]


def resumo_do_mes(a: Armazem, equip_id: str, chave: str, agora=None, *, plano=None) -> dict | None:
    """Totais do mês a partir dos fechamentos em vigor do mês (soma dos trechos com conta).

    Somas de valores já calculados; a faixa de incerteza continua por trecho (não há
    combinação estatística dos trechos nesta versão). None se o mês não tem fechamento.
    Saída: valores em BRL e t, trechos com autor/data/revisão já registrados, motivos de
    ausência e cobertura em dias. `dias_com_conta` e `dias_com_valor` contam apenas a
    interseção dos trechos aprovados com o calendário do mês; dias de outro mês não são
    somados nessa cobertura. Os custos preservam a janela inteira de cada trecho (D111).
    Não há inferência de consumo diário nem complemento de períodos sem registros.

    `completo` exige todos os períodos atribuídos ao mês fechados, conta e preço em todos
    os trechos e nenhuma revisão pendente; não significa cobertura de todo o calendário,
    causa confirmada ou economia. `cobertura` informa os dias que ficaram de fora. Somam-se
    apenas valores gravados em vigor; se um trecho com conta não tem preço, a soma em BRL
    permanece None. Uma correção pendente não recalcula valores aprovados em silêncio.
    """
    fs = [
        f
        for f in fechamentos_vigentes(a, equip_id)
        if (f["resultado"].get("mes") or chave_do_mes(f["fim"])) == chave
    ]  # fechamentos de antes do fechamento mensal entram no mês em que terminam
    if not fs:
        return None
    plano = plano if plano is not None else plano_do_mes(a, equip_id, chave, agora)
    if plano["mes"] != chave:
        raise ValueError("O plano e o resumo devem pertencer ao mesmo mês.")
    trechos, com_conta = [], []
    for f in fs:
        resultado = f["resultado"]
        nucleo = resultado["nucleo"]
        c = nucleo["explicacao_conta"]
        disp = bool(c.get("disponivel"))
        valorado = disp and all(
            c[parte]["custo_brl"] is not None for parte in ("consumido", "esperado", "desvio")
        )
        motivo = None
        if not disp:
            motivo = c.get("motivo") or "Conta indisponível com os dados deste trecho."
        elif not valorado:
            motivo = nucleo["politica_custo"].get("motivo") or (
                "Preço indisponível para valorar a conta deste trecho."
            )
        trechos.append(
            {
                "fechamento_id": f["id"],
                "inicio": f["inicio"],
                "fim": f["fim"],
                "autor": f["autor"],
                "criado_em": f["criado_em"],
                "revisao_dados": f["revisao_dados"],
                "revisa": resultado.get("revisa"),
                "motivo_revisao": resultado.get("motivo_revisao"),
                "referencia_versao": nucleo["referencia"]["versao"],
                "conta_disponivel": disp,
                "valoracao_disponivel": valorado,
                "situacao": f["resultado"]["situacao"],
                "frase": f["resultado"]["situacao_frase"],
                "consumido_brl": c["consumido"]["custo_brl"] if disp else None,
                "esperado_brl": c["esperado"]["custo_brl"] if disp else None,
                "diferenca_brl": c["desvio"]["custo_brl"] if disp else None,
                "combustivel_t": c["consumido"]["combustivel_t"] if disp else None,
                "motivo": motivo,
            }
        )
        if disp:
            com_conta.append(trechos[-1])

    def soma(campo):
        valores = [t[campo] for t in com_conta]
        return None if not valores or any(v is None for v in valores) else float(sum(valores))

    ini_mes, fim_mes = _limites(chave)

    def dias_aprovados(campo):
        return sum(
            _dias(max(_ts(t["inicio"]), ini_mes), min(_ts(t["fim"]), fim_mes))
            for t in trechos
            if t[campo]
        )

    pendentes = sum(p["situacao"] == "aberto" for p in plano["periodos"])
    motivos = [
        f"{_fmt(t['inicio'])} a {_fmt(t['fim'])}: {t['motivo']}" for t in trechos if t["motivo"]
    ]
    if pendentes:
        motivos.append(f"{pendentes} período(s) sem aprovação não entram nos valores apresentados.")
    if plano["a_revisar"]:
        motivos.append(
            "Há registros corrigidos depois da aprovação: os valores registrados permanecem "
            "até a revisão explícita do mês."
        )
    return {
        "mes": chave,
        "rotulo": rotulo_mes(chave),
        "estado": plano["estado"],
        "estado_rotulo": plano["estado_rotulo"],
        "a_revisar": plano["a_revisar"],
        "periodos_pendentes": pendentes,
        "cobertura": {
            **plano["cobertura"],
            "dias_com_conta": dias_aprovados("conta_disponivel"),
            "dias_com_valor": dias_aprovados("valoracao_disponivel"),
        },
        "motivos": motivos,
        "fechamentos": [f["id"] for f in fs],
        "trechos": trechos,
        "trechos_com_valor": sum(t["valoracao_disponivel"] for t in trechos),
        "lacunas": [t for t in trechos if not t["conta_disponivel"]],
        "consumido_brl": soma("consumido_brl"),
        "esperado_brl": soma("esperado_brl"),
        "diferenca_brl": soma("diferenca_brl"),
        "combustivel_t": soma("combustivel_t"),
        "completo": plano["estado"] == "fechado"
        and all(t["valoracao_disponivel"] for t in trechos),
    }
