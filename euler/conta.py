"""Explicação da conta de combustível (D89, E16 em docs/fisica/fisica_para_revisao.md).

Separa "gastou mais" de "perdeu eficiência".

Responde, para o período analisado: quanto custou o combustível consumido, quanto seria
esperado nas condições analisadas e quanto da diferença continua sem explicação. Também
decompõe a variação da conta em relação à referência (produção, condição do vapor,
qualidade do combustível, preço e desvio não explicado).

Só usa números que o motor já calculou. Uma parcela só é separada quando há dado para
isso; senão fica misturada ao desvio, com o motivo (ausente nunca vira zero). Não
confirma causa, não estima parcela evitável e não aplica percentual de recuperação.
"""

from math import exp, isfinite

from euler.formato import num

PERGUNTAS = {
    "producao": "Quanto da variação era esperado para atender à demanda de vapor?",
    "condicao_vapor": "Cada tonelada de vapor exigiu mais ou menos energia?",
    "qualidade": "Foi preciso queimar mais massa porque cada tonelada entregou menos energia?",
    "preco": "Quanto veio da mudança de preço do combustível?",
    "nao_explicado": "Quanto permanece depois dos ajustes que os dados permitem?",
}
TITULOS = {
    "producao": "Produção de vapor",
    "condicao_vapor": "Condição do vapor e da água",
    "qualidade": "Qualidade do combustível",
    "preco": "Preço do combustível",
    "nao_explicado": "Desvio ainda não explicado",
}
NAO_MODELADO = (
    "Carga e regime de operação: não modelados nesta versão; seu efeito permanece no desvio."
)
ORIGEM_PRECO = {
    "recebimentos_do_periodo": "dos recebimentos",
    "fifo": "pela política FIFO",
    "tabela_de_precos": "pela tabela de preços",
}
BASE_PRECO = {
    "recebimentos_do_periodo": "média ponderada dos recebimentos",
    "fifo": "política FIFO: lotes mais antigos do estoque",
    "tabela_de_precos": "tabela de preços vigente, com adicionais declarados",
}


def _f(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and isfinite(x) else None


def _nao_negativo(x) -> float | None:
    """Preço finito >= 0; negativo, NaN ou infinito fica ausente (nunca vira zero)."""
    x = _f(x)
    return x if x is not None and x >= 0 else None


def _brl(v: float | None) -> str:
    if v is None:
        return "—"
    return ("−" if v < 0 else "") + f"R$ {num(abs(v), 0)}"


def _t(v: float) -> str:
    return f"{num(abs(v), 1)} t"


# Por que um desvio não ficou estabelecido (D110): cada caso tem o seu motivo, nunca um
# motivo genérico que possa ser o errado.
FRASE_INCONCLUSIVO = {
    "faixa_inclui_zero": "a diferença cabe na incerteza das medições",
    "cenario_do_patio": (
        "num cenário do pátio (combustível queimado diferente do recebido) a diferença pode "
        "ser zero"
    ),
    "sem_faixa": (
        "sem a incerteza declarada de todos os instrumentos, não dá para saber se a "
        "diferença é maior que o erro de medição"
    ),
}


def motivo_inconclusivo(desvio: dict | None) -> str | None:
    """Motivo de um desvio não estabelecido, derivado do próprio resultado gravado.

    "sem_faixa": falta incerteza para a faixa; "faixa_inclui_zero": a faixa das medições
    inclui zero; "cenario_do_patio": a faixa principal exclui zero, mas um cenário do pátio
    (recebido × queimado) a cruza. None quando o desvio está estabelecido ou indisponível.
    Funciona também com fechamentos antigos (usa só `estado` e `faixa_t`).
    """
    if not desvio:
        return None
    estado = desvio.get("estado")
    if estado == "sem_faixa":
        return "sem_faixa"
    if estado != "nao_estabelecido":
        return None
    faixa = desvio.get("faixa_t")
    if faixa and faixa[0] <= 0 <= faixa[1]:
        return "faixa_inclui_zero"
    return "cenario_do_patio"


def explicar_conta(
    *,
    combustivel_ref_t: float | None,
    vapor_ref_t: float | None,
    combustivel_t: float | None,
    vapor_t: float | None,
    preco_ref_brl_t: float | None,
    preco_brl_t: float | None,
    preco_min_brl_t: float | None = None,
    preco_max_brl_t: float | None = None,
    preco_ref_brl_gj: float | None = None,
    preco_brl_gj: float | None = None,
    horas_ref: float | None = None,
    horas: float | None = None,
    incerteza_consumo_t_t: float | None = None,
    efeito_condicao_vapor_pct: float | None = None,
    motivo_condicao_vapor: str = "energia por tonelada de vapor não calculada nos dois períodos",
    efeito_qualidade_pct: float | None = None,
    cenarios_qualidade_pct: tuple[float, float] | None = None,
    motivo_qualidade: str = "umidade e PCI medidos não disponíveis nos dois períodos",
    verificacao: str | None = None,
    analise_incerteza: dict | None = None,
    politica_custo: str = "recebimentos_do_periodo",
) -> dict:
    """Conta do período analisado (comparação) contra o esperado nas mesmas condições.

    Entradas: massas em t (combustível queimado E9, vapor do totalizador); preços em R$/t
    (pela política declarada; padrão: média ponderada dos recebimentos do período);
    mínimo e máximo por lote somente para a política de recebimentos; efeitos em
    pontos log % no consumo, como o motor os calcula (condição do vapor: razão da energia
    por kg de vapor; qualidade: razão do PCI úmido mais a perda nos gases pela umidade).
    `incerteza_consumo_t_t`: U (k = 2) da diferença de consumo específico com erros de
    instrumento independentes.

    Cadeia (hipótese: mesma eficiência da referência; D89):
      e0 = k_ref × vapor                    (produção, ao consumo por t da referência)
      e1 = e0 × exp(efeito condição / 100)  (se separado)
      e2 = e1 × exp(efeito qualidade / 100) (se separado) = consumo esperado ajustado
      desvio = combustível − e2             (alvo da investigação, não desperdício)
    Variação da conta: m·p − m_ref·p_ref = m_ref·(p − p_ref) + p·(m − m_ref), com
    m − m_ref = (e0 − m_ref) + (e1 − e0) + (e2 − e1) + desvio. A soma fecha exatamente; o
    desvio em reais é o "(observado − esperado ajustado) × preço" do período.

    Faixa do desvio: ± U × vapor, só das medições de consumo e vapor; não inclui a
    incerteza dos ajustes. Estado "acima"/"abaixo" só quando a faixa exclui zero em todos
    os cenários do pátio; senão "nao_estabelecido". Sem U: "sem_faixa".

    `analise_incerteza` (D97, de investigacao._analise_incerteza): parcela de cada fonte na
    faixa, U da diferença se cada instrumento repetir o mesmo erro nos dois períodos (r = 1)
    e U se a fonte dominante tivesse metade da incerteza. Viram faixas e frases em
    desvio["incerteza"]; a faixa e o estado principais continuam os de r = 0.
    """
    # entradas guardadas no resultado: permitem recalcular com outra política de preço (D93)
    entradas = {k: list(v) if isinstance(v, tuple) else v for k, v in locals().items()}
    if politica_custo not in ORIGEM_PRECO:
        raise ValueError("Política de custo desconhecida.")
    m_r, v_r = _f(combustivel_ref_t), _f(vapor_ref_t)
    m, v = _f(combustivel_t), _f(vapor_t)
    p_r, p = _nao_negativo(preco_ref_brl_t), _nao_negativo(preco_brl_t)
    if not all(x is not None and x > 0 for x in (m_r, v_r, m, v)):
        return {
            "disponivel": False,
            "motivo": (
                "Combustível queimado ou vapor não conhecidos nos dois períodos: o consumo "
                "esperado não pode ser calculado."
            ),
            "entradas": entradas,
        }
    k_r = m_r / v_r
    e0 = k_r * v
    ef_dh, ef_w = _f(efeito_condicao_vapor_pct), _f(efeito_qualidade_pct)
    e1 = e0 * exp(ef_dh / 100) if ef_dh is not None else e0
    e2 = e1 * exp(ef_w / 100) if ef_w is not None else e1
    desvio = m - e2

    def custo(t: float | None) -> float | None:
        return None if t is None or p is None else t * p

    ajustado = ["produção de vapor"]
    nao_ajustado = []
    if ef_dh is not None:
        ajustado.append("condição do vapor e da água")
    else:
        nao_ajustado.append(f"Condição do vapor: {motivo_condicao_vapor}; permanece no desvio.")
    if ef_w is not None:
        ajustado.append("qualidade do combustível medida")
    else:
        nao_ajustado.append(f"Qualidade do combustível: {motivo_qualidade}; permanece no desvio.")
    nao_ajustado.append(NAO_MODELADO)

    # cenários do pátio para a qualidade (recebido × FIFO): outros valores do desvio
    centros = [desvio]
    cen_q = None
    if ef_w is not None and cenarios_qualidade_pct:
        alt = {m - e1 * exp(x / 100) for x in cenarios_qualidade_pct if _f(x) is not None}
        if alt - {desvio}:  # só há cenário quando recebido e FIFO dão valores diferentes
            centros += sorted(alt)
            cen_q = None if p is None else sorted(custo(x) for x in alt)

    u = _f(incerteza_consumo_t_t)
    u_t = None if u is None else u * v
    faixa_t = None if u_t is None else (desvio - u_t, desvio + u_t)
    if u_t is None:
        estado = "sem_faixa"
    elif min(c - u_t for c in centros) > 0:
        estado = "acima"
    elif max(c + u_t for c in centros) < 0:
        estado = "abaixo"
    else:
        estado = "nao_estabelecido"

    p_min, p_max = _nao_negativo(preco_min_brl_t), _nao_negativo(preco_max_brl_t)
    cen_p = (
        sorted((desvio * p_min, desvio * p_max))
        if p_min is not None and p_max is not None and p_min != p_max
        else None
    )
    sentido = "acima" if desvio >= 0 else "abaixo"
    valor = custo(desvio)
    faixa_brl = None if faixa_t is None or p is None else [x * p for x in faixa_t]
    em_reais = (
        f", equivalente a {_brl(abs(valor))} "
        + (
            "ao preço médio dos recebimentos"
            if politica_custo == "recebimentos_do_periodo"
            else f"ao preço atribuído {ORIGEM_PRECO[politica_custo]}"
        )
        if valor is not None
        else f" (sem preço {ORIGEM_PRECO[politica_custo]} no período, o valor em reais não foi estimado)"
    )
    faixa_txt = (
        f"de {_brl(faixa_brl[0])} a {_brl(faixa_brl[1])}"
        if faixa_brl
        else (f"de {_t(faixa_t[0])} a {_t(faixa_t[1])}" if faixa_t else "")
    )
    base = f"O consumo ficou {_t(desvio)} {sentido} da referência ajustada{em_reais}"
    if estado == "acima":
        frase = (
            f"{base}. A faixa das medições vai {faixa_txt}. Ainda não se sabe quanto dessa "
            "diferença pode ser evitado."
        )
    elif estado == "abaixo":
        frase = f"{base}. A faixa das medições vai {faixa_txt}: o consumo ficou abaixo do esperado."
    elif estado == "nao_estabelecido":
        conclusao = (
            "o custo adicional não ficou bem estabelecido."
            if desvio >= 0
            else "a diferença não ficou bem estabelecida."
        )
        frase = (
            f"{base}, mas a faixa das medições vai {faixa_txt} e inclui zero: {conclusao}"
            if faixa_t[0] <= 0 <= faixa_t[1]
            else (
                f"{base}. A faixa das medições vai {faixa_txt}, mas em um cenário do pátio "
                f"(combustível queimado diferente do recebido) a diferença pode ser zero: "
                f"{conclusao}"
            )
        )
    else:
        frase = (
            f"{base}, mas sem a incerteza declarada de todos os instrumentos não dá para "
            "saber se a diferença é maior que o erro de medição."
        )

    incerteza = _incerteza_explicada(analise_incerteza, v, desvio, centros, p, estado)
    var = _variacao(m_r, m, e0, e1, e2, desvio, p_r, p, ef_dh, ef_w, politica_custo)
    var["componentes"] = _componentes(
        var,
        v_r,
        v,
        k_r,
        p_r,
        p,
        ef_dh,
        ef_w,
        motivo_condicao_vapor,
        motivo_qualidade,
        preco_ref_brl_gj,
        preco_brl_gj,
        politica_custo,
    )
    return {
        "disponivel": True,
        "motivo": None,
        "entradas": entradas,
        "moeda": "BRL",
        "consumido": {"combustivel_t": m, "preco_brl_t": p, "custo_brl": custo(m)},
        "esperado": {
            "combustivel_t": e2,
            "custo_brl": custo(e2),
            "consumo_referencia_t_t": k_r,
            "ajustado_por": ajustado,
            "nao_ajustado": nao_ajustado,
        },
        "desvio": {
            "combustivel_t": desvio,
            "custo_brl": valor,
            "pct_do_esperado": 100 * desvio / e2,
            "faixa_t": None if faixa_t is None else list(faixa_t),
            "faixa_brl": faixa_brl,
            "cenarios_qualidade_brl": cen_q,
            "cenarios_preco_brl": cen_p,
            "estado": estado,
            "frase": frase,
            "incerteza": incerteza,
        },
        "evitavel": {
            "custo_brl": None,
            "motivo": (
                "Parcela evitável não apurada: depende de verificar um mecanismo específico e "
                "de uma condição de referência tecnicamente justificada. Nenhum percentual de "
                "recuperação é aplicado."
            ),
            "verificacao": verificacao,
        },
        "variacao": var,
        "premissas": _premissas(
            horas_ref, horas, preco_ref_brl_gj, preco_brl_gj, p, politica_custo
        ),
    }


def _incerteza_explicada(analise, v, desvio, centros, p, estado) -> dict | None:
    """De onde vem a faixa do desvio e o que a estreitaria (D97).

    Mesma faixa em toneladas que a principal (U da diferença de consumo × vapor), só que com
    outros U: r = 1 (cada instrumento repete o mesmo erro nos dois períodos) e a fonte
    dominante com metade da incerteza. São cenários com condição explícita; não substituem
    a faixa principal nem mudam o estado do desvio.
    """
    if not analise or estado == "sem_faixa":
        return None

    def faixa(u_t_t):
        u = _f(u_t_t)
        return None if u is None else [desvio - u * v, desvio + u * v]

    def estado_de(f):
        meia = (f[1] - f[0]) / 2
        if min(c - meia for c in centros) > 0:
            return "acima"
        if max(c + meia for c in centros) < 0:
            return "abaixo"
        return "nao_estabelecido"

    def texto(f):
        return (
            f"{_brl(f[0] * p)} a {_brl(f[1] * p)}"
            if p is not None
            else f"{'−' if f[0] < 0 else ''}{_t(f[0])} a {'−' if f[1] < 0 else ''}{_t(f[1])}"
        )

    estabelecido = estado in ("acima", "abaixo")
    parcelas = analise.get("parcelas") or []
    principal = parcelas[0] if parcelas else None
    origem = None
    if principal:
        outras = [x for x in parcelas[1:] if x["parcela_pct"] >= 1]
        origem = (
            f"{principal['nome'][:1].upper()}{principal['nome'][1:]} responde por {num(principal['parcela_pct'], 0)}% da incerteza da faixa"
            + (
                " (" + "; ".join(f"{x['nome']} {num(x['parcela_pct'], 0)}%" for x in outras) + ")."
                if outras
                else "."
            )
        )
    cond = None
    f_cor = faixa(analise.get("U_correlacionada"))
    if f_cor:
        e_cor = estado_de(f_cor)
        nota = (
            f" (o cadastro não registra troca nem recalibração do {principal['nome']} entre eles)"
            if principal and analise.get("mesmo_instrumento")
            else ""
        )
        muda = e_cor in ("acima", "abaixo") and not estabelecido
        cond = {
            "faixa_t": f_cor,
            "faixa_brl": None if p is None else [x * p for x in f_cor],
            "estado": e_cor,
            "frase": (
                f"Se cada instrumento repetir o mesmo erro nos dois períodos{nota}, a faixa "
                f"estreita para {texto(f_cor)}"
                + (": o desvio ficaria estabelecido." if muda else ".")
                + " Para usar essa faixa, confirme com a manutenção que não houve troca nem "
                "recalibração e registre a repetibilidade informada pelo fabricante."
            ),
        }
    melhor = None
    m = analise.get("melhor")
    f_m = faixa(m.get("U")) if m else None
    if f_m:
        e_m = estado_de(f_m)
        melhor = {
            "fonte": m["fonte"],
            "faixa_t": f_m,
            "faixa_brl": None if p is None else [x * p for x in f_m],
            "estado": e_m,
            "frase": (
                f"Se a incerteza declarada do {m['fonte']} caísse {m['descricao']} (por "
                f"exemplo, com uma verificação contra um padrão melhor), a faixa seria de "
                f"{texto(f_m)}"
                + (
                    " e o desvio ficaria estabelecido."
                    if e_m in ("acima", "abaixo") and not estabelecido
                    else "."
                )
            ),
        }
    return {
        "parcelas": parcelas,
        "frase_origem": origem,
        "condicional": cond,
        "melhor": melhor,
        "nota": (
            "Cenários com condição explícita: a faixa e a conclusão principais continuam as "
            "de erros de instrumento independentes (D37, D97)."
        ),
    }


def _variacao(m_r, m, e0, e1, e2, desvio, p_r, p, ef_dh, ef_w, politica) -> dict:
    t = {
        "producao": e0 - m_r,
        "condicao_vapor": e1 - e0 if ef_dh is not None else None,
        "qualidade": e2 - e1 if ef_w is not None else None,
        "nao_explicado": desvio,
    }
    if p is None or p_r is None:
        return {
            "disponivel": False,
            "motivo": (
                f"Sem preço {ORIGEM_PRECO[politica]} "
                + ("nos dois períodos" if p is None and p_r is None else "num dos períodos")
                + ": a variação da conta não pode ser decomposta em reais."
            ),
            "combustivel_t": t,
        }
    brl = {k: None if x is None else x * p for k, x in t.items()}
    brl["preco"] = m_r * (p - p_r)
    return {
        "disponivel": True,
        "motivo": None,
        "custo_referencia_brl": m_r * p_r,
        "custo_brl": m * p,
        "variacao_brl": m * p - m_r * p_r,
        "combustivel_t": t,
        "brl": brl,
    }


def _componentes(
    var, v_r, v, k_r, p_r, p, ef_dh, ef_w, mot_dh, mot_w, pgj_r, pgj, politica
) -> list[dict]:
    t, brl = var["combustivel_t"], var.get("brl") or {}

    def linha(chave: str, base: str, separado: bool = True) -> dict:
        return {
            "id": chave,
            "titulo": TITULOS[chave],
            "pergunta": PERGUNTAS[chave],
            "separado": separado,
            "combustivel_t": t.get(chave),
            "custo_brl": brl.get(chave),
            "base": base,
        }

    preco_base = (
        f"R$ {num(p_r)}/t → R$ {num(p)}/t ({BASE_PRECO[politica]}), aplicada ao "
        "combustível da referência."
        if p is not None and p_r is not None
        else f"Preço {ORIGEM_PRECO[politica]} ausente num dos períodos; parcela não separada."
    )
    if pgj_r is not None and pgj is not None:
        preco_base += (
            f" Por energia: R$ {num(pgj_r)}/GJ → R$ {num(pgj)}/GJ, base PCI úmido dos lotes."
        )
    return [
        linha(
            "producao",
            f"{num(v_r, 1)} t → {num(v, 1)} t de vapor, ao consumo da referência "
            f"({num(k_r, 3)} t de combustível por t de vapor).",
        ),
        linha(
            "condicao_vapor",
            f"Energia por tonelada de vapor: efeito de {num(ef_dh, 1)}% no consumo."
            if ef_dh is not None
            else f"Não separada: {mot_dh}. Permanece no desvio.",
            ef_dh is not None,
        ),
        linha(
            "qualidade",
            f"Umidade e PCI medidos: efeito de {num(ef_w, 1)}% no consumo (inclui a perda nos "
            "gases pela umidade)."
            if ef_w is not None
            else f"Não separada: {mot_w}. Permanece no desvio.",
            ef_w is not None,
        ),
        linha("preco", preco_base, p is not None and p_r is not None),
        linha(
            "nao_explicado",
            "Alvo da investigação; não é automaticamente desperdício recuperável. Inclui as "
            "parcelas não separadas, carga, regime e mecanismos de eficiência (gases, excesso "
            "de ar, purga).",
        ),
    ]


def _premissas(horas_ref, horas, pgj_r, pgj, p, politica) -> list[str]:
    premissa_preco = {
        "recebimentos_do_periodo": (
            "Preço = média ponderada dos recebimentos do período. Compra não é consumo: o "
            "combustível queimado pode ter sido comprado antes, a outro preço."
        ),
        "fifo": (
            "Preço atribuído pela política FIFO, supondo consumo dos lotes mais antigos do "
            "estoque. Depende dos estoques e do histórico de lotes; não comprova a ordem real da queima."
        ),
        "tabela_de_precos": (
            "Preço atribuído pela tabela de preços que cobre todo o período, com os custos "
            "adicionais declarados. A origem está registrada na política do fechamento."
        ),
    }[politica]
    premissas = [
        (
            "Consumo esperado = consumo por tonelada de vapor da referência, ajustado só pelo que "
            "os dados permitem separar (hipótese: mesma eficiência da referência)."
        ),
        premissa_preco,
        (
            "Frete e outros custos variáveis só entram se estiverem no preço informado de cada lote."
            if politica != "tabela_de_precos"
            else "Frete e outros custos variáveis só entram quando declarados na tabela de preços."
        ),
        (
            "Custo do combustível consumido não é necessariamente caixa: contratos com mínimo de "
            "compra ou tarifa fixa não mudam com o consumo."
        ),
        (
            "A faixa vem das medições de consumo e vapor (k = 2); não inclui a incerteza dos "
            "ajustes nem do preço. Cenários de preço e do pátio são variações de premissa, não "
            "intervalos de confiança."
        ),
    ]
    h_r, h = _f(horas_ref), _f(horas)
    if h_r and h and abs(h_r - h) > 1:
        premissas.append(
            f"Períodos com durações diferentes ({num(h_r / 24, 1)} e {num(h / 24, 1)} dias): "
            "a parcela de produção inclui essa diferença."
        )
    if (pgj_r is None or pgj is None) and p is not None:
        premissas.append(
            "Custo por energia (R$/GJ) não informado nesta decomposição pela política "
            f"{BASE_PRECO[politica]}. Com biomassa, R$/t pode confundir quando a umidade muda."
            if politica != "recebimentos_do_periodo"
            else (
                "Custo por energia (R$/GJ) indisponível: com biomassa, R$/t pode confundir quando a "
                "umidade muda."
            )
        )
    return premissas


# ---------------------------------------------------------------- conclusão em um quadro
# Onde o impacto de cada hipótese aparece na decomposição da conta (E16): a umidade
# entra pela parcela de qualidade do combustível; a condição do vapor tem parcela
# própria quando é calculada; as demais ficam na diferença sem explicação.
PARCELA_DA_HIPOTESE = {"umidade_combustivel": "qualidade", "condicao_vapor": "condicao_vapor"}
CONDICAO_EVITAVEL = (
    "Uma parcela só pode ser chamada de evitável depois que a verificação confirmar o "
    "mecanismo e houver uma condição de referência tecnicamente justificada. Os impactos "
    "associados não se somam: podem representar a mesma perda."
)


def _oportunidade(o: dict) -> dict:
    """Aceita a oportunidade da investigação (D90) ou a forma resumida do fechamento."""
    imp = o.get("impacto") if isinstance(o.get("impacto"), dict) else {}
    ver = o.get("verificacao")
    return {
        "id": o.get("id"),
        "titulo": o.get("titulo"),
        "prioridade": o.get("prioridade"),
        "impacto_brl": _f(o["impacto_brl"]) if "impacto_brl" in o else _f(imp.get("custo_brl")),
        "faixa_brl": o["faixa_brl"] if "faixa_brl" in o else imp.get("faixa_brl"),
        "acao": ver.get("acao") if isinstance(ver, dict) else ver,
        "distingue": ver.get("distingue") if isinstance(ver, dict) else None,
    }


def _ponte(v: dict, dias: dict | None) -> dict:
    """Variação da conta em relação à referência em quatro grupos que fecham o total."""
    if not v.get("disponivel"):
        return {"disponivel": False, "motivo": v.get("motivo") or "Variação indisponível."}
    por_id = {x["id"]: x for x in v["componentes"]}

    def valor(k):
        x = por_id.get(k)
        return x["custo_brl"] if x and x["separado"] and x["custo_brl"] is not None else None

    nota_duracao = None
    if dias and dias.get("referencia") and dias.get("comparacao"):
        dr, dc = dias["referencia"], dias["comparacao"]
        if abs(dr - dc) > 0.05 * max(dr, dc):
            nota_duracao = f"inclui a diferença de duração ({num(dr, 0)} → {num(dc, 0)} dias)"
    ajustes = [
        {"id": k, "titulo": TITULOS[k], "custo_brl": valor(k)}
        for k in ("condicao_vapor", "qualidade")
        if valor(k) is not None
    ]
    grupos = [
        {"id": "preco", "titulo": TITULOS["preco"], "custo_brl": valor("preco"), "nota": None},
        {
            "id": "producao",
            "titulo": TITULOS["producao"],
            "custo_brl": valor("producao"),
            "nota": nota_duracao,
        },
        {
            "id": "ajustes",
            "titulo": "Outros ajustes",
            "custo_brl": sum(x["custo_brl"] for x in ajustes) if ajustes else None,
            "nota": ", ".join(x["titulo"].lower() for x in ajustes) if ajustes else None,
            "itens": ajustes,
        },
        {
            "id": "sem_explicacao",
            "titulo": "Sem explicação",
            "custo_brl": valor("nao_explicado"),
            "nota": "igual à diferença da conta do período",
        },
    ]
    soma = sum(g["custo_brl"] for g in grupos if g["custo_brl"] is not None)
    total = v["variacao_brl"]
    if grupos[-1]["custo_brl"] is None or abs(soma - total) > 1e-6 * max(1.0, abs(total)):
        return {
            "disponivel": False,
            "motivo": "As parcelas não fecham a variação total; a ponte não é mostrada.",
        }
    nao_separados = [x["titulo"] for x in v["componentes"] if not x["separado"]]
    return {
        "disponivel": True,
        "motivo": None,
        "referencia_brl": v["custo_referencia_brl"],
        "periodo_brl": v["custo_brl"],
        "variacao_brl": total,
        "dias": dias,
        "grupos": grupos,
        "nao_separados": nao_separados,
        "resposta": resposta_da_ponte(grupos, total, nao_separados),
    }


_PARTE_DA_PONTE = {
    "producao": "pela produção de vapor",
    "preco": "pelo preço do combustível",
    "ajustes": "pelas condições medidas",
    "sem_explicacao": "pelo consumo nas condições comparadas",
}


def resposta_da_ponte(grupos: list[dict], total: float, nao_separados=()) -> str:
    """Uma frase para a pergunta do gestor: a conta mudou por produção, por preço ou por
    consumo nas condições comparadas? (D112). Só reorganiza a ponte, em ordem de tamanho."""
    partes = []
    for g in sorted(
        (g for g in grupos if g["custo_brl"] is not None and abs(g["custo_brl"]) >= 0.5),
        key=lambda g: -abs(g["custo_brl"]),
    ):
        nota = f" — {g['nota']}" if g.get("nota") and g["id"] != "sem_explicacao" else ""
        sentido = "a mais" if g["custo_brl"] > 0 else "a menos"
        partes.append(f"{_brl(abs(g['custo_brl']))} {sentido} {_PARTE_DA_PONTE[g['id']]}{nota}")
    if abs(total) < 0.5:
        frase = "Em relação à referência, a conta ficou igual"
    else:
        frase = (
            f"Em relação à referência, a conta {'subiu' if total > 0 else 'caiu'} "
            f"{_brl(abs(total))}"
        )
    frase += (": " + "; ".join(partes) + ".") if partes else "."
    if nao_separados:
        frase += (
            " Não separados, continuam dentro do consumo nas condições comparadas: "
            + ", ".join(t.lower() for t in nao_separados)
            + "."
        )
    return frase


def conclusao_financeira(conta: dict, oportunidades=(), dias: dict | None = None) -> dict:
    """Quadro único da conclusão financeira (D101, proposta; E16 e D90).

    Entrada: `conta` = resultado de `explicar_conta` (E16); `oportunidades` = lista de
    oportunidades da investigação (D90) ou do fechamento; `dias` = duração em dias da
    referência e do período ({"referencia": float, "comparacao": float}), opcional.

    Saída: a conta do período (custo consumido, esperado nas condições analisadas e a
    diferença sem explicação, com a faixa), a ponte em relação à referência (preço,
    produção, outros ajustes e sem explicação, fechando a variação), e o que falta
    verificar para considerar alguma parcela evitável.

    Só reorganiza números já calculados. "Explicado" quer dizer atribuído a um fator
    medido (preço, produção, qualidade do combustível), não inevitável: a parcela de
    qualidade, por exemplo, pode ter parte evitável. A parcela evitável continua `None`;
    oportunidades não são somadas nem convertidas em economia. Não altera a entrada.
    """
    if not conta or not conta.get("disponivel"):
        return {
            "disponivel": False,
            "motivo": (conta or {}).get("motivo") or "Conta indisponível.",
        }
    cons, esp, des = conta["consumido"], conta["esperado"], conta["desvio"]
    v = conta.get("variacao") or {}
    separados = {x["id"] for x in v.get("componentes", []) if x["separado"]}
    verificacoes = []
    for o in map(_oportunidade, oportunidades or ()):
        if o["prioridade"] not in ("alta", "media") or not o["acao"]:
            continue
        parcela = PARCELA_DA_HIPOTESE.get(o["id"])
        onde = (
            f"na parcela de {TITULOS[parcela].lower()}"
            if parcela in separados
            else "dentro da diferença sem explicação"
        )
        verificacoes.append({**o, "onde": onde})
    if not verificacoes and conta["evitavel"].get("verificacao"):
        verificacoes.append(
            {
                "id": None,
                "titulo": "Próxima verificação",
                "prioridade": None,
                "impacto_brl": None,
                "faixa_brl": None,
                "acao": conta["evitavel"]["verificacao"],
                "distingue": None,
                "onde": None,
            }
        )
    antes = []
    if des["estado"] in ("nao_estabelecido", "sem_faixa"):
        inc = des.get("incerteza") or {}
        partes = [
            "Confirmar que a diferença existe: "
            + FRASE_INCONCLUSIVO[motivo_inconclusivo(des)]
            + ".",
            inc.get("frase_origem"),
            (inc.get("melhor") or {}).get("frase"),
        ]
        antes.append(" ".join(x for x in partes if x))
    return {
        "disponivel": True,
        "motivo": None,
        "frase": des["frase"],
        "estado": des["estado"],
        "consumido": {
            "custo_brl": cons["custo_brl"],
            "combustivel_t": cons["combustivel_t"],
            "preco_brl_t": cons["preco_brl_t"],
        },
        "esperado": {
            "custo_brl": esp["custo_brl"],
            "combustivel_t": esp["combustivel_t"],
            "ajustado_por": list(esp["ajustado_por"]),
        },
        "sem_explicacao": {
            "custo_brl": des["custo_brl"],
            "combustivel_t": des["combustivel_t"],
            "faixa_brl": des["faixa_brl"],
            "estado": des["estado"],
        },
        "ponte": _ponte(v, dias),
        "evitavel": {
            "custo_brl": None,
            "situacao": "Parcela evitável: não apurada",
            "condicao": CONDICAO_EVITAVEL,
            "antes": antes,
            "verificacoes": verificacoes,
            "ainda_no_desvio": list(esp["nao_ajustado"]),
        },
    }
