"""Quantificação opcional da perda energética por purga.

Só calcula quando a massa purgada é medida/informada. Duração ou número de purgas,
sozinhos, não são convertidos em massa por hipótese de válvula.
"""

from __future__ import annotations

from euler.tipos import AnaliseBloqueada
from euler.vapor import h_agua_mj_kg, h_liquido_saturado_mj_kg


def energia_purga_gj(
    *, massa_purga_kg: float, p_bar_abs: float, t_agua_referencia_c: float
) -> float:
    """Energia removida pela purga em relação à água de alimentação, em GJ.

    Q_bd = m_bd · [h_f,sat(p) − h_fw(p,T_fw)].
    Hipótese: líquido da purga na condição saturada à pressão informada e sem crédito de
    recuperação de calor/flash. Se houver tanque flash ou recuperação, o resultado é perda
    bruta na fronteira da caldeira, não perda líquida da planta.
    """
    if massa_purga_kg < 0:
        raise AnaliseBloqueada("Massa de purga negativa: confira a medição.")
    if massa_purga_kg == 0:
        return 0.0
    h_bd = h_liquido_saturado_mj_kg(p_bar_abs)
    h_fw = h_agua_mj_kg(p_bar_abs, t_agua_referencia_c)
    if h_bd <= h_fw:
        raise AnaliseBloqueada(
            "A entalpia calculada da purga não supera a da água de alimentação; confira os dados."
        )
    return massa_purga_kg * (h_bd - h_fw) / 1000
