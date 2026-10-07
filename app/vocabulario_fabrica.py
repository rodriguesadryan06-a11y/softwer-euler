"""Vocabulário de fábrica: como as planilhas costumam chamar cada coluna do contrato (D106).

Regras explícitas e auditáveis, sem IA nem semelhança aproximada. Uma coluna só recebe
sugestão quando o cabeçalho contém pelo menos um termo de cada grupo de uma regra e nenhum
termo que a contradiz. Cabeçalhos ambíguos ("Pressão", "Temperatura", "Consumo") ficam sem
sugestão. Toda sugestão traz o motivo e precisa da confirmação da pessoa antes de importar.

A unidade escrita no cabeçalho ("(°C)", "kgf/cm²", "t/h") vira a unidade sugerida, só quando
existe conversão exata para a unidade do contrato. Pressão absoluta e preço por tonelada
nunca viram pressão manométrica ou preço total.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento; símbolos viram espaço ("Temp. chaminé (°C)" → "temp chamine c")."""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def termos(texto: str) -> list[str]:
    return normalizar(texto).split()


@dataclass(frozen=True)
class Regra:
    """Cada grupo precisa de pelo menos um termo; nenhum termo de `nenhum` pode aparecer.

    Termo terminado em "*" casa com o começo da palavra ("alim*" casa "alimentação").
    """

    alvo: str
    grupos: tuple[tuple[str, ...], ...]
    nenhum: tuple[str, ...] = ()


def _casa(termo: str, palavras: list[str]) -> bool:
    if termo.endswith("*"):
        return any(p.startswith(termo[:-1]) for p in palavras)
    return termo in palavras


def casa(regra: Regra, cabecalho: str) -> bool:
    palavras = termos(cabecalho)
    if any(_casa(t, palavras) for t in regra.nenhum):
        return False
    return all(any(_casa(t, palavras) for t in grupo) for grupo in regra.grupos)


TEMP = ("temp*",)  # "t" sozinho não: confunde com a unidade "(t)"
_ECO = ("econ*", "eco")
_ABS = ("abs", "absoluta", "absoluto", "bara")

REGRAS: dict[str, tuple[Regra, ...]] = {
    "diario": (
        Regra("caldeira_id", (("caldeira",),), ("pressao", "temp*", "vazao", "nivel", "agua")),
        Regra("instante_observado", (("data",), ("hora",)), ("registro", "anotacao", "digitacao")),
        Regra("instante_observado", (("datahora", "timestamp"),)),
        Regra(
            "instante_registrado",
            (("data", "hora", "instante"), ("registro", "anotacao", "anotada", "digitacao")),
        ),
        Regra("turno", (("turno",),)),
        Regra("operador_id", (("operador",),)),
        Regra("regime", (("regime",),)),
        Regra(
            "p_vapor_bar_man",
            (("pressao", "press"), ("vapor",)),
            ("agua", "alim*", "purga*", *_ECO, "referencia", "diferencial", *_ABS),
        ),
        Regra(
            "t_gases_c",
            (TEMP, ("chamine", "gases", "gas", "fumaca", "fumos")),
            (*_ECO, "entrada", "ar", "agua"),
        ),
        Regra(
            "o2_seco_pct", (("o2", "oxigenio"), ("seco", "seca", "bs")), ("umido", "umida", "bu")
        ),
        Regra("co_ppm", (("co",),), ("co2",)),
        Regra(
            "t_agua_alim_c",
            (TEMP, ("agua",), ("alim*",)),
            (*_ECO, "vazao", "pressao"),
        ),
        Regra("t_ar_c", (TEMP, ("ar",)), ("agua", "gases", "gas", "chamine")),
        Regra(
            "t_vapor_c",
            (TEMP, ("vapor",)),
            ("agua", "gases", "gas", "alim*", "chamine"),
        ),
        Regra(
            "vazao_vapor_t_h",
            (("vazao", "fluxo", "producao", "geracao"), ("vapor",)),
            ("total*", "acumulad*", "totalizador", "agua"),
        ),
        Regra("totalizador_vapor_t", (("totalizador", "acumulad*", "integrador"), ("vapor",))),
        Regra("vazao_agua_alim_t_h", (("vazao",), ("agua",), ("alim*",)), _ECO),
        Regra(
            "purgas_n",
            (("purga*", "descarga*"), ("numero", "n", "no", "qtd", "qtde", "quantidade")),
            ("duracao", "tempo", "massa"),
        ),
        Regra(
            "purgas_s",
            (("purga*", "descarga*"), ("duracao", "tempo", "segundos")),
            ("numero", "qtd", "massa"),
        ),
        Regra("ocorrencia", (("ocorrencia*",),)),
    ),
    "combustivel": (
        Regra("data", (("data", "dia"),)),
        Regra("fornecedor_id", (("fornecedor*", "fornec"),)),
        Regra("lote_id", (("lote",),)),
        Regra(
            "massa_kg",
            (("peso", "massa"), ("liquido", "liq", "net")),
            ("bruto", "tara", "seco", "seca"),
        ),
        Regra("massa_kg", (("massa",),), ("bruto", "tara", "seco", "seca", "especifica")),
        # estoque medido no pátio (linhas de estoque); volume e limites não são massa
        Regra(
            "massa_kg",
            (("estoque", "estoques", "inventario"),),
            ("volume", "vol", "m3", "valor", "preco", "minimo", "maximo", "dias"),
        ),
        Regra("volume_m3", (("volume", "vol"),)),
        Regra("densidade_kg_m3", (("densidade",),)),
        Regra(
            "preco_brl",
            (("valor", "preco"), ("total", "nota", "nf", "pago")),
            ("unitario", "unit", "ton", "tonelada", "t", "kg", "m3", "frete"),
        ),
    ),
    "amostras": (
        Regra("amostra_id", (("amostra",),), ("data",)),
        Regra("lote_id", (("lote",),)),
        Regra("data", (("data", "coleta"),)),
        Regra("umidade_bu_frac", (("umidade",),), ("seca", "seco", "bs")),
        Regra("pci_seco_mj_kg", (("pci",), ("seco", "seca", "bs"))),
        Regra("cinzas", (("cinza*",),)),
        Regra("C", (("carbono",),)),
        Regra("H", (("hidrogenio",),)),
        Regra("O", (("oxigenio",),)),
        Regra("N", (("nitrogenio",),)),
        Regra("S", (("enxofre",),)),
        Regra("metodo", (("metodo",),)),
        Regra("laboratorio", (("laboratorio", "lab"),)),
    ),
    "eventos": (
        Regra("instante", (("data", "hora", "quando"),)),
        Regra("descricao", (("descricao", "descr", "servico", "atividade"),)),
        Regra("autorizado_por", (("autorizado*", "aprovado*", "responsavel"),)),
    ),
    "instrumentos": (
        Regra(
            "instrumento_id",
            (("tag", "instrumento", "codigo"),),
            ("tipo", "incerteza", "unidade", "ponto", "resolucao", "verificacao"),
        ),
        Regra("incerteza_declarada", (("incerteza",),), ("tipo", "k", "fator", "abrangencia")),
        Regra("incerteza_tipo", (("incerteza",), ("tipo",))),
        Regra("incerteza_k", (("fator", "abrangencia"),)),
        Regra("ultima_verificacao", (("verificacao", "calibracao"),), ("proxima",)),
    ),
}

# Avisos para cabeçalhos que parecem uma grandeza, mas faltam informações para associar.
NOTAS: dict[str, tuple[tuple[Regra, str], ...]] = {
    "diario": (
        (
            Regra("o2_seco_pct", (("o2", "oxigenio"),), ("seco", "seca", "bs")),
            (
                "Parece O₂ nos gases. A EULER usa O₂ em base seca; associe só se o analisador "
                "medir em base seca."
            ),
        ),
        (
            Regra("p_vapor_bar_man", (("pressao", "press"), ("vapor",), _ABS)),
            (
                "Pressão absoluta: a EULER recebe pressão manométrica e não converte sem a "
                "pressão atmosférica do local."
            ),
        ),
    ),
    "combustivel": (
        (
            Regra("preco_brl", (("preco", "valor"), ("ton", "tonelada", "t", "kg", "unitario"))),
            "Preço por unidade: a EULER recebe o valor total pago pelo lote.",
        ),
        (
            Regra("massa_kg", (("peso", "massa"), ("bruto", "tara"))),
            "Peso bruto ou tara: a EULER recebe o peso líquido do combustível.",
        ),
    ),
}


def sugerir(cabecalho: str, tabela: str) -> str | None:
    """Coluna do contrato sugerida para o cabeçalho, ou None se nenhuma regra casa."""
    alvos = {r.alvo for r in REGRAS.get(tabela, ()) if casa(r, cabecalho)}
    return next(iter(alvos)) if len(alvos) == 1 else None


def nota(cabecalho: str, tabela: str) -> str | None:
    """Explicação quando o cabeçalho parece uma grandeza que não pode ser associada direto."""
    return next((texto for regra, texto in NOTAS.get(tabela, ()) if casa(regra, cabecalho)), None)


# Unidade escrita no cabeçalho → unidade das opções de conversão (app/importacao_guiada.py).
_UNIDADES = (
    (re.compile(r"kgf\s*/\s*cm|kg\s*/\s*cm"), "kgf/cm² manométrico"),
    (re.compile(r"\bpsig?\b"), "psi manométrico"),
    (re.compile(r"\bmpa\b"), "MPa manométrico"),
    (re.compile(r"\bkpa\b"), "kPa manométrico"),
    (re.compile(r"\bbarg?\b"), "bar manométrico"),
    (re.compile(r"°\s*f\b|º\s*f\b|\bgraus? f\b|\(f\)"), "°F"),
    (re.compile(r"°\s*c\b|º\s*c\b|\bgraus? c\b|\(c\)|\bdegc\b"), "°C"),
    (re.compile(r"\(k\)|\bkelvin\b"), "K"),
    (re.compile(r"\bt\s*/\s*dia\b|\bton\s*/\s*dia\b|\bt\s*/\s*d\b"), "t/dia"),
    (re.compile(r"\bkg\s*/\s*h\b"), "kg/h"),
    (re.compile(r"\bt\s*/\s*h\b|\bton\s*/\s*h\b|\btph\b"), "t/h"),
    (re.compile(r"\bmj\s*/\s*kg\b"), "MJ/kg"),
    (re.compile(r"r\$"), "R$"),
    (re.compile(r"\bppm\b"), "ppm"),
    (re.compile(r"\bm3\b|m³"), "m³"),
    (re.compile(r"%"), "%"),
    (re.compile(r"\bkg\b"), "kg"),
    (re.compile(r"\(t\)|\bton\b|\btoneladas?\b"), "t"),
    (re.compile(r"\(s\)|\bsegundos?\b"), "s"),
)


def unidade_escrita(cabecalho: str) -> str | None:
    """A unidade que o cabeçalho declara, em forma curta ("kgf/cm² manométrico", "°C", "t")."""
    t = unicodedata.normalize("NFKC", str(cabecalho)).lower().replace("²", "2").replace("³", "3")
    if re.search(r"\bbar\s*a\b|\bbara\b|\babs", t):
        return None  # absoluta: nunca vira manométrica
    return next((u for padrao, u in _UNIDADES if padrao.search(t)), None)


def unidade_sugerida(cabecalho: str, unidade_contrato: str, opcoes: list[str]) -> str | None:
    """A opção de unidade que corresponde ao que o cabeçalho declara, se houver conversão."""
    escrita = unidade_escrita(cabecalho)
    if escrita is None:
        return None
    if escrita in opcoes:
        return escrita
    # unidades do contrato com descrição longa: "t (acumulado)", "% em base seca", "R$ (total…)"
    candidatas = [o for o in opcoes if o.split(" ")[0].split(",")[0] == escrita]
    if len(candidatas) == 1:
        return candidatas[0]
    if escrita == "MJ/kg" and unidade_contrato.startswith("MJ/kg"):
        return unidade_contrato
    return None
