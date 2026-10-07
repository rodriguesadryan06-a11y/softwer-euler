"""Adaptação explícita de CSV/Excel ao contrato; não calcula grandezas físicas.

Originais permanecem byte a byte em anexos .bin. O manifesto registra hashes,
aba, linha do cabeçalho, colunas, unidades, Data + Hora combinadas e constantes informadas.
O leitor e o banco existentes recebem os CSVs adaptados; não se cria outro caminho de
normalização científica.

Planilha de fábrica como ela chega (D106): o cabeçalho pode estar abaixo de um título, Data e
Hora podem vir em colunas separadas e os nomes seguem o vocabulário da fábrica
(`vocabulario_fabrica`). Tudo é sugestão com motivo; a pessoa confirma antes de importar.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
from vocabulario_fabrica import nota, sugerir, termos, unidade_sugerida

from euler.io.esquemas import TABELAS, rotulo_coluna
from euler.io.leitura import (
    ALIASES_COLUNAS,
    ler_csv,
    numero_na_unidade,
    porcentagens_excel,
)


@dataclass
class FonteGuiada:
    chave: str
    arquivo: str
    aba: str | None
    bruto: pd.DataFrame
    virgula_decimal: bool
    linha_cabecalho: int = 1
    """Linha do cabeçalho no arquivo original (1 = primeira linha)."""
    cabecalho_duplo: bool = False
    """Cabeçalho em duas linhas (grupo em cima, subcolunas embaixo, como em células mescladas)."""
    letras: dict[str, str] = field(default_factory=dict)
    """Letra de cada coluna no arquivo original ("Umidade (%)" → "D"), para apontar a célula."""

    def onde(self, coluna: str, linha: int) -> str:
        """Localização exata de um valor no original: aba (ou arquivo), célula e coluna."""
        letra = self.letras.get(coluna)
        celula = f"célula {letra}{linha}" if letra else f"linha {linha}"
        return f"{self.aba or self.arquivo}, {celula} (“{coluna}”)"


@dataclass(frozen=True)
class Sugestao:
    """Coluna do contrato sugerida para uma coluna da planilha, com o motivo."""

    alvo: str
    motivo: str
    unidade: str | None = None


def assinatura_envio(arquivos: dict[str, bytes], decisoes: dict) -> str:
    """Identidade do conteúdo e das decisões; trocar arquivo de mesmo nome invalida prévia."""
    entrada = {
        "arquivos": {n: hashlib.sha256(b).hexdigest() for n, b in sorted(arquivos.items())},
        "decisoes": decisoes,
    }
    return hashlib.sha256(json.dumps(entrada, sort_keys=True).encode()).hexdigest()


def _normal(nome: str) -> str:
    texto = "".join(c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def _validar_cabecalho(colunas: list[str], nome: str) -> None:
    if len(set(colunas)) != len(colunas):
        raise ValueError(f"{nome}: há nomes de colunas repetidos. Diferencie os cabeçalhos.")
    if any(not c for c in colunas) or "linha" in colunas:
        raise ValueError(
            f"{nome}: preencha todos os cabeçalhos; 'linha' é reservado à rastreabilidade."
        )


# ------------------------------------------------------------ cabeçalho abaixo de um título

_NUMERO_OU_DATA = re.compile(r"^[-+]?[\d.,:/ ]+$")


def detectar_cabecalho(linhas: list[list[str]]) -> int:
    """Índice (0 = primeira) da linha de cabeçalho entre as 30 primeiras linhas.

    Cabeçalho = primeira linha com quase a largura da tabela (≥ 60% da linha mais larga e
    pelo menos 2 células) e só com textos, sem números ou datas. Títulos de uma célula e
    linhas em branco acima dela ficam de fora. Sem candidata, vale a primeira linha.
    """
    topo = [[str(v).strip() for v in linha] for linha in linhas[:30]]
    largura = [sum(1 for v in linha if v) for linha in topo]
    maior = max(largura, default=0)
    for i, linha in enumerate(topo):
        preenchidas = [v for v in linha if v]
        if len(preenchidas) < max(2, 0.6 * maior):
            continue
        if any(_NUMERO_OU_DATA.match(v) for v in preenchidas):
            continue
        return i
    return 0


def _so_texto(valores: list[str]) -> bool:
    return bool(valores) and not any(_NUMERO_OU_DATA.match(v) for v in valores)


def _par_de_cabecalho(cima: list, baixo: list) -> bool:
    """Grupo em cima e subcolunas embaixo, como as células mescladas do Excel deixam.

    Exige: duas linhas só com textos, cada uma com 2+ células, e subcolunas embaixo de
    células vazias de cima que tenham um grupo à esquerda (a parte mesclada do grupo).
    """
    c = [str(v).strip() for v in cima]
    b = [str(v).strip() for v in baixo]
    fc = {j for j, v in enumerate(c) if v}
    fb = {j for j, v in enumerate(b) if v}
    if len(fc) < 2 or len(fb) < 2:
        return False
    if not (_so_texto([c[j] for j in fc]) and _so_texto([b[j] for j in fb])):
        return False
    sob_grupo = [j for j in fb - fc if any(k < j for k in fc)]
    return bool(sob_grupo)


def localizar_cabecalho(linhas: list[list[str]]) -> tuple[int, bool]:
    """(índice da primeira linha do cabeçalho, se ele ocupa duas linhas)."""
    i = detectar_cabecalho(linhas)
    if i > 0 and _par_de_cabecalho(linhas[i - 1], linhas[i]):
        return i - 1, True
    if i + 1 < len(linhas) and _par_de_cabecalho(linhas[i], linhas[i + 1]):
        return i, True
    return i, False


def juntar_cabecalho_duplo(cima: list, baixo: list) -> list[str]:
    """'Temperaturas' (mesclada sobre 3 colunas) + 'Gases' → 'Temperaturas · Gases'."""
    largura = max(len(cima), len(baixo))
    c = [str(v).strip() for v in cima] + [""] * (largura - len(cima))
    b = [str(v).strip() for v in baixo] + [""] * (largura - len(baixo))
    nomes, grupo = [], ""
    for j in range(largura):
        if c[j]:
            grupo = c[j]
        topo = c[j] or (grupo if b[j] else "")
        nomes.append(" · ".join(x for x in (topo, b[j]) if x))
    return nomes


def _nomear_colunas(cabecalho: list[str], dados: list[list[str]]) -> tuple[list[str], list[int]]:
    """Nomes do cabeçalho; colunas sem nome e com dados recebem nome visível; vazias saem."""
    nomes, indices = [], []
    for j, nome in enumerate(cabecalho):
        tem_dado = any(j < len(linha) and str(linha[j]).strip() for linha in dados)
        if nome:
            nomes.append(nome)
            indices.append(j)
        elif tem_dado:
            nomes.append(f"Coluna sem nome ({_letra(j)})")
            indices.append(j)
    return nomes, indices


def _letra(j: int) -> str:
    letras = ""
    j += 1
    while j:
        j, r = divmod(j - 1, 26)
        letras = chr(65 + r) + letras
    return letras


def _decodificar(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252")


def ler_fontes(
    arquivos: dict[str, bytes],
    cabecalhos: dict[str, int] | None = None,
    duplos: dict[str, bool] | None = None,
) -> list[FonteGuiada]:
    """Lê qualquer nome de arquivo/aba, texto intacto.

    O cabeçalho é detectado (`localizar_cabecalho`) ou informado em `cabecalhos`
    ({chave da fonte: linha do cabeçalho, 1 = primeira}) e `duplos` ({chave: True se o
    cabeçalho ocupa duas linhas}). A coluna `linha` guarda o número da linha no original.
    """
    cabecalhos = cabecalhos or {}
    duplos = duplos or {}
    fontes = []
    for nome, conteudo in arquivos.items():
        if nome.lower().endswith(".csv"):
            texto = _decodificar(conteudo)
            linhas_texto = texto.splitlines()
            amostra = "\n".join(linhas_texto[:30])
            sep = ";" if amostra.count(";") > amostra.count(",") else ","
            linhas = list(csv.reader(io.StringIO(amostra), delimiter=sep))
            h_auto, duplo_auto = localizar_cabecalho(linhas)
            h = cabecalhos.get(nome, h_auto + 1) - 1
            duplo = duplos.get(nome, duplo_auto if nome not in cabecalhos else False)
            if not 0 <= h < max(len(linhas_texto), 1):
                raise ValueError(f"{nome}: a linha do cabeçalho está fora do arquivo.")
            linha_cab = linhas_texto[h] if linhas_texto else ""
            sep = ";" if linha_cab.count(";") > linha_cab.count(",") else ","
            cab = [c.strip() for c in next(csv.reader(io.StringIO(linha_cab), delimiter=sep), [])]
            if duplo and h + 1 < len(linhas_texto):
                sub = next(csv.reader(io.StringIO(linhas_texto[h + 1]), delimiter=sep), [])
                cab = juntar_cabecalho_duplo(cab, sub)
            pula = h + (2 if duplo else 1)
            resto = list(csv.reader(io.StringIO("\n".join(linhas_texto[pula:])), delimiter=sep))
            nomes, indices = _nomear_colunas(cab, resto)
            _validar_cabecalho(nomes, nome)
            if h == 0 and not duplo and nomes == cab:
                df, virgula, avisos = ler_csv(conteudo, nome)
                if any(a.tipo in {"colunas_a_mais", "arquivo_vazio"} for a in avisos):
                    raise ValueError(
                        f"{nome}: confira o separador e o número de colunas do arquivo."
                    )
            else:
                registros = []
                for k, valores in enumerate(resto, start=pula + 1):
                    if not any(v.strip() for v in valores):
                        continue
                    if len(valores) > len(cab) and any(v.strip() for v in valores[len(cab) :]):
                        raise ValueError(
                            f"{nome}: a linha {k} tem mais valores que o cabeçalho da linha "
                            f"{h + 1}. Confira a linha do cabeçalho e o separador."
                        )
                    registros.append(
                        {
                            "linha": k,
                            **{
                                n: (valores[j] if j < len(valores) else "")
                                for n, j in zip(nomes, indices, strict=True)
                            },
                        }
                    )
                df = pd.DataFrame(registros, columns=["linha", *nomes])
                virgula = sep == ";"
            letras = {n: _letra(j) for n, j in zip(nomes, indices, strict=True)}
            fontes.append(FonteGuiada(nome, nome, None, df, virgula, h + 1, duplo, letras))
        elif nome.lower().endswith(".xlsx"):
            try:
                abas = pd.read_excel(
                    io.BytesIO(conteudo),
                    sheet_name=None,
                    header=None,
                    dtype=str,
                    keep_default_na=False,
                )
            except (ValueError, BadZipFile, OSError) as exc:
                raise ValueError(
                    f"{nome}: não foi possível ler o Excel. Confira o formato .xlsx."
                ) from exc
            porcentagens = porcentagens_excel(conteudo)
            for aba, bruto in abas.items():
                if bruto.empty:
                    continue
                chave = f"{nome}::{aba}"
                bruto = bruto.fillna("").astype(str)
                # célula de porcentagem: o texto que o Excel mostra ("45%"), convertido uma vez
                for r, c, texto in porcentagens.get(aba, []):
                    if r - 1 < len(bruto) and c - 1 < len(bruto.columns):
                        bruto.iat[r - 1, c - 1] = texto
                linhas = bruto.values.tolist()
                h_auto, duplo_auto = localizar_cabecalho(linhas)
                h = cabecalhos.get(chave, h_auto + 1) - 1
                duplo = duplos.get(chave, duplo_auto if chave not in cabecalhos else False)
                if not 0 <= h < len(linhas):
                    raise ValueError(f"{nome} · {aba}: a linha do cabeçalho está fora da aba.")
                cab = [str(v).strip() for v in linhas[h]]
                if duplo and h + 1 < len(linhas):
                    cab = juntar_cabecalho_duplo(cab, linhas[h + 1])
                pula = h + (2 if duplo else 1)
                nomes, indices = _nomear_colunas(cab, linhas[pula:])
                _validar_cabecalho(nomes, f"{nome} · {aba}")
                df = bruto.iloc[pula:, indices].copy()
                df.columns = nomes
                df.insert(0, "linha", df.index + 1)
                df = df[df[nomes].apply(lambda r: any(v.strip() for v in r), axis=1)]
                letras = {n: _letra(j) for n, j in zip(nomes, indices, strict=True)}
                fontes.append(
                    FonteGuiada(
                        chave, nome, aba, df.reset_index(drop=True), False, h + 1, duplo, letras
                    )
                )
    if not fontes:
        raise ValueError(
            "Nenhuma tabela encontrada. Envie CSV ou Excel com uma linha de cabeçalho."
        )
    return fontes


# ------------------------------------------------------------ sugestões de colunas


def _amostra(fonte_ou_valores) -> list[str]:
    return [str(v).strip() for v in fonte_ou_valores if str(v).strip()][:50]


def _unidade(coluna: str, alvo: str, tabela: str) -> str | None:
    col = TABELAS[tabela].coluna(alvo)
    if col.tipo != "numero":
        return None
    if col.unidade in {"contagem", "na unidade do instrumento", "—"}:
        return col.unidade  # contagem e unidade do próprio instrumento: nada a converter
    opcoes = list(unidades_permitidas(col))
    explicita = coluna == alvo or ALIASES_COLUNAS.get(coluna) == alvo
    return col.unidade if explicita else unidade_sugerida(coluna, col.unidade, opcoes)


def sugestoes_detalhadas(
    colunas: list[str], tabela: str, salvo: dict | None = None
) -> dict[str, Sugestao]:
    """Sugestões com motivo, em ordem de prioridade.

    1) mapeamento salvo desta fonte; 2) nome exato do contrato; 3) rótulo exato ou alias
    explícito; 4) vocabulário de fábrica. Um destino escolhido por uma prioridade maior não
    é repetido. Duas colunas candidatas ao mesmo destino pelo vocabulário ficam sem
    sugestão: a pessoa escolhe.
    """
    contrato = TABELAS[tabela]
    nomes = {c.nome for c in contrato.colunas}
    candidatos: dict[str, set[str]] = {}
    porque: dict[str, str] = {}
    for col in contrato.colunas:
        for rotulo, texto in ((col.nome, "nome do modelo"), (col.rotulo, "rótulo do modelo")):
            candidatos.setdefault(_normal(rotulo), set()).add(col.nome)
            porque.setdefault(_normal(rotulo), f"nome igual ao {texto}, sem acentos e símbolos")
    for alias, alvo in ALIASES_COLUNAS.items():
        if alvo in nomes:
            candidatos.setdefault(_normal(alias), set()).add(alvo)
            porque.setdefault(_normal(alias), "nome reconhecido na lista de nomes equivalentes")
    resultado: dict[str, Sugestao] = {}
    usados: set[str] = set()

    def pegar(coluna: str, alvo: str, motivo: str) -> None:
        if coluna in resultado or alvo in usados:
            return
        resultado[coluna] = Sugestao(alvo, motivo, _unidade(coluna, alvo, tabela))
        usados.add(alvo)

    for coluna in colunas:
        if salvo and salvo.get(coluna) in nomes:
            pegar(coluna, salvo[coluna], "mapeamento salvo desta fonte")
    for coluna in colunas:
        if coluna in nomes:
            pegar(coluna, coluna, "nome igual ao do modelo")
    for coluna in colunas:
        if len(opcoes := candidatos.get(_normal(coluna), set())) == 1:
            pegar(coluna, next(iter(opcoes)), porque[_normal(coluna)])
    por_vocabulario: dict[str, list[str]] = {}
    for coluna in colunas:
        if coluna not in resultado and (alvo := sugerir(coluna, tabela)) and alvo not in usados:
            por_vocabulario.setdefault(alvo, []).append(coluna)
    for alvo, cols in por_vocabulario.items():
        if len(cols) == 1:
            pegar(cols[0], alvo, f"o cabeçalho fala de {rotulo_coluna(alvo)}")
    return resultado


def sugerir_mapeamento(colunas: list[str], tabela: str, salvo: dict | None = None) -> dict:
    """{coluna da planilha: coluna do contrato} sugerido (ver `sugestoes_detalhadas`)."""
    return {c: s.alvo for c, s in sugestoes_detalhadas(colunas, tabela, salvo).items()}


# nomes de abas e arquivos como a fábrica costuma dar
_NOMES_TABELA = {
    "diario": ("diario", "turno", "turnos", "leituras", "operacao", "caldeira"),
    "combustivel": (
        "combustivel",
        "lenha",
        "cavaco",
        "biomassa",
        "compras",
        "recebimentos",
        "balanca",
        "estoque",
    ),
    "amostras": ("amostras", "amostra", "laboratorio", "umidade", "analises"),
    "eventos": ("eventos", "evento", "ocorrencias", "manutencao"),
    "instrumentos": ("instrumentos", "instrumento", "calibracao"),
}
# podem vir como valor único informado na tela
_CONSTANTES = {"caldeira_id", "tipo", "origem_dado"}


def sugerir_tabela(fonte: FonteGuiada) -> str | None:
    """Nome conhecido da aba/arquivo ou cobertura inequívoca das colunas obrigatórias."""
    nome = (fonte.aba or Path(fonte.arquivo).stem).strip().lower()
    if nome in TABELAS:
        return nome
    palavras = termos(nome)
    pelo_nome = [t for t, ps in _NOMES_TABELA.items() if any(p in palavras for p in ps)]
    if len(pelo_nome) == 1:
        return pelo_nome[0]
    candidatos = []
    colunas = [c for c in fonte.bruto if c != "linha"]
    for nome, tabela in TABELAS.items():
        mapa = sugerir_mapeamento(colunas, nome)
        cobertos = set(mapa.values())
        if sugerir_combinacao(fonte, nome, mapa):
            cobertos.add(
                next(c.nome for c in tabela.colunas if c.tipo == "instante" and c.obrigatoria)
            )
        obrigatorias = {c.nome for c in tabela.colunas if c.obrigatoria} - _CONSTANTES
        if obrigatorias <= cobertos:
            candidatos.append((len(mapa), nome))
    candidatos.sort(reverse=True)
    if candidatos and (len(candidatos) == 1 or candidatos[0][0] > candidatos[1][0]):
        return candidatos[0][1]
    return None


# ------------------------------------------------------------ Data + Hora separadas

_DATA = re.compile(r"^(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})( 00:00(:00)?)?$")
_HORA = re.compile(r"^(?:1899-12-3[01] |1900-01-0\d )?(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_HORA_H = re.compile(r"^(\d{1,2})\s*h\s*(\d{2})?$", re.IGNORECASE)


def _so_data(valor: str) -> str | None:
    m = _DATA.match(valor.strip())
    return m.group(1) if m else None


def _so_hora(valor: str) -> str | None:
    v = valor.strip()
    if m := _HORA.match(v):
        h, mi, se = m.groups()
        return f"{int(h):02d}:{mi}" + (f":{se}" if se else "")
    if m := _HORA_H.match(v):
        h, mi = m.groups()
        return f"{int(h):02d}:{mi or '00'}"
    return None


def combinar_data_hora(datas: pd.Series, horas: pd.Series) -> pd.Series:
    """'01/09/2026' + '08:00' → '01/09/2026 08:00'. Se faltar a data ou a hora, fica vazio
    (ausente): nada é preenchido. Valor que não é data ou hora também fica vazio e o
    original continua guardado."""

    def juntar(d: str, h: str) -> str:
        data, hora = _so_data(str(d)), _so_hora(str(h))
        if not data or not hora:
            return ""
        if re.match(r"^\d{4}-", data) and len(hora) == 5:
            hora += ":00"
        return f"{data} {hora}"

    return pd.Series([juntar(d, h) for d, h in zip(datas, horas, strict=True)], index=datas.index)


def sugerir_combinacao(fonte: FonteGuiada, tabela: str, mapa: dict) -> dict | None:
    """Data e Hora em colunas separadas para o instante obrigatório da tabela, se faltar.

    Exige uma coluna "Data" cujos valores são datas sem hora e uma "Hora" cujos valores são
    horas. Se a "Data" já foi associada sozinha ao instante (a coluna de combustível também
    se chama "data"), a junção ainda é sugerida: sem ela, a hora ao lado se perderia.
    Fora disso, nada é sugerido.
    """
    alvo = next(
        (c.nome for c in TABELAS[tabela].colunas if c.tipo == "instante" and c.obrigatoria), None
    )
    if alvo is None:
        return None

    def todas(coluna, teste) -> bool:
        valores = _amostra(fonte.bruto[coluna])
        return bool(valores) and all(teste(v) for v in valores)

    ja = [c for c, a in mapa.items() if a == alvo]
    if ja and (len(ja) > 1 or not todas(ja[0], _so_data)):
        return None
    colunas = [c for c in fonte.bruto if c != "linha" and (c not in mapa or c in ja)]
    datas = [c for c in colunas if {"data", "dia"} & set(termos(c)) and todas(c, _so_data)]
    horas = [c for c in colunas if {"hora", "horario"} & set(termos(c)) and todas(c, _so_hora)]
    if len(datas) == 1 and len(horas) == 1:
        return {"alvo": alvo, "data": datas[0], "hora": horas[0]}
    return None


# ------------------------------------------------------------ unidades


def unidades_permitidas(col) -> dict[str, tuple[float, float]]:
    """Conversões dimensionais exatas (destino = origem × fator + offset).

    Não converte preço unitário em total, volume em massa ou pressão absoluta
    em manométrica: essas operações requerem informação física adicional.
    Fatores por definição: 1 kgf/cm² = 0,980665 bar; 1 psi = 0,0689475729316836 bar;
    t(°C) = (t(°F) − 32) × 5/9.
    """
    opcoes = {col.unidade: (1.0, 0.0)}
    manometrica = {
        "kPa manométrico": (0.01, 0.0),
        "kgf/cm² manométrico": (0.980665, 0.0),
        "psi manométrico": (0.0689475729316836, 0.0),
        "MPa manométrico": (10.0, 0.0),
    }
    extras = {
        "kg": {"t": (1000.0, 0.0)},
        "kg (como recebido, úmido)": {"kg": (1.0, 0.0), "t": (1000.0, 0.0)},
        "t/h": {"kg/h": (0.001, 0.0), "t/dia": (1 / 24, 0.0)},
        "kg/h": {"t/h": (1000.0, 0.0)},
        "t (acumulado)": {"kg (acumulado)": (0.001, 0.0)},
        "°C": {"K": (1.0, -273.15), "°F": (5 / 9, -160 / 9)},
        "bar manométrico": manometrica,
        "fração, base úmida": {"%, base úmida": (0.01, 0.0)},
        "fração, base seca": {"%, base seca": (0.01, 0.0)},
        "% em base seca": {"fração em base seca": (100.0, 0.0)},
    }
    opcoes.update(extras.get(col.unidade, {}))
    return opcoes


# ------------------------------------------------------------ lote adaptado


_MARCAS_AUSENTE = {"-", "--", "nan", "na", "n/a", "s/d", "sd", "null", "none"}


def _converter(fonte, coluna, v, linha, unidade, fator, offset) -> str:
    """Um valor da planilha na unidade do contrato; erro aponta a célula exata."""
    texto = str(v).strip()
    if not texto or texto.lower() in _MARCAS_AUSENTE:
        return ""
    try:
        numero = numero_na_unidade(texto, fonte.virgula_decimal, unidade)[0]
        resultado = numero * fator + offset
        if not math.isfinite(resultado):
            raise ValueError(texto)
        return str(resultado)
    except (ValueError, TypeError, OverflowError) as exc:
        porque = (
            "é porcentagem; escolha uma unidade em % ou em fração"
            if texto.endswith("%")
            else f"não é um número em {unidade}"
        )
        raise ValueError(
            f"{fonte.onde(coluna, int(linha))}: '{texto}' {porque}. Confira a unidade e o valor."
        ) from exc


def preparar_lote(arquivos: dict[str, bytes], decisoes: dict) -> dict[str, bytes]:
    """Produz CSVs do contrato e trilha auditável. Ausentes continuam vazios.

    Várias fontes da mesma tabela (um mês por aba, recebimentos e estoques em abas
    separadas) são juntadas na ordem em que chegaram (D107). O mesmo registro em duas
    fontes: se igual, entra uma vez (anotado no manifesto); se diferente, nada é
    escolhido e a importação para com o nome das duas fontes e das linhas.
    Constantes são declarações do usuário, apenas em colunas não existentes.
    """
    saida: dict[str, bytes] = {}
    adaptacoes = []
    partes: dict[str, list] = {}
    cabecalhos = {
        k: int(d["linha_cabecalho"]) for k, d in decisoes.items() if d.get("linha_cabecalho")
    }
    duplos = {k: bool(d["cabecalho_duplo"]) for k, d in decisoes.items() if "cabecalho_duplo" in d}
    for fonte in ler_fontes(arquivos, cabecalhos, duplos):
        escolha = decisoes.get(fonte.chave, {})
        tabela = escolha.get("tabela")
        if not tabela:
            continue
        contrato = TABELAS[tabela]
        destino = contrato.arquivo
        mapa = escolha.get("mapeamento", {})
        unidades = escolha.get("unidades", {})
        constantes = escolha.get("constantes", {})
        combinar = escolha.get("combinar")
        if len(set(mapa.values())) != len(mapa):
            raise ValueError("Duas colunas apontam para a mesma coluna EULER. Escolha apenas uma.")
        df = pd.DataFrame(index=fonte.bruto.index)
        ids = [c for c in fonte.bruto if _normal(c) in {"caldeira id", "boiler id", "caldeira"}]
        if "caldeira_id" in {c.nome for c in contrato.colunas}:
            for coluna_id in ids:
                if mapa.get(coluna_id) != "caldeira_id":
                    raise ValueError(
                        "Preserve a coluna de identificação da caldeira do arquivo; ela não pode ser ignorada ou substituída."
                    )
        # Origem existente é vinculante, mesmo se o usuário tentar ignorá-la.
        origens = [c for c in fonte.bruto if _normal(c) in {"origem dado", "origem do dado"}]
        for c in origens:
            if mapa.get(c) not in (None, "origem_dado"):
                raise ValueError("A coluna de origem não pode ser usada como outra grandeza.")
            if "origem_dado" in mapa.values() and mapa.get(c) != "origem_dado":
                raise ValueError("Mais de uma coluna de origem. Confira a declaração original.")
            existentes = {v.strip() for v in fonte.bruto[c] if v.strip()}
            if constantes.get("origem_dado") and existentes - {constantes["origem_dado"]}:
                raise ValueError("A origem declarada não pode substituir a origem do arquivo.")
            df["origem_dado"] = fonte.bruto[c]
        for origem, alvo in mapa.items():
            if origem not in fonte.bruto or alvo not in {c.nome for c in contrato.colunas}:
                raise ValueError("Mapeamento contém coluna inexistente.")
            col = contrato.coluna(alvo)
            valores = fonte.bruto[origem].copy()
            if col.tipo == "numero":
                unidade = unidades.get(origem)
                if unidade not in unidades_permitidas(col):
                    raise ValueError(
                        f"Confirme a unidade de {origem}; unidade ausente ou incompatível."
                    )
                fator, offset = unidades_permitidas(col)[unidade]
                valores = pd.Series(
                    [
                        _converter(fonte, origem, v, linha, unidade, fator, offset)
                        for v, linha in zip(valores, fonte.bruto["linha"], strict=True)
                    ],
                    index=valores.index,
                )
            df[alvo] = valores
        if combinar:
            alvo, c_data, c_hora = combinar.get("alvo"), combinar.get("data"), combinar.get("hora")
            col = next((c for c in contrato.colunas if c.nome == alvo), None)
            if col is None or col.tipo != "instante":
                raise ValueError("Data + Hora só podem formar uma coluna de data e hora do modelo.")
            if c_data not in fonte.bruto or c_hora not in fonte.bruto or c_data == c_hora:
                raise ValueError(
                    "Escolha uma coluna de data e outra de hora existentes no arquivo."
                )
            if alvo in mapa.values() or c_data in mapa or c_hora in mapa:
                raise ValueError(
                    "As colunas de data e hora já foram associadas a outra coluna. Escolha uma forma só."
                )
            df[alvo] = combinar_data_hora(fonte.bruto[c_data], fonte.bruto[c_hora])
        for campo, valor in constantes.items():
            if campo not in {"origem_dado", "caldeira_id", "tipo"}:
                raise ValueError("Constante não permitida; informe medições na planilha.")
            if campo not in df and valor:
                df[campo] = valor
        faltam = [c.rotulo for c in contrato.colunas if c.obrigatoria and c.nome not in df]
        if faltam:
            raise ValueError(
                f"{contrato.titulo}: associe as colunas obrigatórias: {', '.join(faltam)}."
            )
        usadas = set(mapa) | ({combinar["data"], combinar["hora"]} if combinar else set())
        adaptacao = {
            "fonte": fonte.chave,
            "arquivo": fonte.arquivo,
            "aba": fonte.aba,
            "tabela": tabela,
            "linha_cabecalho": fonte.linha_cabecalho,
            **({"cabecalho_duplo": True} if fonte.cabecalho_duplo else {}),
            "mapeamento": mapa,
            "unidades": unidades,
            "constantes": constantes,
            **({"combinar": combinar} if combinar else {}),
            **({"sugerido": escolha["sugerido"]} if escolha.get("sugerido") else {}),
            "linhas_originais": fonte.bruto["linha"].tolist(),
            "colunas_nao_usadas": [c for c in fonte.bruto if c != "linha" and c not in usadas],
        }
        partes.setdefault(destino, []).append((fonte, df, adaptacao))
    for destino, lista in partes.items():
        junto = _juntar_fontes(TABELAS[lista[0][2]["tabela"]], lista)
        saida[destino] = junto.to_csv(index=False, lineterminator="\n").encode("utf-8")
        for _, _, adaptacao in lista:
            adaptacao["sha256_adaptado"] = hashlib.sha256(saida[destino]).hexdigest()
            adaptacoes.append(adaptacao)
    if not adaptacoes:
        raise ValueError("Selecione ao menos uma tabela para analisar.")
    originais = []
    for i, (nome, conteudo) in enumerate(arquivos.items(), 1):
        guardado = f"original_{i:02d}.bin"
        saida[guardado] = conteudo
        originais.append(
            {
                "nome": nome,
                "arquivo_guardado": guardado,
                "tipo": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if nome.lower().endswith(".xlsx")
                else "text/csv",
                "sha256": hashlib.sha256(conteudo).hexdigest(),
            }
        )
    saida["euler_importacao.json"] = json.dumps(
        {"versao": 1, "originais": originais, "adaptacoes": adaptacoes},
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")
    return saida


def _juntar_fontes(contrato, lista: list) -> pd.DataFrame:
    """Junta as fontes de uma tabela; registra em cada adaptação as linhas que ocupou."""
    if len(lista) == 1:
        _, df, adaptacao = lista[0]
        adaptacao["linhas_no_adaptado"] = [2, len(df) + 1]
        return df
    colunas = list(dict.fromkeys(c for _, df, _ in lista for c in df.columns))
    vistos: dict[tuple, tuple] = {}
    blocos, proxima = [], 2
    for fonte, df, adaptacao in lista:
        df = df.reindex(columns=colunas).fillna("")
        manter, repetidas = [], []
        for idx, linha in df.iterrows():
            chave = tuple(str(linha.get(c, "")).strip() for c in contrato.chave)
            conteudo = tuple(str(v).strip() for v in linha.tolist())
            original = int(fonte.bruto.loc[idx, "linha"])
            if all(chave) and chave in vistos and vistos[chave][0] != fonte.chave:
                outra_fonte, outra_linha, outro_conteudo = vistos[chave]
                if outro_conteudo == conteudo:
                    repetidas.append(original)
                    continue
                raise ValueError(
                    f"{contrato.titulo}: o mesmo registro ({' · '.join(chave)}) aparece em "
                    f"“{outra_fonte}” (linha {outra_linha}) e em “{fonte.chave}” (linha "
                    f"{original}) com valores diferentes. Confira qual vale; a EULER não "
                    "escolhe sozinha."
                )
            if all(chave):
                vistos.setdefault(chave, (fonte.chave, original, conteudo))
            manter.append(idx)
        bloco = df.loc[manter]
        adaptacao["linhas_no_adaptado"] = [proxima, proxima + len(bloco) - 1]
        if repetidas:
            adaptacao["repetidas_iguais_entraram_uma_vez"] = repetidas
        proxima += len(bloco)
        blocos.append(bloco)
    return pd.concat(blocos, ignore_index=True)


# ------------------------------------------------------------ o que a tela já traz preenchido (T16)


_TIPO_PELO_NOME = {
    "recebimento": {"recebimento", "recebimentos", "entrada", "entradas", "compra", "compras"},
    "estoque": {"estoque", "estoques", "inventario"},
}


def sugerir_tipo(fonte: FonteGuiada) -> str | None:
    """Tipo dos registros de combustível pelo nome da aba ou do arquivo, se inequívoco."""
    palavras = set(termos(fonte.aba or Path(fonte.arquivo).stem))
    achados = [t for t, nomes in _TIPO_PELO_NOME.items() if nomes & palavras]
    return achados[0] if len(achados) == 1 else None


def valores_unicos_da_tela(tabela: str, mapa: dict, colunas: list[str]) -> list[str]:
    """Valores únicos que a tela pede para a tabela, dada a associação das colunas."""
    nomes = {c.nome for c in TABELAS[tabela].colunas}
    tem_origem = any(_normal(c) in {"origem dado", "origem do dado"} for c in colunas)
    pede = []
    if "caldeira_id" in nomes and "caldeira_id" not in mapa.values():
        pede.append("caldeira_id")
    if "origem_dado" in nomes and "origem_dado" not in mapa.values() and not tem_origem:
        pede.append("origem_dado")
    if tabela == "combustivel" and "tipo" not in mapa.values():
        pede.append("tipo")
    return pede


def sugestao_da_fonte(
    fonte: FonteGuiada,
    tabela: str | None = None,
    *,
    salvo: dict | None = None,
    origem: str | None = None,
    caldeira: str | None = None,
) -> dict:
    """O que a tela de conferência traz preenchido para esta fonte, no formato das decisões.

    `tabela` é a tabela escolhida pela pessoa (as associações sugeridas dependem dela); o
    campo "tabela" do resultado é sempre a tabela que a EULER sugeriu. Valores únicos que a
    tela não preenche (o tipo dos registros de combustível, a origem quando a planta não a
    define) aparecem vazios: a pessoa precisa declarar.
    """
    sugerida = sugerir_tabela(fonte)
    alvo_tabela = tabela or sugerida
    base = {
        "tabela": sugerida,
        "linha_cabecalho": fonte.linha_cabecalho,
        "cabecalho_duplo": fonte.cabecalho_duplo,
    }
    if not alvo_tabela:
        return {**base, "mapeamento": {}, "unidades": {}, "constantes": {}}
    colunas = [c for c in fonte.bruto if c != "linha"]
    combinacao = sugerir_combinacao(
        fonte, alvo_tabela, sugerir_mapeamento(colunas, alvo_tabela, salvo)
    )
    usadas = {combinacao["data"], combinacao["hora"]} if combinacao else set()
    s = sugestoes_detalhadas([c for c in colunas if c not in usadas], alvo_tabela, salvo)
    mapa = {c: x.alvo for c, x in s.items()}
    padrao = {
        "caldeira_id": caldeira or "",
        "origem_dado": origem if origem in {"real", "publico", "sintetico"} else "",
        "tipo": sugerir_tipo(fonte) or "",
    }
    constantes = {k: padrao[k] for k in valores_unicos_da_tela(alvo_tabela, mapa, colunas)}
    return {
        **base,
        "mapeamento": mapa,
        "unidades": {c: x.unidade for c, x in s.items() if x.unidade},
        "constantes": constantes,
        **({"combinar": combinacao} if combinacao else {}),
    }


def contar_ajustes(final: dict, sugerido: dict) -> dict[str, int]:
    """Quantas escolhas da pessoa diferem do que a tela já trazia preenchido (T16).

    Cada campo alterado ou preenchido conta 1: a tabela, a linha e a forma do cabeçalho, a
    junção Data + Hora, a associação de cada coluna, a unidade de cada coluna numérica (em
    comparação com a unidade que a tela mostra para a coluna escolhida) e cada valor único
    declarado. `sugerido` deve ter sido calculado para a tabela final (`sugestao_da_fonte`).
    """
    tabela = final.get("tabela")
    mapa_f, mapa_s = final.get("mapeamento", {}), sugerido.get("mapeamento", {})
    const_f, const_s = final.get("constantes", {}), sugerido.get("constantes", {})
    unidades = 0
    for coluna, alvo in mapa_f.items():
        if tabela and TABELAS[tabela].coluna(alvo).tipo == "numero":
            unidades += int(final.get("unidades", {}).get(coluna) != _unidade(coluna, alvo, tabela))
    detalhe = {
        "tabela": int(tabela != sugerido.get("tabela")),
        "cabecalho": int(
            int(final.get("linha_cabecalho") or 1) != int(sugerido.get("linha_cabecalho") or 1)
        )
        + int(bool(final.get("cabecalho_duplo")) != bool(sugerido.get("cabecalho_duplo"))),
        "data_hora": int((final.get("combinar") or None) != (sugerido.get("combinar") or None)),
        "colunas": sum(
            int(mapa_f.get(c) != mapa_s.get(c)) for c in dict.fromkeys([*mapa_s, *mapa_f])
        ),
        "unidades": unidades,
        "valores_unicos": sum(
            int((const_f.get(k) or "") != (const_s.get(k) or ""))
            for k in dict.fromkeys([*const_s, *const_f])
        ),
    }
    return {**detalhe, "total": sum(detalhe.values())}


def ajustes_do_lote(lote: dict[str, bytes]) -> dict | None:
    """Soma dos ajustes da pessoa em um lote preparado pela conferência (manifesto).

    None quando o lote não passou pela conferência guiada ou não guardou o que a tela
    sugeriu: ausente não vira zero.
    """
    try:
        manifesto = json.loads(lote["euler_importacao.json"])
    except (KeyError, ValueError):
        return None
    adaptacoes = manifesto.get("adaptacoes", [])
    if not adaptacoes or any("sugerido" not in a for a in adaptacoes):
        return None
    total: dict[str, int] = {}
    for a in adaptacoes:
        for k, v in contar_ajustes(a, a["sugerido"]).items():
            total[k] = total.get(k, 0) + v
    return {**total, "fontes": len(adaptacoes)}


# ------------------------------------------------------------ resumo do que foi entendido

# Colunas que as análises usam (pré-requisitos em euler/capacidades.py) e o que elas liberam.
USADAS_NAS_ANALISES = {
    "diario": (
        (("t_gases_c",), "perda nos gases"),
        (("o2_seco_pct",), "perda nos gases"),
        (("t_ar_c",), "perda nos gases"),
        (("totalizador_vapor_t",), "energia útil do vapor e eficiência direta"),
        (("p_vapor_bar_man",), "energia útil do vapor"),
        (("t_agua_alim_c",), "energia útil do vapor"),
    ),
    "combustivel": (
        (("massa_kg", "volume_m3"), "combustível queimado no período"),
        (("fornecedor_id",), "extrato por fornecedor"),
        (("preco_brl",), "conta em reais e extrato por fornecedor"),
        (("lote_id",), "ligação com as amostras de umidade"),
    ),
    "amostras": (
        (("umidade_bu_frac",), "energia do combustível e extrato por fornecedor"),
        (("pci_seco_mj_kg",), "energia do combustível"),
    ),
}


def resumo_da_fonte(fonte: FonteGuiada, decisao: dict) -> dict[str, list[str]]:
    """O que entra (e de onde vem), o que fica de fora (guardado no original) e o que falta.

    "faltam" lista colunas usadas pelas análises que esta tabela não trouxe, com a análise
    afetada; outras tabelas ou envios podem trazê-las depois.
    """
    tabela = decisao.get("tabela")
    if not tabela:
        return {"entram": [], "fora": [c for c in fonte.bruto if c != "linha"], "faltam": []}
    contrato = TABELAS[tabela]
    mapa = decisao.get("mapeamento", {})
    unidades = decisao.get("unidades", {})
    combinar = decisao.get("combinar")
    entram = []
    for origem, alvo in mapa.items():
        col = contrato.coluna(alvo)
        texto = f"{col.rotulo} ← “{origem}”"
        u = unidades.get(origem)
        if col.tipo == "numero" and u and u != col.unidade:
            texto += f" · convertida de {u} para {col.unidade}"
        entram.append(texto)
    if combinar:
        rot = contrato.coluna(combinar["alvo"]).rotulo
        entram.append(f"{rot} ← “{combinar['data']}” + “{combinar['hora']}”")
    for campo, valor in decisao.get("constantes", {}).items():
        if valor and campo not in mapa.values():
            entram.append(f"{rotulo_coluna(campo)} = {valor} (informado para todas as linhas)")
    usadas = set(mapa) | ({combinar["data"], combinar["hora"]} if combinar else set())
    fora = [c for c in fonte.bruto if c != "linha" and c not in usadas]
    presentes = set(mapa.values()) | ({combinar["alvo"]} if combinar else set())
    faltam = []
    for alvos, analise in USADAS_NAS_ANALISES.get(tabela, ()):
        if not presentes & set(alvos):
            nomes = " ou ".join(rotulo_coluna(a) for a in alvos)
            faltam.append(f"{nomes} (usada em: {analise})")
    return {"entram": entram, "fora": fora, "faltam": faltam}


# ------------------------------------------------------------ formulário


def guia_importacao(arquivos, *, chave, salvo=None, origem=None, caldeira=None):
    """Formulário compartilhado; retorna lote adaptado e perfil somente após confirmação."""
    import streamlit as st

    identidade = assinatura_envio(arquivos, {})[:12]
    base = f"{chave}_{identidade}"
    ajustes = st.session_state.setdefault(f"{base}_cabecalhos", {})
    duplos = st.session_state.setdefault(f"{base}_duplos", {})
    fontes = ler_fontes(arquivos, ajustes, duplos)
    # o que a EULER detectou sozinha, para registrar o que a pessoa ajustou (T16)
    detectado = {
        f.chave: (f.linha_cabecalho, f.cabecalho_duplo)
        for f in (ler_fontes(arquivos) if ajustes or duplos else fontes)
    }
    decisoes, perfil = {}, {}
    st.markdown("**Confira como a EULER vai ler sua planilha**")
    st.caption(
        "As sugestões vêm do nome de cada coluna e da unidade escrita nele, e precisam da sua "
        "confirmação. Valores vazios continuam ausentes; o arquivo original fica guardado."
    )
    for i, fonte in enumerate(fontes):
        prefixo = f"{base}_{i}"
        with st.expander(f"{fonte.chave} · {len(fonte.bruto)} registros", expanded=True):
            linha_cab = st.number_input(
                "Linha do cabeçalho (nomes das colunas)",
                min_value=1,
                value=fonte.linha_cabecalho,
                step=1,
                key=f"{prefixo}_cabecalho_{fonte.linha_cabecalho}",
                help="A EULER procura a linha com os nomes das colunas, abaixo de títulos. "
                "Corrija se ela errou.",
            )
            if linha_cab != fonte.linha_cabecalho:
                ajustes[fonte.chave] = int(linha_cab)
                st.rerun()
            duplo = st.checkbox(
                "Cabeçalho em duas linhas (grupo em cima, colunas embaixo)",
                value=fonte.cabecalho_duplo,
                key=f"{prefixo}_duplo_{fonte.linha_cabecalho}_{fonte.cabecalho_duplo}",
                help="Para células mescladas como “Temperaturas” sobre “Gases · Água · Ar”: "
                "os nomes viram “Temperaturas · Gases” e assim por diante.",
            )
            if duplo != fonte.cabecalho_duplo:
                duplos[fonte.chave] = duplo
                st.rerun()
            if fonte.linha_cabecalho > 1:
                st.caption(
                    f"Cabeçalho encontrado na linha {fonte.linha_cabecalho}"
                    + (f" e {fonte.linha_cabecalho + 1}" if fonte.cabecalho_duplo else "")
                    + "; as linhas acima (títulos) ficam só no original."
                )
            tabelas = ["", *TABELAS]
            sugestao = sugerir_tabela(fonte) or ""
            tabela = st.selectbox(
                "Que registros esta tabela contém?",
                tabelas,
                index=tabelas.index(sugestao),
                format_func=lambda t: (
                    TABELAS[t].titulo if t else "Selecionar / não usar esta tabela"
                ),
                key=f"{prefixo}_tabela",
            )
            if not tabela:
                continue
            contrato = TABELAS[tabela]
            colunas = [c for c in fonte.bruto if c != "linha"]
            combinacao = sugerir_combinacao(
                fonte, tabela, sugerir_mapeamento(colunas, tabela, salvo)
            )
            juntar = None
            if combinacao:
                rot = contrato.coluna(combinacao["alvo"]).rotulo
                if st.checkbox(
                    f"Juntar “{combinacao['data']}” + “{combinacao['hora']}” em {rot}",
                    value=True,
                    key=f"{prefixo}_{tabela}_juntar",
                    help="Data e hora em colunas separadas viram uma só. Linha sem data ou "
                    "sem hora fica com a hora ausente.",
                ):
                    juntar = combinacao
            livres = [c for c in colunas if not juntar or c not in (juntar["data"], juntar["hora"])]
            sugestoes = sugestoes_detalhadas(livres, tabela, salvo)
            mapa, unidades = {}, {}
            st.caption(
                f"{len(sugestoes) + (2 if juntar else 0)} de {len(colunas)} colunas reconhecidas. "
                "Confira as associações antes de confirmar."
            )
            with st.expander(
                "Conferir ou ajustar colunas e unidades",
                expanded=any(c not in sugestoes for c in livres),
            ):
                for j, coluna in enumerate(livres):
                    c1, c2 = st.columns([2, 1])
                    opcoes = ["", *[c.nome for c in contrato.colunas]]
                    s = sugestoes.get(coluna)
                    alvo = c1.selectbox(
                        f"{coluna} →",
                        opcoes,
                        index=opcoes.index(s.alvo if s else ""),
                        format_func=lambda n, t=contrato: (
                            t.coluna(n).rotulo_inicial if n else "Não usar"
                        ),
                        key=f"{prefixo}_{tabela}_{j}_col",
                        help="Associe pela grandeza; não confunda total de vapor com vazão, ou preço total com preço por tonelada.",
                    )
                    if s and alvo == s.alvo:
                        c1.caption(f"Sugestão: {s.motivo}.")
                    elif not alvo and (texto := nota(coluna, tabela)):
                        c1.caption(texto)
                    if not alvo:
                        continue
                    mapa[coluna] = alvo
                    col = contrato.coluna(alvo)
                    if col.tipo == "numero":
                        opcoes_u = ["", *unidades_permitidas(col)]
                        u_sug = _unidade(coluna, alvo, tabela)
                        unidade = c2.selectbox(
                            "Unidade no arquivo",
                            opcoes_u,
                            index=opcoes_u.index(u_sug) if u_sug in opcoes_u else 0,
                            format_func=lambda u: u or "Confirmar unidade",
                            key=f"{prefixo}_{tabela}_{j}_{alvo}_unit",
                            help=col.descricao,
                        )
                        unidades[coluna] = unidade
                        if unidade and unidade != col.unidade:
                            c2.caption(f"Será convertida para {col.unidade}.")
            constantes = {}
            if (
                "caldeira_id" in {c.nome for c in contrato.colunas}
                and "caldeira_id" not in mapa.values()
            ):
                constantes["caldeira_id"] = st.text_input(
                    "Código da caldeira (aplica-se a todas as linhas desta tabela)",
                    value=caldeira or "",
                    key=f"{prefixo}_caldeira",
                ).strip()
            tem_origem = any(_normal(c) in {"origem dado", "origem do dado"} for c in colunas)
            if (
                "origem_dado" in {c.nome for c in contrato.colunas}
                and "origem_dado" not in mapa.values()
                and not tem_origem
            ):
                origens = ["", "real", "publico", "sintetico"]
                constantes["origem_dado"] = st.selectbox(
                    "Origem de todos os registros desta tabela",
                    origens,
                    index=origens.index(origem) if origem in origens else 0,
                    format_func=lambda o: {
                        "": "Informar origem",
                        "real": "Empresa · uso autorizado",
                        "publico": "Dados públicos",
                        "sintetico": "Demonstração sintética",
                    }[o],
                    key=f"{prefixo}_origem",
                )
            if tabela == "combustivel" and "tipo" not in mapa.values():
                tipos = ["", "recebimento", "estoque"]
                tipo_sugerido = sugerir_tipo(fonte) or ""
                constantes["tipo"] = st.selectbox(
                    "O que todas as linhas representam?",
                    tipos,
                    index=tipos.index(tipo_sugerido),
                    format_func=lambda t: t or "Informe ou associe uma coluna com o tipo",
                    key=f"{prefixo}_tipo",
                )
                if tipo_sugerido and constantes["tipo"] == tipo_sugerido:
                    st.caption(
                        f"Sugestão: o nome “{fonte.aba or fonte.arquivo}” fala de {tipo_sugerido}."
                    )
            sugerido = sugestao_da_fonte(
                fonte, tabela, salvo=salvo, origem=origem, caldeira=caldeira
            )
            sugerido["linha_cabecalho"], sugerido["cabecalho_duplo"] = detectado.get(
                fonte.chave, (fonte.linha_cabecalho, fonte.cabecalho_duplo)
            )
            decisoes[fonte.chave] = {
                "tabela": tabela,
                "mapeamento": mapa,
                "unidades": unidades,
                "constantes": constantes,
                "linha_cabecalho": fonte.linha_cabecalho,
                "cabecalho_duplo": fonte.cabecalho_duplo,
                **({"combinar": juntar} if juntar else {}),
                "sugerido": sugerido,
            }
            perfil.update(mapa)
            r = resumo_da_fonte(fonte, decisoes[fonte.chave])
            with st.container(border=True, key=f"cartao-resumo-{prefixo}"):
                st.markdown(f"**O que a EULER entendeu** · {contrato.titulo}")
                st.markdown(
                    f"**Vai entrar ({len(r['entram'])})**\n\n"
                    + "\n".join(f"- {t}" for t in r["entram"])
                )
                if r["fora"]:
                    st.caption(
                        f"Fica de fora, guardado no original ({len(r['fora'])}): "
                        + ", ".join(f"“{c}”" for c in r["fora"])
                    )
                if r["faltam"]:
                    st.caption(
                        "Não veio nesta tabela: "
                        + "; ".join(r["faltam"])
                        + ". Sem essas colunas, essas análises ficam bloqueadas ou parciais."
                    )
            with st.expander("Ver primeiras linhas do arquivo original"):
                st.dataframe(fonte.bruto.head(8), hide_index=True, width="stretch")
    por_tabela: dict[str, list[str]] = {}
    for k, d in decisoes.items():
        por_tabela.setdefault(d["tabela"], []).append(k)
    for t, chaves in por_tabela.items():
        if len(chaves) > 1:
            st.info(
                f"{len(chaves)} fontes vão para {TABELAS[t].titulo} ("
                + ", ".join(f"“{k}”" for k in chaves)
                + "): as linhas se juntam nesta ordem. O mesmo registro repetido igual entra "
                "uma vez; com valores diferentes, a importação para e mostra onde.",
                icon=":material/merge:",
            )
    identidade_decisoes = assinatura_envio(arquivos, decisoes)[:12]
    confirmado = st.checkbox(
        "Conferi as colunas, as unidades e a origem dos registros selecionados",
        key=f"{base}_{identidade_decisoes}_confirmado",
    )
    st.caption(
        "O envio preserva os arquivos originais e um registro das adaptações. Nenhum arquivo é enviado ao GitHub."
    )
    if not confirmado:
        return None, perfil
    return preparar_lote(arquivos, decisoes), perfil
