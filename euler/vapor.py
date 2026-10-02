"""Entalpias de vapor e água pela IAPWS-IF97 (E8 em docs/fisica_para_revisao.md).

Unidades: pressão em bar absoluto, temperatura em °C, entalpia em MJ/kg.
A biblioteca `iapws` trabalha em MPa, K e kJ/kg; a conversão fica só aqui.
"""

from iapws import IAPWS97

from euler.tipos import AnaliseBloqueada

P_ATM_NIVEL_DO_MAR_BAR = 1.01325
P_CRITICA_BAR = 220.64
P_MIN_SATURACAO_BAR = 0.00612  # ponto triplo
ESTADOS_VAPOR = ("saturado_seco", "umido", "superaquecido")


def _checar_pressao(p_bar_abs: float) -> None:
    if not P_MIN_SATURACAO_BAR < p_bar_abs < P_CRITICA_BAR:
        raise AnaliseBloqueada(
            f"Pressão de {p_bar_abs:g} bar abs fora da faixa em que há vapor saturado "
            f"(entre {P_MIN_SATURACAO_BAR} e {P_CRITICA_BAR} bar abs). Confira a unidade."
        )


def p_atm_por_altitude_bar(altitude_m: float) -> float:
    """Pressão atmosférica padrão na altitude do local, em bar.

    Atmosfera padrão internacional (ISA, troposfera):
    p = 1,01325 · (1 − 2,25577·10⁻⁵ · h)^5,25588.
    Usada quando não há barômetro (E8). O resultado é `estimado`: o tempo
    (clima) muda a pressão real em alguns milibares.

    Entrada: altitude_m, altitude do local em metros (−500 a 5000).
    """
    if not -500 <= altitude_m <= 5000:
        raise AnaliseBloqueada(
            f"Altitude de {altitude_m:g} m fora da faixa aceita (−500 a 5000 m). Confira o valor."
        )
    return P_ATM_NIVEL_DO_MAR_BAR * (1 - 2.25577e-5 * altitude_m) ** 5.25588


def p_absoluta_bar(p_man_bar: float, p_atm_bar: float) -> float:
    """Converte pressão manométrica em absoluta: p_abs = p_man + p_atm (E8).

    Entradas em bar. Bloqueia se o resultado não for positivo (unidade trocada
    ou leitura impossível).
    """
    p_abs = p_man_bar + p_atm_bar
    if p_abs <= 0:
        raise AnaliseBloqueada(
            f"Pressão manométrica de {p_man_bar:g} bar resulta em pressão absoluta "
            "não positiva. Confira a leitura e a unidade."
        )
    return p_abs


def t_sat_c(p_bar_abs: float) -> float:
    """Temperatura de saturação da água (°C) na pressão dada (bar abs), IF97."""
    _checar_pressao(p_bar_abs)
    return IAPWS97(P=p_bar_abs / 10, x=1).T - 273.15


def h_liquido_saturado_mj_kg(p_bar_abs: float) -> float:
    """Entalpia do líquido saturado (MJ/kg) na pressão dada, IF97."""
    _checar_pressao(p_bar_abs)
    return IAPWS97(P=p_bar_abs / 10, x=0).h / 1000


def h_vapor_mj_kg(
    p_bar_abs: float,
    estado: str,
    t_vapor_c: float | None = None,
    titulo: float | None = None,
) -> float:
    """Entalpia específica do vapor produzido (MJ/kg), IF97 (E8).

    Entradas:
        p_bar_abs: pressão do vapor, bar absoluto.
        estado: "saturado_seco" (x = 1), "umido" (exige `titulo` medido)
            ou "superaquecido" (exige `t_vapor_c` acima da saturação).
    Hipótese: sem medição de título, quem chama usa "saturado_seco" e marca a
    origem como `assumido` (E8). Este módulo nunca escolhe o título sozinho.
    """
    if estado not in ESTADOS_VAPOR:
        raise ValueError(f"estado do vapor desconhecido: {estado!r} (use {ESTADOS_VAPOR})")
    _checar_pressao(p_bar_abs)
    p_mpa = p_bar_abs / 10
    if estado == "saturado_seco":
        return IAPWS97(P=p_mpa, x=1).h / 1000
    if estado == "umido":
        if titulo is None:
            raise AnaliseBloqueada(
                "Vapor úmido sem título medido: não dá para calcular a entalpia.",
                falta=["título do vapor (x)"],
            )
        if not 0 <= titulo <= 1:
            raise AnaliseBloqueada(f"Título do vapor {titulo:g} fora de 0 a 1.")
        return IAPWS97(P=p_mpa, x=titulo).h / 1000
    if t_vapor_c is None:
        raise AnaliseBloqueada(
            "Vapor superaquecido sem temperatura medida: não dá para calcular a entalpia.",
            falta=["temperatura do vapor"],
        )
    t_sat = t_sat_c(p_bar_abs)
    if t_vapor_c <= t_sat:
        raise AnaliseBloqueada(
            f"Temperatura do vapor ({t_vapor_c:g} °C) não está acima da saturação "
            f"({t_sat:.1f} °C a {p_bar_abs:g} bar abs): não é vapor superaquecido."
        )
    return IAPWS97(P=p_mpa, T=t_vapor_c + 273.15).h / 1000


def h_agua_mj_kg(p_bar_abs: float, t_c: float) -> float:
    """Entalpia da água líquida (MJ/kg) na pressão p (bar abs) e temperatura t (°C), IF97.

    Usada para a água de alimentação, avaliada na pressão da caldeira (E8: h_a(p, T_a)).
    Bloqueia se a água não estiver líquida nessa pressão.
    """
    t_sat = t_sat_c(p_bar_abs)
    if t_c >= t_sat:
        raise AnaliseBloqueada(
            f"Água a {t_c:g} °C não está líquida a {p_bar_abs:g} bar abs "
            f"(saturação {t_sat:.1f} °C). Confira a temperatura da água de alimentação."
        )
    if t_c <= 0:
        raise AnaliseBloqueada(f"Temperatura da água de {t_c:g} °C fora da faixa (acima de 0 °C).")
    return IAPWS97(P=p_bar_abs / 10, T=t_c + 273.15).h / 1000


def delta_h_mj_kg(
    p_bar_abs: float,
    estado: str,
    t_agua_alim_c: float,
    t_vapor_c: float | None = None,
    titulo: float | None = None,
) -> float:
    """Energia entregue por kg de vapor: Δh = h_s − h_a (MJ/kg), E8.

    Referência (golden V01): 10 bar abs, saturado seco, água a 80 °C → 2,4414 MJ/kg.
    """
    h_s = h_vapor_mj_kg(p_bar_abs, estado, t_vapor_c=t_vapor_c, titulo=titulo)
    h_a = h_agua_mj_kg(p_bar_abs, t_agua_alim_c)
    return h_s - h_a
