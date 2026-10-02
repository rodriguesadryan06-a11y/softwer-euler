"""Resumo de um período de operação a partir das tabelas importadas.

Um período vai de uma medição de estoque a outra (é o que permite saber quanto
combustível foi queimado, E9). Para cada período: médias das leituras do diário,
vapor produzido, combustível queimado, qualidade do combustível recebido e do
**provavelmente** queimado, composição, preço, purgas e eventos. Nada é preenchido:
o que não pode ser determinado vira um **bloqueio** com motivo, em `bloqueios`.

Fase R (revisão do motor físico):
- cada grandeza carrega um orçamento de incerteza por componente (euler.incerteza);
- a qualidade do combustível **queimado** não é igualada à do recebido sem aviso:
  calculamos cenários de uso do pátio e os limites possíveis (D38);
- recebimento no mesmo horário de uma medição de estoque bloqueia o E9 (ER-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from math import sqrt

import numpy as np
import pandas as pd

from euler.combustivel import combustivel_queimado_kg, extrato_por_fornecedor
from euler.deteccao import Estatistica, estatistica_diaria
from euler.formato import num, pct
from euler.incerteza import Componente, Falta, Orcamento, incerteza_padrao
from euler.io import Pacote
from euler.io.leitura import FUSO_PADRAO
from euler.tipos import AnaliseBloqueada, Grandeza
from euler.vapor import delta_h_mj_kg

LEITURAS_DIARIO = {
    "t_gases_c": "°C",
    "o2_seco_pct": "%",
    "co_ppm": "ppm",
    "t_ar_c": "°C",
    "t_agua_alim_c": "°C",
    "p_vapor_bar_abs": "bar abs",
}
ELEMENTOS = ("C", "H", "O", "N", "S")
TOLERANCIA_INSTANTE = pd.Timedelta(minutes=1)

# Como reconhecer cada instrumento pelo `tipo` em instrumentos.csv (D23) e pelas palavras
# que o identificam na descrição de um evento de calibração/troca (D37).
INSTRUMENTOS = {
    "vapor": (("vapor",), ("vapor",)),
    "estoque": (("estoque",), ("estoque",)),
    "balanca": (("balanca",), ("balança", "balanca")),
    "umidade": (("umidade", "estufa"), ("estufa", "umidade")),
    "t_gases_c": (("gases",), ("termopar", "temperatura dos gases")),
    "o2_seco_pct": (("o2",), ("o₂", "o2", "oxigênio")),
    "p_vapor_bar_abs": (("manometro", "pressao"), ("manômetro", "manometro", "pressão")),
    "t_agua_alim_c": (("agua",), ("água de alimentação", "agua de alimentacao")),
    "t_ar_c": (("ar_combustao", "temperatura_ar"), ("ar de combustão",)),
    "pci_seco": (("calorimetro", "pci"), ("calorímetro", "calorimetro", "poder calorífico")),
}


ROTULO_LEITURA = {
    "t_gases_c": "temperatura dos gases",
    "o2_seco_pct": "O₂ nos gases",
    "p_vapor_bar_abs": "pressão do vapor",
    "t_agua_alim_c": "temperatura da água de alimentação",
    "t_ar_c": "temperatura do ar de combustão",
}
FALTA_METODO_UMIDADE = "incerteza do método de umidade (estufa)"
FALTA_PCI_SECO = "incerteza da análise de PCI seco (calorímetro)"


# ---------------------------------------------------------------- instrumentos


@dataclass(frozen=True)
class Instrumento:
    """Instrumento cadastrado e sua incerteza-padrão (k = 1)."""

    id: str
    tipo: str
    u: float
    relativa: bool
    interpretacao: str


def buscar_instrumento(
    pacote: Pacote, grandeza: str, id_preferido: str | None = None
) -> Instrumento | None:
    """Instrumento cadastrado para a grandeza, com a incerteza convertida (GUM, D35).

    Incerteza em `pct_da_leitura` vira fração relativa; `pct`/`pct_bu` de umidade vira
    fração absoluta; demais unidades ficam na unidade da grandeza.
    """
    inst = pacote.dados("instrumentos")
    if inst is None:
        return None
    candidatos = inst[inst["incerteza_declarada"].notna()]
    if id_preferido is not None and (candidatos["instrumento_id"] == id_preferido).any():
        candidatos = candidatos[candidatos["instrumento_id"] == id_preferido]
    else:
        palavras = INSTRUMENTOS[grandeza][0]
        tipo = candidatos["tipo"].fillna("").str.lower()
        candidatos = candidatos[tipo.apply(lambda t: any(p in t for p in palavras))]
    if candidatos.empty:
        return None
    linha = candidatos.iloc[0]
    tipo_decl = None if pd.isna(linha.get("incerteza_tipo")) else str(linha["incerteza_tipo"])
    k = None if pd.isna(linha.get("incerteza_k")) else float(linha["incerteza_k"])
    u, como = incerteza_padrao(float(linha["incerteza_declarada"]), tipo_decl, k)
    unidade = str(linha["unidade"]).lower()
    relativa = unidade == "pct_da_leitura"
    if relativa or grandeza == "umidade" and unidade.startswith("pct"):
        u /= 100
    return Instrumento(str(linha["instrumento_id"]), str(linha["tipo"]), u, relativa, como)


def chave_instrumento(
    pacote: Pacote,
    inst: Instrumento,
    grandeza: str,
    inicio: pd.Timestamp,
    fim: pd.Timestamp,
    outras_datas: tuple[pd.Timestamp, ...] = (),
) -> str:
    """Chave da "época" do instrumento: muda a cada calibração ou troca (D37).

    Datas consideradas: `ultima_verificacao` do instrumento, eventos de calibração ou
    troca que citam o instrumento (pelo código ou por palavra-chave) e `outras_datas`
    (ex.: reinício do totalizador). Evento dentro do período → época mista, só dele.
    """
    datas: list[pd.Timestamp] = list(outras_datas)
    cadastro = pacote.dados("instrumentos")
    if cadastro is not None:
        linha = cadastro[cadastro["instrumento_id"] == inst.id]
        if len(linha) and pd.notna(linha["ultima_verificacao"].iloc[0]):
            datas.append(pd.Timestamp(linha["ultima_verificacao"].iloc[0]).tz_localize(FUSO_PADRAO))
    eventos = pacote.dados("eventos")
    if eventos is not None:
        palavras = INSTRUMENTOS[grandeza][1]
        for _, ev in eventos[eventos["tipo"].isin(["calibracao", "troca_instrumento"])].iterrows():
            texto = str(ev["descricao"]).lower()
            if inst.id.lower() in texto or any(p in texto for p in palavras):
                datas.append(ev["instante"])
    if any(inicio < d < fim for d in datas):
        return f"instrumento:{inst.id}@misto:{inicio.isoformat()}"
    anteriores = [d for d in datas if d <= inicio]
    return f"instrumento:{inst.id}@{max(anteriores).isoformat() if anteriores else 'origem'}"


# ---------------------------------------------------------------- resumo


@dataclass(frozen=True)
class Cenarios:
    """Grandeza do combustível **queimado** sob hipóteses de uso do pátio (D38).

    recebido: o que entra no período é o que queima (D22, estimativa central). Lotes do
        período sem amostra entram com a média dos medidos — hipótese declarada em
        `condicoes` (D51).
    fifo: o pátio usa primeiro o material mais antigo (estoque inicial = últimos lotes
        recebidos antes do período). None quando os dados não cobrem o estoque inicial ou
        quando parte do material que o FIFO queimaria não tem qualidade conhecida (A1); o
        motivo fica em `fifo_indisponivel`.
    minimo/maximo: limites **contábeis** para qualquer uso do pátio, supondo o estoque
        inicial e os lotes sem amostra dentro da faixa observada nos lotes medidos. Não são
        intervalo de confiança nem desempenho validado.
    condicoes: hipóteses de cada cenário, em texto, para o JSON, a tela e o relatório.
    """

    recebido: float
    fifo: float | None
    minimo: float
    maximo: float
    fifo_indisponivel: str | None = None
    condicoes: tuple[str, ...] = ()

    @property
    def faixa_plausivel(self) -> tuple[float, float]:
        valores = [v for v in (self.recebido, self.fifo) if v is not None]
        return min(valores), max(valores)


@dataclass
class ResumoPeriodo:
    inicio: pd.Timestamp
    fim: pd.Timestamp
    leituras: dict[str, Estatistica] = field(default_factory=dict)
    leituras_grandeza: dict[str, Grandeza] = field(default_factory=dict)
    n_leituras_diario: int = 0
    cobertura_diario: float | None = None
    ponto_gases_id: str | None = None
    instrumento_o2_id: str | None = None
    vapor_t: Grandeza | None = None
    energia_util_intervalos_gj: float | None = None
    combustivel_kg: Grandeza | None = None
    estoque_inicial_kg: float | None = None
    estoque_final_kg: float | None = None
    umidade_mistura: Grandeza | None = None
    pci_umido_mistura: Grandeza | None = None
    pci_queimado: Cenarios | None = None
    umidade_queimada: Cenarios | None = None
    fracao_estoque: float | None = None
    pci_seco_mistura: float | None = None
    pci_seco: Grandeza | None = None
    composicao: dict[str, float] | None = None
    composicao_origem: str | None = None
    preco_brl_t: float | None = None
    preco_brl_gj: float | None = None
    lotes: int = 0
    lotes_sem_umidade: int = 0
    fracao_massa_sem_umidade: float | None = None
    umidade_por_fornecedor: dict[str, float] = field(default_factory=dict)
    purgas_n: float | None = None
    purgas_s: float | None = None
    eventos: list[dict] = field(default_factory=list)
    bloqueios: dict[str, AnaliseBloqueada] = field(default_factory=dict)

    @property
    def horas(self) -> float:
        return (self.fim - self.inicio).total_seconds() / 3600

    def rotulo(self) -> str:
        return f"{self.inicio:%d/%m/%Y %H:%M} a {self.fim:%d/%m/%Y %H:%M}"


def medicoes_de_estoque(pacote: Pacote) -> pd.DataFrame:
    """Medições de estoque com massa conhecida, em ordem de data."""
    comb = pacote.dados("combustivel")
    if comb is None:
        return pd.DataFrame(columns=["data", "massa_kg_calc", "linha"])
    estoques = comb[(comb["tipo"] == "estoque") & comb["massa_kg_calc"].notna()]
    return estoques.sort_values("data")[["data", "massa_kg_calc", "linha"]].reset_index(drop=True)


def periodos_entre_estoques(pacote: Pacote) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Intervalos entre medições de estoque consecutivas (os períodos possíveis)."""
    return list(pairwise(medicoes_de_estoque(pacote)["data"]))


def incerteza_relativa_instrumento(pacote: Pacote, tipo_contem: str) -> float | None:
    """Incerteza-padrão relativa (fração) de um instrumento em % da leitura (D35).

    Mantida por compatibilidade (capacidades); usa a interpretação do GUM, não k = 2 fixo.
    """
    inst = buscar_instrumento(pacote, tipo_contem)
    return inst.u if inst is not None and inst.relativa else None


def _intervalo_tipico_h(diario: pd.DataFrame) -> float:
    passos = diario["instante_observado"].dropna().sort_values().diff().dt.total_seconds() / 3600
    passos = passos[passos > 0]
    return float(passos.median()) if len(passos) else 2.0


def _lotes_todos(pacote: Pacote) -> pd.DataFrame:
    """Todos os lotes recebidos com massa, umidade e PCI úmido (calculado uma vez)."""
    cache = pacote.__dict__.setdefault("_cache_periodos", {})
    if "lotes" not in cache:
        comb, amos = pacote.dados("combustivel"), pacote.dados("amostras")
        lotes = extrato_por_fornecedor(comb, amos).lotes if comb is not None else pd.DataFrame()
        cache["lotes"] = lotes.dropna(subset=["massa_kg"]) if len(lotes) else lotes
    return cache["lotes"]


def _vapor(pacote: Pacote, diario: pd.DataFrame, r: ResumoPeriodo) -> None:
    """Vapor produzido no período pelo totalizador (só diferenças, nunca preenchido)."""
    falta = ["leituras do totalizador de vapor no início e no fim do período, sem reinício"]
    todos = diario.dropna(subset=["totalizador_vapor_t"]).sort_values(
        ["instante_observado", "linha"]
    )
    tot = todos[(todos["instante_observado"] >= r.inicio) & (todos["instante_observado"] <= r.fim)]
    if len(tot) < 2:
        r.bloqueios["vapor"] = AnaliseBloqueada(
            "Sem leituras do totalizador de vapor neste período: o vapor produzido não é conhecido.",
            falta,
        )
        return
    valores = tot["totalizador_vapor_t"].astype(float).values
    if not np.isfinite(valores).all():
        r.bloqueios["vapor"] = AnaliseBloqueada(
            "Leitura do totalizador de vapor inválida (não é um número finito) neste período.",
            falta,
        )
        return
    reinicio = [i for i in range(1, len(valores)) if valores[i] < valores[i - 1]]
    if reinicio:
        linha = int(tot["linha"].iloc[reinicio[0]])
        r.bloqueios["vapor"] = AnaliseBloqueada(
            f"O totalizador de vapor reiniciou dentro do período (linha {linha} do diário): "
            "o vapor produzido entre essas leituras não é conhecido.",
            falta,
        )
        return
    tipico = _intervalo_tipico_h(diario)
    primeira, ultima = tot["instante_observado"].iloc[0], tot["instante_observado"].iloc[-1]
    folga_ini = (primeira - r.inicio).total_seconds() / 3600
    folga_fim = (r.fim - ultima).total_seconds() / 3600
    if folga_ini > tipico or folga_fim > tipico:
        r.bloqueios["vapor"] = AnaliseBloqueada(
            "Faltam leituras do totalizador de vapor perto do início ou do fim do período "
            f"(primeira às {primeira:%d/%m %H:%M}, última às {ultima:%d/%m %H:%M}).",
            falta,
        )
        return
    horas_lidas = (ultima - primeira).total_seconds() / 3600
    medido = float(valores[-1] - valores[0])
    if horas_lidas <= 0:
        r.bloqueios["vapor"] = AnaliseBloqueada(
            "As leituras do totalizador de vapor deste período têm todas o mesmo horário: não "
            "há intervalo para medir o vapor.",
            falta,
        )
        return
    if medido <= 0:
        r.bloqueios["vapor"] = AnaliseBloqueada(
            f"O totalizador de vapor não avançou no período ({valores[0]:.1f} t do início ao "
            "fim): caldeira parada ou totalizador travado. Sem vapor produzido, consumo por "
            "tonelada e eficiência não se aplicam.",
            ["vapor produzido no período (totalizador funcionando)"],
        )
        return
    vapor = medido * r.horas / horas_lidas
    _energia_util_intervalos(tot, r, r.horas / horas_lidas)

    orc = Orcamento()
    # bordas: vapor estimado pela vazão média; erro ~ variação da vazão × horas de borda
    horas = tot["instante_observado"].diff().dt.total_seconds().div(3600).iloc[1:].values
    vazoes = pd.Series(valores).diff().iloc[1:].values / horas
    horas_borda = folga_ini + folga_fim
    if horas_borda > 0 and len(vazoes) >= 2:
        orc.componentes.append(
            Componente(
                "vapor nas bordas do período (estimado pela vazão média)",
                float(pd.Series(vazoes).std(ddof=1)) * horas_borda / vapor,
                "modelo",
                nota=f"{horas_borda:.1f} h de borda × variação da vazão entre leituras",
            )
        )
    # medidor: erro sistemático declarado; a época muda com calibração, troca ou reinício
    inst = buscar_instrumento(pacote, "vapor")
    if inst is not None and inst.relativa:
        reinicios = tuple(
            todos["instante_observado"].iloc[i]
            for i in range(1, len(todos))
            if todos["totalizador_vapor_t"].iloc[i] < todos["totalizador_vapor_t"].iloc[i - 1]
        )
        orc.componentes.append(
            Componente(
                f"medidor de vapor {inst.id}",
                inst.u,
                "instrumental",
                chave_instrumento(pacote, inst, "vapor", r.inicio, r.fim, reinicios),
                inst.interpretacao,
            )
        )
    else:
        orc.faltam.append(Falta("incerteza do medidor de vapor"))
    r.vapor_t = Grandeza(
        vapor,
        "t",
        "estimado" if abs(horas_lidas - r.horas) > 1e-6 else "medido",
        incerteza=orc.incerteza_k2(vapor),
        nota=(
            f"totalizador lido de {primeira:%d/%m %H:%M} a {ultima:%d/%m %H:%M} "
            f"({horas_lidas:.0f} h de {r.horas:.0f} h); bordas pela vazão média do período"
        ),
        orcamento=orc,
    )


def _energia_util_intervalos(tot: pd.DataFrame, r: ResumoPeriodo, escala: float) -> None:
    """Q_s = Σ ΔM_k · Δh(p_k, T_a,k) (E8), intervalo a intervalo entre leituras do
    totalizador, com p e T_a médias das duas leituras do intervalo. Só é usado quando
    todos os intervalos têm pressão e água de alimentação; senão fica None (D46)."""
    soma, cobertos = 0.0, 0
    linhas = list(tot.itertuples())
    for ant, atual in pairwise(linhas):
        massa = float(atual.totalizador_vapor_t) - float(ant.totalizador_vapor_t)
        p = pd.Series([ant.p_vapor_bar_abs, atual.p_vapor_bar_abs]).dropna()
        t = pd.Series([ant.t_agua_alim_c, atual.t_agua_alim_c]).dropna()
        if massa == 0:
            cobertos += 1
            continue
        if p.empty or t.empty:
            continue
        try:
            soma += massa * delta_h_mj_kg(float(p.mean()), "saturado_seco", float(t.mean()))
        except AnaliseBloqueada:
            continue
        cobertos += 1
    if linhas and cobertos == len(linhas) - 1:
        r.energia_util_intervalos_gj = soma * escala


def _combustivel(pacote: Pacote, r: ResumoPeriodo) -> None:
    """Combustível queimado no período (E9), com a incerteza de cada medição de estoque."""
    comb = pacote.dados("combustivel")
    if comb is None:
        r.bloqueios["combustivel"] = AnaliseBloqueada(
            "Sem recebimentos de combustível: o combustível queimado não é conhecido.",
            ["recebimentos e medições de estoque"],
        )
        return
    estoques = medicoes_de_estoque(pacote)
    ini = estoques[(estoques["data"] - r.inicio).abs() <= TOLERANCIA_INSTANTE]
    fim = estoques[(estoques["data"] - r.fim).abs() <= TOLERANCIA_INSTANTE]
    receb_todos = comb[comb["tipo"] == "recebimento"]
    simultaneos = receb_todos[
        ((receb_todos["data"] - r.inicio).abs() <= TOLERANCIA_INSTANTE)
        | ((receb_todos["data"] - r.fim).abs() <= TOLERANCIA_INSTANTE)
    ]
    if len(simultaneos):
        linhas = ", ".join(str(int(n)) for n in simultaneos["linha"])
        r.bloqueios["combustivel"] = AnaliseBloqueada(
            f"Recebimento registrado no mesmo horário de uma medição de estoque (linha {linhas} "
            "dos recebimentos de combustível): não dá para saber se ele já estava no estoque "
            "medido.",
            ["horário do recebimento ou da medição de estoque, com a ordem entre eles"],
        )
        return
    receb = receb_todos[(receb_todos["data"] > r.inicio) & (receb_todos["data"] <= r.fim)]
    s0 = None if ini.empty else float(ini["massa_kg_calc"].iloc[0])
    s1 = None if fim.empty else float(fim["massa_kg_calc"].iloc[0])
    try:
        m = combustivel_queimado_kg(
            s0, [None if pd.isna(x) else float(x) for x in receb["massa_kg_calc"]], s1
        )
    except AnaliseBloqueada as b:
        r.bloqueios["combustivel"] = b
        return
    r.estoque_inicial_kg, r.estoque_final_kg = s0, s1
    if not np.isfinite(m) or m <= 0:
        r.bloqueios["combustivel"] = AnaliseBloqueada(
            f"O combustível queimado no período dá zero ({m:.0f} kg: estoque inicial + "
            "recebimentos − estoque final): caldeira parada ou medições de estoque repetidas. "
            "Consumo por tonelada e eficiência não se aplicam.",
            ["medições de estoque e recebimentos do período"],
        )
        return

    orc = Orcamento()
    inst_est = buscar_instrumento(pacote, "estoque")
    if inst_est is not None and inst_est.relativa:
        for sinal, massa, instante in ((+1, s0, r.inicio), (-1, s1, r.fim)):
            orc.componentes.append(
                Componente(
                    f"medição de estoque de {instante:%d/%m %H:%M}",
                    sinal * inst_est.u * massa / m,
                    "instrumental",
                    f"medicao:estoque@{instante.isoformat()}",
                    inst_est.interpretacao,
                )
            )
        orc.nao_incluidos.append(
            "parcela sistemática comum às medições de estoque (método), não declarada à parte"
        )
    else:
        orc.faltam.append(Falta("incerteza da medição de estoque"))
    inst_bal = buscar_instrumento(pacote, "balanca")
    if inst_bal is not None and not inst_bal.relativa and len(receb):
        # O cadastro não separa a parte aleatória da sistemática (calibração): o erro é
        # tratado como comum a todas as pesagens (n·u, limite superior), sem dividir por √n
        # (GUM 5.2; D45). Pesagens independentes dariam √n·u.
        orc.componentes.append(
            Componente(
                f"pesagem de {len(receb)} recebimentos ({inst_bal.id})",
                len(receb) * inst_bal.u / m,
                "instrumental",
                chave_instrumento(pacote, inst_bal, "balanca", r.inicio, r.fim),
                inst_bal.interpretacao
                + "; erro tratado como comum a todas as pesagens (limite superior)",
            )
        )
    elif len(receb):
        orc.faltam.append(Falta("incerteza da balança dos recebimentos"))
    origens = set(receb["massa_origem"].dropna())
    if "estimado" in origens:
        orc.faltam.append(Falta("incerteza da densidade usada nos recebimentos medidos por volume"))
    r.combustivel_kg = Grandeza(
        m,
        "kg",
        "medido" if origens <= {"medido"} else "estimado",
        incerteza=orc.incerteza_k2(m),
        nota=f"estoque inicial + {len(receb)} recebimentos − estoque final (E9)",
        orcamento=orc,
    )


def _media_ponderada(df: pd.DataFrame, col: str) -> float:
    return float((df[col] * df["massa_kg"]).sum() / df["massa_kg"].sum())


def _cenarios(
    lotes_todos: pd.DataFrame, col: str, r: ResumoPeriodo, recebido: float
) -> Cenarios | None:
    """Qualidade do combustível queimado sob uso FIFO do pátio e limites para qualquer uso.

    Nada é preenchido em silêncio: massa sem qualidade conhecida nunca some do denominador.
    O FIFO fica indisponível se queimaria massa sem qualidade conhecida (A1); as hipóteses
    dos outros cenários vão para `condicoes`.
    """
    if r.estoque_inicial_kg is None or r.estoque_final_kg is None or r.combustivel_kg is None:
        return None
    m_queimado = r.combustivel_kg.valor
    conhecidos = lotes_todos.dropna(subset=[col])
    if conhecidos.empty or m_queimado <= 0:
        return None
    q_min, q_max = float(conhecidos[col].min()), float(conhecidos[col].max())
    antes = lotes_todos[lotes_todos["data"] <= r.inicio].sort_values("data")
    no_periodo = lotes_todos[
        (lotes_todos["data"] > r.inicio) & (lotes_todos["data"] <= r.fim)
    ].sort_values("data")
    qualidade = "umidade" if col == "umidade_bu_frac" else "PCI"
    condicoes = []
    sem_q = float(no_periodo.loc[no_periodo[col].isna(), "massa_kg"].sum())
    if sem_q > 0:
        condicoes.append(
            f"recebido: {_t(sem_q)} de lotes do período sem amostra ({pct(sem_q / float(no_periodo['massa_kg'].sum()))} "
            f"da massa recebida) entram com a média dos lotes medidos (hipótese, D51)"
        )

    # FIFO: estoque inicial = últimos lotes antes do início, até completar S0
    fifo, fifo_indisponivel = None, None
    estoque_ini, falta = [], r.estoque_inicial_kg
    for _, lote in antes.iloc[::-1].iterrows():
        if falta <= 0:
            break
        usar = min(falta, float(lote["massa_kg"]))
        estoque_ini.insert(0, (usar, lote[col]))
        falta -= usar
    if falta > 1e-6:
        fifo_indisponivel = (
            f"os lotes registrados antes do período cobrem só {_t(r.estoque_inicial_kg - falta)} "
            f"dos {_t(r.estoque_inicial_kg)} do estoque inicial"
        )
    else:
        fila = estoque_ini + [(float(x["massa_kg"]), x[col]) for _, x in no_periodo.iterrows()]
        massa_q, soma_q, sem_qualidade, restante = 0.0, 0.0, 0.0, m_queimado
        for massa, q in fila:
            if restante <= 0:
                break
            usar = min(massa, restante)
            restante -= usar
            if pd.notna(q):
                massa_q += usar
                soma_q += usar * float(q)
            else:
                sem_qualidade += usar
        if sem_qualidade > 1e-6:
            fifo_indisponivel = (
                f"{_t(sem_qualidade)} do combustível que o FIFO queimaria vêm de lotes sem "
                f"{qualidade} conhecida"
            )
        elif restante > 1e-6 or massa_q <= 0:
            fifo_indisponivel = "os lotes registrados não cobrem o combustível queimado"
        else:
            fifo = soma_q / massa_q

    def limite(maximo: bool) -> float:
        """Estoque inicial de qualidade desconhecida; o estoque final pode ser qualquer parte
        do material disponível. Para o máximo do queimado, o pior material fica no pátio."""
        desconhecido = q_max if maximo else q_min
        material = [(r.estoque_inicial_kg, desconhecido)] + [
            (float(x["massa_kg"]), float(x[col]) if pd.notna(x[col]) else desconhecido)
            for _, x in no_periodo.iterrows()
        ]
        material.sort(key=lambda par: par[1], reverse=not maximo)
        sobra, no_final = r.estoque_final_kg, 0.0
        for massa, q in material:
            usar = min(massa, sobra)
            no_final += usar * q
            sobra -= usar
            if sobra <= 0:
                break
        total = sum(massa * q for massa, q in material)
        return (total - no_final) / m_queimado

    faixa = f"{_q(col, q_min)} a {_q(col, q_max)}"
    condicoes.append(
        "mínimo e máximo: limites contábeis para qualquer uso do pátio, supondo o estoque "
        + "inicial"
        + (" e os lotes sem amostra" if sem_q > 0 else "")
        + f" dentro da faixa observada nos lotes medidos ({faixa}); não são intervalo de "
        "confiança"
    )
    return Cenarios(
        recebido, fifo, limite(False), limite(True), fifo_indisponivel, tuple(condicoes)
    )


def _t(kg: float) -> str:
    return f"{num(kg / 1000, 0)} t"


def _q(col: str, valor: float) -> str:
    return pct(valor) if col == "umidade_bu_frac" else f"{num(valor, 2)} MJ/kg"


def _mistura(pacote: Pacote, r: ResumoPeriodo) -> None:
    """Qualidade da mistura recebida e do combustível provavelmente queimado (D22, D38)."""
    comb, amos = pacote.dados("combustivel"), pacote.dados("amostras")
    if comb is None:
        return
    e = extrato_por_fornecedor(comb, amos, inicio=r.inicio + pd.Timedelta(seconds=1), fim=r.fim)
    lotes = e.lotes.dropna(subset=["massa_kg"])
    r.lotes = len(e.lotes)
    if lotes.empty:
        r.bloqueios["mistura"] = AnaliseBloqueada(
            "Nenhum recebimento com massa conhecida neste período.", ["recebimentos pesados"]
        )
        return
    medidos = lotes.dropna(subset=["umidade_bu_frac"])
    r.lotes_sem_umidade = int(len(e.lotes) - len(e.lotes.dropna(subset=["umidade_bu_frac"])))
    r.fracao_massa_sem_umidade = float(1 - medidos["massa_kg"].sum() / lotes["massa_kg"].sum())
    det = lotes[lotes["situacao"] == "determinada"]
    if len(medidos) < 2 or len(det) < 2:
        r.bloqueios["mistura"] = AnaliseBloqueada(
            "Menos de dois lotes com umidade e PCI conhecidos neste período: a energia da "
            "mistura de combustível não é conhecida.",
            ["umidade medida de cada lote recebido"],
        )
        return

    w = _media_ponderada(medidos, "umidade_bu_frac")
    # variação entre lotes: dispersão do PROCESSO (serve para dizer se a umidade recebida
    # mudou além do normal); não é incerteza de medição (ER-1)
    var_lotes = float(medidos["umidade_bu_frac"].std(ddof=1) / sqrt(len(medidos))) / w
    orc_w = Orcamento(
        [
            Componente(
                "variação entre lotes (dispersão do processo)",
                var_lotes,
                "aleatoria",
                entrada="umidade_bu_frac",
            )
        ]
    )
    inst_w = buscar_instrumento(pacote, "umidade")
    chave_w = (
        None
        if inst_w is None or inst_w.relativa
        else chave_instrumento(pacote, inst_w, "umidade", r.inicio, r.fim)
    )
    if chave_w is not None:
        orc_w.componentes.append(
            Componente(
                f"método de umidade ({inst_w.id})",
                inst_w.u / w,
                "instrumental",
                chave_w,
                inst_w.interpretacao,
                "umidade_bu_frac",
            )
        )
    else:
        orc_w.faltam.append(Falta(FALTA_METODO_UMIDADE))
    orc_w.nao_incluidos.append("representatividade da amostra de cada lote (E11)")
    nota = f"média dos {len(medidos)} lotes recebidos com umidade medida, ponderada pela massa" + (
        f"; {r.fracao_massa_sem_umidade:.0%} da massa sem umidade medida"
        if r.fracao_massa_sem_umidade
        else ""
    )
    r.umidade_mistura = Grandeza(w, "fração", "estimado", orc_w.incerteza_k2(w), nota, orc_w)

    pci = _media_ponderada(det, "pci_umido_mj_kg")
    r.pci_seco_mistura = _media_ponderada(det, "pci_seco_mj_kg")
    orc_pci = Orcamento()
    # PCI seco: entra nos dois caminhos (PCI úmido → η; denominador da perda nos gases)
    orc_s = Orcamento()
    inst_c = buscar_instrumento(pacote, "pci_seco")
    if inst_c is not None:
        u_s = inst_c.u * r.pci_seco_mistura if inst_c.relativa else inst_c.u
        chave_c = chave_instrumento(pacote, inst_c, "pci_seco", r.inicio, r.fim)
        orc_s.componentes.append(
            Componente(
                f"análise de PCI seco ({inst_c.id})",
                u_s / r.pci_seco_mistura,
                "instrumental",
                chave_c,
                inst_c.interpretacao,
                "pci_seco_mj_kg",
            )
        )
        orc_pci.componentes.append(
            Componente(
                f"análise de PCI seco ({inst_c.id})",
                (1 - w) * u_s / pci,  # ∂PCI_u/∂PCI_s = 1 − w (E5)
                "instrumental",
                chave_c,
                inst_c.interpretacao,
                "pci_seco_mj_kg",
            )
        )
    else:
        orc_s.faltam.append(Falta(FALTA_PCI_SECO))
        orc_pci.faltam.append(Falta(FALTA_PCI_SECO))
    orc_s.nao_incluidos.append("representatividade da amostra de cada lote (E11)")
    r.pci_seco = Grandeza(
        r.pci_seco_mistura,
        "MJ/kg",
        "estimado",
        orc_s.incerteza_k2(r.pci_seco_mistura),
        "PCI seco médio dos lotes recebidos, ponderado pela massa",
        orc_s,
    )
    if chave_w is not None:
        orc_pci.componentes.append(
            Componente(
                f"método de umidade ({inst_w.id})",
                -(r.pci_seco_mistura + 2.442) * inst_w.u / pci,  # ∂PCI_u/∂w (E5)
                "instrumental",
                chave_w,
                inst_w.interpretacao,
                "umidade_bu_frac",
            )
        )
    else:
        orc_pci.faltam.append(Falta(FALTA_METODO_UMIDADE))
    orc_pci.nao_incluidos += [
        "representatividade da amostra de cada lote (E11)",
        "diferença entre o combustível recebido e o queimado (ver cenários do pátio, D38)",
    ]
    r.pci_umido_mistura = Grandeza(
        pci,
        "MJ/kg",
        "estimado",
        None,
        "PCI úmido médio dos lotes recebidos no período (cenário 'o que entra é o que queima')",
        orc_pci,
    )
    todos = _lotes_todos(pacote)
    r.pci_queimado = _cenarios(todos, "pci_umido_mj_kg", r, pci)
    r.umidade_queimada = _cenarios(todos, "umidade_bu_frac", r, w)
    if r.combustivel_kg is not None and r.estoque_inicial_kg is not None:
        r.fracao_estoque = (r.estoque_inicial_kg + r.estoque_final_kg) / r.combustivel_kg.valor
    com_preco = lotes.dropna(subset=["preco_brl"])
    if len(com_preco):
        r.preco_brl_t = float(com_preco["preco_brl"].sum() / (com_preco["massa_kg"].sum() / 1000))
    det_preco = det.dropna(subset=["brl_gj"])
    if len(det_preco):
        r.preco_brl_gj = float(det_preco["preco_brl"].sum() / det_preco["energia_gj"].sum())
    for forn, g in medidos.dropna(subset=["fornecedor_id"]).groupby("fornecedor_id"):
        r.umidade_por_fornecedor[forn] = _media_ponderada(g, "umidade_bu_frac")


def _composicao(pacote: Pacote, r: ResumoPeriodo) -> None:
    """Composição elementar média das análises do período (ou a mais próxima, assumida)."""
    amos = pacote.dados("amostras")
    if amos is None:
        return
    completas = amos.dropna(subset=list(ELEMENTOS))
    if completas.empty:
        return
    no_periodo = completas[(completas["data"] >= r.inicio) & (completas["data"] <= r.fim)]
    if len(no_periodo):
        r.composicao = {e: float(no_periodo[e].mean()) for e in ELEMENTOS}
        r.composicao_origem = f"medido ({len(no_periodo)} análises no período)"
    else:
        meio = r.inicio + (r.fim - r.inicio) / 2
        mais_proxima = completas.loc[(completas["data"] - meio).abs().idxmin()]
        r.composicao = {e: float(mais_proxima[e]) for e in ELEMENTOS}
        r.composicao_origem = f"assumido (análise de {mais_proxima['data']:%d/%m/%Y})"


def grandeza_leitura(
    pacote: Pacote, r: ResumoPeriodo, coluna: str, id_instrumento: str | None = None
) -> Grandeza | None:
    """Média de uma leitura do diário com orçamento: dispersão diária + instrumento."""
    est = r.leituras.get(coluna)
    if est is None or est.media == 0:
        return None
    orc = Orcamento()
    if est.erro_padrao is not None:
        orc.componentes.append(
            Componente("dispersão das médias diárias", est.erro_padrao / est.media, "aleatoria")
        )
    else:
        orc.faltam.append(Falta("dispersão das médias diárias (menos de dois dias)", False))
    if coluna in INSTRUMENTOS:
        inst = buscar_instrumento(pacote, coluna, id_instrumento)
        if inst is not None:
            u_abs = inst.u * est.media if inst.relativa else inst.u
            orc.componentes.append(
                Componente(
                    f"instrumento {inst.id}",
                    u_abs / est.media,
                    "instrumental",
                    chave_instrumento(pacote, inst, coluna, r.inicio, r.fim),
                    inst.interpretacao,
                )
            )
        else:
            orc.faltam.append(Falta(f"incerteza do instrumento de {ROTULO_LEITURA[coluna]}"))
    return Grandeza(
        est.media, est.unidade, "medido", orc.incerteza_k2(est.media), "média do período", orc
    )


def resumir_periodo(pacote: Pacote, inicio: pd.Timestamp, fim: pd.Timestamp) -> ResumoPeriodo:
    """Resume o período [inicio, fim] (inicio e fim devem ser medições de estoque)."""
    r = ResumoPeriodo(inicio=inicio, fim=fim)
    diario = pacote.dados("diario")
    if diario is None:
        r.bloqueios["diario"] = AnaliseBloqueada(
            "Sem diário do operador: não há leituras da caldeira.", ["diário do operador"]
        )
    else:
        no_periodo = diario[
            (diario["instante_observado"] >= inicio) & (diario["instante_observado"] < fim)
        ]
        operando = no_periodo[no_periodo["regime"].fillna("estavel") != "parada"]
        operando = operando.drop_duplicates(subset=[c for c in operando.columns if c != "linha"])
        r.n_leituras_diario = len(operando)

        # Temperatura e O₂ só podem alimentar o caminho indireto quando pertencem a uma
        # mesma fronteira física. Misturar, por exemplo, saída da caldeira e pós-economizador
        # cria uma média que não representa nenhum estado real (D67).
        usa_gases = operando["t_gases_c"].notna() | operando["o2_seco_pct"].notna()
        pontos = operando.loc[usa_gases, "ponto_gases_id"].dropna().astype(str).str.strip()
        pontos = tuple(dict.fromkeys(p for p in pontos if p))
        if len(pontos) == 1:
            r.ponto_gases_id = pontos[0]
        elif len(pontos) > 1:
            r.bloqueios["ponto_gases"] = AnaliseBloqueada(
                "Há leituras de gases em mais de um ponto no mesmo período "
                f"({', '.join(pontos)}). A EULER não mistura pontos físicos diferentes.",
                [
                    (
                        "selecionar um único ponto de medição dos gases para o período "
                        "ou analisar cada ponto separadamente"
                    )
                ],
            )
        if r.horas > 0 and len(no_periodo):
            r.cobertura_diario = min(1.0, len(no_periodo) * _intervalo_tipico_h(diario) / r.horas)
        for coluna, unidade in LEITURAS_DIARIO.items():
            est = estatistica_diaria(operando[coluna], operando["instante_observado"], unidade)
            if est is not None:
                r.leituras[coluna] = est
        id_o2 = operando.loc[operando["o2_seco_pct"].notna(), "instrumento_o2_id"]
        id_o2 = tuple(dict.fromkeys(str(x).strip() for x in id_o2.dropna() if str(x).strip()))
        if len(id_o2) == 1:
            r.instrumento_o2_id = id_o2[0]
        elif len(id_o2) > 1:
            r.bloqueios["instrumento_o2"] = AnaliseBloqueada(
                "Há leituras de O₂ de mais de um analisador no mesmo período "
                f"({', '.join(id_o2)}). A EULER não atribui a média à incerteza de um único "
                "instrumento.",
                [
                    (
                        "separar as leituras por analisador de O₂ ou confirmar qual instrumento "
                        "representa o período"
                    )
                ],
            )
        for coluna in r.leituras:
            g = grandeza_leitura(
                pacote,
                r,
                coluna,
                r.instrumento_o2_id if coluna == "o2_seco_pct" else None,
            )
            if g is not None:
                r.leituras_grandeza[coluna] = g
        if no_periodo["purgas_n"].notna().any():
            r.purgas_n = float(no_periodo["purgas_n"].sum())
        if no_periodo["purgas_s"].notna().any():
            r.purgas_s = float(no_periodo["purgas_s"].sum())
        _vapor(pacote, diario, r)
    _combustivel(pacote, r)
    _mistura(pacote, r)
    _composicao(pacote, r)
    eventos = pacote.dados("eventos")
    if eventos is not None:
        ev = eventos[(eventos["instante"] >= inicio) & (eventos["instante"] <= fim)]
        r.eventos = [
            {"instante": t, "tipo": tipo, "descricao": d}
            for t, tipo, d in zip(ev["instante"], ev["tipo"], ev["descricao"], strict=True)
        ]
    return r
