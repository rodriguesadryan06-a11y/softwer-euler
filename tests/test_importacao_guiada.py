"""Planilhas da empresa: mapeamento explícito, unidades e originais preservados."""

import hashlib
import io
import json

import pandas as pd
import pytest

from app.importacao_guiada import (
    assinatura_envio,
    ler_fontes,
    preparar_lote,
    sugerir_mapeamento,
    sugerir_tabela,
)
from euler.armazem import criar_planta
from euler.io import fontes_de_arquivos, importar_pacote


def decisao(fonte, tabela, mapa, unidades=None, constantes=None):
    return {
        fonte.chave: {
            "tabela": tabela,
            "mapeamento": mapa,
            "unidades": unidades or {},
            "constantes": constantes or {},
        }
    }


def test_sugestoes_conservadoras_sem_adivinhar_grandeza():
    mapa = sugerir_mapeamento(
        ["Caldeira", "Hora da leitura", "steam_flow_t_h", "Pressão", "Consumo", "R$"],
        "diario",
    )
    assert mapa == {
        "Caldeira": "caldeira_id",
        "Hora da leitura": "instante_observado",
        "steam_flow_t_h": "vazao_vapor_t_h",
    }


def test_csv_br_e_excel_com_aba_fora_do_modelo():
    csv = {
        "turnos.csv": "Caldeira;Hora da leitura;Vazão de vapor\nB1;05/10/2026 08:00;1,5\n".encode()
    }
    fonte = ler_fontes(csv)[0]
    assert fonte.virgula_decimal
    assert sugerir_tabela(fonte) == "diario"
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame({"Data": ["05/10/2026"], "Massa": [2.5]}).to_excel(
            writer, sheet_name="Entrada de lenha", index=False
        )
    abas = ler_fontes({"compras.xlsx": out.getvalue()})
    assert abas[0].aba == "Entrada de lenha"
    assert str(abas[0].bruto["Massa"].iloc[0]) == "2.5"


def test_cabecalho_duplicado_e_recusado_antes_de_perder_coluna():
    with pytest.raises(ValueError, match="repetid"):
        ler_fontes({"dados.csv": b"Data;Data\n1;2\n"})


def test_conversao_de_toneladas_preserva_original_e_ausente():
    arquivos = {"compras.csv": b"Data;Tipo;Peso\n2026-10-01;recebimento;2,5\n2026-10-02;estoque;\n"}
    f = ler_fontes(arquivos)[0]
    escolhas = decisao(
        f,
        "combustivel",
        {"Data": "data", "Tipo": "tipo", "Peso": "massa_kg"},
        {"Peso": "t"},
        {"origem_dado": "publico"},
    )
    lote = preparar_lote(arquivos, escolhas)
    p = importar_pacote(fontes_de_arquivos(lote)[0])
    assert p.dados("combustivel")["massa_kg"].iloc[0] == 2500
    assert pd.isna(p.dados("combustivel")["massa_kg"].iloc[1])
    manifesto = json.loads(lote["euler_importacao.json"])
    original = manifesto["originais"][0]
    assert lote[original["arquivo_guardado"]] == arquivos["compras.csv"]
    assert original["nome"] == "compras.csv"
    assert original["sha256"] == hashlib.sha256(arquivos["compras.csv"]).hexdigest()
    assert manifesto["adaptacoes"][0]["unidades"] == {"Peso": "t"}
    assert manifesto["adaptacoes"][0]["constantes"]["origem_dado"] == "publico"


@pytest.mark.parametrize("unidade", [None, "R$/t", "bar absoluto"])
def test_unidade_ausente_ou_incompativel_bloqueia(unidade):
    arquivos = {"dados.csv": b"Data;Tipo;Valor\n2026-10-01;recebimento;100\n"}
    f = ler_fontes(arquivos)[0]
    escolhas = decisao(
        f,
        "combustivel",
        {"Data": "data", "Tipo": "tipo", "Valor": "preco_brl"},
        {} if unidade is None else {"Valor": unidade},
    )
    with pytest.raises(ValueError, match="unidade"):
        preparar_lote(arquivos, escolhas)


def test_origem_declarada_nao_pode_substituir_sintetico_por_real():
    arquivos = {"dados.csv": b"data,tipo,origem_dado\n2026-10-01,recebimento,sintetico\n"}
    f = ler_fontes(arquivos)[0]
    escolhas = decisao(
        f, "combustivel", {"data": "data", "tipo": "tipo"}, constantes={"origem_dado": "real"}
    )
    with pytest.raises(ValueError, match="origem"):
        preparar_lote(arquivos, escolhas)


def test_duas_colunas_para_mesma_grandeza_bloqueiam_e_fontes_da_mesma_tabela_se_juntam():
    arquivos = {"a.csv": b"data,tipo,valor,outro\n2026-10-01,recebimento,1,2\n"}
    f = ler_fontes(arquivos)[0]
    escolhas = decisao(
        f,
        "combustivel",
        {"data": "data", "tipo": "tipo", "valor": "massa_kg", "outro": "massa_kg"},
        {"valor": "kg", "outro": "kg"},
    )
    with pytest.raises(ValueError, match="mesma coluna"):
        preparar_lote(arquivos, escolhas)
    # D107: duas fontes da mesma tabela se juntam; o mesmo registro igual entra uma vez
    arquivos = {
        "a.csv": b"data,tipo,lote,kg\n2026-10-01,recebimento,L1,10\n2026-10-02,recebimento,L2,20\n",
        "b.csv": b"data,tipo,lote,kg\n2026-10-02,recebimento,L2,20\n2026-10-03,recebimento,L3,30\n",
    }
    mapa = {"data": "data", "tipo": "tipo", "lote": "lote_id", "kg": "massa_kg"}
    escolhas = {
        f.chave: {"tabela": "combustivel", "mapeamento": mapa, "unidades": {"kg": "kg"}}
        for f in ler_fontes(arquivos)
    }
    lote = preparar_lote(arquivos, escolhas)
    junto = pd.read_csv(io.BytesIO(lote["combustivel.csv"]))
    assert junto["lote_id"].tolist() == ["L1", "L2", "L3"]
    ad = {a["fonte"]: a for a in json.loads(lote["euler_importacao.json"])["adaptacoes"]}
    assert ad["a.csv"]["linhas_no_adaptado"] == [2, 3]
    assert ad["b.csv"]["linhas_no_adaptado"] == [4, 4]
    assert ad["b.csv"]["repetidas_iguais_entraram_uma_vez"] == [2]
    # o mesmo registro com valores diferentes: a EULER não escolhe qual vale
    arquivos["b.csv"] = arquivos["b.csv"].replace(b"L2,20", b"L2,25")
    with pytest.raises(ValueError, match="valores diferentes"):
        preparar_lote(arquivos, escolhas)


def test_assinatura_muda_com_conteudo_mesmo_nome_e_unidade():
    assert assinatura_envio({"a.csv": b"1"}, {}) != assinatura_envio({"a.csv": b"2"}, {})
    assert assinatura_envio({"a.csv": b"1"}, {"unit": "kg"}) != assinatura_envio(
        {"a.csv": b"1"}, {"unit": "t"}
    )


def test_lote_guiado_persiste_originais_e_reimportacao_nao_duplica(tmp_path):
    arquivos = {"turno.csv": b"Caldeira;Hora da leitura;Vapor\nB1;2026-10-01 08:00;1000\n"}
    f = ler_fontes(arquivos)[0]
    escolhas = decisao(
        f,
        "diario",
        {
            "Caldeira": "caldeira_id",
            "Hora da leitura": "instante_observado",
            "Vapor": "vazao_vapor_t_h",
        },
        {"Vapor": "kg/h"},
        {"origem_dado": "publico"},
    )
    lote = preparar_lote(arquivos, escolhas)
    a = criar_planta("Teste público", "publico", raiz=tmp_path)
    try:
        a.criar_equipamento("B1", "Caldeira B1", "B1")
        r = a.confirmar(a.previa("B1", lote), autor="Teste")
        assert r["novas"] == 1
        assert a.previa("B1", lote).contagem()["diario"]["igual"] == 1
        assert a.pacote("B1").dados("diario")["vazao_vapor_t_h"].iloc[0] == 1
    finally:
        a.fechar()


def test_identificacao_existente_nao_pode_ser_reescrita_por_constante():
    arquivos = {"turno.csv": b"caldeira_id,instante_observado\nB2,2026-10-01 08:00\n"}
    f = ler_fontes(arquivos)[0]
    escolhas = decisao(
        f, "diario", {"instante_observado": "instante_observado"}, constantes={"caldeira_id": "B1"}
    )
    with pytest.raises(ValueError, match="caldeira"):
        preparar_lote(arquivos, escolhas)


def test_conversao_temperatura_rastreia_unidade_e_linha():
    arquivos = {
        "turno.csv": b"caldeira_id;instante_observado;Temperatura\nB1;2026-10-01 08:00;373,15\n"
    }
    f = ler_fontes(arquivos)[0]
    escolhas = decisao(
        f,
        "diario",
        {
            "caldeira_id": "caldeira_id",
            "instante_observado": "instante_observado",
            "Temperatura": "t_agua_alim_c",
        },
        {"Temperatura": "K"},
    )
    lote = preparar_lote(arquivos, escolhas)
    p = importar_pacote(fontes_de_arquivos(lote)[0])
    assert p.dados("diario")["t_agua_alim_c"].iloc[0] == pytest.approx(100)
    m = json.loads(lote["euler_importacao.json"])
    assert m["adaptacoes"][0]["linhas_originais"] == [2]


def test_excel_invalido_tem_erro_legivel():
    with pytest.raises(ValueError, match="Excel"):
        ler_fontes({"arquivo.xlsx": b"nao e uma planilha"})
