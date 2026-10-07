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
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
from vocabulario_fabrica import nota, sugerir, termos, unidade_sugerida

from euler.io.esquemas import TABELAS, rotulo_coluna
from euler.io.leitura import ALIASES_COLUNAS, _numero, ler_csv


@dataclass
class FonteGuiada:
    chave: str
    arquivo: str
    aba: str | None
    bruto: pd.DataFrame
    virgula_decimal: bool
    linha_cabecalho: int = 1
    """Linha do cabeçalho no arquivo original (1 = primeira linha)."""


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
    arquivos: dict[str, bytes], cabecalhos: dict[str, int] | None = None
) -> list[FonteGuiada]:
    """Lê qualquer nome de arquivo/aba, texto intacto.

    O cabeçalho é detectado (`detectar_cabecalho`) ou informado em `cabecalhos`
    ({chave da fonte: linha do cabeçalho, 1 = primeira}). A coluna `linha` guarda o número
    da linha no arquivo original.
    """
    cabecalhos = cabecalhos or {}
    fontes = []
    for nome, conteudo in arquivos.items():
        if nome.lower().endswith(".csv"):
            texto = _decodificar(conteudo)
            linhas_texto = texto.splitlines()
            amostra = "\n".join(linhas_texto[:30])
            sep = ";" if amostra.count(";") > amostra.count(",") else ","
            linhas = list(csv.reader(io.StringIO(amostra), delimiter=sep))
            h = cabecalhos.get(nome, detectar_cabecalho(linhas) + 1) - 1
            if not 0 <= h < max(len(linhas_texto), 1):
                raise ValueError(f"{nome}: a linha do cabeçalho está fora do arquivo.")
            linha_cab = linhas_texto[h] if linhas_texto else ""
            sep = ";" if linha_cab.count(";") > linha_cab.count(",") else ","
            cab = [c.strip() for c in next(csv.reader(io.StringIO(linha_cab), delimiter=sep), [])]
            resto = list(csv.reader(io.StringIO("\n".join(linhas_texto[h + 1 :])), delimiter=sep))
            nomes, indices = _nomear_colunas(cab, resto)
            _validar_cabecalho(nomes, nome)
            if h == 0 and nomes == cab:
                df, virgula, avisos = ler_csv(conteudo, nome)
                if any(a.tipo in {"colunas_a_mais", "arquivo_vazio"} for a in avisos):
                    raise ValueError(
                        f"{nome}: confira o separador e o número de colunas do arquivo."
                    )
            else:
                registros = []
                for k, valores in enumerate(resto, start=h + 2):
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
            fontes.append(FonteGuiada(nome, nome, None, df, virgula, h + 1))
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
            for aba, bruto in abas.items():
                if bruto.empty:
                    continue
                chave = f"{nome}::{aba}"
                bruto = bruto.fillna("").astype(str)
                linhas = bruto.values.tolist()
                h = cabecalhos.get(chave, detectar_cabecalho(linhas) + 1) - 1
                if not 0 <= h < len(linhas):
                    raise ValueError(f"{nome} · {aba}: a linha do cabeçalho está fora da aba.")
                cab = [str(v).strip() for v in linhas[h]]
                nomes, indices = _nomear_colunas(cab, linhas[h + 1 :])
                _validar_cabecalho(nomes, f"{nome} · {aba}")
                df = bruto.iloc[h + 1 :, indices].copy()
                df.columns = nomes
                df.insert(0, "linha", df.index + 1)
                df = df[df[nomes].apply(lambda r: any(v.strip() for v in r), axis=1)]
                fontes.append(
                    FonteGuiada(chave, nome, aba, df.reset_index(drop=True), False, h + 1)
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
    horas. Fora disso, nada é sugerido.
    """
    alvo = next(
        (c.nome for c in TABELAS[tabela].colunas if c.tipo == "instante" and c.obrigatoria), None
    )
    if alvo is None or alvo in mapa.values():
        return None
    colunas = [c for c in fonte.bruto if c != "linha" and c not in mapa]

    def todas(coluna, teste) -> bool:
        valores = _amostra(fonte.bruto[coluna])
        return bool(valores) and all(teste(v) for v in valores)

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


def preparar_lote(arquivos: dict[str, bytes], decisoes: dict) -> dict[str, bytes]:
    """Produz CSVs do contrato e trilha auditável. Ausentes continuam vazios.

    Cada tabela recebe uma única fonte; não escolhe entre fontes sobrepostas.
    Constantes são declarações do usuário, apenas em colunas não existentes.
    """
    saida: dict[str, bytes] = {}
    adaptacoes = []
    cabecalhos = {
        k: int(d["linha_cabecalho"]) for k, d in decisoes.items() if d.get("linha_cabecalho")
    }
    for fonte in ler_fontes(arquivos, cabecalhos):
        escolha = decisoes.get(fonte.chave, {})
        tabela = escolha.get("tabela")
        if not tabela:
            continue
        contrato = TABELAS[tabela]
        destino = contrato.arquivo
        if destino in saida:
            raise ValueError(
                "Duas fontes apontam para a mesma tabela. Envie um conjunto por tabela."
            )
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

                def converter(v, virgula=fonte.virgula_decimal, f=fator, o=offset, nome=origem):
                    if not v.strip() or v.strip().lower() in _MARCAS_AUSENTE:
                        return ""
                    try:
                        numero = _numero(v, virgula)[0]
                        resultado = numero * f + o
                        if not math.isfinite(resultado):
                            raise ValueError(v)
                        return str(resultado)
                    except (ValueError, TypeError, OverflowError) as exc:
                        raise ValueError(
                            f"{nome}: não foi possível converter '{v}'. Confira a unidade e o valor."
                        ) from exc

                valores = valores.map(converter)
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
        saida[destino] = df.to_csv(index=False, lineterminator="\n").encode("utf-8")
        usadas = set(mapa) | ({combinar["data"], combinar["hora"]} if combinar else set())
        adaptacoes.append(
            {
                "fonte": fonte.chave,
                "arquivo": fonte.arquivo,
                "aba": fonte.aba,
                "tabela": tabela,
                "linha_cabecalho": fonte.linha_cabecalho,
                "mapeamento": mapa,
                "unidades": unidades,
                "constantes": constantes,
                **({"combinar": combinar} if combinar else {}),
                "linhas_originais": fonte.bruto["linha"].tolist(),
                "colunas_nao_usadas": [c for c in fonte.bruto if c != "linha" and c not in usadas],
                "sha256_adaptado": hashlib.sha256(saida[destino]).hexdigest(),
            }
        )
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
    fontes = ler_fontes(arquivos, ajustes)
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
            if fonte.linha_cabecalho > 1:
                st.caption(
                    f"Cabeçalho encontrado na linha {fonte.linha_cabecalho}; as linhas acima "
                    "(títulos) ficam só no original."
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
                constantes["tipo"] = st.selectbox(
                    "O que todas as linhas representam?",
                    ["", "recebimento", "estoque"],
                    format_func=lambda t: t or "Informe ou associe uma coluna com o tipo",
                    key=f"{prefixo}_tipo",
                )
            decisoes[fonte.chave] = {
                "tabela": tabela,
                "mapeamento": mapa,
                "unidades": unidades,
                "constantes": constantes,
                "linha_cabecalho": fonte.linha_cabecalho,
                **({"combinar": juntar} if juntar else {}),
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
