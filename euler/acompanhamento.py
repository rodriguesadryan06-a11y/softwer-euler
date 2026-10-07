"""Investigações acompanhadas, intervenções e verificação posterior (D94).

A EULER recomenda verificações e registra decisões dos responsáveis técnicos; nunca gera
comando operacional para a caldeira. Encerrar uma investigação não significa causa
confirmada: o resultado e o motivo do encerramento ficam registrados.

Avaliação de uma intervenção, em três níveis que não se confundem:
1. diferença observada depois da ação (sempre que há dado);
2. melhoria associada à ação: só com diferença fora da incerteza, condições comparáveis e
   nenhuma outra mudança registrada na janela (associação, não prova de causa);
3. economia verificada segundo o protocolo EULER-MV 0.1 (proposto, D94): exige a melhoria
   associada, duração mínima depois da ação, referência avaliável e preço pela política
   declarada. Cadastrar uma intervenção nunca preenche economia.
"""

from __future__ import annotations

import json

import pandas as pd

from euler.armazem import Armazem, ErroArmazem, agora_iso, jdump, sha
from euler.conta import FRASE_INCONCLUSIVO, motivo_inconclusivo
from euler.formato import num
from euler.investigacao import investigar
from euler.periodos import periodos_entre_estoques

ESTADOS = {
    "aguardando_dados": "Aguardando dados",
    "em_investigacao": "Em investigação",
    "acao_registrada": "Ação registrada",
    "em_verificacao": "Em verificação",
    "encerrada": "Encerrada",
}
TRANSICOES = {
    "aguardando_dados": {"em_investigacao", "encerrada"},
    "em_investigacao": {"aguardando_dados", "acao_registrada", "encerrada"},
    "acao_registrada": {"em_verificacao", "em_investigacao", "encerrada"},
    "em_verificacao": {"em_investigacao", "acao_registrada", "encerrada"},
    "encerrada": {"em_investigacao"},  # reabertura, com motivo
}
RESULTADOS = {
    "inconclusiva": "Inconclusiva",
    "hipotese_sustentada_por_verificacao": "Hipótese sustentada pela verificação registrada",
    "hipotese_enfraquecida": "Hipótese enfraquecida pela verificação",
    "desvio_nao_confirmado": "Desvio não se confirmou",
    "outra": "Outro resultado (ver motivo)",
}
TIPOS_INTERVENCAO = {
    "limpeza": "Limpeza",
    "manutencao": "Manutenção",
    "calibracao": "Calibração",
    "mudanca_combustivel": "Mudança de combustível",
    "alteracao_operacional": "Alteração operacional decidida pela equipe",
    "outra": "Outra",
}
PROTOCOLO = "EULER-MV 0.1 (proposto, pendente de revisão; D94)"


def _ts(x) -> pd.Timestamp:
    return pd.Timestamp(x)


def _obrigatorio(**campos) -> None:
    faltam = [k for k, v in campos.items() if not (v or "").strip()]
    if faltam:
        raise ErroArmazem(f"Campo obrigatório: {', '.join(faltam)}.")


# ---------------------------------------------------------------- investigações


def investigacao(a: Armazem, inv_id: int) -> dict:
    r = a.con.execute("SELECT * FROM investigacao WHERE id=?", (inv_id,)).fetchone()
    if r is None:
        raise ErroArmazem("Investigação não encontrada.")
    eventos = [
        {**dict(e), "dados": json.loads(e["dados"] or "{}")}
        for e in a.con.execute(
            "SELECT * FROM inv_evento WHERE investigacao_id=? ORDER BY id", (inv_id,)
        )
    ]
    return {**dict(r), "dados": json.loads(r["dados"]), "eventos": eventos}


def investigacoes(a: Armazem, equip_id: str, abertas: bool | None = None) -> list[dict]:
    sql = "SELECT id FROM investigacao WHERE equipamento_id=?"
    if abertas is True:
        sql += " AND estado != 'encerrada'"
    elif abertas is False:
        sql += " AND estado = 'encerrada'"
    return [investigacao(a, r["id"]) for r in a.con.execute(sql + " ORDER BY id", (equip_id,))]


def _inv_evento(cur, inv_id, tipo, autor, texto=None, dados=None) -> None:
    cur.execute(
        "INSERT INTO inv_evento (investigacao_id, quando, tipo, autor, texto, dados) "
        "VALUES (?,?,?,?,?,?)",
        (inv_id, agora_iso(), tipo, autor, texto, jdump(dados or {})),
    )
    cur.execute("UPDATE investigacao SET atualizada_em=? WHERE id=?", (agora_iso(), inv_id))


def abrir_do_fechamento(
    a: Armazem, fechamento_id: int, autor: str, responsavel: str | None = None
) -> dict:
    """Abre (ou atualiza) a investigação do desvio de um fechamento.

    Agrupamento: equipamento + hipótese principal. Se já existe uma investigação aberta
    com a mesma chave, a nova ocorrência entra no histórico dela em vez de criar outro
    alerta; nenhuma ocorrência é escondida.
    """
    from euler.fechamento import fechamento

    _obrigatorio(autor=autor)
    f = fechamento(a, fechamento_id)
    nuc = f["resultado"]["nucleo"]
    ops = [o for o in nuc["oportunidades"] if o["prioridade"] in ("alta", "media")]
    principal = ops[0] if ops else None
    if principal is None and f["resultado"]["situacao"] != "acima":
        raise ErroArmazem(
            "Este fechamento não tem desvio estabelecido nem hipótese a verificar: não há o que "
            "investigar. "
            + (
                "A conta não pôde ser calculada; complete os dados primeiro."
                if f["resultado"]["situacao"] is None
                else ""
            )
        )
    chave = f"{f['equipamento_id']}:{principal['id'] if principal else 'desvio_sem_hipotese'}"
    conta = nuc["explicacao_conta"]
    desvio = {
        "fechamento_id": fechamento_id,
        "periodo": nuc["periodo"],
        "situacao": f["resultado"]["situacao"],
        "frase": (conta.get("desvio") or {}).get("frase") or conta.get("motivo"),
        "custo_brl": (conta.get("desvio") or {}).get("custo_brl"),
    }
    existente = a.con.execute(
        "SELECT id FROM investigacao WHERE chave_grupo=? AND estado != 'encerrada'", (chave,)
    ).fetchone()
    with a._transacao() as cur:
        a._nova_revisao(cur)
        if existente:
            inv_id = existente["id"]
            _inv_evento(cur, inv_id, "ocorrencia", autor, desvio["frase"], desvio)
        else:
            sem_base = principal is None
            dados = {
                "periodo": nuc["periodo"],
                "desvio": desvio,
                "hipoteses": ops,
                "evidencias": nuc["evidencias"],
                "limitacoes": [x for x in (conta.get("esperado") or {}).get("nao_ajustado", [])]
                + nuc.get("sobreposicao", []),
                "proxima_verificacao": nuc["proxima_verificacao"],
                "resultado": None,
                "motivo_encerramento": None,
            }
            cur.execute(
                "INSERT INTO investigacao (equipamento_id, chave_grupo, titulo, estado, "
                "responsavel, criada_em, atualizada_em, dados) VALUES (?,?,?,?,?,?,?,?)",
                (
                    f["equipamento_id"],
                    chave,
                    principal["titulo"] if principal else "Desvio sem hipótese priorizada",
                    "aguardando_dados" if sem_base else "em_investigacao",
                    responsavel,
                    agora_iso(),
                    agora_iso(),
                    jdump(dados),
                ),
            )
            inv_id = cur.lastrowid
            _inv_evento(cur, inv_id, "criada", autor, desvio["frase"], desvio)
        a._evento(cur, f["equipamento_id"], "investigacao", inv_id, "ocorrencia", autor, desvio)
    return investigacao(a, inv_id)


def adicionar_evidencia(
    a: Armazem, inv_id: int, texto: str, autor: str, referencia: str | None = None
) -> dict:
    """Evidência nova (texto e, opcionalmente, onde está o documento ou a medição)."""
    _obrigatorio(texto=texto, autor=autor)
    inv = investigacao(a, inv_id)
    with a._transacao() as cur:
        a._nova_revisao(cur)
        _inv_evento(cur, inv_id, "evidencia", autor, texto, {"referencia": referencia})
        a._evento(cur, inv["equipamento_id"], "investigacao", inv_id, "evidencia", autor)
    return investigacao(a, inv_id)


def mudar_estado(a: Armazem, inv_id: int, novo: str, autor: str, motivo: str) -> dict:
    _obrigatorio(autor=autor, motivo=motivo)
    inv = investigacao(a, inv_id)
    if novo == "encerrada":
        raise ErroArmazem("Use o encerramento, que exige resultado e motivo.")
    if novo not in TRANSICOES[inv["estado"]]:
        raise ErroArmazem(
            f"Não é possível passar de '{ESTADOS[inv['estado']]}' para '{ESTADOS.get(novo, novo)}'."
        )
    with a._transacao() as cur:
        a._nova_revisao(cur)
        cur.execute("UPDATE investigacao SET estado=? WHERE id=?", (novo, inv_id))
        _inv_evento(cur, inv_id, "estado", autor, motivo, {"de": inv["estado"], "para": novo})
        a._evento(cur, inv["equipamento_id"], "investigacao", inv_id, f"estado:{novo}", autor)
    return investigacao(a, inv_id)


def definir_responsavel(a: Armazem, inv_id: int, responsavel: str, autor: str) -> dict:
    _obrigatorio(responsavel=responsavel, autor=autor)
    inv = investigacao(a, inv_id)
    with a._transacao() as cur:
        a._nova_revisao(cur)
        cur.execute("UPDATE investigacao SET responsavel=? WHERE id=?", (responsavel, inv_id))
        _inv_evento(cur, inv_id, "responsavel", autor, responsavel, {"antes": inv["responsavel"]})
    return investigacao(a, inv_id)


def encerrar(a: Armazem, inv_id: int, resultado: str, motivo: str, autor: str) -> dict:
    """Encerra com resultado e motivo. Inconclusiva é um resultado válido."""
    _obrigatorio(motivo=motivo, autor=autor)
    if resultado not in RESULTADOS:
        raise ErroArmazem("Resultado de encerramento desconhecido.")
    inv = investigacao(a, inv_id)
    if inv["estado"] == "encerrada":
        raise ErroArmazem("Investigação já encerrada.")
    dados = {**inv["dados"], "resultado": resultado, "motivo_encerramento": motivo}
    with a._transacao() as cur:
        a._nova_revisao(cur)
        cur.execute(
            "UPDATE investigacao SET estado='encerrada', dados=? WHERE id=?", (jdump(dados), inv_id)
        )
        _inv_evento(cur, inv_id, "encerrada", autor, motivo, {"resultado": resultado})
        a._evento(
            cur,
            inv["equipamento_id"],
            "investigacao",
            inv_id,
            "encerrada",
            autor,
            {"resultado": resultado},
        )
    return investigacao(a, inv_id)


# ---------------------------------------------------------------- intervenções


def intervencao(a: Armazem, int_id: int) -> dict:
    r = a.con.execute("SELECT * FROM intervencao WHERE id=?", (int_id,)).fetchone()
    if r is None:
        raise ErroArmazem("Intervenção não encontrada.")
    return {**dict(r), "dados": json.loads(r["dados"] or "{}")}


def intervencoes(a: Armazem, equip_id: str) -> list[dict]:
    return [
        intervencao(a, r["id"])
        for r in a.con.execute(
            "SELECT id FROM intervencao WHERE equipamento_id=? ORDER BY data, id", (equip_id,)
        )
    ]


def registrar_intervencao(
    a: Armazem,
    equip_id: str,
    data,
    tipo: str,
    descricao: str,
    autor: str,
    responsavel: str | None = None,
    investigacao_id: int | None = None,
    hipotese: str | None = None,
    evidencias: str | None = None,
    concomitantes: list[str] | None = None,
    custo_brl: float | None = None,
    custo_origem: str | None = None,
) -> dict:
    """Registra o que a equipe fez. Não gera economia: isso só vem da avaliação posterior."""
    _obrigatorio(descricao=descricao, autor=autor)
    if tipo not in TIPOS_INTERVENCAO:
        raise ErroArmazem("Tipo de intervenção desconhecido.")
    if custo_brl is not None and (custo_brl < 0 or not (custo_origem or "").strip()):
        raise ErroArmazem("Custo da intervenção precisa ser não negativo e ter origem declarada.")
    a.equipamento(equip_id)
    quando = _ts(data)
    with a._transacao() as cur:
        a._nova_revisao(cur)
        cur.execute(
            "INSERT INTO intervencao (equipamento_id, data, tipo, descricao, responsavel, "
            "investigacao_id, custo_brl, custo_origem, criada_em, autor, dados) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                equip_id,
                quando.isoformat(),
                tipo,
                descricao,
                responsavel,
                investigacao_id,
                custo_brl,
                custo_origem,
                agora_iso(),
                autor,
                jdump(
                    {
                        "hipotese": hipotese,
                        "evidencias": evidencias,
                        "concomitantes": [c for c in (concomitantes or []) if c.strip()],
                    }
                ),
            ),
        )
        int_id = cur.lastrowid
        a._evento(cur, equip_id, "intervencao", int_id, "registrada", autor, {"tipo": tipo})
        if investigacao_id is not None:
            inv = investigacao(a, investigacao_id)
            _inv_evento(cur, investigacao_id, "acao", autor, descricao, {"intervencao_id": int_id})
            if "acao_registrada" in TRANSICOES[inv["estado"]]:
                cur.execute(
                    "UPDATE investigacao SET estado='acao_registrada' WHERE id=?",
                    (investigacao_id,),
                )
                _inv_evento(
                    cur,
                    investigacao_id,
                    "estado",
                    autor,
                    "Ação registrada.",
                    {"de": inv["estado"], "para": "acao_registrada"},
                )
    return intervencao(a, int_id)


def registrar_custo_servico(
    a: Armazem,
    equip_id: str | None,
    data,
    tipo: str,
    descricao: str,
    valor_brl: float,
    origem: str,
    autor: str,
) -> int:
    """Custo de medição, acompanhamento ou outro gasto ligado à verificação (informado)."""
    _obrigatorio(descricao=descricao, origem=origem, autor=autor)
    if tipo not in ("medicao", "acompanhamento", "outro") or valor_brl < 0:
        raise ErroArmazem("Tipo de custo desconhecido ou valor negativo.")
    with a._transacao() as cur:
        a._nova_revisao(cur)
        cur.execute(
            "INSERT INTO custo_servico (equipamento_id, data, tipo, descricao, valor_brl, origem,"
            " criado_em, autor) VALUES (?,?,?,?,?,?,?,?)",
            (
                equip_id,
                _ts(data).isoformat(),
                tipo,
                descricao,
                float(valor_brl),
                origem,
                agora_iso(),
                autor,
            ),
        )
        return cur.lastrowid


def custos_servico(a: Armazem, equip_id: str) -> list[dict]:
    return [
        dict(r)
        for r in a.con.execute(
            "SELECT * FROM custo_servico WHERE equipamento_id=? ORDER BY data", (equip_id,)
        )
    ]


# ---------------------------------------------------------------- avaliação posterior


def avaliacoes(a: Armazem, int_id: int) -> list[dict]:
    return [
        {**dict(r), "resultado": json.loads(r["resultado"])}
        for r in a.con.execute(
            "SELECT * FROM avaliacao WHERE intervencao_id=? ORDER BY id", (int_id,)
        )
    ]


def ultima_avaliacao(a: Armazem, int_id: int) -> dict | None:
    av = avaliacoes(a, int_id)
    return av[-1] if av else None


def _cargas(j: dict) -> tuple[list[float], list[float]]:
    ref = (j.get("diagnostico_evidencias") or {}).get("dimensoes", {}).get("referencia", {})
    antes = [x["carga_t_h"] for x in ref.get("serie", []) if x.get("carga_t_h") is not None]
    depois = [
        x["carga_t_h"] for x in ref.get("serie_comparacao", []) if x.get("carga_t_h") is not None
    ]
    return antes, depois


def avaliar_intervencao(a: Armazem, int_id: int, autor: str) -> dict:
    """Compara a referência anterior à ação com os períodos completos depois dela."""
    from euler.fechamento import (
        p_atm,
        preco_do_periodo,
        referencias,
        sequencia_valida,
        validade_periodos,
    )

    _obrigatorio(autor=autor)
    it = intervencao(a, int_id)
    equip_id = it["equipamento_id"]
    cfg = a.equipamento(equip_id)["config"]
    data = _ts(it["data"])
    revisao = a.revisao
    pacote = a.pacote(equip_id, revisao=revisao, p_atm_bar=p_atm(a, equip_id))
    refs = [r for r in referencias(a, equip_id) if _ts(r["fim"]) <= data]
    ref = refs[-1] if refs else None
    depois = validade_periodos(pacote, [p for p in periodos_entre_estoques(pacote) if p[0] >= data])
    # primeira sequência de períodos válidos depois da ação: períodos iniciais sem dado são
    # pulados e listados; a sequência termina no primeiro período inválido seguinte
    inicio_valido = next((i for i, x in enumerate(depois) if x["valido"]), len(depois))
    validos = sequencia_valida(depois[inicio_valido:])
    pos = [(x["inicio"], x["fim"]) for x in validos]
    excluidos = [
        f"{x['inicio']:%d/%m} a {x['fim']:%d/%m}: {x['motivo']}" for x in depois if not x["valido"]
    ]
    minimo = int(cfg["periodos_minimos_pos_intervencao"])
    base = {
        "intervencao_id": int_id,
        "protocolo": PROTOCOLO,
        "referencia": None
        if ref is None
        else {"id": ref["id"], "versao": ref["versao"], "inicio": ref["inicio"], "fim": ref["fim"]},
        "periodos_depois": len(pos),
        "periodos_excluidos": excluidos,
        "periodos_minimos": minimo,
        "diferenca_observada": None,
        "melhoria_associada": None,
        "economia_verificada": None,
    }
    faltas = []
    if ref is None:
        faltas.append("uma referência que termine antes da data da intervenção")
    if not pos:
        faltas.append(
            f"pelo menos um período completo, com vapor e combustível conhecidos, entre "
            f"medições de estoque depois de {data:%d/%m/%Y}"
            + (f" ({'; '.join(excluidos)})" if excluidos else "")
        )
    if faltas:
        resultado = {
            **base,
            "resultado": "nao_avaliavel",
            "frase": "Dados insuficientes para avaliar a ação: faltam " + "; ".join(faltas) + ".",
            "faltam": faltas,
        }
        return _gravar_avaliacao(a, it, revisao, ref, resultado, autor)

    j = investigar(pacote, (_ts(ref["inicio"]), _ts(ref["fim"])), (pos[0][0], pos[-1][1]))
    politica = cfg["politica_custo"]
    preco = preco_do_periodo(a, equip_id, pacote, pos[0][0], pos[-1][1], politica)
    conta = j["explicacao_conta"]
    c = j["o_que_mudou"]["consumo_especifico"]
    desvio = conta.get("desvio") or {}
    p = preco.get("preco_brl_t")
    base["diferenca_observada"] = {
        "periodo_depois": {"inicio": pos[0][0].isoformat(), "fim": pos[-1][1].isoformat()},
        "consumo_antes_t_t": c.get("referencia"),
        "consumo_depois_t_t": c.get("comparacao"),
        "variacao_pct": None if not c.get("variacao") else 100 * c["variacao"] / c["referencia"],
        "detectabilidade": c.get("detectabilidade"),
        "desvio_t": desvio.get("combustivel_t"),
        "desvio_faixa_t": desvio.get("faixa_t"),
        "desvio_estado": desvio.get("estado"),
        "desvio_brl": None
        if desvio.get("combustivel_t") is None or p is None
        else desvio["combustivel_t"] * p,
        "ajustes": (conta.get("esperado") or {}).get("ajustado_por", []),
        "nao_ajustado": (conta.get("esperado") or {}).get("nao_ajustado", []),
        "variacao_conta": conta.get("variacao"),
        "frase": desvio.get("frase") or conta.get("motivo"),
    }

    # comparabilidade e outras mudanças na janela
    bloqueios = []
    outras = [
        x
        for x in intervencoes(a, equip_id)
        if x["id"] != int_id and _ts(ref["fim"]) < _ts(x["data"]) <= pos[-1][1]
    ]
    if outras:
        bloqueios.append(
            "outra intervenção registrada na mesma janela: "
            + ", ".join(f"#{x['id']} {x['descricao']} ({_ts(x['data']):%d/%m})" for x in outras)
        )
    if it["dados"].get("concomitantes"):
        bloqueios.append(
            "mudanças concomitantes declaradas: " + "; ".join(it["dados"]["concomitantes"])
        )
    antes, depois = _cargas(j)
    if antes and depois and (min(depois) < min(antes) or max(depois) > max(antes)):
        bloqueios.append(
            f"carga depois da ação ({num(min(depois), 1)}–{num(max(depois), 1)} t/h) fora da "
            f"faixa da referência ({num(min(antes), 1)}–{num(max(antes), 1)} t/h)"
        )
    qualidade = (
        (j.get("diagnostico_evidencias") or {}).get("dimensoes", {}).get("qualidade_dados", {})
    )
    if qualidade.get("nivel") == "INSUFICIENTE":
        bloqueios.append("qualidade dos dados insuficiente no período depois da ação")
    base["comparabilidade"] = {"comparavel": not bloqueios, "motivos": bloqueios}
    base["outras_intervencoes"] = [x["id"] for x in outras]

    resultado, frase = resultado_da_avaliacao(desvio, conta.get("motivo"), bloqueios)
    if resultado == "positivo":
        lo, hi = desvio["faixa_t"]
        base["melhoria_associada"] = {
            "combustivel_t": -desvio["combustivel_t"],
            "faixa_t": [-hi, -lo],
            "pct_do_esperado": -desvio["pct_do_esperado"],
            "custo_brl": None if p is None else -desvio["combustivel_t"] * p,
            "faixa_brl": None if p is None else [-hi * p, -lo * p],
            "nota": "Associação estatística em condições comparáveis; não prova que a ação causou a melhoria.",
        }
        base["economia_verificada"] = _protocolo(a, it, j, preco, base, minimo, pos)
    return _gravar_avaliacao(
        a, it, revisao, ref, {**base, "resultado": resultado, "frase": frase}, autor
    )


def resultado_da_avaliacao(
    desvio: dict, motivo_conta: str | None, bloqueios: list[str]
) -> tuple[str, str]:
    """Resultado da avaliação de uma ação e a frase com o motivo certo (D94, D110).

    "nao_avaliavel" sem conta; "negativo" acima da referência; "inconclusivo" quando o
    desvio não foi estabelecido (com o motivo do próprio desvio: faixa que inclui zero,
    cenário do pátio ou falta de incerteza) ou quando a melhora não pode ser associada à
    ação (bloqueios); "positivo" só abaixo, fora da incerteza e sem bloqueios.
    """
    estado = desvio.get("estado")
    outros = ("; ".join(bloqueios) + ".") if bloqueios else ""
    if estado is None:
        return "nao_avaliavel", motivo_conta or "Conta indisponível."
    if estado == "acima":
        frase = "Depois da ação, o consumo ficou acima da referência ajustada, fora da incerteza."
        return "negativo", frase + (f" Atenção na leitura: {outros}" if outros else "")
    if estado in ("nao_estabelecido", "sem_faixa"):
        motivo = FRASE_INCONCLUSIVO[motivo_inconclusivo(desvio)]
        frase = f"Depois da ação, a diferença não ficou estabelecida: {motivo}."
        return "inconclusivo", frase + (f" Além disso: {outros}" if outros else "")
    if bloqueios:
        return (
            "inconclusivo",
            "Consumo abaixo da referência ajustada, mas não é possível associar à ação: " + outros,
        )
    return (
        "positivo",
        (
            "Consumo abaixo da referência ajustada, fora da incerteza, em condições comparáveis "
            "e sem outra mudança registrada: melhoria associada à ação (não prova de causa)."
        ),
    )


def _protocolo(a, it, j, preco, base, minimo, pos) -> dict:
    """EULER-MV 0.1 (proposto): condições explícitas; qualquer falta deixa o valor ausente."""
    falhas = []
    if len(pos) < minimo:
        falhas.append(f"{len(pos)} período(s) depois da ação; o protocolo exige {minimo}")
    nivel_ref = (
        (j.get("diagnostico_evidencias") or {})
        .get("dimensoes", {})
        .get("referencia", {})
        .get("nivel")
    )
    if nivel_ref in (None, "INSUFICIENTE"):
        falhas.append("referência sem avaliação mínima (qualidade da referência insuficiente)")
    if preco.get("preco_brl_t") is None:
        falhas.append(f"preço indisponível pela política declarada ({preco.get('motivo')})")
    if falhas:
        return {"valor_brl": None, "protocolo": PROTOCOLO, "criterios_nao_atendidos": falhas}
    m = base["melhoria_associada"]
    custos = [
        x
        for x in custos_servico(a, it["equipamento_id"])
        if _ts(it["data"]) <= _ts(x["data"]) <= pos[-1][1]
    ]
    custo_total = (it["custo_brl"] or 0.0) + sum(x["valor_brl"] for x in custos)
    return {
        "valor_brl": m["custo_brl"],
        "faixa_brl": m["faixa_brl"],
        "periodo": base["diferenca_observada"]["periodo_depois"],
        "protocolo": PROTOCOLO,
        "politica_custo": preco["politica"],
        "custos_considerados_brl": custo_total if it["custo_brl"] is not None else None,
        "beneficio_liquido_brl": m["custo_brl"] - custo_total
        if it["custo_brl"] is not None
        else None,
        "nota_custos": (
            "Custo da intervenção não informado: benefício líquido não calculado."
            if it["custo_brl"] is None
            else "Benefício líquido = economia verificada − custo da intervenção − custos de "
            "medição e acompanhamento informados na janela."
        ),
        "nota": (
            "Valor do período avaliado, não projetado para o ano. O benefício é da ação da "
            "equipe; a EULER registra e verifica."
        ),
    }


def _gravar_avaliacao(a, it, revisao, ref, resultado, autor) -> dict:
    with a._transacao() as cur:
        a._nova_revisao(cur)
        cur.execute(
            "INSERT INTO avaliacao (intervencao_id, criada_em, revisao_dados, referencia_id, "
            "resultado, resultado_sha) VALUES (?,?,?,?,?,?)",
            (
                it["id"],
                agora_iso(),
                revisao,
                None if ref is None else ref["id"],
                jdump(resultado),
                sha(resultado),
            ),
        )
        aid = cur.lastrowid
        a._evento(cur, it["equipamento_id"], "avaliacao", aid, resultado["resultado"], autor)
        inv_id = it["investigacao_id"]
        if inv_id is not None:
            inv = investigacao(a, inv_id)
            _inv_evento(
                cur,
                inv_id,
                "verificacao",
                autor,
                resultado["frase"],
                {"avaliacao_id": aid, "resultado": resultado["resultado"]},
            )
            if inv["estado"] == "acao_registrada" and resultado["resultado"] != "nao_avaliavel":
                cur.execute("UPDATE investigacao SET estado='em_verificacao' WHERE id=?", (inv_id,))
                _inv_evento(
                    cur,
                    inv_id,
                    "estado",
                    autor,
                    "Avaliação posterior registrada.",
                    {"de": "acao_registrada", "para": "em_verificacao"},
                )
    return ultima_avaliacao(a, it["id"])


def adotar_referencia_pos_intervencao(
    a: Armazem, int_id: int, autor: str, motivo: str, confirmar_absorcao: bool = False
) -> dict:
    """Nova versão da referência a partir dos períodos depois da ação, para acompanhar se o
    desempenho se mantém. A proteção contra absorver piora da `criar_referencia` vale."""
    from euler.fechamento import criar_referencia

    av = ultima_avaliacao(a, int_id)
    if av is None or av["resultado"].get("diferenca_observada") is None:
        raise ErroArmazem("Avalie a intervenção com dados depois dela antes de mudar a referência.")
    per = av["resultado"]["diferenca_observada"]["periodo_depois"]
    it = intervencao(a, int_id)
    return criar_referencia(
        a,
        it["equipamento_id"],
        per["inicio"],
        per["fim"],
        "estrutural",
        f"Depois da intervenção #{int_id} ({it['descricao']}): {motivo}",
        autor,
        intervencao_id=int_id,
        confirmar_absorcao=confirmar_absorcao,
    )


# ---------------------------------------------------------------- contexto do fechamento


def contexto_para_fechamento(a: Armazem, equip_id: str, inicio, fim, nucleo: dict) -> dict:
    """O que os registros dizem naquele momento: investigações e resultados de ações.

    Guardado com o fechamento, mas fora do núcleo reproduzível (muda com o tempo).
    """
    from euler.fechamento import referencia

    abertas = investigacoes(a, equip_id, abertas=True)
    acoes = []
    for it in intervencoes(a, equip_id):
        av = ultima_avaliacao(a, it["id"])
        acoes.append(
            {
                "id": it["id"],
                "data": it["data"],
                "descricao": it["descricao"],
                "resultado": None if av is None else av["resultado"]["resultado"],
                "frase": "Ainda não avaliada." if av is None else av["resultado"]["frase"],
                "economia_verificada_brl": None
                if av is None or not av["resultado"].get("economia_verificada")
                else av["resultado"]["economia_verificada"].get("valor_brl"),
            }
        )
    ref = referencia(a, nucleo["referencia"]["id"])
    desempenho = None
    if ref["intervencao_id"] is not None:
        estado = (nucleo["explicacao_conta"].get("desvio") or {}).get("estado")
        desempenho = {
            "acima": (
                f"Nova deterioração detectável em relação à referência depois da intervenção "
                f"#{ref['intervencao_id']}."
            ),
            "abaixo": "Desempenho melhor que a referência depois da intervenção.",
            "nao_estabelecido": (
                "Desempenho compatível com a referência depois da intervenção: sem nova "
                "deterioração detectável (isso não é 'economia preservada')."
            ),
        }.get(estado, "Persistência não avaliável neste período.")
    return {
        "investigacoes_abertas": [
            {
                "id": x["id"],
                "titulo": x["titulo"],
                "estado": x["estado"],
                "ocorrencias": sum(e["tipo"] in ("criada", "ocorrencia") for e in x["eventos"]),
            }
            for x in abertas
        ],
        "acoes": acoes,
        "persistencia": desempenho,
    }
