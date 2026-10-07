"""Inconsistências apontadas na revisão de 07/10/2026, cada uma com o caso que a reproduz.

1. Célula de porcentagem do Excel (mostra 45%, guarda 0,45) convertida duas vezes.
Dados sintéticos.
"""

import io

import pytest
from openpyxl import Workbook

from app.importacao_guiada import ler_fontes, preparar_lote
from euler.io import fontes_de_arquivos, importar_pacote
from euler.io.leitura import ler_planilha

# ------------------------------------------------------------ 1. porcentagem do Excel


def _xlsx(abas: dict[str, list[list]], formatos: dict[tuple[str, str], str]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for nome, linhas in abas.items():
        ws = wb.create_sheet(nome)
        for linha in linhas:
            ws.append(linha)
    for (aba, celula), formato in formatos.items():
        wb[aba][celula].number_format = formato
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _amostras(unidade: str, umidade_cel=0.45, formato="0%") -> tuple[dict, dict]:
    conteudo = _xlsx(
        {
            "Umidade": [
                ["Amostra", "Lote", "Data", "Umidade (%)"],
                ["A1", "L1", "01/09/2026", umidade_cel],
            ]
        },
        {("Umidade", "D2"): formato} if formato else {},
    )
    arquivos = {"lab.xlsx": conteudo}
    (f,) = ler_fontes(arquivos)
    decisoes = {
        f.chave: {
            "tabela": "amostras",
            "mapeamento": {
                "Amostra": "amostra_id",
                "Lote": "lote_id",
                "Data": "data",
                "Umidade (%)": "umidade_bu_frac",
            },
            "unidades": {"Umidade (%)": unidade},
            "constantes": {"origem_dado": "sintetico"},
        }
    }
    return arquivos, decisoes


@pytest.mark.parametrize("unidade", ["%, base úmida", "fração, base úmida"])
def test_celula_que_mostra_45_porcento_entra_como_045(unidade):
    arquivos, decisoes = _amostras(unidade)
    (f,) = ler_fontes(arquivos)
    assert f.bruto["Umidade (%)"].tolist() == ["45%"]  # o que a pessoa vê no Excel
    lote = preparar_lote(arquivos, decisoes)
    p = importar_pacote(fontes_de_arquivos(lote)[0])
    assert p.dados("amostras")["umidade_bu_frac"].tolist() == pytest.approx([0.45])


def test_porcentagem_com_casas_decimais_e_numero_comum_continuam_certos():
    arquivos, decisoes = _amostras("%, base úmida", 0.123, "0.0%")
    lote = preparar_lote(arquivos, decisoes)
    p = importar_pacote(fontes_de_arquivos(lote)[0])
    assert p.dados("amostras")["umidade_bu_frac"].tolist() == pytest.approx([0.123])
    # célula sem formato de porcentagem: o número digitado vale na unidade escolhida
    arquivos, decisoes = _amostras("%, base úmida", 45, None)
    lote = preparar_lote(arquivos, decisoes)
    p = importar_pacote(fontes_de_arquivos(lote)[0])
    assert p.dados("amostras")["umidade_bu_frac"].tolist() == pytest.approx([0.45])


def test_porcentagem_em_coluna_de_massa_e_recusada():
    conteudo = _xlsx(
        {"Lenha": [["Data", "Tipo", "Massa (kg)"], ["01/09/2026", "recebimento", 0.5]]},
        {("Lenha", "C2"): "0%"},
    )
    arquivos = {"lenha.xlsx": conteudo}
    (f,) = ler_fontes(arquivos)
    decisoes = {
        f.chave: {
            "tabela": "combustivel",
            "mapeamento": {"Data": "data", "Tipo": "tipo", "Massa (kg)": "massa_kg"},
            "unidades": {"Massa (kg)": "kg"},
            "constantes": {"origem_dado": "sintetico"},
        }
    }
    with pytest.raises(ValueError, match="porcentagem"):
        preparar_lote(arquivos, decisoes)


def test_planilha_modelo_com_porcentagem_do_excel():
    """Leitor do modelo (abas com nome de tabela): O₂ em % e umidade em fração."""
    conteudo = _xlsx(
        {
            "diario": [
                ["caldeira_id", "instante_observado", "o2_seco_pct", "origem_dado"],
                ["C1", "2026-09-01 08:00", 0.08, "sintetico"],
            ],
            "amostras": [
                ["amostra_id", "lote_id", "data", "umidade_bu_frac", "origem_dado"],
                ["A1", "L1", "2026-09-01", 0.45, "sintetico"],
            ],
        },
        {("diario", "C2"): "0%", ("amostras", "D2"): "0%"},
    )
    abas = ler_planilha(conteudo)
    assert abas["diario"]["o2_seco_pct"].tolist() == ["8%"]
    p = importar_pacote(fontes_de_arquivos({"modelo.xlsx": conteudo})[0])
    assert p.dados("diario")["o2_seco_pct"].tolist() == pytest.approx([8.0])
    assert p.dados("amostras")["umidade_bu_frac"].tolist() == pytest.approx([0.45])
    assert any("porcentagem" in a.mensagem for a in p.avisos)  # interpretação registrada


# ------------------------------------------------------------ 2. conta sem preço


def _conta(preco=150.0, incerteza=0.01, **extra):
    from euler.conta import explicar_conta

    return explicar_conta(
        combustivel_ref_t=100.0,
        vapor_ref_t=300.0,
        combustivel_t=110.0,
        vapor_t=300.0,
        preco_ref_brl_t=150.0,
        preco_brl_t=preco,
        incerteza_consumo_t_t=incerteza,
        **extra,
    )


def _fechamento_falso(conta, lotes_sem_valor=0):
    return {
        "resultado": {
            "nucleo": {
                "explicacao_conta": conta,
                "conta_do_periodo": {"lotes_sem_valor": lotes_sem_valor},
            }
        }
    }


def test_conta_sem_preco_nao_e_completa():
    from euler.linha_do_tempo import _qualidade

    rotulo, motivo = _qualidade(_fechamento_falso(_conta(preco=None)))
    assert rotulo == "sem preço" and "sem valor em reais" in motivo
    assert _qualidade(_fechamento_falso(_conta()))[0] == "completa"
    assert _qualidade(_fechamento_falso(_conta(), lotes_sem_valor=2))[0] == "preço incompleto"


# ------------------------------------------------------------ 3. motivo do inconclusivo


def _conta_cenario_do_patio():
    """Desvio 6 t com faixa 3–9 t (exclui zero); um cenário do pátio leva o centro a −1 t."""
    import math

    ef = 100 * math.log(104 / 100)
    alt = 100 * math.log(111 / 100)
    return _conta(efeito_qualidade_pct=ef, cenarios_qualidade_pct=(ef, alt))


def test_motivo_do_inconclusivo_e_o_certo():
    from euler.conta import motivo_inconclusivo

    c = _conta_cenario_do_patio()
    d = c["desvio"]
    assert d["estado"] == "nao_estabelecido"
    assert d["faixa_t"][0] > 0  # a faixa das medições não inclui zero
    assert motivo_inconclusivo(d) == "cenario_do_patio"
    assert motivo_inconclusivo(_conta(incerteza=0.2)["desvio"]) == "faixa_inclui_zero"
    assert motivo_inconclusivo(_conta(incerteza=None)["desvio"]) == "sem_faixa"
    assert motivo_inconclusivo(_conta(incerteza=0.001)["desvio"]) is None  # estabelecido


def test_fechamento_e_linha_do_tempo_nao_culpam_a_incerteza_das_medicoes():
    from euler.fechamento import frase_situacao
    from euler.linha_do_tempo import _leitura

    nucleo = {"explicacao_conta": _conta_cenario_do_patio()}
    frase = frase_situacao(nucleo)
    assert "cenário do pátio" in frase and "dentro da incerteza" not in frase
    assert frase_situacao({"explicacao_conta": _conta(incerteza=0.2)}).startswith(
        "Diferença dentro da incerteza"
    )
    periodo = {
        "estado": "nao_estabelecido",
        "motivo_inconclusivo": "cenario_do_patio",
        "acoes": [],
        "referencia_versao": 1,
        "dias": 14,
        "qualidade": "completa",
        "qualidade_motivo": "Conta com preço e faixa de incerteza.",
    }
    leitura = " ".join(_leitura([periodo]))
    assert "cenário do pátio" in leitura and "cabe na incerteza" not in leitura


def test_avaliacao_inconclusiva_diz_o_motivo_certo():
    from euler.acompanhamento import resultado_da_avaliacao

    r, frase = resultado_da_avaliacao(_conta(incerteza=None)["desvio"], None, [])
    assert r == "inconclusivo"
    assert "incerteza declarada" in frase and "ficou dentro da incerteza" not in frase
    r, frase = resultado_da_avaliacao(_conta_cenario_do_patio()["desvio"], None, ["outra ação"])
    assert r == "inconclusivo" and "cenário do pátio" in frase and "outra ação" in frase
    r, frase = resultado_da_avaliacao(_conta(incerteza=0.2)["desvio"], None, [])
    assert "cabe na incerteza das medições" in frase
    assert resultado_da_avaliacao({}, "Conta indisponível: sem vapor.", [])[0] == "nao_avaliavel"


# ------------------------------------------------------------ 4. "não avaliável" não conclui


def test_acao_nao_avaliavel_nao_conclui_a_etapa_de_resultado(tmp_path, monkeypatch):
    from euler import percurso as pc
    from euler.armazem import criar_planta

    a = criar_planta("Percurso (sintético)", "sintetico", raiz=tmp_path)
    try:
        a.criar_equipamento("C1", "Caldeira 1")
        monkeypatch.setattr(
            pc,
            "intervencoes",
            lambda a, e: [{"id": 7, "data": "2026-09-01", "investigacao_id": None}],
        )
        monkeypatch.setattr(pc, "investigacoes", lambda a, e: [])
        avaliacao = {"resultado": {"resultado": "nao_avaliavel"}}
        monkeypatch.setattr(pc, "ultima_avaliacao", lambda a, i: avaliacao)
        passo = {p["id"]: p for p in pc.percurso(a, "C1")}["resultado"]
        assert passo["estado"] == "pendente" and "não avaliável" in passo["frase"]
        avaliacao["resultado"]["resultado"] = "inconclusivo"
        passo = {p["id"]: p for p in pc.percurso(a, "C1")}["resultado"]
        assert passo["estado"] == "feito"
    finally:
        a.fechar()


# ------------------------------------------------------------ 5. selo de dados sintéticos


def test_relatorios_exportados_levam_o_selo_de_dados_sinteticos(tmp_path, monkeypatch):
    from pathlib import Path

    from euler.entrega import entrega_do_fechamento, texto_entrega
    from euler.fechamento import criar_referencia, produzir_fechamento
    from euler.painel import texto_fechamento
    from euler.periodos import periodos_entre_estoques
    from euler.persistencia import Repositorio

    monkeypatch.setenv("EULER_DADOS_DIR", str(tmp_path / "dados"))
    raiz = Path(__file__).resolve().parents[1]
    repo = Repositorio()
    planta = repo.criar_planta("Selo (sintético)", classe="sintetico")
    a = repo.armazem(planta["id"])
    try:
        a.criar_equipamento(
            "CALD-DEMO-01", "Caldeira A", "CALD-DEMO-01", config={"altitude_m": 1000.0}
        )
        arquivos = {
            p.name: p.read_bytes() for p in (raiz / "demo/caso_demo_completo").glob("*.csv")
        }
        a.confirmar(a.previa("CALD-DEMO-01", arquivos), autor="Teste")
        s = periodos_entre_estoques(a.pacote("CALD-DEMO-01"))
        criar_referencia(a, "CALD-DEMO-01", s[0][0], s[3][1], "inicial", "Base", "Teste")
        f = produzir_fechamento(a, "CALD-DEMO-01", "Teste")
        assert f["resultado"]["origem_dados"] == "sintetico"
        assert "DADOS SINTÉTICOS" in texto_fechamento(f)
        e = entrega_do_fechamento(a, "CALD-DEMO-01")
        assert "DADOS SINTÉTICOS" in texto_entrega(e, "Caldeira A")
        # fechamento gravado antes da origem no resultado: a origem vem da planta
        antigo = {
            **f,
            "resultado": {k: v for k, v in f["resultado"].items() if k != "origem_dados"},
        }
        assert "DADOS SINTÉTICOS" not in texto_fechamento(antigo)
        assert "DADOS SINTÉTICOS" in texto_fechamento(antigo, "sintetico")
    finally:
        a.fechar()
