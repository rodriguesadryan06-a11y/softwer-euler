"""Mapa adaptativo da planta: primeiro pergunta "o que esta planta tem?".

A EULER não exige um pacote universal de tags. Este módulo inventaria dados se transformasse
ausência em zero; em vez disso, ele identifica os sinais observados e escolhe, por pergunta
física, a rota com maior cobertura entre alternativas explícitas.

O mapa descreve o que pode ser calculado/investigado. Ele não eleva correlação a causa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from euler.io import Pacote

SituacaoRota = Literal["disponivel", "parcial", "indisponivel"]


@dataclass(frozen=True)
class Sinal:
    id: str
    nome: str
    tabela: str
    n: int
    cobertura: float | None = None


@dataclass(frozen=True)
class RotaFisica:
    id: str
    nome: str
    pergunta: str
    situacao: SituacaoRota
    alternativa: str
    usando: tuple[str, ...] = ()
    faltam: tuple[str, ...] = ()
    nota: str = ""


@dataclass(frozen=True)
class PerfilPlanta:
    sinais: dict[str, Sinal] = field(default_factory=dict)
    rotas: tuple[RotaFisica, ...] = ()

    def rota(self, id_: str) -> RotaFisica:
        return next(r for r in self.rotas if r.id == id_)

    @property
    def disponiveis(self) -> tuple[RotaFisica, ...]:
        return tuple(r for r in self.rotas if r.situacao == "disponivel")


ROTULOS = {
    "p_atm": "pressão atmosférica/altitude",
    "p_vapor_bar_abs": "pressão absoluta do vapor",
    "p_vapor_bar_man": "pressão do vapor",
    "t_vapor_c": "temperatura do vapor",
    "titulo_vapor": "título do vapor",
    "estado_vapor": "estado do vapor",
    "t_agua_alim_c": "temperatura da água de alimentação",
    "totalizador_vapor_t": "totalizador de vapor",
    "vazao_vapor_t_h": "vazão de vapor",
    "vazao_combustivel_kg_h": "vazão mássica de combustível",
    "pci_combustivel_mj_kg": "PCI do combustível em operação",
    "potencia_combustivel_mw": "potência térmica do combustível",
    "t_gases_c": "temperatura dos gases",
    "o2_seco_pct": "O₂ seco nos gases",
    "co_ppm": "CO nos gases",
    "t_ar_c": "temperatura do ar de combustão",
    "umidade_bu_frac": "umidade do combustível",
    "pci_seco_mj_kg": "PCI seco",
    "C": "carbono",
    "H": "hidrogênio",
    "O": "oxigênio",
    "N": "nitrogênio",
    "S": "enxofre",
    "massa_purga_kg": "massa purgada",
    "p_purga_bar_abs": "pressão absoluta da purga",
    "vazao_agua_alim_t_h": "vazão de água de alimentação",
    "p_agua_eco_bar_abs": "pressão da água no economizador",
    "t_agua_eco_entrada_c": "temperatura da água na entrada do economizador",
    "t_agua_eco_saida_c": "temperatura da água na saída do economizador",
    "t_gases_eco_entrada_c": "temperatura dos gases na entrada do economizador",
    "t_gases_eco_saida_c": "temperatura dos gases na saída do economizador",
    "dp_gases_mbar": "ΔP no caminho dos gases",
    "recebimentos": "recebimentos de combustível",
    "estoques": "medições de estoque",
    "preco_brl": "preço do combustível",
}


def _n(df: pd.DataFrame | None, coluna: str) -> int:
    return 0 if df is None or coluna not in df else int(df[coluna].notna().sum())


def _sinal(sinais: dict[str, Sinal], id_: str, nome: str, tabela: str, n: int, total: int | None):
    if n <= 0:
        return
    cobertura = None if not total else n / total
    sinais[id_] = Sinal(id_, nome, tabela, n, cobertura)


def _avaliar_rota(
    observados: set[str],
    id_: str,
    nome: str,
    pergunta: str,
    alternativas: tuple[tuple[str, tuple[str, ...]], ...],
    nota: str = "",
) -> RotaFisica:
    candidatos = []
    for nome_alt, requisitos in alternativas:
        usando = tuple(x for x in requisitos if x in observados)
        faltam = tuple(x for x in requisitos if x not in observados)
        candidatos.append((len(faltam), -len(usando), nome_alt, usando, faltam))
    _, _, nome_alt, usando, faltam = min(candidatos)
    if not faltam:
        situacao: SituacaoRota = "disponivel"
    elif usando:
        situacao = "parcial"
    else:
        situacao = "indisponivel"
    return RotaFisica(
        id_,
        nome,
        pergunta,
        situacao,
        nome_alt,
        tuple(ROTULOS.get(x, x) for x in usando),
        tuple(ROTULOS.get(x, x) for x in faltam),
        nota,
    )


def mapear_planta(pacote: Pacote) -> PerfilPlanta:
    diario = pacote.dados("diario")
    combustivel = pacote.dados("combustivel")
    amostras = pacote.dados("amostras")
    sinais: dict[str, Sinal] = {}

    total_d = None if diario is None else len(diario)
    for coluna, nome in ROTULOS.items():
        if coluna in {"p_atm", "recebimentos", "estoques"}:
            continue
        if coluna in (amostras.columns if amostras is not None else []):
            _sinal(sinais, coluna, nome, "amostras", _n(amostras, coluna), len(amostras))
        elif coluna in (combustivel.columns if combustivel is not None else []):
            _sinal(
                sinais, coluna, nome, "combustivel", _n(combustivel, coluna), len(combustivel)
            )
        elif coluna in (diario.columns if diario is not None else []):
            _sinal(sinais, coluna, nome, "diario", _n(diario, coluna), total_d)

    if pacote.p_atm_bar is not None:
        sinais["p_atm"] = Sinal("p_atm", ROTULOS["p_atm"], "local", 1, 1.0)
    if combustivel is not None and "tipo" in combustivel:
        n_rec = int((combustivel["tipo"] == "recebimento").sum())
        n_est = int((combustivel["tipo"] == "estoque").sum())
        if n_rec:
            sinais["recebimentos"] = Sinal("recebimentos", ROTULOS["recebimentos"], "combustivel", n_rec)
        if n_est:
            sinais["estoques"] = Sinal("estoques", ROTULOS["estoques"], "combustivel", n_est)

    obs = set(sinais)
    estado = ("estado_vapor",)
    termo_vapor = ("p_vapor_bar_abs", "t_agua_alim_c")
    rotas = [
        _avaliar_rota(
            obs,
            "estado_vapor",
            "Estado termodinâmico do vapor",
            "Qual é o estado energético do vapor disponível?",
            (
                ("P + T do vapor", ("p_vapor_bar_abs", "t_vapor_c")),
                ("P + estado declarado", ("p_vapor_bar_abs", "estado_vapor")),
            ),
            "Perto da saturação, P e T não determinam o título; a EULER não inventa x.",
        ),
        _avaliar_rota(
            obs,
            "energia_vapor",
            "Energia útil do vapor",
            "Quanta energia saiu como vapor?",
            (
                ("totalizador", ("totalizador_vapor_t", *termo_vapor)),
                ("vazão integrada", ("vazao_vapor_t_h", *termo_vapor)),
            ),
            "O estado do vapor é resolvido separadamente; superaquecido exige T e vapor úmido exige x.",
        ),
        _avaliar_rota(
            obs,
            "energia_combustivel",
            "Energia do combustível",
            "Quanta energia entrou pelo combustível?",
            (
                (
                    "vazão mássica + PCI",
                    ("vazao_combustivel_kg_h", "pci_combustivel_mj_kg"),
                ),
                ("potência térmica do historiador", ("potencia_combustivel_mw",)),
                (
                    "balanço de pátio",
                    ("recebimentos", "estoques", "umidade_bu_frac", "pci_seco_mj_kg"),
                ),
            ),
        ),
        _avaliar_rota(
            obs,
            "eficiencia_direta",
            "Eficiência combustível → vapor",
            "Quanto da energia de entrada virou energia útil do vapor?",
            (
                (
                    "historiador por vazões",
                    (
                        "vazao_vapor_t_h",
                        "p_vapor_bar_abs",
                        "t_agua_alim_c",
                        "vazao_combustivel_kg_h",
                        "pci_combustivel_mj_kg",
                    ),
                ),
                (
                    "totalizadores/pátio",
                    (
                        "totalizador_vapor_t",
                        "p_vapor_bar_abs",
                        "t_agua_alim_c",
                        "recebimentos",
                        "estoques",
                        "umidade_bu_frac",
                        "pci_seco_mj_kg",
                    ),
                ),
            ),
        ),
        _avaliar_rota(
            obs,
            "perda_gases",
            "Perda sensível nos gases",
            "Quanto da energia está saindo pela chaminé nesta fronteira?",
            (
                (
                    "combustão completa",
                    (
                        "t_gases_c",
                        "o2_seco_pct",
                        "t_ar_c",
                        "umidade_bu_frac",
                        "pci_seco_mj_kg",
                        "C",
                        "H",
                        "O",
                        "N",
                        "S",
                    ),
                ),
            ),
        ),
        _avaliar_rota(
            obs,
            "purga",
            "Perda energética por purga",
            "Quanta energia sai com a purga medida?",
            (
                (
                    "massa medida",
                    ("massa_purga_kg", "p_purga_bar_abs", "t_agua_alim_c"),
                ),
            ),
            "Número/duração da abertura não são convertidos em massa sem caracterização da válvula.",
        ),
        _avaliar_rota(
            obs,
            "economizador",
            "Transferência no economizador",
            "A capacidade aparente de troca térmica mudou?",
            (
                (
                    "UA pelo lado da água",
                    (
                        "vazao_agua_alim_t_h",
                        "p_agua_eco_bar_abs",
                        "t_agua_eco_entrada_c",
                        "t_agua_eco_saida_c",
                        "t_gases_eco_entrada_c",
                        "t_gases_eco_saida_c",
                    ),
                ),
            ),
            "UA aparente não prova fouling; precisa ser contextualizado por carga, bypass e ΔP.",
        ),
        _avaliar_rota(
            obs,
            "tendencias",
            "Mudanças operacionais",
            "Há sinais que mudaram mesmo sem fechar um balanço completo?",
            (
                ("vapor", ("vazao_vapor_t_h",)),
                ("gases", ("t_gases_c",)),
                ("oxigênio", ("o2_seco_pct",)),
                ("combustível", ("vazao_combustivel_kg_h",)),
                ("pressão", ("p_vapor_bar_abs",)),
            ),
            "Detectar mudança em um sinal não identifica a causa nem equivale a perda de eficiência.",
        ),
    ]
    return PerfilPlanta(sinais=sinais, rotas=tuple(rotas))
