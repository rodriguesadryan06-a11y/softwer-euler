"""Registro de atendimento (T16): medição da tela gravada no lote, caminho até o primeiro
fechamento, horas lançadas pela equipe e contagem de ajustes da conferência. Sintético."""

import csv
import io
import json
from datetime import UTC, datetime, timedelta

import pytest
from construtor_caso import Periodo, montar

from app.importacao_guiada import (
    ajustes_do_lote,
    contar_ajustes,
    ler_fontes,
    preparar_lote,
    sugerir_tipo,
    sugestao_da_fonte,
)
from euler.armazem import ErroArmazem, criar_planta
from euler.atendimento import (
    atendimentos_registrados,
    csv_atendimento,
    minutos_por_mes,
    registro_atendimento,
)

EQ = "CALD-T"


@pytest.fixture
def planta(tmp_path):
    a = criar_planta("Usina Teste", "sintetico", raiz=tmp_path)
    a.criar_equipamento(EQ, "Caldeira de teste")
    yield a
    a.fechar()


def arquivos_caso():
    pacote, _ = montar([Periodo(11.773), Periodo(11.773)])
    return {f"{k}.csv": v for k, v in pacote._arquivos_teste.items()}


# ------------------------------------------------------------ medição gravada no lote


def test_medicao_da_tela_fica_no_lote_e_no_evento(planta):
    r = planta.confirmar(
        planta.previa(EQ, arquivos_caso()),
        autor="Ana",
        atendimento={"segundos_na_tela": 312.04, "ajustes": {"colunas": 2, "total": 2}},
    )
    assert r["atendimento"] == {"segundos_na_tela": 312.0, "ajustes": {"colunas": 2, "total": 2}}
    lote = planta.importacoes(EQ)[0]
    assert lote["resumo"]["atendimento"]["segundos_na_tela"] == 312.0
    reg = registro_atendimento(planta, EQ)
    assert reg["envios_ate_fechamento"] == 1 and reg["envios_medidos"] == 1
    assert reg["segundos_na_tela"] == 312.0 and reg["ajustes"] == 2
    assert reg["primeiro_fechamento"] is None and reg["horas_ate_primeiro_fechamento"] is None


def test_envio_sem_medicao_nao_vira_zero(planta):
    planta.confirmar(planta.previa(EQ, arquivos_caso()), autor="Ana")
    reg = registro_atendimento(planta, EQ)
    assert reg["envios_sem_medicao"] == 1
    assert reg["segundos_na_tela"] is None and reg["ajustes"] is None


@pytest.mark.parametrize(
    "atendimento",
    [
        {"segundos_na_tela": -1},
        {"segundos_na_tela": float("nan")},
        {"segundos_na_tela": True},
        {"ajustes": {"total": -2}},
        {"ajustes": {"total": 1.5}},
        {"minutos": 3},
    ],
)
def test_medicao_invalida_e_recusada(planta, atendimento):
    with pytest.raises(ErroArmazem):
        planta.confirmar(planta.previa(EQ, arquivos_caso()), autor="Ana", atendimento=atendimento)
    assert planta.importacoes(EQ) == []


# ------------------------------------------------------------ horas lançadas pela equipe


def test_horas_lancadas_por_mes_e_csv(planta):
    planta.registrar_atendimento(EQ, "2026-09-02", "implantacao", 45, "Adryan", "primeira conversa")
    planta.registrar_atendimento(EQ, "2026-09-10", "planilha", 30, "Adryan")
    planta.registrar_atendimento(EQ, "2026-10-01", "duvida", 15, "Bia", "=SOMA(A1)")
    registros = atendimentos_registrados(planta, EQ)
    assert [r["minutos"] for r in registros] == [45, 30, 15]
    meses = minutos_por_mes(registros)
    assert meses["2026-09"] == {"minutos": 75, "por_tarefa": {"implantacao": 45, "planilha": 30}}
    assert meses["2026-10"]["minutos"] == 15
    linhas = list(csv.reader(io.StringIO(csv_atendimento("Usina Teste", EQ, registros).decode())))
    assert linhas[0] == ["cliente", "equipamento_id", "data", "tarefa", "minutos", "autor", "nota"]
    assert linhas[3][-1] == "'=SOMA(A1)"  # planilha não executa como fórmula
    # lançar horas não muda a revisão dos dados nem cria lote
    assert planta.importacoes(EQ) == []


@pytest.mark.parametrize(
    ("dia", "tarefa", "minutos", "autor"),
    [
        ("2026-09-02", "café", 10, "Ana"),
        ("2026-09-02", "duvida", 0, "Ana"),
        ("2026-09-02", "duvida", 2000, "Ana"),
        ("2026-09-02", "duvida", None, "Ana"),
        ("02/09/2026", "duvida", 10, "Ana"),
        ("2026-09-02", "duvida", 10, " "),
        ((datetime.now(UTC) + timedelta(days=3)).date().isoformat(), "duvida", 10, "Ana"),
    ],
)
def test_lancamento_invalido_e_recusado(planta, dia, tarefa, minutos, autor):
    with pytest.raises(ErroArmazem):
        planta.registrar_atendimento(EQ, dia, tarefa, minutos, autor)
    assert atendimentos_registrados(planta, EQ) == []


# ------------------------------------------------------------ ajustes da conferência


def test_aceitar_tudo_conta_zero_e_cada_mudanca_conta_um():
    texto = "Data;Hora;Peso líquido (t);Fornecedor\n01/09/2026;08:00;28,4;F1\n"
    arquivos = {"Entrada de lenha.csv": texto.encode()}
    f = ler_fontes(arquivos)[0]
    sugerido = sugestao_da_fonte(f, origem="sintetico")
    assert sugerido["tabela"] == "combustivel"
    assert sugerido["combinar"] == {"alvo": "data", "data": "Data", "hora": "Hora"}
    assert sugerido["constantes"] == {"origem_dado": "sintetico", "tipo": "recebimento"}
    final = {k: v for k, v in sugerido.items()}
    assert contar_ajustes(final, sugerido)["total"] == 0
    outro = {
        **final,
        "unidades": {"Peso líquido (t)": "kg"},
        "constantes": {**final["constantes"], "tipo": "estoque"},
    }
    assert contar_ajustes(outro, sugerido) == {
        "tabela": 0,
        "cabecalho": 0,
        "data_hora": 0,
        "colunas": 0,
        "unidades": 1,
        "valores_unicos": 1,
        "total": 2,
    }
    lote = preparar_lote(arquivos, {f.chave: {**outro, "sugerido": sugerido}})
    assert ajustes_do_lote(lote) == {**contar_ajustes(outro, sugerido), "fontes": 1}
    assert json.loads(lote["euler_importacao.json"])["adaptacoes"][0]["sugerido"] == sugerido


def test_lote_sem_sugestao_guardada_nao_tem_contagem():
    arquivos = {"c.csv": b"data,tipo\n2026-10-01,recebimento\n"}
    f = ler_fontes(arquivos)[0]
    lote = preparar_lote(
        arquivos,
        {f.chave: {"tabela": "combustivel", "mapeamento": {"data": "data", "tipo": "tipo"}}},
    )
    assert ajustes_do_lote(lote) is None
    assert ajustes_do_lote({}) is None


@pytest.mark.parametrize(
    ("nome", "tipo"),
    [
        ("Entrada de lenha", "recebimento"),
        ("Recebimentos", "recebimento"),
        ("Estoque do pátio", "estoque"),
        ("Inventário", "estoque"),
        ("Lenha", None),
        ("Entrada e estoque", None),  # as duas palavras: a pessoa escolhe
    ],
)
def test_tipo_dos_registros_pelo_nome_da_aba(nome, tipo):
    f = ler_fontes({f"{nome}.csv": b"Data,Peso (t)\n01/09/2026,1\n"})[0]
    assert sugerir_tipo(f) == tipo
