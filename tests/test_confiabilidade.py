"""Revisão de confiabilidade (auditoria externa da Fase R, 01/10/2026; achados A1–A5).

Cada teste reproduz um contraexemplo da auditoria (versão examinada 2cd4dc3) e fixa o
comportamento esperado depois da correção: nenhuma estimativa indevida, nenhuma falha,
e toda conclusão dependente só das informações que a sustentam.
"""

from __future__ import annotations

import copy
from functools import partial
from math import sqrt

import pandas as pd
import pytest
from construtor_caso import INSTRUMENTOS_SINTETICOS, Periodo, montar

from euler.deteccao import comparar
from euler.direto import balanco_direto
from euler.incerteza import Componente, Falta, Orcamento
from euler.indireto import COMPOSICAO_REFERENCIA, o2_seco_equivalente
from euler.investigacao import indireto_periodo, investigar
from euler.periodos import ResumoPeriodo, _cenarios, resumir_periodo
from euler.relatorio import gerar_html, mudou_detectavel
from euler.tipos import AnaliseBloqueada, Grandeza

G01, G09 = 11.773, 12.307
FUSO = "America/Sao_Paulo"


def _h5(j: dict) -> dict:
    return next(h for h in j["hipoteses"] if h["id"] == "perdas_nao_medidas")


# ---------------------------------------------------------------- A1 · FIFO sem qualidade


def test_a1_fifo_indisponivel_quando_parte_queimada_nao_tem_qualidade():
    """Contraexemplo da auditoria: estoque inicial de 10 t sem PCI; 20 t a 8 e 20 t a 9;
    estoque final 10 t. O FIFO queima 10 t desconhecidas: não há PCI FIFO das 40 t
    (a versão examinada devolvia 8,333 MJ/kg, média só da parte conhecida)."""
    t = pd.Timestamp("2026-01-05T07:30", tz=FUSO)
    lotes = pd.DataFrame(
        {
            "data": [
                t - pd.Timedelta(days=1),
                t + pd.Timedelta(hours=2),
                t + pd.Timedelta(hours=5),
            ],
            "massa_kg": [10_000.0, 20_000.0, 20_000.0],
            "pci_umido_mj_kg": [float("nan"), 8.0, 9.0],
        }
    )
    r = ResumoPeriodo(inicio=t, fim=t + pd.Timedelta(days=1))
    r.estoque_inicial_kg, r.estoque_final_kg = 10_000.0, 10_000.0
    r.combustivel_kg = Grandeza(40_000.0, "kg", "medido")
    c = _cenarios(lotes, "pci_umido_mj_kg", r, recebido=8.5)
    assert c.fifo is None
    assert "10 t" in c.fifo_indisponivel and "sem" in c.fifo_indisponivel
    # os limites continuam existindo, mas declaram a hipótese sobre a parte desconhecida
    assert c.minimo <= c.recebido <= c.maximo
    assert any("faixa observada" in x for x in c.condicoes)


def _sem_amostra_no_fim_do_primeiro_periodo():
    """Dois períodos; o último lote do primeiro fica sem amostra (vai para o estoque
    inicial do segundo no cenário FIFO)."""
    pacote, lim = montar([Periodo(G01, dias=7), Periodo(G01, dias=7)])
    comb = pacote.importacoes["combustivel"].dados
    receb = comb[(comb["tipo"] == "recebimento") & (comb["data"] <= lim[0][1])]
    lote = receb.sort_values("data")["lote_id"].iloc[-1]
    amos = pacote.importacoes["amostras"].dados
    pacote.importacoes["amostras"].dados = amos[amos["lote_id"] != lote].reset_index(drop=True)
    return pacote, lim


def test_a1_fifo_sem_qualidade_se_propaga_ate_o_relatorio():
    pacote, lim = _sem_amostra_no_fim_do_primeiro_periodo()
    r = resumir_periodo(pacote, *lim[1])
    assert r.pci_queimado.fifo is None and r.pci_queimado.fifo_indisponivel
    assert "fifo" not in balanco_direto(r).eficiencia_cenarios
    j = investigar(pacote, lim[0], lim[1])
    cen = j["periodos"]["comparacao"]["pci_queimado_cenarios"]
    assert cen["fifo"] is None and cen["fifo_indisponivel"]
    assert any("FIFO" in f for f in j["o_que_falta"])
    # o primeiro período tem massa recebida sem amostra: a hipótese do cenário 'recebido'
    # fica explícita, não silenciosa
    assert any(
        "sem amostra" in x
        for x in j["periodos"]["referencia"]["pci_queimado_cenarios"]["condicoes"]
    )
    html = gerar_html(j)
    assert "FIFO" in html


# ---------------------------------------------------------------- A2 · umidade uma vez só


def _amostras_do_periodo(pacote, inicio, fim) -> pd.Series:
    comb = pacote.importacoes["combustivel"].dados
    lotes = comb[(comb["tipo"] == "recebimento") & (comb["data"] > inicio) & (comb["data"] <= fim)]
    amos = pacote.importacoes["amostras"].dados
    return amos["lote_id"].isin(set(lotes["lote_id"])) & amos["umidade_bu_frac"].notna()


def _residuo(pacote, lim) -> float:
    return _h5(investigar(pacote, lim[0], lim[1]))["efeito"]["perda_gases_pp"]


def _perturbado(pacote, mudar) -> object:
    p = copy.deepcopy(pacote)
    p.__dict__.pop("_cache_periodos", None)
    mudar(p)
    return p


def _derivada(pacote, lim, mudar_com_passo, passo: float) -> float:
    """Derivada central do resíduo pela cadeia inteira (importação → investigar)."""
    mais = _residuo(_perturbado(pacote, lambda p: mudar_com_passo(p, +passo)), lim)
    menos = _residuo(_perturbado(pacote, lambda p: mudar_com_passo(p, -passo)), lim)
    return (mais - menos) / (2 * passo)


@pytest.fixture(scope="module")
def caso_umidade():
    return montar([Periodo(G01, umidade=0.40), Periodo(G09, umidade=0.45)])


def _mudar_amostras(p, d, ini, fim, coluna):
    sel = _amostras_do_periodo(p, ini, fim)
    p.importacoes["amostras"].dados.loc[sel, coluna] += d


def _mudar_leitura(p, d, ini, fim, coluna):
    dia = p.importacoes["diario"].dados
    sel = (dia["instante_observado"] >= ini) & (dia["instante_observado"] < fim)
    dia.loc[sel, coluna] += d


def test_a2_cada_fonte_entra_uma_vez_no_residuo(caso_umidade):
    """Contribuição de cada fonte no resíduo publicado por `investigar` = derivada do
    resíduo calculada perturbando os DADOS (cálculo independente da montagem do orçamento)
    × incerteza-padrão da fonte. Cobre as duas entradas usadas pelos dois caminhos (umidade
    e PCI seco) e duas de um caminho só. A versão examinada somava a umidade duas vezes.

    Tolerância 1%: derivada central com passo pequeno; o motor usa derivada à frente para a
    perda nos gases (diferença de segunda ordem)."""
    pacote, lim = caso_umidade
    r = resumir_periodo(pacote, *lim[0])
    j = investigar(pacote, lim[0], lim[1])
    orc = _h5(j)["orcamento_residuo"]
    assert orc["situacao"] == "completo"
    # incertezas-padrão das fontes (declaradas sem tipo → limites, u = a/√3, D35)
    fontes = {
        "ESTUFA": ("amostras", "umidade_bu_frac", 0.002, 0.5 / 100 / sqrt(3)),
        "CALOR": ("amostras", "pci_seco_mj_kg", 0.05, 0.01 / sqrt(3) * r.pci_seco_mistura),
        "TERMO-AGUA": ("diario", "t_agua_alim_c", 0.5, 1 / sqrt(3)),
        "TERMO-G": ("diario", "t_gases_c", 1.0, 2 / sqrt(3)),
    }
    for periodo, (ini, fim) in (("referencia", lim[0]), ("comparacao", lim[1])):
        for codigo, (tabela, coluna, passo, u) in fontes.items():
            mudar = _mudar_amostras if tabela == "amostras" else _mudar_leitura
            derivada = _derivada(
                pacote, lim, partial(mudar, ini=ini, fim=fim, coluna=coluna), passo
            )
            publicada = sum(c["u_pp"] for c in orc[periodo] if codigo in c["fonte"])
            assert publicada == pytest.approx(derivada * u, rel=0.01), (periodo, codigo)


def test_a2_combinacao_por_fonte_r0_e_r1(caso_umidade):
    """A incerteza publicada é a combinação das contribuições publicadas, juntando a mesma
    fonte dentro de cada período antes de combinar os períodos (GUM 5.2.2)."""
    pacote, lim = caso_umidade
    orc = _h5(investigar(pacote, lim[0], lim[1]))["orcamento_residuo"]

    def u(r: float) -> float:
        var, fontes = 0.0, {}
        for periodo in ("referencia", "comparacao"):
            for c in orc[periodo]:
                if c["chave"] is None:
                    var += c["u_pp"] ** 2
                else:
                    por = fontes.setdefault(c["chave"], {})
                    por[periodo] = por.get(periodo, 0.0) + c["u_pp"]
        for chave, por in fontes.items():
            rr = 1.0 if chave.startswith("medicao:") else r
            v = list(por.values())
            var += rr * sum(v) ** 2 + (1 - rr) * sum(x * x for x in v)
        return sqrt(var)

    assert orc["incerteza_k2_r0"] == pytest.approx(2 * u(0.0), rel=1e-9)
    assert orc["incerteza_k2_r1"] == pytest.approx(2 * u(1.0), rel=1e-9)


def test_a2_sem_metodo_de_umidade_o_residuo_nao_e_avaliado():
    sem_estufa = tuple(c for c in INSTRUMENTOS_SINTETICOS if c != "ESTUFA")
    pacote, lim = montar(
        [Periodo(G01, umidade=0.40), Periodo(G09, umidade=0.45)], instrumentos=sem_estufa
    )
    h = _h5(investigar(pacote, lim[0], lim[1]))
    assert h["status"] == "nao_avaliavel"
    assert h["orcamento_residuo"]["situacao"] == "parcial"
    assert "umidade" in h["porque"]


# ---------------------------------------------------------------- A3 · ausente ≠ zero


def test_a3_orcamento_completo_parcial_indisponivel():
    c = Componente("medidor", 0.01, "instrumental")
    assert Orcamento([c]).situacao == "completo"
    assert Orcamento([c], faltam=[Falta("termômetro")]).situacao == "parcial"
    assert Orcamento(faltam=[Falta("termômetro")]).situacao == "indisponivel"
    junto = Orcamento([c]).mais(Orcamento(faltam=[Falta("balança")]))
    assert junto.situacao == "parcial" and [f.nome for f in junto.faltam] == ["balança"]


def test_a3_comparacao_com_orcamento_parcial_nunca_diz_sim():
    """O que falta só pode aumentar a incerteza: 'não' continua seguro; 'sim' não."""

    def g(valor, faltam):
        orc = Orcamento([Componente("dispersão", 0.01, "aleatoria")], faltam=faltam)
        return Grandeza(valor, "°C", "medido", None, "", orc)

    sistematica = [Falta("termopar", sistematica=True)]
    assert comparar("T", "°C", g(100, sistematica), g(101, sistematica)).detectabilidade == "nao"
    grande = comparar("T", "°C", g(100, sistematica), g(130, sistematica))
    assert grande.detectabilidade == "condicional" and "termopar" in grande.faltam
    outra = [Falta("dispersão diária", sistematica=False)]
    assert comparar("T", "°C", g(100, outra), g(130, outra)).detectabilidade is None


def test_a3_sem_instrumentos_nada_vira_zero():
    """Contraexemplo da auditoria: sem instrumentos, a versão examinada dava incerteza de
    Δh igual a 0,0 e 'descartava' as perdas não medidas com margem de ~±0,3 p.p."""
    pacote, lim = montar([Periodo(G01), Periodo(G01, outras_perdas_pp=8.5)], instrumentos=False)
    b = balanco_direto(resumir_periodo(pacote, *lim[0]))
    assert b.delta_h_mj_kg.incerteza is None
    orc_dh = b.delta_h_mj_kg.orcamento
    assert orc_dh.situacao == "parcial"  # conhecida só a dispersão diária
    assert {f.nome for f in orc_dh.faltam} == {
        "incerteza do instrumento de pressão do vapor",
        "incerteza do instrumento de temperatura da água de alimentação",
    }
    assert b.eficiencia.incerteza is None
    j = investigar(pacote, lim[0], lim[1])
    h = _h5(j)
    assert h["status"] == "nao_avaliavel" and "faltam incertezas" in h["porque"]
    dh = j["periodos"]["referencia"]["eficiencia_direta"]
    assert dh["incerteza_k2"] is None and dh["situacao_incerteza"] != "completo"
    assert dh["faltam_na_incerteza"]
    html = gerar_html(j)
    assert "±0,0" not in html and "± 0,0" not in html


# ---------------------------------------------------------------- A4 · zero não quebra


def test_a4_consumo_zero_bloqueia_sem_falhar():
    pacote, lim = montar([Periodo(G01, dias=3)])
    comb = pacote.importacoes["combustivel"].dados
    ini, fim = lim[0]
    no_periodo = (comb["tipo"] == "recebimento") & (comb["data"] > ini) & (comb["data"] <= fim)
    comb = comb[~no_periodo].copy()
    estoque_ini = comb.loc[(comb["tipo"] == "estoque") & (comb["data"] == ini), "massa_kg_calc"]
    comb.loc[(comb["tipo"] == "estoque") & (comb["data"] == fim), "massa_kg_calc"] = float(
        estoque_ini.iloc[0]
    )
    pacote.importacoes["combustivel"].dados = comb.reset_index(drop=True)
    r = resumir_periodo(pacote, ini, fim)
    assert r.combustivel_kg is None and "zero" in r.bloqueios["combustivel"].motivo
    assert not balanco_direto(r).disponivel


def test_a4_totalizador_parado_bloqueia_sem_falhar():
    pacote, lim = montar([Periodo(G01, dias=3), Periodo(G01, dias=3)])
    d = pacote.importacoes["diario"].dados
    ini, fim = lim[1]
    sel = (d["instante_observado"] >= ini) & (d["instante_observado"] <= fim)
    d.loc[sel, "totalizador_vapor_t"] = float(d.loc[sel, "totalizador_vapor_t"].iloc[0])
    r = resumir_periodo(pacote, ini, fim)
    assert r.vapor_t is None and "não avançou" in r.bloqueios["vapor"].motivo
    b = balanco_direto(r)
    assert not b.disponivel and b.consumo_t_por_t is None
    j = investigar(pacote, lim[0], lim[1])  # não pode falhar
    assert j["conclusao"]["abstencao"] is True


# ---------------------------------------------------------------- A5 · O₂ fora do domínio


def test_a5_o2_umido_fora_do_dominio_e_recusado():
    """20,9% úmido exigiria λ acima do limite da busca; a versão examinada devolvia a borda
    (20,58% seco, menor que o úmido — impossível)."""
    with pytest.raises(AnaliseBloqueada, match="λ"):
        o2_seco_equivalente(20.9, COMPOSICAO_REFERENCIA, 0.40)


@pytest.mark.parametrize("w", [0.10, 0.30, 0.50, 0.60])
@pytest.mark.parametrize("o2", [0.5, 4, 8, 12, 16, 18])
def test_a5_o2_seco_nunca_menor_que_o_umido(o2, w):
    assert o2_seco_equivalente(o2, COMPOSICAO_REFERENCIA, w) >= o2


# ---------------------------------------------------------------- A6 · ponto físico dos gases


def test_a6_dois_pontos_de_gases_no_mesmo_periodo_bloqueiam_o_indireto():
    """Temperaturas/O₂ de pontos diferentes não podem virar uma média física única."""
    pacote, lim = montar([Periodo(G01, dias=3)])
    diario = pacote.importacoes["diario"].dados
    ini, fim = lim[0]
    sel = (diario["instante_observado"] >= ini) & (diario["instante_observado"] < fim)
    idx = diario.index[sel]
    metade = len(idx) // 2
    diario.loc[idx[:metade], "ponto_gases_id"] = "SAIDA-CALDEIRA"
    diario.loc[idx[metade:], "ponto_gases_id"] = "POS-ECONOMIZADOR"

    r = resumir_periodo(pacote, ini, fim)
    assert "ponto_gases" in r.bloqueios
    assert "mais de um ponto" in r.bloqueios["ponto_gases"].motivo
    i = indireto_periodo(r, p_gases=1.01325)
    assert i.resultado is None and i.bloqueio is not None
    assert "ponto" in i.bloqueio.motivo


def test_a6_um_unico_ponto_de_gases_preserva_o_calculo():
    pacote, lim = montar([Periodo(G01, dias=3)])
    diario = pacote.importacoes["diario"].dados
    ini, fim = lim[0]
    sel = (diario["instante_observado"] >= ini) & (diario["instante_observado"] < fim)
    diario.loc[sel, "ponto_gases_id"] = "SAIDA-CALDEIRA"

    r = resumir_periodo(pacote, ini, fim)
    assert r.ponto_gases_id == "SAIDA-CALDEIRA"
    assert "ponto_gases" not in r.bloqueios
    assert indireto_periodo(r, p_gases=1.01325).resultado is not None


def test_a6_dois_analisadores_de_o2_no_mesmo_periodo_nao_viram_um_so():
    """A média de O₂ não pode herdar a incerteza de apenas um de dois analisadores."""
    pacote, lim = montar([Periodo(G01, dias=3)])
    diario = pacote.importacoes["diario"].dados
    ini, fim = lim[0]
    sel = (diario["instante_observado"] >= ini) & (diario["instante_observado"] < fim)
    idx = diario.index[sel]
    metade = len(idx) // 2
    diario.loc[idx[:metade], "instrumento_o2_id"] = "ANALIS-A"
    diario.loc[idx[metade:], "instrumento_o2_id"] = "ANALIS-B"

    r = resumir_periodo(pacote, ini, fim)
    assert "instrumento_o2" in r.bloqueios
    i = indireto_periodo(r, p_gases=1.01325)
    assert i.resultado is None and "analisador" in i.bloqueio.motivo


def test_a6_o2_nao_e_rotulado_como_causa_unica_de_excesso_de_ar():
    pacote, lim = montar([Periodo(G01), Periodo(G01, o2_seco_pct=10.5)])
    j = investigar(pacote, lim[0], lim[1])
    h = next(x for x in j["hipoteses"] if x["id"] == "excesso_ar")
    texto = " ".join(str(h.get(k, "")) for k in ("titulo", "porque", "verificacao", "evidencia"))
    texto = texto.lower()
    assert "dilui" in texto or "ar falso" in texto
    assert "não separa" in texto or "nao separa" in texto


# ---------------------------------------------------------------- relatório: quatro estados


def test_relatorio_distingue_os_quatro_estados_de_deteccao():
    textos = {
        nivel: mudou_detectavel({"variacao": 1.0, "detectabilidade": nivel})
        for nivel in ("sim", "condicional", "nao", None)
    }
    assert len(set(textos.values())) == 4
    assert textos["sim"] == "sim"
    assert "repetir" in textos["condicional"]
    assert "incerteza" in textos[None]


def test_a3_explicacao_condicional_aponta_o_que_falta_cadastrar():
    """Degrau de umidade 30% → 45% sem a incerteza do método de umidade: a mudança da
    umidade é só 'condicional'. A EULER não a usa como explicação, mas mostra que ela
    fecharia a mudança SE confirmada, e a próxima verificação é cadastrar o que falta."""
    sem_estufa = tuple(c for c in INSTRUMENTOS_SINTETICOS if c != "ESTUFA")
    pacote, lim = montar(
        [Periodo(11.0, umidade=0.30), Periodo(12.981, umidade=0.50)], instrumentos=sem_estufa
    )
    j = investigar(pacote, lim[0], lim[1])
    w = next(h for h in j["hipoteses"] if h["id"] == "umidade_combustivel")
    assert w["avaliacao"]["mudanca_detectavel"] == "condicional" and w["status"] == "possivel"
    f = j["o_que_mudou"]["fechamento"]
    assert f["veredito"] == "sobra" and f["veredito_com_condicionais"] == "fecha"
    assert j["conclusao"]["abstencao"] and "não está confirmada" in j["conclusao"]["motivo"]
    partes = j["conclusao"]["texto"].split("Mesmo assim")
    assert len(partes) == 1 or "mais úmido" not in partes[1]  # não é mudança confirmada
    assert j["proxima_verificacao"]["acao"].startswith("Registrar no cadastro de instrumentos")
    assert j["proxima_verificacao"]["separa"] == ["umidade_combustivel"]
