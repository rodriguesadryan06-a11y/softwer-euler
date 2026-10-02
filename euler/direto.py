"""Balanço direto: energia útil do vapor ÷ energia do combustível (E8, E10, E13, E15; T10).

Fronteira física (D39):
- **entra**: o combustível queimado no período (E9, massa como recebida) com seu PCI;
- **sai como energia útil**: só o vapor que passa pelo medidor, do estado da água de
  alimentação (no ponto em que a temperatura é medida, na pressão da caldeira) até vapor
  saturado; título x = 1 **assumido** quando não medido;
- **fica fora da energia útil** e aparece como "outras perdas" no confronto com o caminho
  indireto: purga (D27), gases da chaminé, casco, cinzas e incombustos, vazamentos e
  qualquer vapor consumido antes do medidor.

Assim, η_D = Q_s / E_f é a eficiência **direta** dessa fronteira. Ela **não** é a perda
nos gases: a perda nos gases é só uma parcela de (1 − η_D).

Energia útil (E8): intervalo a intervalo entre leituras do totalizador quando há pressão e
água de alimentação em todos os intervalos; senão, com as condições médias (D26).

Não circularidade (E13): a eficiência é sempre resultado; nenhuma função deste módulo (nem
de vapor/combustível/períodos) recebe eficiência como entrada — há um teste para isso.

Incerteza (E15, GUM): orçamentos por componente (euler.incerteza). A diferença entre o
combustível recebido e o queimado não entra no orçamento: é tratada como **cenários**
(`eficiencia_cenarios`), porque é uma hipótese de modelo e não um erro aleatório (D38).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iapws import IAPWS97

from euler.incerteza import Componente, Falta, Orcamento
from euler.periodos import ROTULO_LEITURA, ResumoPeriodo
from euler.tipos import AnaliseBloqueada, Grandeza
from euler.vapor import delta_h_mj_kg

FRONTEIRA = (
    "Entra: combustível queimado no período (estoques + recebimentos) com o PCI do material. "
    "Sai como energia útil: o vapor medido no totalizador, da água de alimentação até o estado "
    "termodinâmico usado no cálculo. Ficam fora: purga, gases da chaminé, casco, cinzas, "
    "vazamentos e vapor usado antes do medidor."
)


def _fronteira_estado(estado: str, origem: str) -> str:
    nomes = {
        "saturado_seco": "vapor saturado seco (x = 1)",
        "umido": "vapor úmido com título medido",
        "superaquecido": "vapor superaquecido com temperatura medida",
    }
    sufixo = " assumido" if origem == "assumido" else ""
    return (
        "Entra: combustível queimado no período (estoques + recebimentos) com o PCI do material. "
        "Sai como energia útil: o vapor medido no totalizador, da água de alimentação até "
        f"{nomes.get(estado, estado)}{sufixo}. Ficam fora: purga, gases da chaminé, casco, "
        "cinzas, vazamentos e vapor usado antes do medidor."
    )


MEDICOES_DIRETO = (
    "totalizador de vapor",
    "pressão do vapor",
    "temperatura da água de alimentação",
    "estoques de combustível",
    "pesagem dos recebimentos",
    "umidade das amostras",
    "PCI seco das amostras",
)


@dataclass
class BalancoDireto:
    """Resultado do balanço direto de um período; campos None quando bloqueados."""

    delta_h_mj_kg: Grandeza | None = None
    energia_util_gj: Grandeza | None = None
    metodo_energia_util: str | None = None
    energia_combustivel_gj: Grandeza | None = None
    eficiencia: Grandeza | None = None
    eficiencia_cenarios: dict[str, float] | None = None
    consumo_t_por_t: Grandeza | None = None
    intensidade_gj_por_t: Grandeza | None = None
    estado_vapor: str = "saturado_seco"
    estado_vapor_origem: str = "assumido"
    t_vapor_c: float | None = None
    titulo_vapor: float | None = 1.0
    sensibilidade_titulo_pct: float | None = None
    """Variação relativa de Δh (e de η) se o título for 0,99 em vez de 1 (sempre negativa)."""
    fronteira: str = FRONTEIRA
    sem_incerteza: list[str] = field(default_factory=list)
    bloqueios: list[AnaliseBloqueada] = field(default_factory=list)

    @property
    def disponivel(self) -> bool:
        return self.eficiencia is not None


def _orcamento_delta_h(
    r: ResumoPeriodo,
    p: float,
    t: float,
    dh: float,
    estado: str,
    t_vapor_c: float | None,
    titulo: float | None,
) -> Orcamento:
    """Incerteza de Δh pelas grandezas que definem o estado de entrada e saída.

    A derivada numérica usa a mesma IF97 do valor central. O que não tiver incerteza
    declarada vai para `faltam`; nunca vira zero.
    """
    orc = Orcamento()
    entradas: list[tuple[str, float]] = [
        ("p_vapor_bar_abs", 0.1),
        ("t_agua_alim_c", 1.0),
    ]
    if estado == "superaquecido":
        entradas.append(("t_vapor_c", 0.5))
    elif estado == "umido":
        entradas.append(("titulo_vapor_frac", 0.001))

    for coluna, passo in entradas:
        g = r.leituras_grandeza.get(coluna)
        if g is None or g.orcamento is None:
            orc.faltam.append(Falta(f"incerteza de {ROTULO_LEITURA[coluna]}", False))
            continue
        pp, tt, tv, xx = p, t, t_vapor_c, titulo
        delta = passo
        if coluna == "p_vapor_bar_abs":
            pp += delta
        elif coluna == "t_agua_alim_c":
            tt += delta
        elif coluna == "t_vapor_c":
            tv = float(tv) + delta
        else:
            if xx is None:
                orc.faltam.append(Falta("título do vapor", False))
                continue
            if xx + delta > 1:
                delta = -delta
            xx += delta
        try:
            dh2 = delta_h_mj_kg(pp, estado, tt, t_vapor_c=tv, titulo=xx)
        except AnaliseBloqueada:
            orc.faltam.append(Falta(f"sensibilidade de {ROTULO_LEITURA[coluna]}", False))
            continue
        sens = (dh2 - dh) / delta
        for c in g.orcamento.componentes:
            orc.componentes.append(
                Componente(
                    f"{ROTULO_LEITURA[coluna]}: {c.nome}",
                    sens * c.u_rel * g.valor / dh,
                    c.natureza,
                    c.chave,
                    c.nota,
                    coluna,
                )
            )
        orc.faltam += g.orcamento.faltam
    orc.faltam = list(dict.fromkeys(orc.faltam))
    if estado == "saturado_seco" and r.estado_vapor_origem == "assumido":
        orc.nao_incluidos.append("estado do vapor não medido (saturado seco, x = 1, assumido)")
    return orc


def _grandeza(valor: float, unidade: str, orc: Orcamento, nota: str) -> Grandeza:
    """Incerteza só com o orçamento completo; com algo faltando, fica None (A3)."""
    return Grandeza(valor, unidade, "estimado", orc.incerteza_k2(valor), nota, orc)


def balanco_direto(r: ResumoPeriodo) -> BalancoDireto:
    """Eficiência direta, consumo específico e intensidade energética do período."""
    b = BalancoDireto()
    b.estado_vapor = r.estado_vapor
    b.estado_vapor_origem = r.estado_vapor_origem
    b.fronteira = _fronteira_estado(r.estado_vapor, r.estado_vapor_origem)
    if r.estado_vapor == "superaquecido":
        g_tv = r.leituras_grandeza.get("t_vapor_c")
        b.t_vapor_c = None if g_tv is None else g_tv.valor
        b.titulo_vapor = None
    elif r.estado_vapor == "umido":
        g_x = r.leituras_grandeza.get("titulo_vapor_frac")
        b.titulo_vapor = None if g_x is None else g_x.valor
    for chave in ("vapor", "combustivel", "mistura", "estado_vapor"):
        if chave in r.bloqueios:
            b.bloqueios.append(r.bloqueios[chave])

    p = r.leituras.get("p_vapor_bar_abs")
    t_agua = r.leituras.get("t_agua_alim_c")
    if p is None:
        b.bloqueios.append(
            AnaliseBloqueada(
                "Sem pressão absoluta do vapor: falta a pressão do manômetro ou a altitude do local.",
                ["pressão do vapor e altitude do local"],
            )
        )
    elif t_agua is None:
        b.bloqueios.append(
            AnaliseBloqueada(
                "Sem temperatura da água de alimentação: a energia por tonelada de vapor não é "
                "conhecida.",
                ["temperatura da água de alimentação"],
            )
        )
    elif "estado_vapor" not in r.bloqueios:
        estado = r.estado_vapor
        g_tv = r.leituras_grandeza.get("t_vapor_c")
        g_x = r.leituras_grandeza.get("titulo_vapor_frac")
        tv = None if g_tv is None else g_tv.valor
        titulo = None if g_x is None else g_x.valor
        if estado == "superaquecido" and tv is None:
            b.bloqueios.append(
                AnaliseBloqueada(
                    "O vapor foi registrado como superaquecido, mas falta a temperatura do vapor.",
                    ["temperatura do vapor"],
                )
            )
        elif estado == "umido" and titulo is None:
            b.bloqueios.append(
                AnaliseBloqueada(
                    "O vapor foi registrado como úmido, mas falta o título do vapor.",
                    ["título do vapor"],
                )
            )
        else:
            try:
                dh = delta_h_mj_kg(
                    p.media,
                    estado,
                    t_agua.media,
                    t_vapor_c=tv,
                    titulo=titulo,
                )
                if estado == "saturado_seco":
                    nota_estado = (
                        "vapor saturado seco; x = 1 assumido"
                        if r.estado_vapor_origem == "assumido"
                        else "vapor saturado seco registrado"
                    )
                elif estado == "superaquecido":
                    nota_estado = f"vapor a {tv:.1f} °C"
                else:
                    nota_estado = f"vapor úmido com x = {titulo:.4f}"
                b.delta_h_mj_kg = _grandeza(
                    dh,
                    "MJ/kg",
                    _orcamento_delta_h(
                        r,
                        p.media,
                        t_agua.media,
                        dh,
                        estado,
                        tv,
                        titulo,
                    ),
                    f"IF97 a {p.media:.2f} bar abs, água a {t_agua.media:.0f} °C; {nota_estado}",
                )
                if estado == "saturado_seco" and r.estado_vapor_origem == "assumido":
                    umido = IAPWS97(P=p.media / 10, x=0.99).h / 1000 - (
                        IAPWS97(P=p.media / 10, x=1).h / 1000 - dh
                    )
                    b.sensibilidade_titulo_pct = 100 * (umido / dh - 1)
            except AnaliseBloqueada as bloqueio:
                b.bloqueios.append(bloqueio)

    vapor, comb, pci = r.vapor_t, r.combustivel_kg, r.pci_umido_mistura
    if vapor is not None and b.delta_h_mj_kg is not None:
        orc_q = vapor.orcamento.mais(b.delta_h_mj_kg.orcamento)
        if r.energia_util_intervalos_gj is not None:
            q, b.metodo_energia_util = r.energia_util_intervalos_gj, "intervalo a intervalo"
        else:
            q = vapor.valor * b.delta_h_mj_kg.valor  # t × MJ/kg = GJ
            b.metodo_energia_util = "condições médias do período"
        b.energia_util_gj = _grandeza(q, "GJ", orc_q, b.metodo_energia_util)
    if comb is not None and pci is not None:
        e = comb.valor * pci.valor / 1000
        b.energia_combustivel_gj = _grandeza(
            e, "GJ", comb.orcamento.mais(pci.orcamento), "cenário 'o que entra é o que queima'"
        )

    if vapor is None or comb is None:
        return b
    if vapor.valor <= 0 or comb.valor <= 0:  # defesa (A4): os resumos já bloqueiam zero
        b.bloqueios.append(
            AnaliseBloqueada(
                "Vapor ou combustível do período igual a zero: consumo por tonelada e "
                "eficiência não se aplicam.",
                ["vapor e combustível do período"],
            )
        )
        return b
    for nome, g in (("medidor de vapor", vapor), ("medição de estoque", comb)):
        if g.incerteza is None:
            b.sem_incerteza.append(nome)

    b.consumo_t_por_t = _grandeza(
        (comb.valor / 1000) / vapor.valor,
        "t de combustível / t de vapor",
        comb.orcamento.mais(vapor.orcamento, -1),
        "combustível queimado (E9) ÷ vapor do totalizador; não depende da qualidade do combustível",
    )
    if b.energia_combustivel_gj is None:
        return b
    b.intensidade_gj_por_t = _grandeza(
        b.energia_combustivel_gj.valor / vapor.valor,
        "GJ de combustível / t de vapor",
        b.energia_combustivel_gj.orcamento.mais(vapor.orcamento, -1),
        "cenário 'o que entra é o que queima'",
    )
    if b.energia_util_gj is None:
        return b
    eta = b.energia_util_gj.valor / b.energia_combustivel_gj.valor
    b.eficiencia = _grandeza(
        eta,
        "fração",
        b.energia_util_gj.orcamento.mais(b.energia_combustivel_gj.orcamento, -1),
        "energia útil do vapor ÷ energia do combustível (E10), base PCI; cenário 'o que entra "
        "é o que queima'",
    )
    if r.pci_queimado is not None:
        cen = r.pci_queimado
        b.eficiencia_cenarios = {
            nome: b.energia_util_gj.valor / (comb.valor * valor / 1000)
            for nome, valor in (
                ("recebido", cen.recebido),
                ("fifo", cen.fifo),
                ("minimo", cen.maximo),  # PCI máximo → eficiência mínima
                ("maximo", cen.minimo),
            )
            if valor is not None
        }
    return b
