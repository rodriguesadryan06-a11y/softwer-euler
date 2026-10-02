"""Importadores e verificações de qualidade (T03, T05)."""

from pathlib import Path

import pandas as pd
import pytest

from euler.io import fontes_de_arquivos, importar_pacote, importar_pasta
from euler.io.diario import importar_diario
from euler.io.leitura import importar_tabela

RAIZ = Path(__file__).resolve().parents[1]
PROBLEMAS = RAIZ / "demo" / "qualidade"


@pytest.fixture(scope="module")
def pacote_problemas():
    return importar_pasta(PROBLEMAS, p_atm_bar=1.0)


def test_modelos_importam_sem_avisos_de_qualidade():
    p = importar_pasta(RAIZ / "templates", p_atm_bar=1.01325)
    assert set(p.importacoes) == {"diario", "combustivel", "amostras", "eventos", "instrumentos"}
    assert [a for a in p.avisos if a.gravidade != "info"] == []
    d = p.dados("diario")
    assert str(d["instante_observado"].dt.tz) == "America/Sao_Paulo"
    assert d["instante_observado"].iloc[0] == pd.Timestamp("2026-10-05T08:00:00-03:00")
    assert d["p_vapor_bar_abs"].iloc[0] == pytest.approx(9.0 + 1.01325)


@pytest.mark.parametrize(
    ("tabela", "linha", "tipo"),
    [
        ("diario", 5, "duplicata"),
        ("diario", 6, "unidade_suspeita"),
        ("diario", 7, "unidade_suspeita"),
        ("diario", 8, "registro_tardio"),
        ("diario", 9, "lacuna"),
        ("diario", 10, "totalizador_reiniciado"),
        ("diario", 11, "unidade_suspeita"),
        ("diario", 12, "valor_ilegivel"),
        ("diario", 14, "duplicata_conflitante"),
        ("diario", 15, "instrumento_indisponivel"),
        ("diario", 16, "interpretacao"),
        ("diario", None, "instrumento_sem_cadastro"),
        ("combustivel", 4, "volume_sem_densidade"),
        ("combustivel", 5, "massa_estimada"),
        ("combustivel", 6, "sem_fornecedor"),
        ("combustivel", 6, "unidade_suspeita"),
        ("combustivel", 7, "duplicata_conflitante"),
        ("combustivel", 8, "sem_preco"),
        ("combustivel", 8, "lote_sem_umidade"),
        ("amostras", 3, "unidade_suspeita"),
        ("amostras", 4, "lote_desconhecido"),
        ("amostras", 5, "composicao_incompleta"),
    ],
)
def test_cada_problema_plantado_e_detectado_na_linha_certa(pacote_problemas, tabela, linha, tipo):
    encontrados = {(a.tabela, a.linha, a.tipo) for a in pacote_problemas.avisos}
    assert (tabela, linha, tipo) in encontrados


def test_linhas_sem_problema_nao_geram_aviso(pacote_problemas):
    linhas_com_aviso = {a.linha for a in pacote_problemas.avisos if a.tabela == "diario"}
    assert {2, 3, 4}.isdisjoint(linhas_com_aviso)


def test_original_preservado_e_ausente_nao_vira_zero(pacote_problemas):
    imp = pacote_problemas.importacoes["diario"]
    original = imp.original.set_index("linha")
    dados = imp.dados.set_index("linha")
    assert original.loc[12, "t_gases_c"] == "abc"
    assert pd.isna(dados.loc[12, "t_gases_c"])
    assert pd.isna(dados.loc[15, "t_gases_c"])
    # nada é apagado nem inventado: mesma quantidade de linhas, duplicatas mantidas
    assert len(imp.dados) == len(imp.original) == 15
    # valores suspeitos são mantidos como vieram
    assert dados.loc[6, "t_gases_c"] == 455


def test_volume_sem_densidade_nao_vira_massa(pacote_problemas):
    d = pacote_problemas.dados("combustivel").set_index("linha")
    assert pd.isna(d.loc[4, "massa_kg_calc"])
    assert d.loc[5, "massa_kg_calc"] == pytest.approx(90 * 330)
    assert d.loc[5, "massa_origem"] == "estimado"
    assert d.loc[3, "massa_origem"] == "medido"


def test_csv_do_excel_brasileiro_ponto_e_virgula_e_virgula_decimal():
    conteudo = (
        "caldeira_id;instante_observado;t_gases_c;totalizador_vapor_t\n"
        "C1;2026-10-05T08:00:00-03:00;182,5;15.234,5\n"
    ).encode("cp1252")
    imp = importar_diario(conteudo)
    assert imp.dados["t_gases_c"].iloc[0] == pytest.approx(182.5)
    assert imp.dados["totalizador_vapor_t"].iloc[0] == pytest.approx(15234.5)
    tipos = {a.tipo for a in imp.avisos}
    assert "interpretacao" in tipos


def test_diario_aceita_estado_temperatura_e_titulo_do_vapor():
    conteudo = (
        b"caldeira_id,instante_observado,estado_vapor,t_vapor_c,titulo_vapor_frac\n"
        b"C1,2026-10-05T08:00:00-03:00,superaquecido,250,\n"
        b"C1,2026-10-05T10:00:00-03:00,umido,,0.95\n"
    )
    imp = importar_diario(conteudo)
    assert not imp.bloqueada
    assert list(imp.dados["estado_vapor"]) == ["superaquecido", "umido"]
    assert imp.dados["t_vapor_c"].iloc[0] == pytest.approx(250.0)
    assert imp.dados["titulo_vapor_frac"].iloc[1] == pytest.approx(0.95)


def test_codificacao_windows_e_registrada():
    conteudo = "instante,tipo,descricao\n2026-10-12T14:00:00-03:00,limpeza,Limpeza dos tubos\n"
    conteudo = conteudo.replace("Limpeza dos tubos", "Inspeção").encode("cp1252")
    imp = importar_tabela("eventos", conteudo)
    assert imp.dados["descricao"].iloc[0] == "Inspeção"
    assert any(a.tipo == "codificacao" for a in imp.avisos)


def test_coluna_obrigatoria_ausente_bloqueia_a_tabela():
    imp = importar_diario(b"caldeira_id,t_gases_c\nC1,180\n")
    assert imp.bloqueada
    assert any(a.tipo == "coluna_obrigatoria_ausente" for a in imp.avisos)


def test_marcas_de_sem_dado_viram_ausente_com_registro():
    imp = importar_diario(
        b"caldeira_id,instante_observado,t_gases_c\nC1,2026-10-05T08:00-03:00,-\n"
    )
    assert pd.isna(imp.dados["t_gases_c"].iloc[0])
    assert any("lido como ausente" in a.mensagem for a in imp.avisos)


def test_sem_pressao_atmosferica_nao_calcula_absoluta():
    imp = importar_diario(RAIZ / "templates" / "diario.csv")
    assert pd.isna(imp.dados["p_vapor_bar_abs"].iloc[0])
    assert any(a.tipo == "sem_pressao_atmosferica" for a in imp.avisos)


def test_arquivo_com_nome_desconhecido_gera_aviso():
    fontes, avisos = fontes_de_arquivos({"planilha_qualquer.csv": b"a,b\n1,2\n"})
    assert fontes == {}
    assert avisos and avisos[0].tipo == "arquivo_desconhecido"


def test_planilha_modelo_xlsx_importa_igual_aos_csvs():
    conteudo = (RAIZ / "templates" / "planilha_modelo_euler.xlsx").read_bytes()
    fontes, avisos = fontes_de_arquivos({"planilha_modelo_euler.xlsx": conteudo})
    assert avisos == []
    assert set(fontes) == {"diario", "combustivel", "amostras", "eventos", "instrumentos"}
    p = importar_pacote(fontes, p_atm_bar=1.01325)
    assert [a for a in p.avisos if a.gravidade != "info"] == []
    pelo_csv = importar_pasta(RAIZ / "templates", p_atm_bar=1.01325)
    for nome in fontes:
        a = p.dados(nome).drop(columns="linha").reset_index(drop=True)
        b = pelo_csv.dados(nome).drop(columns="linha").reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_tabela_de_avisos_ordena_por_gravidade(pacote_problemas):
    tabela = pacote_problemas.tabela_avisos()
    ordem = tabela["Gravidade"].map({"Erro": 0, "Atenção": 1, "Informação": 2})
    assert ordem.is_monotonic_increasing
