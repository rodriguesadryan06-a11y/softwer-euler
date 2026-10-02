"""Contrato de dados: tabelas, colunas, unidades, obrigatoriedade e faixas plausíveis (T02).

Fonte única do contrato. `docs/contrato_dados.md` e `templates/planilha_modelo_euler.xlsx`
são gerados a partir daqui (`python scripts/gerar_modelos.py`); um teste garante que
estão em dia.

Faixas plausíveis só geram **aviso**: o valor nunca é corrigido (AGENTS.md, regra 2).
"""

from dataclasses import dataclass, field
from typing import Literal

TipoColuna = Literal["texto", "numero", "instante", "data", "booleano", "categoria"]

ORIGENS_DADO = ("sintetico", "publico", "real")


ROTULOS = {
    "caldeira_id": "caldeira", "instante_observado": "hora da leitura",
    "instante_registrado": "hora da anotação", "turno": "turno", "operador_id": "operador",
    "regime": "regime", "p_vapor_bar_man": "pressão do vapor", "t_gases_c": "temperatura dos gases",
    "estado_vapor": "estado do vapor", "t_vapor_c": "temperatura do vapor",
    "titulo_vapor_frac": "título do vapor",
    "ponto_gases_id": "ponto de medição dos gases", "o2_seco_pct": "O₂ nos gases",
    "instrumento_o2_id": "analisador de O₂", "co_ppm": "CO nos gases",
    "t_agua_alim_c": "temperatura da água de alimentação", "t_ar_c": "temperatura do ar de combustão",
    "purgas_n": "número de purgas", "purgas_s": "duração das purgas",
    "totalizador_vapor_t": "totalizador de vapor", "producao": "produção",
    "ocorrencia": "ocorrência", "flag_instrumento_indisponivel": "instrumento fora de serviço",
    "origem_dado": "origem do dado", "data": "data", "tipo": "tipo", "fornecedor_id": "fornecedor",
    "lote_id": "lote", "massa_kg": "massa", "volume_m3": "volume", "densidade_kg_m3": "densidade",
    "origem_densidade": "origem da densidade", "preco_brl": "preço", "amostra_id": "amostra",
    "umidade_bu_frac": "umidade", "pci_seco_mj_kg": "PCI seco", "C": "carbono", "H": "hidrogênio",
    "O": "oxigênio", "N": "nitrogênio", "S": "enxofre", "cinzas": "cinzas", "metodo": "método",
    "laboratorio": "laboratório", "instante": "hora do evento", "descricao": "descrição",
    "autorizado_por": "autorizado por", "instrumento_id": "instrumento", "ponto": "ponto de instalação",
    "unidade": "unidade", "resolucao": "resolução", "incerteza_declarada": "incerteza declarada",
    "ultima_verificacao": "última verificação", "observacao": "observação",
    "incerteza_tipo": "tipo da incerteza", "incerteza_k": "fator k da incerteza",
}  # fmt: skip
"""Nome de cada coluna em português, para as mensagens ao usuário (linguagem de fábrica, D64).
O nome técnico fica no contrato de dados e nos "Detalhes técnicos"."""


def rotulo_coluna(nome: str) -> str:
    return ROTULOS.get(nome, nome.replace("_", " "))


def rotulo_categoria(valor: str) -> str:
    """Valor de categoria como o usuário escreve (o importador aceita espaço no lugar de _)."""
    return valor.replace("_", " ")


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: TipoColuna
    unidade: str
    obrigatoria: bool
    descricao: str
    exemplo: str
    faixa: tuple[float, float] | None = None
    dica_faixa: str | tuple[str, str] = ""
    """Dica quando o valor sai da faixa; tupla = (dica abaixo, dica acima)."""
    categorias: tuple[str, ...] = ()

    @property
    def rotulo(self) -> str:
        return rotulo_coluna(self.nome)

    @property
    def rotulo_inicial(self) -> str:
        """O rótulo com a primeira letra maiúscula, para começar uma frase."""
        return self.rotulo[0].upper() + self.rotulo[1:]


@dataclass(frozen=True)
class Tabela:
    nome: str
    titulo: str
    descricao: str
    colunas: tuple[Coluna, ...]
    chave: tuple[str, ...] = field(default_factory=tuple)

    @property
    def arquivo(self) -> str:
        return f"{self.nome}.csv"

    @property
    def rotulo(self) -> str:
        return self.titulo[0].lower() + self.titulo[1:]

    def coluna(self, nome: str) -> Coluna:
        return next(c for c in self.colunas if c.nome == nome)


def _origem_dado(obrigatoria: bool = False) -> Coluna:
    return Coluna(
        "origem_dado",
        "categoria",
        "—",
        obrigatoria,
        "De onde vem o dado. Dados reais de clientes nunca entram no repositório.",
        "sintetico",
        categorias=ORIGENS_DADO,
    )


DIARIO = Tabela(
    nome="diario",
    titulo="Diário do operador",
    descricao="Uma linha por leitura do operador (ou do sistema) na caldeira.",
    chave=("caldeira_id", "instante_observado"),
    colunas=(
        Coluna("caldeira_id", "texto", "—", True, "Identificação da caldeira.", "CALD-SINT-01"),
        Coluna(
            "instante_observado",
            "instante",
            "data e hora com fuso",
            True,
            "Quando a leitura foi feita (ISO 8601).",
            "2026-10-05T08:00:00-03:00",
        ),
        Coluna(
            "instante_registrado",
            "instante",
            "data e hora com fuso",
            False,
            "Quando a leitura foi anotada. Serve para detectar registro tardio.",
            "2026-10-05T08:05:00-03:00",
        ),
        Coluna("turno", "texto", "—", False, "Turno (A, B, C…).", "A"),
        Coluna("operador_id", "texto", "—", False, "Código do operador.", "OP-01"),
        Coluna(
            "regime",
            "categoria",
            "—",
            False,
            "Situação da caldeira na leitura.",
            "estavel",
            categorias=("estavel", "transitorio", "partida", "parada"),
        ),
        Coluna(
            "p_vapor_bar_man",
            "numero",
            "bar manométrico",
            False,
            "Pressão do vapor lida no manômetro.",
            "9.0",
            faixa=(0, 40),
            dica_faixa="Acima de 40 bar: confira se a leitura está em kPa ou psi.",
        ),
        Coluna(
            "t_gases_c",
            "numero",
            "°C",
            False,
            "Temperatura dos gases na chaminé.",
            "182",
            faixa=(50, 450),
            dica_faixa=(
                "Abaixo de 50 °C: confira o ponto de medição e o instrumento.",
                "Acima de 450 °C: confira se está em kelvin (K = °C + 273).",
            ),
        ),
        Coluna(
            "ponto_gases_id",
            "texto",
            "—",
            False,
            "Ponto onde a temperatura dos gases é medida.",
            "CHAMINE-1",
        ),
        Coluna(
            "o2_seco_pct",
            "numero",
            "% em base seca",
            False,
            "Oxigênio nos gases secos.",
            "8.1",
            faixa=(1, 20.5),
            dica_faixa=(
                "Abaixo de 1%: confira se foi anotado como fração (0,08) em vez de % (8).",
                "Perto de 21% é ar ambiente: caldeira parada ou analisador fora do ponto.",
            ),
        ),
        Coluna(
            "instrumento_o2_id",
            "texto",
            "—",
            False,
            "Analisador usado na leitura de O₂ (ver instrumentos.csv).",
            "ANALIS-01",
        ),
        Coluna(
            "co_ppm",
            "numero",
            "ppm",
            False,
            "Monóxido de carbono nos gases.",
            "",
            faixa=(0, 20000),
            dica_faixa="Acima de 20.000 ppm: confira a unidade (ppm, não mg/Nm³).",
        ),
        Coluna(
            "t_agua_alim_c",
            "numero",
            "°C",
            False,
            "Temperatura da água de alimentação.",
            "80",
            faixa=(5, 180),
            dica_faixa="Fora de 5 a 180 °C: confira o ponto de medição e a unidade.",
        ),
        Coluna(
            "t_ar_c",
            "numero",
            "°C",
            False,
            "Temperatura do ar de combustão.",
            "28",
            faixa=(-10, 60),
            dica_faixa="Fora de −10 a 60 °C: ar pré-aquecido? Confira o ponto de medição.",
        ),
        Coluna(
            "purgas_n",
            "numero",
            "contagem",
            False,
            "Número de purgas desde a leitura anterior.",
            "1",
            faixa=(0, 50),
        ),
        Coluna(
            "purgas_s",
            "numero",
            "s",
            False,
            "Duração total das purgas desde a leitura anterior.",
            "20",
            faixa=(0, 3600),
        ),
        Coluna(
            "totalizador_vapor_t",
            "numero",
            "t (acumulado)",
            False,
            "Leitura do totalizador de vapor (acumulado desde a instalação).",
            "15234.5",
            faixa=(0, 1e9),
        ),
        Coluna(
            "producao",
            "texto",
            "—",
            False,
            "Observação livre sobre a produção da fábrica no momento.",
            "",
        ),
        Coluna("ocorrencia", "texto", "—", False, "Ocorrência anotada pelo operador.", ""),
        Coluna(
            "flag_instrumento_indisponivel",
            "booleano",
            "true/false",
            False,
            "Marque true se algum instrumento estava fora de serviço nesta leitura.",
            "false",
        ),
        _origem_dado(),
        Coluna(
            "estado_vapor",
            "categoria",
            "—",
            False,
            "Estado termodinâmico do vapor na linha medida. Se vazio, a EULER mantém a hipótese "
            "conservadora atual de vapor saturado seco e marca essa hipótese como assumida.",
            "",
            categorias=("saturado_seco", "umido", "superaquecido"),
        ),
        Coluna(
            "t_vapor_c",
            "numero",
            "°C",
            False,
            "Temperatura do vapor quando o estado registrado é superaquecido.",
            "",
            faixa=(50, 650),
            dica_faixa="Confira o ponto de medição e a unidade da temperatura do vapor.",
        ),
        Coluna(
            "titulo_vapor_frac",
            "numero",
            "fração",
            False,
            "Título x do vapor úmido (0 a 1). Só é usado quando o estado registrado é umido.",
            "",
            faixa=(0, 1),
            dica_faixa="O título deve ser informado como fração entre 0 e 1.",
        ),
    ),
)

COMBUSTIVEL = Tabela(
    nome="combustivel",
    titulo="Combustível: recebimentos e estoques",
    descricao=(
        "Uma linha por recebimento de combustível (tipo = recebimento) ou por medição de "
        "estoque no pátio (tipo = estoque)."
    ),
    chave=("tipo", "lote_id"),
    colunas=(
        Coluna(
            "data",
            "instante",
            "data e hora com fuso",
            True,
            "Quando o recebimento ou a medição de estoque aconteceu.",
            "2026-10-05T10:30:00-03:00",
        ),
        Coluna(
            "tipo",
            "categoria",
            "—",
            True,
            "recebimento ou estoque.",
            "recebimento",
            categorias=("recebimento", "estoque"),
        ),
        Coluna("fornecedor_id", "texto", "—", False, "Código do fornecedor.", "F1"),
        Coluna(
            "lote_id",
            "texto",
            "—",
            False,
            "Código do lote; liga o recebimento às amostras.",
            "L-0001",
        ),
        Coluna(
            "massa_kg",
            "numero",
            "kg (como recebido, úmido)",
            False,
            "Massa pesada na balança (ou estoque medido em massa).",
            "30000",
            faixa=(100, 1_000_000),
            dica_faixa=(
                "Abaixo de 100 kg: confira se está em toneladas em vez de kg.",
                "Acima de 1.000 t: confira a unidade (kg).",
            ),
        ),
        Coluna(
            "volume_m3",
            "numero",
            "m³",
            False,
            "Volume, quando não há balança. Só vira massa com densidade declarada.",
            "",
            faixa=(0, 5000),
        ),
        Coluna(
            "densidade_kg_m3",
            "numero",
            "kg/m³",
            False,
            "Densidade aparente do combustível para converter volume em massa.",
            "",
            faixa=(100, 1200),
            dica_faixa="Fora de 100 a 1.200 kg/m³: confira a unidade.",
        ),
        Coluna(
            "origem_densidade",
            "categoria",
            "—",
            False,
            "De onde veio a densidade.",
            "",
            categorias=("medida", "declarada_fornecedor", "assumida"),
        ),
        Coluna(
            "preco_brl",
            "numero",
            "R$ (total do lote)",
            False,
            "Preço total pago pelo lote.",
            "5400.00",
            faixa=(0, 10_000_000),
        ),
        _origem_dado(),
    ),
)

AMOSTRAS = Tabela(
    nome="amostras",
    titulo="Amostras de combustível",
    descricao="Uma linha por amostra analisada (umidade e, quando houver, PCI e composição).",
    chave=("amostra_id",),
    colunas=(
        Coluna("amostra_id", "texto", "—", True, "Código da amostra.", "A-0001"),
        Coluna("lote_id", "texto", "—", True, "Lote de onde a amostra foi tirada.", "L-0001"),
        Coluna(
            "data",
            "instante",
            "data e hora com fuso",
            True,
            "Quando a amostra foi coletada.",
            "2026-10-05T11:00:00-03:00",
        ),
        Coluna(
            "umidade_bu_frac",
            "numero",
            "fração, base úmida",
            False,
            "kg de água por kg de combustível úmido (0,38 = 38%).",
            "0.38",
            faixa=(0.02, 0.75),
            dica_faixa="Acima de 1: parece estar em % (use 0,38 para 38%).",
        ),
        Coluna(
            "pci_seco_mj_kg",
            "numero",
            "MJ/kg seco",
            False,
            "Poder calorífico inferior em base seca.",
            "18.5",
            faixa=(10, 35),
            dica_faixa="Fora de 10 a 35 MJ/kg: confira se está em kcal/kg ou base úmida.",
        ),
        *(
            Coluna(
                el,
                "numero",
                "fração, base seca",
                False,
                f"Fração mássica de {nome} em base seca.",
                ex,
                faixa=(0, 1),
                dica_faixa="Acima de 1: parece estar em % (use fração).",
            )
            for el, nome, ex in (
                ("C", "carbono", "0.50"),
                ("H", "hidrogênio", "0.06"),
                ("O", "oxigênio", "0.43"),
                ("N", "nitrogênio", "0.003"),
                ("S", "enxofre", "0.0005"),
                ("cinzas", "cinzas", "0.0065"),
            )
        ),
        Coluna("metodo", "texto", "—", False, "Método de análise.", "estufa_ISO18134"),
        Coluna("laboratorio", "texto", "—", False, "Quem analisou.", "interno"),
        _origem_dado(),
    ),
)

EVENTOS = Tabela(
    nome="eventos",
    titulo="Eventos",
    descricao="Manutenções, limpezas, trocas de instrumento e outros fatos que mudam a caldeira.",
    chave=("instante", "tipo"),
    colunas=(
        Coluna(
            "instante",
            "instante",
            "data e hora com fuso",
            True,
            "Quando o evento aconteceu.",
            "2026-10-12T14:00:00-03:00",
        ),
        Coluna(
            "tipo",
            "categoria",
            "—",
            True,
            "Tipo do evento.",
            "limpeza",
            categorias=(
                "limpeza",
                "manutencao",
                "troca_instrumento",
                "calibracao",
                "parada",
                "partida",
                "mudanca_combustivel",
                "outro",
            ),
        ),
        Coluna("descricao", "texto", "—", True, "O que foi feito.", "Limpeza dos tubos de fumaça"),
        Coluna("autorizado_por", "texto", "—", False, "Quem autorizou.", "SUP-01"),
        _origem_dado(),
    ),
)

INSTRUMENTOS = Tabela(
    nome="instrumentos",
    titulo="Instrumentos",
    descricao="Cadastro dos instrumentos usados nas leituras e sua incerteza declarada.",
    chave=("instrumento_id",),
    colunas=(
        Coluna("instrumento_id", "texto", "—", True, "Código do instrumento.", "ANALIS-01"),
        Coluna("tipo", "texto", "—", True, "Tipo do instrumento.", "analisador_o2"),
        Coluna("ponto", "texto", "—", False, "Onde está instalado.", "CHAMINE-1"),
        Coluna(
            "unidade",
            "texto",
            "—",
            True,
            "Unidade da leitura do instrumento (vale para resolução e incerteza).",
            "pct_seco",
        ),
        Coluna(
            "resolucao",
            "numero",
            "na unidade do instrumento",
            False,
            "Menor variação que o instrumento mostra.",
            "0.1",
            faixa=(0, 1e6),
        ),
        Coluna(
            "incerteza_declarada",
            "numero",
            "na unidade do instrumento",
            False,
            "Incerteza declarada pelo fabricante ou pela calibração.",
            "0.3",
            faixa=(0, 1e6),
        ),
        Coluna(
            "ultima_verificacao",
            "data",
            "data",
            False,
            "Data da última verificação ou calibração.",
            "2026-09-01",
        ),
        Coluna("observacao", "texto", "—", False, "Observação livre.", "sintetico"),
        Coluna(
            "incerteza_tipo",
            "categoria",
            "—",
            False,
            "Como a incerteza foi declarada (padrao, expandida ou limite). Sem esta "
            "informação, a EULER supõe que o valor é um limite ±a (hipótese do projeto, "
            "D35) e usa u = a/√3 (modelo retangular do GUM 4.3.7); informe o tipo para "
            "evitar essa suposição.",
            "",
            categorias=("padrao", "expandida", "limite"),
        ),
        Coluna(
            "incerteza_k",
            "numero",
            "—",
            False,
            "Fator de abrangência k, quando a incerteza é expandida (ex.: 2).",
            "",
            faixa=(1, 4),
        ),
    ),
)

TABELAS: dict[str, Tabela] = {
    t.nome: t for t in (DIARIO, COMBUSTIVEL, AMOSTRAS, EVENTOS, INSTRUMENTOS)
}
