"""Motor de investigação: regras → JSON de investigação (T13; E12, E14, E15).

Pergunta: "O consumo de combustível mudou. O que os registros sustentam, quais
explicações continuam possíveis e qual verificação separa essas explicações?"

Compara um período de **referência** com um de **comparação** (cada um entre duas
medições de estoque) e devolve um dicionário serializável em JSON.

Vocabulário (revisado na Fase R, D44) — quatro coisas diferentes:
- **mudança detectável**: a diferença é maior que a incerteza U = 2u da diferença
  (`sim`; `condicional` = só se o erro do mesmo instrumento se repetir; `nao`);
- **relevância prática**: o efeito esperado no consumo é pelo menos uma fração (D29) da
  menor mudança de consumo que os dados conseguem detectar;
- **explicação compatível**: mudou de forma detectável, é relevante e empurra o consumo no
  mesmo sentido da mudança medida → status `sustentada` ("os dados sustentam como
  explicação compatível");
- **causa comprovada**: a EULER **nunca** afirma a partir dos dados; exige a verificação
  indicada (`causa_comprovada: false` em toda hipótese).

Um fator que mudou de forma detectável e relevante, mas no sentido **oposto** ao da mudança
de consumo, recebe o status `oposta`: não explica a mudança, mas compensou parte dela e
pode estar escondendo um problema (ex.: combustível mais seco mascarando gases mais quentes).

Além das hipóteses: `fechamento` (as explicações somadas cobrem a mudança medida?),
resíduo direto − indireto com a umidade **compartilhada** pelos dois caminhos (E12
aplicado no número) e robustez ao uso do pátio (recebido × queimado, D38).

Formato proposto (D28): a seção 7 da spec v0.3 não estava disponível.
O texto nunca traz comando operacional: só verificações (AGENTS.md, regra 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import product
from math import exp, isnan, log, sqrt

import pandas as pd

from euler import __version__
from euler.deteccao import Comparacao, comparar
from euler.direto import MEDICOES_DIRETO, BalancoDireto, balanco_direto
from euler.formato import num, pct, plural
from euler.incerteza import (
    Componente,
    Falta,
    Orcamento,
    agregar_por_fonte,
    detectabilidade,
    u_combinada,
)
from euler.indireto import ResultadoPerdaGases, perda_gases
from euler.io import Pacote
from euler.periodos import ResumoPeriodo, resumir_periodo
from euler.tipos import AnaliseBloqueada, Grandeza
from euler.vapor import P_ATM_NIVEL_DO_MAR_BAR

MEDICOES_INDIRETO = (
    "temperatura dos gases",
    "O₂ nos gases",
    "temperatura do ar",
    "umidade das amostras",
    "PCI seco das amostras",
    "composição elementar",
)
STATUS = ("sustentada", "oposta", "possivel", "descartada", "nao_avaliavel")
SUFIXO_CADASTRAR = ": registrar no cadastro de instrumentos, com o tipo da incerteza"
"""Fim dos itens de "o que falta" que pedem cadastrar uma incerteza (a tela agrupa por ele)."""
"""oposta: mudou de forma detectável e relevante, mas empurra o consumo no sentido contrário
ao medido — não explica a mudança, compensou parte dela (Fase R)."""
CRITERIO_RELEVANCIA = 0.5
"""D29: efeito relevante ≥ 0,5 × menor mudança de consumo detectável (proposta)."""
ALTERNATIVAS_D29 = (0.0, 0.5, 1.0)
LIMITACOES_INDIRETO = (
    (
        "cp constante (modo de referência): com cp(T) a perda sai 0,3 a 0,4 p.p. menor nos "
        "casos golden (sensibilidade calculada nessas condições)"
    ),
    "umidade do ar de combustão não incluída (+0,2 p.p. no caso G01 a 25 °C e UR 60%)",
    (
        "O₂ suposto em base seca: se o analisador medir em base úmida, a perda fica "
        "subestimada (0,4 a 1,7 p.p. nos casos golden)"
    ),
    "CO e incombustos fora desta perda",
    "orvalho ácido não modelado",
    "incerteza da composição elementar não declarada (fora do contrato de dados)",
)
ROTULO_ENTRADA = {
    "t_gases_c": "temperatura dos gases",
    "o2_seco_pct": "O₂",
    "t_ar_c": "temperatura do ar",
    "umidade_bu_frac": "umidade",
    "pci_seco_mj_kg": "PCI seco",
}
PASSO = {
    "t_gases_c": 1.0,
    "o2_seco_pct": 0.1,
    "t_ar_c": 1.0,
    "umidade_bu_frac": 0.005,
    "pci_seco_mj_kg": 0.1,
}
COMPARTILHADAS = ("umidade_bu_frac", "pci_seco_mj_kg")
"""Entradas usadas pelos dois caminhos (E12): no resíduo entram uma vez só, pelo gradiente
conjunto (auditoria A2)."""


# ---------------------------------------------------------------- caminho indireto


@dataclass
class Indireto:
    """Perda nos gases de um período, com orçamento de incerteza por componente (E15)."""

    resultado: ResultadoPerdaGases | None
    perda: Grandeza | None
    entradas: dict[str, float]
    sensibilidades: dict[str, float] = field(default_factory=dict)
    bloqueio: AnaliseBloqueada | None = None


def _entradas_indireto(
    r: ResumoPeriodo, umidade: float | None = None
) -> dict[str, float] | AnaliseBloqueada:
    for chave_bloqueio in ("ponto_gases", "instrumento_o2"):
        if chave_bloqueio in r.bloqueios:
            return r.bloqueios[chave_bloqueio]
    faltas = []
    for chave, nome in (
        ("t_gases_c", "temperatura dos gases"),
        ("o2_seco_pct", "O₂ nos gases"),
        ("t_ar_c", "temperatura do ar de combustão"),
    ):
        if chave not in r.leituras:
            faltas.append(nome)
    if r.umidade_mistura is None:
        faltas.append("umidade medida dos lotes")
    if r.composicao is None or r.pci_seco_mistura is None:
        faltas.append("análise elementar e PCI seco do combustível")
    if faltas:
        return AnaliseBloqueada(
            "Perda nos gases não calculada: falta " + ", ".join(faltas) + ".", faltas
        )
    return {
        "t_gases_c": r.leituras["t_gases_c"].media,
        "o2_seco_pct": r.leituras["o2_seco_pct"].media,
        "umidade_bu_frac": r.umidade_mistura.valor if umidade is None else umidade,
        "t_ar_c": r.leituras["t_ar_c"].media,
        "pci_seco_mj_kg": r.pci_seco_mistura,
    }


def _perda(r: ResumoPeriodo, entradas: dict[str, float], p_gases: float) -> ResultadoPerdaGases:
    return perda_gases(composicao_seca=r.composicao, p_gases_bar_abs=p_gases, **entradas)


def indireto_periodo(r: ResumoPeriodo, p_gases: float, umidade: float | None = None) -> Indireto:
    """Perda nos gases com as médias do período; incerteza por derivadas parciais (E15),
    com cada componente levando a chave da sua fonte de erro (para as diferenças)."""
    entradas = _entradas_indireto(r, umidade)
    if isinstance(entradas, AnaliseBloqueada):
        return Indireto(None, None, {}, bloqueio=entradas)
    try:
        res = _perda(r, entradas, p_gases)
    except AnaliseBloqueada as b:
        return Indireto(None, None, entradas, bloqueio=b)
    fontes = {
        "t_gases_c": r.leituras_grandeza.get("t_gases_c"),
        "o2_seco_pct": r.leituras_grandeza.get("o2_seco_pct"),
        "t_ar_c": r.leituras_grandeza.get("t_ar_c"),
        "umidade_bu_frac": r.umidade_mistura,
        "pci_seco_mj_kg": r.pci_seco,
    }
    orc, sens = Orcamento(), {}
    for chave, g in fontes.items():
        try:
            mais = _perda(r, {**entradas, chave: entradas[chave] + PASSO[chave]}, p_gases).perda_pct
        except AnaliseBloqueada:
            orc.faltam.append(
                Falta(f"sensibilidade à {ROTULO_ENTRADA[chave]} (cálculo bloqueado)", False)
            )
            continue
        sens[chave] = (mais - res.perda_pct) / PASSO[chave]
        if g is None or g.orcamento is None:
            orc.faltam.append(Falta(f"incerteza de {ROTULO_ENTRADA[chave]}", False))
            continue
        for c in g.orcamento.componentes:
            orc.componentes.append(
                Componente(
                    f"{ROTULO_ENTRADA[chave]}: {c.nome}",
                    sens[chave] * c.u_rel * g.valor / res.perda_pct,
                    c.natureza,
                    c.chave,
                    c.nota,
                    chave,
                )
            )
        orc.nao_incluidos += g.orcamento.nao_incluidos
        orc.faltam += g.orcamento.faltam
    orc.nao_incluidos = list(dict.fromkeys(orc.nao_incluidos + list(LIMITACOES_INDIRETO)))
    orc.faltam = list(dict.fromkeys(orc.faltam))
    perda = Grandeza(
        res.perda_pct,
        "% do PCI",
        "estimado",
        orc.incerteza_k2(res.perda_pct),
        "perda sensível nos gases com as médias do período (E6, cp constante)",
        orc,
    )
    return Indireto(res, perda, entradas, sens)


def _efeito_isolado(
    ref: ResumoPeriodo, i_ref: Indireto, i_comp: Indireto, chave: str, p_gases: float
) -> float | None:
    """Mudança na perda (p.p.) trocando só uma entrada da referência pela da comparação."""
    if i_ref.resultado is None or chave not in i_comp.entradas:
        return None
    try:
        trocada = _perda(ref, {**i_ref.entradas, chave: i_comp.entradas[chave]}, p_gases)
    except AnaliseBloqueada:
        return None
    return trocada.perda_pct - i_ref.resultado.perda_pct


# ---------------------------------------------------------------- resíduo direto − indireto


@dataclass
class OrcamentoResiduo:
    """Incerteza do resíduo R = −Δ(100·η) − Δperda, em p.p., com cada fonte uma vez só.

    contribuicoes: por período, (contribuição com sinal em p.p., chave da fonte, nome).
    faltam: incertezas necessárias não informadas em qualquer dos dois caminhos (A3).
    """

    contribuicoes: dict[str, list[tuple[float, str | None, str]]]
    faltam: list[Falta]

    @property
    def situacao(self) -> str:
        if not self.faltam:
            return "completo"
        return "parcial" if any(self.contribuicoes.values()) else "indisponivel"

    def u(self, r_instrumento: float) -> float:
        """Junta a mesma fonte dentro de cada período e combina os períodos (GUM 5.2.2)."""
        lista = []
        for itens in self.contribuicoes.values():
            lista += agregar_por_fonte([(u, chave) for u, chave, _ in itens])
        return u_combinada(lista, r_instrumento)

    def json(self) -> dict:
        completo = self.situacao == "completo"
        return {
            "situacao": self.situacao,
            "faltam": [f.nome for f in self.faltam],
            "incerteza_k2_r0": 2 * self.u(0.0) if completo else None,
            "incerteza_k2_r1": 2 * self.u(1.0) if completo else None,
            **{
                periodo: [{"fonte": n, "chave": ch, "u_pp": u} for u, ch, n in itens]
                for periodo, itens in self.contribuicoes.items()
            },
        }


def orcamento_residuo(
    periodos: tuple[tuple[str, ResumoPeriodo, BalancoDireto, Indireto, float], ...],
) -> OrcamentoResiduo:
    """Orçamento do resíduo (E12 no número, auditoria A2).

    periodos: (nome, resumo, balanço direto, indireto, sinal no resíduo: +1 referência,
    −1 comparação). Cada entrada primária contribui uma vez: as fontes de um só caminho
    entram pelo orçamento dele; as **compartilhadas** (umidade e PCI seco) saem dos dois
    orçamentos e entram pelo gradiente conjunto ∂R/∂x = sinal·(100·∂η/∂x + ∂perda/∂x).
    Só o erro de medição dessas entradas entra: a variação entre lotes é dispersão do
    processo, não erro da média (ER-1).
    """
    contrib, faltam = {}, []
    for nome, r, b, ind, sinal in periodos:
        eta, perda, lista = b.eficiencia, ind.perda, []
        for c in eta.orcamento.componentes:
            if c.entrada not in COMPARTILHADAS:
                lista.append((sinal * 100 * c.u_rel * eta.valor, c.chave, f"η: {c.nome}"))
        for c in perda.orcamento.componentes:
            if c.entrada not in COMPARTILHADAS:
                lista.append((sinal * c.u_rel * perda.valor, c.chave, f"perda: {c.nome}"))
        pci_u, w = r.pci_umido_mistura.valor, r.umidade_mistura.valor
        deta = {  # ∂η/∂x com Q e M fixos: η = Q / (M · PCI_u), PCI_u = (1 − w)·PCI_s − 2,442·w
            "umidade_bu_frac": eta.valor * (r.pci_seco_mistura + 2.442) / pci_u,
            "pci_seco_mj_kg": -eta.valor * (1 - w) / pci_u,
        }
        for entrada, g in (("umidade_bu_frac", r.umidade_mistura), ("pci_seco_mj_kg", r.pci_seco)):
            if g is None or g.orcamento is None:
                continue
            s = sinal * (100 * deta[entrada] + ind.sensibilidades.get(entrada, 0.0))
            for c in g.orcamento.componentes:
                if c.natureza == "instrumental":
                    lista.append(
                        (s * c.u_rel * g.valor, c.chave, f"{ROTULO_ENTRADA[entrada]}: {c.nome}")
                    )
        contrib[nome] = lista
        faltam += eta.orcamento.faltam + perda.orcamento.faltam
    return OrcamentoResiduo(contrib, list(dict.fromkeys(faltam)))


# ---------------------------------------------------------------- utilidades


def _simples(pontos_log: float | None) -> float | None:
    """Pontos log (100·ln) → variação percentual simples."""
    return None if pontos_log is None else 100 * (exp(pontos_log / 100) - 1)


def _lista(itens) -> str:
    itens = list(itens)
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def _subiu(delta: float) -> str:
    return "subiu" if delta > 0 else "caiu"


def _sinal(x: float, casas: int = 1) -> str:
    x = round(float(x), casas) + 0.0  # evita "-0,0"
    return ("+" if x >= 0 else "") + num(x, casas)


def _curto(titulo: str) -> str:
    """Título da hipótese sem o parêntese explicativo, começando em minúscula."""
    base = titulo.split(" (")[0].strip()
    return base[:1].lower() + base[1:]


def _com_efeito(h: dict) -> str:
    efeito = h["efeito"]["consumo_pct"]
    return _curto(h["titulo"]) + ("" if efeito is None else f" ({_sinal(efeito)}%)")


def _acao_curta(acao: str) -> str:
    """Primeira parte da próxima verificação, sem parênteses (para o resumo)."""
    texto = re.sub(r"\s*\([^()]*\)", "", acao)
    texto = re.split(r"; |\. ", texto, maxsplit=1)[0].strip().rstrip(".")
    return texto + "."


def _resumo(
    c_cons: Comparacao,
    hipoteses: list[dict],
    abstem: bool,
    motivo: str,
    pendentes: list[dict],
    prox: dict,
) -> list[str]:
    """Resultado em até três frases curtas (D63): o consumo; o que explica e o que foi
    descartado (ou por que não dá para concluir); a próxima verificação.

    Só junta textos e números que a investigação já calculou: nenhuma conta nova.
    """
    frases = []
    if not c_cons.disponivel:
        frases.append("Não dá para saber se o consumo por tonelada de vapor mudou.")
    elif c_cons.detectabilidade == "sim":
        v = 100 * c_cons.delta / c_cons.referencia
        frases.append(f"O consumo por tonelada de vapor {_subiu(c_cons.delta)} {num(abs(v), 1)}%.")
    else:
        v = 100 * c_cons.delta / c_cons.referencia
        frases.append(
            f"O consumo por tonelada de vapor variou {_sinal(v)}%, mas não dá para afirmar "
            "que mudou."
        )

    def ordem(lista):
        return sorted(lista, key=lambda h: -abs(h["efeito"]["consumo_pct"] or 0))

    sustentadas = ordem([h for h in hipoteses if h["status"] == "sustentada"])
    descartadas = [
        h for h in hipoteses if h["status"] == "descartada" and h["id"] != "perdas_nao_medidas"
    ]
    descartado = (
        f"; descartado: {_lista(_curto(h['titulo']) for h in descartadas)}" if descartadas else ""
    )
    if not abstem and sustentadas:
        frases.append(
            "Explicações compatíveis com os dados: "
            + _lista(_com_efeito(h) for h in sustentadas)
            + descartado
            + "."
        )
    elif abstem and pendentes:
        pend = _lista(_com_efeito(h) for h in ordem(pendentes))
        if sustentadas:
            frases.append(
                f"Não dá para concluir: {_lista(_com_efeito(h) for h in sustentadas)} é "
                f"compatível com os dados, mas {pend} ainda não está confirmado{descartado}."
            )
        else:
            frases.append(
                f"Não dá para concluir: {pend} explicaria a mudança, mas ainda não está "
                f"confirmado{descartado}."
            )
    elif abstem and not c_cons.disponivel:
        mudaram = [
            h
            for h in hipoteses
            if h["status"] in ("sustentada", "oposta", "possivel")
            and h["id"] != "perdas_nao_medidas"
            and h["avaliacao"]["mudanca_detectavel"] == "sim"
        ]
        if mudaram:
            frases.append(
                "Mesmo assim, mudou de forma detectável: "
                + _lista(_curto(h["titulo"]) for h in mudaram)
                + "."
            )
    elif abstem:
        frases.append(f"Não dá para concluir: {motivo}.")
    frases.append(f"Próxima verificação: {_acao_curta(prox['acao'])}")
    return frases


def _limpar(obj):
    """Converte tipos do numpy e NaN em tipos simples, para o JSON."""
    if isinstance(obj, dict):
        return {k: _limpar(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_limpar(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, str):
        obj = obj.item()
    if isinstance(obj, float) and isnan(obj):
        return None
    return obj


def _grandeza_json(g: Grandeza | None) -> dict | None:
    """Valor, origem e incerteza; com o orçamento incompleto, a incerteza é None e a parte
    conhecida sai separada, identificada como parcial (A3)."""
    if g is None:
        return None
    orc = g.orcamento
    parcial = orc is not None and orc.situacao == "parcial"
    return {
        "valor": g.valor,
        "unidade": g.unidade,
        "origem": g.origem,
        "incerteza_k2": g.incerteza,
        "situacao_incerteza": None if orc is None else orc.situacao,
        "faltam_na_incerteza": [] if orc is None else [f.nome for f in orc.faltam],
        "incerteza_parcial_k2": 2 * orc.u_rel() * abs(g.valor) if parcial else None,
        "nota": g.nota,
        "nao_incluido_na_incerteza": [] if orc is None else orc.nao_incluidos,
    }


def _comparacao_json(c: Comparacao) -> dict:
    return {
        "nome": c.nome,
        "unidade": c.unidade,
        "referencia": c.referencia,
        "comparacao": c.comparacao,
        "variacao": c.delta,
        "incerteza_variacao": c.incerteza_delta,
        "incerteza_variacao_correlacionada": c.incerteza_delta_correlacionada,
        "detectabilidade": c.detectabilidade,
        "detectavel": c.detectavel,
        "faltam_na_incerteza": list(c.faltam),
    }


def _custo_vapor(r: ResumoPeriodo, b: BalancoDireto) -> Grandeza | None:
    """Custo do combustível por tonelada de vapor: R$/GJ × GJ/t (E14)."""
    if r.preco_brl_gj is None or b.intensidade_gj_por_t is None:
        return None
    i = b.intensidade_gj_por_t
    return Grandeza(
        r.preco_brl_gj * i.valor,
        "R$/t de vapor",
        "estimado",
        None if i.incerteza is None else r.preco_brl_gj * i.incerteza,
        "preço da energia × intensidade",
        i.orcamento,
    )


def _texto_mudanca(
    c: Comparacao, nome: str, unidade: str, casas: int, como_pct: bool = False
) -> str:
    """Frase sobre a mudança de um fator. `nome` já vem com artigo."""
    inicio = nome[0].upper() + nome[1:]
    if not c.disponivel:
        return f"Faltam dados para comparar {nome} nos dois períodos."

    def f(v: float) -> str:
        if como_pct:
            return pct(v)
        return f"{num(v, casas)}%" if unidade == "%" else f"{num(v, casas)} {unidade}".strip()

    def fu(v: float) -> str:
        """Incerteza de uma diferença: em pontos percentuais quando a grandeza já é %."""
        if como_pct:
            return f"{num(100 * v, 1)} p.p."
        return f"{num(v, casas)} p.p." if unidade == "%" else f(v)

    variacao = f"{f(c.referencia)} → {f(c.comparacao)}"
    if c.detectabilidade == "nao" and c.faltam:
        return (
            f"{inicio} ficou estável ({variacao}): a diferença cabe até na parte conhecida da "
            f"incerteza (falta cadastrar a {_lista(c.faltam)})."
        )
    if c.detectabilidade == "nao":
        return (
            f"{inicio} ficou estável ({variacao}): a diferença está dentro da incerteza "
            f"(±{fu(c.incerteza_delta_correlacionada)})."
        )
    if c.detectabilidade == "condicional" and c.faltam:
        return (
            f"{inicio} variou ({variacao}), mas falta cadastrar a {_lista(c.faltam)}: a diferença só é maior "
            "que a incerteza se o erro desse instrumento se repetir nos dois períodos."
        )
    if c.detectabilidade == "condicional":
        return (
            f"{inicio} variou ({variacao}), mas a diferença só é maior que a incerteza se o erro do "
            "mesmo instrumento se repetir nos dois períodos."
        )
    if c.detectabilidade is None:
        return (
            f"{inicio} variou ({variacao}), mas falta incerteza declarada para saber se é mais que "
            "o erro de medição."
        )
    return (
        f"{inicio} {_subiu(c.delta)} de forma detectável ({variacao}, incerteza "
        f"±{fu(c.incerteza_delta)})."
    )


def _avaliar(
    c: Comparacao, efeito: float | None, limiar: float | None, cons: Comparacao
) -> tuple[str, dict]:
    """Status de uma hipótese pelos quatro critérios (D44); devolve (status, avaliação)."""
    av = {
        "mudanca_detectavel": c.detectabilidade if c.disponivel else None,
        "relevante": None if efeito is None or limiar is None else bool(abs(efeito) >= limiar),
        "compativel_com_consumo": None,
        "causa_comprovada": False,
    }
    if not c.disponivel:
        return "nao_avaliavel", av
    if cons.disponivel and cons.detectabilidade in ("sim", "condicional") and efeito is not None:
        av["compativel_com_consumo"] = bool((efeito > 0) == (cons.delta > 0))
    if av["mudanca_detectavel"] == "nao" or av["relevante"] is False:
        return "descartada", av
    if av["compativel_com_consumo"] is False:
        return ("oposta" if av["mudanca_detectavel"] == "sim" else "descartada"), av
    if (
        av["mudanca_detectavel"] == "sim"
        and av["compativel_com_consumo"] is True
        and cons.detectabilidade == "sim"
    ):
        return "sustentada", av
    return "possivel", av


def _complemento(
    av: dict, efeito: float | None, limiar: float | None, fator: float, cons: Comparacao
) -> str:
    """Explica, em palavras, o critério que decidiu o status."""
    if av["mudanca_detectavel"] in (None, "nao"):
        return ""
    if av["relevante"] is False:
        minimo = limiar / fator if fator else limiar
        return (
            f" O efeito esperado no consumo ({_sinal(_simples(efeito), 2)}%) é pequeno demais para aparecer "
            f"nos dados (menor mudança detectável ≈ {num(minimo)}%)."
        )
    if av["mudanca_detectavel"] == "condicional":
        return ""
    if av["compativel_com_consumo"] is False:
        return (
            f" Mudou de verdade, mas empurra o consumo para o lado contrário do que foi medido "
            f"(efeito estimado {_sinal(_simples(efeito))}%): compensou parte da mudança e pode "
            "estar escondendo um problema. Vale verificar mesmo assim."
        )
    if not cons.disponivel:
        return " Sem o consumo por tonelada de vapor, não dá para confirmar o efeito no consumo."
    if cons.detectabilidade == "nao":
        return (
            " Mas o consumo não mudou de forma detectável: outro fator pode ter compensado, ou o "
            "efeito ficou dentro da incerteza."
        )
    if cons.detectabilidade in ("condicional", None):
        return (
            " A mudança de consumo não é detectável com segurança: não dá para confirmar o efeito."
        )
    return " Explicação compatível com os dados; não é causa comprovada."


def _hipotese(
    id_: str,
    titulo: str,
    status: str,
    avaliacao: dict,
    porque: str,
    verificacao: str,
    evidencia: str,
    medicoes: tuple[str, ...] | list[str],
    efeito_perda_pp: float | None = None,
    efeito_consumo_pct: float | None = None,
    faixa_consumo_pct: tuple[float, float] | None = None,
) -> dict:
    assert status in STATUS
    return {
        "id": id_,
        "titulo": titulo,
        "status": status,
        "avaliacao": avaliacao,
        "porque": porque,
        "efeito": {
            "perda_gases_pp": efeito_perda_pp,
            "consumo_pct": _simples(efeito_consumo_pct),
            "consumo_pct_faixa_patio": None
            if faixa_consumo_pct is None
            else [_simples(x) for x in faixa_consumo_pct],
        },
        "evidencia": evidencia,
        "medicoes": list(medicoes),
        "verificacao": verificacao,
        "para_comprovar": verificacao,
    }


# ---------------------------------------------------------------- investigação


def investigar(
    pacote: Pacote,
    referencia: tuple[pd.Timestamp, pd.Timestamp],
    comparacao: tuple[pd.Timestamp, pd.Timestamp],
    criterio_relevancia: float = CRITERIO_RELEVANCIA,
) -> dict:
    """Compara dois períodos e devolve o JSON de investigação (ver docstring do módulo).

    Bloqueia (AnaliseBloqueada) se os períodos se sobrepõem: a comparação não teria sentido.
    """
    if not (referencia[1] <= comparacao[0] or comparacao[1] <= referencia[0]):
        raise AnaliseBloqueada(
            "Os períodos de referência e de comparação se sobrepõem: escolha períodos separados.",
            ["dois períodos sem sobreposição"],
        )
    ref, comp = resumir_periodo(pacote, *referencia), resumir_periodo(pacote, *comparacao)
    b_ref, b_comp = balanco_direto(ref), balanco_direto(comp)
    p_gases = pacote.p_atm_bar or P_ATM_NIVEL_DO_MAR_BAR
    i_ref, i_comp = indireto_periodo(ref, p_gases), indireto_periodo(comp, p_gases)

    def leitura(chave: str, nome: str, unidade: str) -> Comparacao:
        return comparar(
            nome, unidade, ref.leituras_grandeza.get(chave), comp.leituras_grandeza.get(chave)
        )

    c_tg = leitura("t_gases_c", "temperatura dos gases", "°C")
    c_o2 = leitura("o2_seco_pct", "O₂ nos gases", "%")
    c_tar = leitura("t_ar_c", "temperatura do ar de combustão", "°C")
    c_co = comparar("CO nos gases", "ppm", ref.leituras.get("co_ppm"), comp.leituras.get("co_ppm"))
    c_w = comparar(
        "umidade do combustível recebido", "fração", ref.umidade_mistura, comp.umidade_mistura
    )
    c_dh = comparar("energia por kg de vapor", "MJ/kg", b_ref.delta_h_mj_kg, b_comp.delta_h_mj_kg)
    c_cons = comparar("consumo específico", "t/t", b_ref.consumo_t_por_t, b_comp.consumo_t_por_t)
    c_eta = comparar("eficiência direta", "fração", b_ref.eficiencia, b_comp.eficiencia)
    c_custo = comparar(
        "custo do vapor", "R$/t", _custo_vapor(ref, b_ref), _custo_vapor(comp, b_comp)
    )
    c_perda = comparar("perda nos gases", "% do PCI", i_ref.perda, i_comp.perda)

    # ------------------------------------------------ o que mudou: consumo
    if c_cons.disponivel:
        variacao_pct = 100 * c_cons.delta / c_cons.referencia
        u0 = (
            None
            if c_cons.incerteza_delta is None
            else 100 * c_cons.incerteza_delta / c_cons.referencia
        )
        u1 = (
            None
            if c_cons.incerteza_delta_correlacionada is None
            else 100 * c_cons.incerteza_delta_correlacionada / c_cons.referencia
        )
        de_para = (
            f"de {num(c_cons.referencia, 3)} para {num(c_cons.comparacao, 3)} t por t de vapor"
        )
        if c_cons.detectabilidade == "sim":
            frase_consumo = (
                f"O consumo de combustível por tonelada de vapor {_subiu(c_cons.delta)} "
                f"{num(abs(variacao_pct), 1)}% ({de_para}; incerteza ±{num(u0, 1)}%)."
            )
        elif c_cons.detectabilidade == "condicional" and c_cons.faltam:
            frase_consumo = (
                f"O consumo por tonelada de vapor variou {_sinal(variacao_pct)}% ({de_para}), mas "
                f"falta cadastrar a {_lista(c_cons.faltam)}: só é uma mudança real se o erro desses "
                "instrumentos for o mesmo nos dois períodos."
            )
        elif c_cons.detectabilidade == "condicional":
            frase_consumo = (
                f"O consumo por tonelada de vapor variou {_sinal(variacao_pct)}% ({de_para}). Só é "
                "uma mudança real se o erro do medidor de vapor for o mesmo nos dois períodos "
                f"(incerteza ±{num(u1, 1)}% nesse caso; ±{num(u0, 1)}% se não for)."
            )
        elif c_cons.detectabilidade == "nao":
            frase_consumo = (
                f"O consumo por tonelada de vapor variou {_sinal(variacao_pct)}% ({de_para}), dentro "
                "da incerteza das medições"
                + (
                    f" (mesmo sem {_lista(c_cons.faltam)})"
                    if c_cons.faltam
                    else f" (±{num(u1, 1)}%)"
                )
                + ": não dá para afirmar que mudou."
            )
        else:
            frase_consumo = (
                f"O consumo por tonelada de vapor variou {_sinal(variacao_pct)}% ({de_para}); sem "
                + (
                    f"{_lista(c_cons.faltam)}"
                    if c_cons.faltam
                    else "incerteza declarada dos instrumentos"
                )
                + ", não dá para dizer se é mais que o erro de medição."
            )
    else:
        motivos = [b.motivo for b in (*b_ref.bloqueios, *b_comp.bloqueios)]
        frase_consumo = "Não dá para saber se o consumo por tonelada de vapor mudou: " + " ".join(
            dict.fromkeys(motivos)
        )

    # ------------------------------------------------ efeitos de cada fator (no consumo, %)
    if b_ref.eficiencia is not None:
        eta_ref, eta_origem = b_ref.eficiencia.valor, "balanço direto da referência"
    elif i_ref.resultado is not None:
        eta_ref = 1 - i_ref.resultado.perda_pct / 100
        eta_origem = "limite superior (só a perda nos gases): os efeitos ficam subestimados"
    else:
        eta_ref, eta_origem = None, None

    def por_perda(dp: float | None) -> float | None:
        """Efeito no consumo (pontos log, %) de uma mudança de perda dp (p.p.):
        consumo ∝ 1/η → −100·ln(1 − dp/(100·η_ref)). Ver ER-7."""
        if dp is None or eta_ref is None:
            return None
        return -100 * log(1 - dp / (100 * eta_ref))

    ef_tg = _efeito_isolado(ref, i_ref, i_comp, "t_gases_c", p_gases)
    ef_o2 = _efeito_isolado(ref, i_ref, i_comp, "o2_seco_pct", p_gases)
    ef_tar = _efeito_isolado(ref, i_ref, i_comp, "t_ar_c", p_gases)
    ef_w_perda = _efeito_isolado(ref, i_ref, i_comp, "umidade_bu_frac", p_gases)
    ef_w = faixa_w = None
    if ref.pci_umido_mistura is not None and comp.pci_umido_mistura is not None:
        parte_perda = por_perda(ef_w_perda) or 0
        ef_w = -100 * log(comp.pci_umido_mistura.valor / ref.pci_umido_mistura.valor) + parte_perda
        if ref.pci_queimado is not None and comp.pci_queimado is not None:
            plaus_ref = [v for v in (ref.pci_queimado.recebido, ref.pci_queimado.fifo) if v]
            plaus_comp = [v for v in (comp.pci_queimado.recebido, comp.pci_queimado.fifo) if v]
            valores = [-100 * log(c / a) + parte_perda for a, c in product(plaus_ref, plaus_comp)]
            faixa_w = (min(valores), max(valores))
    ef_dh = None if not c_dh.disponivel else 100 * log(c_dh.comparacao / c_dh.referencia)

    # menor efeito relevante (D29): fração da menor mudança de consumo detectável (r = 0)
    def limiar(fator: float) -> float | None:
        if c_cons.incerteza_delta is not None:
            return fator * 100 * c_cons.incerteza_delta / c_cons.referencia
        if c_perda.incerteza_delta is not None and eta_ref:
            return fator * c_perda.incerteza_delta / eta_ref
        return None

    def avaliar_fatores(fator: float) -> dict[str, tuple[str, dict]]:
        lim = limiar(fator)
        return {
            "temperatura_gases": _avaliar(c_tg, por_perda(ef_tg), lim, c_cons),
            "excesso_ar": _avaliar(c_o2, por_perda(ef_o2), lim, c_cons),
            "umidade_combustivel": _avaliar(c_w, ef_w, lim, c_cons),
            "condicao_vapor": _avaliar(c_dh, ef_dh, lim, c_cons),
        }

    avaliacoes = avaliar_fatores(criterio_relevancia)
    lim = limiar(criterio_relevancia)

    def complemento(av: dict, efeito: float | None) -> str:
        return _complemento(av, efeito, lim, criterio_relevancia, c_cons)

    def titulo(c: Comparacao, subiu: str, caiu: str, neutro: str) -> str:
        if c.disponivel and c.detectabilidade in ("sim", "condicional"):
            return subiu if c.delta > 0 else caiu
        if c_cons.disponivel and c_cons.detectabilidade == "sim":
            return subiu if c_cons.delta > 0 else caiu
        return neutro

    hipoteses = []
    st, av = avaliacoes["temperatura_gases"]
    porque = _texto_mudanca(c_tg, "a temperatura dos gases", "°C", 1)
    if c_tg.detectabilidade == "sim" and ef_tg is not None:
        porque += f" Só isso muda a perda nos gases em {_sinal(ef_tg)} p.p. do PCI."
    porque += complemento(av, por_perda(ef_tg))
    hipoteses.append(
        _hipotese(
            "temperatura_gases",
            titulo(
                c_tg,
                "Mais calor saindo pela chaminé (temperatura dos gases)",
                "Menos calor saindo pela chaminé (temperatura dos gases)",
                "Calor saindo pela chaminé (temperatura dos gases)",
            ),
            st,
            av,
            porque,
            "Comparar a leitura do termopar da chaminé com um termômetro de referência. Se a "
            "leitura se confirmar, inspecionar as superfícies de troca (fuligem ou incrustação) "
            "na próxima parada programada.",
            "Uma fonte: o termopar dos gases (caminho indireto). O balanço direto só corrobora se "
            "o resíduo direto − indireto ficar dentro da incerteza; os dois caminhos compartilham "
            "a umidade e o PCI das amostras.",
            ("temperatura dos gases",),
            ef_tg,
            por_perda(ef_tg),
        )
    )
    st, av = avaliacoes["excesso_ar"]
    porque = _texto_mudanca(c_o2, "o O₂ nos gases", "%", 1)
    if c_o2.detectabilidade == "sim" and ef_o2 is not None:
        porque += f" Só isso muda a perda nos gases em {_sinal(ef_o2)} p.p. do PCI."
    porque += complemento(av, por_perda(ef_o2))
    hipoteses.append(
        _hipotese(
            "excesso_ar",
            titulo(
                c_o2,
                "O₂ maior nos gases",
                "O₂ menor nos gases",
                "O₂ diferente nos gases",
            ),
            st,
            av,
            porque,
            "Conferir a calibração do analisador de O₂, a base da medição (seca ou úmida), "
            "o ponto físico e comparar com uma medição portátil no mesmo ponto. Se a leitura se "
            "confirmar, comparar O₂ em pontos a montante e a jusante para separar excesso de ar "
            "na combustão de entrada de ar falso no caminho dos gases.",
            "Uma fonte: o analisador de O₂ (caminho indireto). O₂ maior, sozinho, não separa "
            "excesso de ar na combustão de entrada de ar falso após a zona de combustão.",
            ("O₂ nos gases",),
            ef_o2,
            por_perda(ef_o2),
        )
    )
    st, av = avaliacoes["umidade_combustivel"]
    porque = _texto_mudanca(c_w, "a umidade do combustível recebido", "", 3, como_pct=True)
    mudancas = {
        f: comp.umidade_por_fornecedor[f] - ref.umidade_por_fornecedor[f]
        for f in comp.umidade_por_fornecedor
        if f in ref.umidade_por_fornecedor
    }
    forn_maior = max(mudancas, key=mudancas.get) if mudancas else None
    if c_w.detectabilidade == "sim" and ef_w is not None:
        porque += (
            f" Cada tonelada recebida entrega {'menos' if ef_w > 0 else 'mais'} energia "
            f"(efeito estimado {_sinal(_simples(ef_w))}% no consumo"
        )
        if faixa_w is not None:
            porque += (
                f"; entre {_sinal(_simples(faixa_w[0]))}% e {_sinal(_simples(faixa_w[1]))}% conforme o uso do pátio, "
                "porque o combustível queimado não é exatamente o recebido"
            )
        porque += ")."
        if forn_maior and mudancas[forn_maior] > 0:
            porque += (
                f" A maior alta foi no fornecedor {forn_maior} "
                f"({pct(ref.umidade_por_fornecedor[forn_maior])} → "
                f"{pct(comp.umidade_por_fornecedor[forn_maior])})."
            )
    porque += complemento(av, ef_w)
    hipoteses.append(
        _hipotese(
            "umidade_combustivel",
            titulo(
                c_w,
                "Combustível mais úmido (menos energia por tonelada)",
                "Combustível mais seco (mais energia por tonelada)",
                "Umidade do combustível",
            ),
            st,
            av,
            porque,
            "Conferir a amostragem de umidade dos lotes"
            + (f" do fornecedor {forn_maior}" if forn_maior and st == "sustentada" else "")
            + " (método de estufa e número de amostras por lote) e medir a umidade do pátio.",
            "Uma fonte: as amostras de umidade. O mesmo dado entra no balanço direto e na perda "
            "nos gases, então não há corroboração independente.",
            ("umidade das amostras", "PCI seco das amostras"),
            ef_w_perda,
            ef_w,
            faixa_w,
        )
    )
    st, av = avaliacoes["condicao_vapor"]
    if not c_dh.disponivel:
        porque = (
            "Faltam pressão do vapor, altitude ou temperatura da água de alimentação em um dos "
            "períodos."
        )
    else:
        fim_frase = {
            "nao": ": dentro da incerteza.",
            "condicional": ": só detectável se os erros dos instrumentos se repetirem.",
        }.get(c_dh.detectabilidade, ".")
        porque = (
            "A energia por kg de vapor (pressão e água de alimentação) variou "
            f"{_sinal(_simples(ef_dh), 2)}%{fim_frase}" + complemento(av, ef_dh)
        )
    hipoteses.append(
        _hipotese(
            "condicao_vapor",
            titulo(
                c_dh,
                "Vapor mais exigente (pressão maior ou água de alimentação mais fria)",
                "Vapor menos exigente (pressão menor ou água de alimentação mais quente)",
                "Condição do vapor (pressão e água de alimentação)",
            ),
            st,
            av,
            porque,
            "Conferir as leituras de pressão do vapor e de temperatura da água de alimentação.",
            "Manômetro e termômetro da água de alimentação.",
            ("pressão do vapor", "temperatura da água de alimentação"),
            None,
            ef_dh,
        )
    )

    # ------------------------------------------------ resíduo direto − indireto (E12 no número)
    residuo = orc_res = faixa_residuo = None
    if (
        c_eta.disponivel
        and c_perda.disponivel
        and b_ref.eficiencia.orcamento is not None
        and i_ref.perda.orcamento is not None
        and b_comp.eficiencia.orcamento is not None
        and i_comp.perda.orcamento is not None
    ):
        residuo = -100 * c_eta.delta - c_perda.delta
        orc_res = orcamento_residuo(
            (
                ("referencia", ref, b_ref, i_ref, +1.0),
                ("comparacao", comp, b_comp, i_comp, -1.0),
            )
        )
        if b_ref.eficiencia_cenarios and b_comp.eficiencia_cenarios:
            plaus = [
                -100 * (b_comp.eficiencia_cenarios[nc] - b_ref.eficiencia_cenarios[nr])
                - c_perda.delta
                for nr, nc in product(("recebido", "fifo"), repeat=2)
                if nr in b_ref.eficiencia_cenarios and nc in b_comp.eficiencia_cenarios
            ]
            faixa_residuo = (min(plaus), max(plaus))
    purgas_registradas = ref.purgas_n is not None and comp.purgas_n is not None
    av_res = {
        "mudanca_detectavel": None,
        "relevante": None,
        "compativel_com_consumo": None,
        "causa_comprovada": False,
    }
    if residuo is None:
        st_res = "nao_avaliavel"
        porque = (
            "Sem balanço direto e perda nos gases nos dois períodos, não dá para ver se sobra perda "
            "sem explicação."
        )
    elif orc_res.situacao != "completo":
        # ausente ≠ zero (A3): sem todas as incertezas, nem confirmar nem descartar
        st_res = "nao_avaliavel"
        porque = (
            f"A diferença entre o balanço direto e a perda nos gases é de {_sinal(residuo)} p.p., "
            f"mas faltam incertezas para avaliá-la: {_lista(f.nome for f in orc_res.faltam)}. "
            "Sem elas, não dá para dizer se sobra perda sem explicação nem descartar essa hipótese."
        )
    else:
        u_ind, u_cor = max(orc_res.u(0.0), orc_res.u(1.0)), min(orc_res.u(0.0), orc_res.u(1.0))
        nivel = detectabilidade(residuo, u_ind, u_cor)
        texto_u = (
            f"±{num(2 * u_ind, 1)} p.p."
            if abs(u_ind - u_cor) < 0.05
            else f"±{num(2 * u_ind, 1)} p.p.; ±{num(2 * u_cor, 1)} p.p. conforme os erros dos "
            "mesmos instrumentos se repitam ou não entre os períodos"
        )
        av_res["mudanca_detectavel"] = nivel
        depende_patio = faixa_residuo is not None and any(
            detectabilidade(x, u_ind, u_cor) != nivel for x in faixa_residuo
        )
        if depende_patio and nivel == "nao":
            st_res = "nao_avaliavel"
            porque = (
                f"Com o cenário 'o que entra é o que queima', o balanço direto e a perda nos gases "
                f"concordam (diferença de {_sinal(residuo)} p.p., incerteza {texto_u}). "
                f"Mas, conforme o uso do pátio, a diferença vai de {_sinal(faixa_residuo[0])} a "
                f"{_sinal(faixa_residuo[1])} p.p.: sem medir o combustível do pátio, não dá para "
                "avaliar com segurança se sobra perda sem explicação."
            )
        elif nivel == "nao":
            st_res = "descartada"
            porque = (
                "O balanço direto e a perda nos gases contam a mesma história, dentro da incerteza "
                f"(diferença de {_sinal(residuo)} p.p., incerteza {texto_u}; a umidade e o PCI "
                "seco, usados pelos dois caminhos, entram uma vez só)."
            )
        elif residuo < 0:
            st_res = "descartada"
            porque = (
                f"O balanço direto mostra {num(-residuo)} p.p. de perda a menos do que a chaminé "
                "explica: não indica perda extra."
            )
        else:
            st_res = "possivel"
            porque = (
                f"O balanço direto mostra {_sinal(residuo)} p.p. de perda além do que a chaminé "
                f"explica (incerteza {texto_u}). Pode ser purga, casco, vazamento de vapor ou "
                "combustão incompleta: os registros atuais não separam essas causas."
            )
            if nivel == "condicional":
                porque += (
                    " A diferença só passa da incerteza numa das hipóteses sobre os erros dos "
                    "instrumentos: pode ser real, mas não é certa."
                )
            if depende_patio:
                porque += (
                    f" Conforme o uso do pátio, a diferença vai de {_sinal(faixa_residuo[0])} a "
                    f"{_sinal(faixa_residuo[1])} p.p.: a conclusão depende de qual combustível "
                    "realmente queimou."
                )
        if st_res == "possivel":
            if not purgas_registradas:
                porque += " As purgas não foram registradas."
            if c_co.detectavel and c_co.delta > 0:
                porque += (
                    f" O CO subiu ({num(c_co.referencia, 0)} → {num(c_co.comparacao, 0)} ppm)."
                )
    hipoteses.append(
        _hipotese(
            "perdas_nao_medidas",
            "Outras perdas não medidas (purga, casco, vazamentos, combustão incompleta)",
            st_res,
            av_res,
            porque,
            "Registrar número e duração das purgas em todos os turnos, medir CO nos gases e "
            "procurar vazamentos de vapor e de condensado.",
            "Diferença entre os dois caminhos (direto e indireto), que compartilham a umidade.",
            ("balanço direto", "perda nos gases", "purgas"),
            residuo,
            por_perda(residuo) if st_res == "possivel" else None,
        )
    )
    hipoteses[-1]["orcamento_residuo"] = None if orc_res is None else orc_res.json()

    # ------------------------------------------------ fechamento: as explicações cobrem a mudança?
    termos = {
        "temperatura dos gases": (por_perda(ef_tg), c_tg),
        "O₂ nos gases": (por_perda(ef_o2), c_o2),
        "temperatura do ar de combustão": (por_perda(ef_tar), c_tar),
        "umidade do combustível": (ef_w, c_w),
        "energia por kg de vapor": (ef_dh, c_dh),
    }
    hipotese_do_termo = {
        "temperatura dos gases": "temperatura_gases",
        "O₂ nos gases": "excesso_ar",
        "umidade do combustível": "umidade_combustivel",
        "energia por kg de vapor": "condicao_vapor",
    }
    por_id = {h["id"]: h for h in hipoteses}
    fechamento = None
    if c_cons.disponivel and c_cons.incerteza_delta is not None:
        incluidos = {
            k: e for k, (e, c) in termos.items() if e is not None and c.detectabilidade == "sim"
        }
        u_termos = [
            abs(e / c.delta) * c.incerteza_delta / 2
            for k, (e, c) in termos.items()
            if k in incluidos and c.delta and c.incerteza_delta is not None
        ]
        # efeitos se compõem multiplicativamente: soma em pontos log, comparada com
        # ln(consumo_comp/consumo_ref); exibição em % simples (ER-7)
        observado_log = 100 * log(c_cons.comparacao / c_cons.referencia)
        u_obs = 100 * c_cons.incerteza_delta / c_cons.referencia / 2
        soma_log = sum(incluidos.values())
        u_dif = sqrt(u_obs**2 + sum(u**2 for u in u_termos))
        dif_log = observado_log - soma_log

        def veredito_de(dif: float) -> str:
            return "fecha" if abs(dif) <= 2 * u_dif else ("sobra" if dif > 0 else "excede")

        veredito = veredito_de(dif_log)
        soma_faixa = vereditos_faixa = None
        if faixa_w is not None and "umidade do combustível" in incluidos:
            base = soma_log - incluidos["umidade do combustível"]
            soma_faixa = (_simples(base + faixa_w[0]), _simples(base + faixa_w[1]))
            vereditos_faixa = sorted(
                {veredito_de(observado_log - base - f) for f in faixa_w} | {veredito}
            )
        observado, soma, dif = _simples(observado_log), _simples(soma_log), observado_log - soma_log
        frases = {
            "fecha": (
                f"As mudanças detectadas explicam {_sinal(soma)}% de {_sinal(observado)}% "
                f"observados: fecham dentro da incerteza (±{num(2 * u_dif)}%)."
            ),
            "sobra": (
                f"As mudanças detectadas explicam {_sinal(soma)}% de {_sinal(observado)}% "
                f"observados: sobra cerca de {_sinal(dif)}% sem explicação (incerteza ±{num(2 * u_dif)}%)."
            ),
            "excede": (
                f"As mudanças detectadas somariam {_sinal(soma)}%, mais do que os "
                f"{_sinal(observado)}% observados (incerteza ±{num(2 * u_dif)}%): algum fator não "
                "medido compensou."
            ),
        }
        # explicações 'possíveis' cuja mudança é só condicional (ex.: falta a incerteza de um
        # instrumento): mostram o que fecharia SE a mudança for confirmada (A3)
        condicionais = {
            k: e
            for k, (e, c) in termos.items()
            if e is not None
            and c.detectabilidade == "condicional"
            and k in hipotese_do_termo
            and por_id[hipotese_do_termo[k]]["status"] == "possivel"
            and por_id[hipotese_do_termo[k]]["avaliacao"]["compativel_com_consumo"]
        }
        veredito_cond = frase_cond = None
        if condicionais and veredito == "sobra":
            soma_cond = soma_log + sum(condicionais.values())
            veredito_cond = veredito_de(observado_log - soma_cond)
            frase_cond = (
                f"Contando também {_lista(condicionais)} (mudança ainda não confirmada), as "
                f"mudanças explicariam {_sinal(_simples(soma_cond))}%: "
                + {
                    "fecha": "fechariam dentro da incerteza.",
                    "sobra": "ainda sobraria parte sem explicação.",
                    "excede": "passariam do observado.",
                }[veredito_cond]
            )
        fechamento = {
            "observado_pct": observado,
            "explicado_pct": soma,
            "termos_condicionais": {k: _simples(v) for k, v in condicionais.items()},
            "veredito_com_condicionais": veredito_cond,
            "frase_com_condicionais": frase_cond,
            "explicado_pct_faixa_patio": soma_faixa,
            "diferenca_pontos_log": dif,
            "incerteza_diferenca_k2_pontos_log": 2 * u_dif,
            "termos": {k: _simples(v) for k, v in incluidos.items()},
            "veredito": veredito,
            "vereditos_conforme_patio": vereditos_faixa,
            "frase": frases[veredito],
            "nota": (
                "Efeitos calculados um fator por vez (interações desprezadas) e compostos "
                "multiplicativamente; efeito da umidade com o cenário 'o que entra é o que queima'."
            ),
        }

    # ------------------------------------------------ independência dos caminhos (E12)
    compartilhadas = [m for m in MEDICOES_INDIRETO if m in MEDICOES_DIRETO]
    independencia = {
        "caminho_direto": list(MEDICOES_DIRETO),
        "caminho_indireto": list(MEDICOES_INDIRETO),
        "compartilham": compartilhadas,
        "independentes": not compartilhadas,
        "nota": (
            "O balanço direto e a perda nos gases usam a mesma umidade e o mesmo PCI das amostras: "
            "se a umidade estiver errada, os dois erram juntos. Isso já é considerado na incerteza "
            "do resíduo entre eles. A temperatura dos gases e o O₂ aparecem só no caminho indireto; "
            "o vapor e os estoques, só no direto."
        ),
    }

    # ------------------------------------------------ o que falta
    falta: list[str] = []
    for r in (ref, comp):
        for b in r.bloqueios.values():
            falta += b.falta
    for b in (*b_ref.bloqueios, *b_comp.bloqueios):
        falta += b.falta
    for ind in (i_ref, i_comp):
        if ind.bloqueio is not None:
            falta += ind.bloqueio.falta
    if not purgas_registradas:
        falta.append("registro de purgas (número e duração) nos dois períodos")
    # incertezas necessárias não informadas (A3): em instrumentos.csv
    for g in (
        b_ref.eficiencia, b_comp.eficiencia, b_ref.consumo_t_por_t, b_comp.consumo_t_por_t,
        i_ref.perda, i_comp.perda,
    ):  # fmt: skip
        if g is not None and g.orcamento is not None:
            falta += [f"{f.nome}{SUFIXO_CADASTRAR}" for f in g.orcamento.faltam if f.sistematica]
    for g in (b_comp.eficiencia, b_comp.consumo_t_por_t):
        if g is not None and g.orcamento is not None:
            falta += [n for n in g.orcamento.nao_incluidos if n.startswith("título")]
    for r in (ref, comp):
        if r.pci_queimado is not None and r.pci_queimado.fifo_indisponivel:
            falta.append(
                f"qualidade do combustível do estoque no período {r.rotulo()}: o cenário FIFO "
                f"não pode ser calculado ({r.pci_queimado.fifo_indisponivel})"
            )
    for r in (ref, comp):
        if r.fracao_massa_sem_umidade:
            falta.append(
                f"umidade de {plural(r.lotes_sem_umidade, 'lote', 'lotes')} do período {r.rotulo()} "
                f"({pct(r.fracao_massa_sem_umidade)} da massa)"
            )
    if any(r.fracao_estoque is not None for r in (ref, comp)):
        falta.append(
            "umidade do combustível do pátio (estoque): sem ela, a eficiência depende de como o "
            "pátio é usado (ver faixas por período)"
        )
    falta = list(dict.fromkeys(falta))

    # ------------------------------------------------ conclusão e abstenção
    # explicações que fechariam a mudança se fossem confirmadas (dependem do que falta, A3)
    pendentes, faltas_pendentes = [], []
    if fechamento is not None and fechamento["veredito_com_condicionais"] == "fecha":
        for k in fechamento["termos_condicionais"]:
            pendentes.append(por_id[hipotese_do_termo[k]])
            faltas_pendentes += list(termos[k][1].faltam)
        faltas_pendentes = list(dict.fromkeys(faltas_pendentes))
    sustentadas = [h for h in hipoteses if h["status"] == "sustentada"]
    possiveis = [h for h in hipoteses if h["status"] == "possivel"]
    sobra = fechamento is not None and fechamento["veredito"] == "sobra"
    residuo_aberto = any(h["id"] == "perdas_nao_medidas" for h in possiveis)
    abstem, motivo = False, ""
    if not c_cons.disponivel:
        abstem, motivo = True, "o consumo por tonelada de vapor não pode ser calculado"
    elif c_cons.detectabilidade == "nao":
        abstem, motivo = True, "a variação do consumo não é maior que a incerteza das medições"
    elif c_cons.detectabilidade == "condicional":
        abstem, motivo = (
            True,
            (
                f"falta cadastrar a {_lista(c_cons.faltam)}; a variação do consumo só é real se o erro desses "
                "instrumentos for o mesmo nos dois períodos"
                if c_cons.faltam
                else "a variação do consumo só é real se o erro do medidor de vapor for o mesmo "
                "nos dois períodos"
            ),
        )
    elif c_cons.detectabilidade is None:
        abstem, motivo = (
            True,
            ("sem incerteza declarada, não dá para saber se a variação do consumo é real"),
        )
    elif sobra and pendentes and not residuo_aberto:
        abstem, motivo = (
            True,
            "o resto da mudança seria explicado por "
            + _lista(h["titulo"].lower() for h in pendentes)
            + ", mas essa mudança ainda não está confirmada"
            + (
                f", porque falta cadastrar a {_lista(faltas_pendentes)}" if faltas_pendentes else ""
            ),
        )
    elif sobra or residuo_aberto:
        abstem, motivo = True, "parte da mudança não é explicada pelos registros"
    elif not sustentadas:
        abstem, motivo = True, "nenhuma das causas medidas explica a mudança"

    if abstem:
        texto = f"Não dá para concluir: {motivo}."
        mudaram = [
            h
            for h in hipoteses
            if h["status"] in ("sustentada", "oposta", "possivel")
            and h["id"] != "perdas_nao_medidas"
            and h["avaliacao"]["mudanca_detectavel"] == "sim"
        ]
        if mudaram:
            texto += (
                " Mesmo assim, mudaram de forma detectável: "
                + "; ".join(h["titulo"].lower() for h in mudaram)
                + "."
            )
    else:
        texto = (
            "Explicações compatíveis com os dados: "
            + "; ".join(h["titulo"].lower() for h in sustentadas)
            + ". Nenhuma é causa comprovada sem a verificação indicada."
        )
    opostas = [h for h in hipoteses if h["status"] == "oposta"]
    if opostas:
        texto += (
            " Mudou no sentido contrário e compensou parte da mudança: "
            + "; ".join(h["titulo"].lower() for h in opostas)
            + "."
        )

    # ------------------------------------------------ próxima verificação
    if not c_cons.disponivel:
        faltas_consumo = [f for b in (*b_ref.bloqueios, *b_comp.bloqueios) for f in b.falta]
        prox = {
            "acao": "Registrar o que falta para completar o balanço: "
            + "; ".join(dict.fromkeys(faltas_consumo))
            + ".",
            "separa": [h["id"] for h in hipoteses if h["status"] in ("sustentada", "possivel")],
            "porque": "Sem o consumo por tonelada de vapor, não dá para medir o tamanho do efeito.",
        }
    elif c_cons.detectabilidade in ("condicional", None):
        prox = {
            "acao": (
                "Conferir a calibração do medidor de vapor e registrar a incerteza dele no "
                "cadastro de instrumentos (com o tipo: limite, padrão ou expandida)."
            ),
            "separa": [],
            "porque": "A conclusão depende de o erro do medidor ser o mesmo nos dois períodos.",
        }
    elif sobra and pendentes and not residuo_aberto:
        principal = max(pendentes, key=lambda h: abs(h["efeito"]["consumo_pct"] or 0))
        acao = principal["verificacao"]
        if faltas_pendentes:
            acao = (
                f"Registrar no cadastro de instrumentos a {_lista(faltas_pendentes)}, informando "
                f"o tipo da incerteza; e {acao[0].lower()}{acao[1:]}"
            )
        prox = {
            "acao": acao,
            "separa": [h["id"] for h in pendentes],
            "porque": (
                f"Decide se {_lista(h['titulo'].lower() for h in pendentes)} explica o resto da "
                "mudança: hoje essa mudança só passa da incerteza se o erro do instrumento se "
                "repetir nos dois períodos."
            ),
        }
    elif residuo_aberto or sobra:
        h = next(h for h in hipoteses if h["id"] == "perdas_nao_medidas")
        prox = {
            "acao": h["verificacao"],
            "separa": ["perdas_nao_medidas"] + [x["id"] for x in sustentadas],
            "porque": "É a parte da mudança que os registros atuais não explicam.",
        }
    elif sustentadas:
        principal = max(sustentadas, key=lambda h: abs(h["efeito"]["consumo_pct"] or 0))
        prox = {
            "acao": principal["verificacao"],
            "separa": [principal["id"]],
            "porque": (
                "Confirma a explicação de maior efeito antes de qualquer decisão; os dados só "
                "mostram compatibilidade."
            ),
        }
    else:
        prox = {
            "acao": "Manter os registros e repetir a comparação com mais semanas de dados.",
            "separa": [],
            "porque": "Com mais dados, a incerteza diminui e mudanças menores ficam visíveis.",
        }
    if opostas:
        prox["porque"] += " Verifique também: " + " ".join(h["verificacao"] for h in opostas)
        prox["separa"] = list(dict.fromkeys(prox["separa"] + [h["id"] for h in opostas]))
    resumo = _resumo(c_cons, hipoteses, abstem, motivo, pendentes, prox)

    # ------------------------------------------------ valor em jogo (só com base)
    valor_em_jogo, motivo_valor = None, ""
    if (
        c_cons.detectabilidade == "sim"
        and c_cons.delta > 0
        and comp.vapor_t is not None
        and comp.preco_brl_t is not None
    ):
        extra_t = c_cons.delta * comp.vapor_t.valor
        valor_em_jogo = {
            "valor_brl": extra_t * comp.preco_brl_t,
            "incerteza_brl": None
            if c_cons.incerteza_delta is None
            else c_cons.incerteza_delta * comp.vapor_t.valor * comp.preco_brl_t,
            "combustivel_extra_t": extra_t,
            "origem": "estimado",
            "base": (
                f"{num(extra_t, 0)} t de combustível a mais no período {comp.rotulo()}, em relação "
                f"ao consumo por tonelada de vapor da referência, ao preço médio pago "
                f"(R$ {num(comp.preco_brl_t)}/t). Não é promessa de economia."
            ),
        }
    else:
        # motivo específico: por que o valor em jogo não foi estimado (regra: não inventar)
        if not c_cons.disponivel:
            razao = "o consumo por tonelada de vapor não pode ser calculado"
        elif c_cons.detectabilidade != "sim":
            razao = "o aumento de consumo não está confirmado pelas incertezas"
        elif c_cons.delta <= 0:
            razao = "o consumo por tonelada de vapor não aumentou"
        else:
            razao = "falta o vapor ou o preço do combustível no período de comparação"
        motivo_valor = f"Valor em jogo não estimado: {razao} (regra: não inventar números)."

    # ------------------------------------------------ custo do vapor (E14)
    custo = None
    if c_custo.disponivel and ref.preco_brl_gj and comp.preco_brl_gj:
        efeito_preco = 100 * log(comp.preco_brl_gj / ref.preco_brl_gj)
        efeito_intensidade = 100 * log(c_custo.comparacao / c_custo.referencia) - efeito_preco
        custo = {
            **_comparacao_json(c_custo),
            "efeito_preco_pct": efeito_preco,
            "efeito_intensidade_pct": efeito_intensidade,
            "frase": (
                f"O custo do combustível por tonelada de vapor foi de R$ {num(c_custo.referencia)} "
                f"para R$ {num(c_custo.comparacao)} "
                f"({_sinal(100 * c_custo.delta / c_custo.referencia)}%): "
                f"{_sinal(efeito_preco)}% pelo preço da energia comprada (R$/GJ) e "
                f"{_sinal(efeito_intensidade)}% pela energia gasta por tonelada de vapor. "
                "Variação de preço não é perda de eficiência."
            ),
        }

    # ------------------------------------------------ sensibilidade ao critério D29
    sensibilidade = []
    for fator in ALTERNATIVAS_D29:
        if fator == criterio_relevancia:
            continue
        outros = avaliar_fatores(fator)
        mudam = {k: outros[k][0] for k in outros if outros[k][0] != avaliacoes[k][0]}
        sensibilidade.append({"criterio": fator, "muda_status": mudam})

    def periodo_json(r: ResumoPeriodo, b: BalancoDireto, i: Indireto) -> dict:
        cen = r.pci_queimado
        return {
            "inicio": r.inicio.isoformat(),
            "fim": r.fim.isoformat(),
            "rotulo": r.rotulo(),
            "leituras_diario": r.n_leituras_diario,
            "cobertura_diario": r.cobertura_diario,
            "ponto_gases_id": r.ponto_gases_id,
            "instrumento_o2_id": r.instrumento_o2_id,
            "vapor_t": _grandeza_json(r.vapor_t),
            "energia_util": {
                "metodo": b.metodo_energia_util,
                **(_grandeza_json(b.energia_util_gj) or {}),
            },
            "combustivel_kg": _grandeza_json(r.combustivel_kg),
            "fracao_estoque": r.fracao_estoque,
            "umidade_recebida": _grandeza_json(r.umidade_mistura),
            "pci_umido_recebido": _grandeza_json(r.pci_umido_mistura),
            "pci_queimado_cenarios": None
            if cen is None
            else {
                "recebido": cen.recebido,
                "fifo": cen.fifo,
                "fifo_indisponivel": cen.fifo_indisponivel,
                "minimo": cen.minimo,
                "maximo": cen.maximo,
                "condicoes": list(cen.condicoes),
            },
            "composicao_origem": r.composicao_origem,
            "eficiencia_direta": _grandeza_json(b.eficiencia),
            "eficiencia_cenarios_patio": b.eficiencia_cenarios,
            "estado_vapor": {
                "estado": b.estado_vapor,
                "origem": b.estado_vapor_origem,
                "titulo": b.titulo_vapor,
            },
            "sensibilidade_titulo_vapor_pct": b.sensibilidade_titulo_pct,
            "fronteira_balanco_direto": b.fronteira,
            "consumo_t_por_t": _grandeza_json(b.consumo_t_por_t),
            "perda_gases": _grandeza_json(i.perda),
            "preco_brl_t": r.preco_brl_t,
            "preco_brl_gj": r.preco_brl_gj,
            "purgas_n": r.purgas_n,
            "eventos": [
                {
                    "instante": e["instante"].isoformat(),
                    "tipo": e["tipo"],
                    "descricao": e["descricao"],
                }
                for e in r.eventos
            ],
            "bloqueios": [x.motivo for x in [*r.bloqueios.values(), *b.bloqueios]]
            + ([] if i.bloqueio is None else [i.bloqueio.motivo]),
        }

    origens = pacote.origens_de_dado()
    diario = pacote.dados("diario")
    caldeira = (
        None if diario is None or diario.empty else str(diario["caldeira_id"].dropna().iloc[0])
    )
    return _limpar(
        {
            "versao_euler": __version__,
            "formato": "investigacao/0.2 (proposta D28, revisada na Fase R)",
            "caldeira_id": caldeira,
            "origem_dados": sorted(origens),
            "periodos": {
                "referencia": periodo_json(ref, b_ref, i_ref),
                "comparacao": periodo_json(comp, b_comp, i_comp),
            },
            "o_que_mudou": {
                "frase": frase_consumo,
                "consumo_especifico": _comparacao_json(c_cons),
                "custo_vapor": custo,
                "fechamento": fechamento,
                "indicadores": [
                    _comparacao_json(c)
                    for c in (c_tg, c_o2, c_tar, c_co, c_w, c_dh, c_perda, c_eta)
                ],
            },
            "hipoteses": hipoteses,
            "independencia": independencia,
            "o_que_falta": falta,
            "proxima_verificacao": prox,
            "conclusao": {"abstencao": abstem, "motivo": motivo, "texto": texto},
            "resumo": {"frases": resumo, "texto": " ".join(resumo)},
            "valor_em_jogo": valor_em_jogo,
            "valor_em_jogo_motivo": motivo_valor,
            "criterios": {
                "relevancia_d29": criterio_relevancia,
                "efeito_minimo_relevante_consumo_pct": lim,
                "eficiencia_referencia_para_efeitos": eta_origem,
                "sensibilidade_d29": sensibilidade,
                "nota": (
                    "Detectável = maior que U = 2u da diferença (sim: mesmo com erros de "
                    "instrumento independentes; condicional: só se o erro do mesmo instrumento "
                    "se repetir). Relevância: D29. Incertezas declaradas sem tipo são tratadas "
                    "como limites retangulares (GUM 4.3.7, D35)."
                ),
            },
        }
    )
