"""Dia a dia da caldeira (D114): o que os registros mostram por dia, para o Painel.

Só agrega leituras gravadas; não calcula consumo de combustível por dia (o consumo só é
conhecido entre medições de estoque, E9). Por dia:

- vazão média de vapor (t/h): incrementos do totalizador divididos pelas horas cobertas
  pelas leituras do dia (uma leitura perdida não diminui a média, ao contrário de um
  total); só com pelo menos 12 h cobertas, senão fica ausente ("dia parcial");
  totalizador reiniciado ou instrumento indisponível não entram (não viram zero);
- temperatura dos gases e O₂ em base seca: média das leituras do dia;
- combustível recebido (t): soma das notas do dia (compra, não consumo).

A faixa da referência é a faixa entre o 10º e o 90º percentil dos valores diários do
período de referência: "o que era comum" na base de comparação, não um limite de projeto.
"""

from __future__ import annotations

import pandas as pd

from euler.formato import num

FUSO = "America/Sao_Paulo"
HORAS_MINIMAS = 12.0


def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t if t.tzinfo else t.tz_localize("UTC")


def diario_por_dia(pacote) -> pd.DataFrame:
    """Uma linha por dia com registros: dia, horas_cobertas, vazao_t_h, t_gases_c,
    o2_seco_pct, recebido_t. Ausentes ficam NaN."""
    d = pacote.dados("diario")
    if d is None or d.empty:
        return pd.DataFrame(
            columns=["dia", "horas_cobertas", "vazao_t_h", "t_gases_c", "o2_seco_pct", "recebido_t"]
        )
    d = d[d["instante_observado"].notna()].sort_values("instante_observado").copy()
    d["dia"] = d["instante_observado"].dt.tz_convert(FUSO).dt.normalize()
    linhas = {}
    if "totalizador_vapor_t" in d:
        t = d[d["totalizador_vapor_t"].notna()]
        if "flag_instrumento_indisponivel" in t:
            t = t[~t["flag_instrumento_indisponivel"].fillna(False).astype(bool)]
        horas = t["instante_observado"].diff().dt.total_seconds() / 3600
        vapor = t["totalizador_vapor_t"].astype(float).diff()
        passo = float(horas[horas > 0].median()) if (horas > 0).any() else 0.0
        ok = (horas > 0) & (vapor >= 0) & (horas <= 4 * passo)
        inc = pd.DataFrame({"dia": t["dia"], "horas": horas, "vapor": vapor})[ok]
        por_dia = inc.groupby("dia").agg(horas=("horas", "sum"), vapor=("vapor", "sum"))
        for dia, r in por_dia.iterrows():
            linhas.setdefault(dia, {})["horas_cobertas"] = float(r["horas"])
            linhas[dia]["vazao_t_h"] = (
                float(r["vapor"] / r["horas"]) if r["horas"] >= HORAS_MINIMAS else None
            )
    for col in ("t_gases_c", "o2_seco_pct"):
        if col in d:
            for dia, v in d.groupby("dia")[col].mean().items():
                linhas.setdefault(dia, {})[col] = None if pd.isna(v) else float(v)
    c = pacote.dados("combustivel")
    if c is not None and not c.empty and "massa_kg" in c:
        rec = c[(c["tipo"] == "recebimento") & c["massa_kg"].notna() & c["data"].notna()]
        dias = rec["data"].dt.tz_convert(FUSO).dt.normalize()
        for dia, v in (rec["massa_kg"].groupby(dias).sum() / 1000).items():
            linhas.setdefault(dia, {})["recebido_t"] = float(v)
    df = pd.DataFrame(
        [{"dia": dia, **valores} for dia, valores in sorted(linhas.items())],
        columns=["dia", "horas_cobertas", "vazao_t_h", "t_gases_c", "o2_seco_pct", "recebido_t"],
    )
    return df


def _faixa(serie: pd.Series) -> list[float] | None:
    s = serie.dropna()
    if len(s) < 5:
        return None
    return [float(s.quantile(0.10)), float(s.quantile(0.90))]


def dia_a_dia(pacote, referencia: dict | None = None, dias: int = 30) -> dict:
    """Últimos `dias` dias com registro, a faixa da referência e os quadros dos últimos 7 dias.

    Saída: `serie` (lista de dias), `faixas` {grandeza: [p10, p90] da referência ou None},
    `quadros` (média dos últimos 7 dias com registro, a mesma média na referência e a
    frase), `ultimo_dia` e `frases`.
    """
    tudo = diario_por_dia(pacote)
    if tudo.empty:
        return {"serie": [], "faixas": {}, "quadros": [], "ultimo_dia": None, "frases": []}
    ultimo = tudo["dia"].max()
    serie = tudo[tudo["dia"] > ultimo - pd.Timedelta(days=dias)]
    faixas, ref = {}, None
    if referencia:
        ini = _ts(referencia["inicio"]).tz_convert(FUSO).normalize()
        fim = _ts(referencia["fim"]).tz_convert(FUSO).normalize()
        ref = tudo[(tudo["dia"] > ini) & (tudo["dia"] < fim)]  # dias inteiros da referência
        for col in ("vazao_t_h", "t_gases_c", "o2_seco_pct"):
            faixas[col] = _faixa(ref[col])
    semana = tudo[tudo["dia"] > ultimo - pd.Timedelta(days=7)]
    quadros = []
    for col, nome, unidade, casas in (
        ("vazao_t_h", "Vapor (vazão média)", "t/h", 1),
        ("t_gases_c", "Temperatura dos gases", "°C", 0),
        ("o2_seco_pct", "O₂ nos gases (base seca)", "%", 1),
        ("recebido_t", "Combustível recebido", "t/dia", 0),
    ):
        if col not in semana:
            continue
        valores = semana[col].dropna()
        media = float(valores.mean()) if len(valores) else None
        media_ref = None
        if ref is not None and col in ref and ref[col].notna().any():
            media_ref = float(ref[col].mean())
        faixa = faixas.get(col)
        if media is None:
            frase = "sem leituras completas nos últimos 7 dias"
        elif col == "recebido_t":
            frase = "compras registradas (não é consumo)"
        elif faixa is None:
            frase = "sem faixa da referência"
        elif faixa[0] <= media <= faixa[1]:
            frase = "dentro do comum na referência"
        else:
            frase = (
                f"{'acima' if media > faixa[1] else 'abaixo'} do comum na referência "
                f"({num(faixa[0], casas)} a {num(faixa[1], casas)} {unidade})"
            )
        quadros.append(
            {
                "grandeza": col,
                "nome": nome,
                "unidade": unidade,
                "casas": casas,
                "media_7d": media,
                "dias_com_valor": len(valores),
                "media_referencia": media_ref,
                "faixa_referencia": faixa,
                "fora_da_faixa": None
                if media is None or faixa is None or col == "recebido_t"
                else not faixa[0] <= media <= faixa[1],
                "frase": frase,
            }
        )
    parciais = int(serie["vazao_t_h"].isna().sum()) if "vazao_t_h" in serie else 0
    frases = []
    if parciais:
        frases.append(
            f"{parciais} dia(s) sem vapor do dia: leituras do totalizador cobriram menos de "
            f"{num(HORAS_MINIMAS, 0)} h ou o totalizador reiniciou (o dia fica em branco, não zero)."
        )
    return {
        "serie": [
            {k: (None if pd.isna(v) else v) for k, v in r.items()}
            for r in serie.to_dict(orient="records")
        ],
        "faixas": faixas,
        "quadros": quadros,
        "ultimo_dia": ultimo.isoformat(),
        "frases": frases,
    }
