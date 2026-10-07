"""Medição de escala (D109): cinco clientes sintéticos do primeiro envio ao segundo fechamento.

Roda o mesmo caminho das telas para cada formato de planilha e verifica o que foi contado:
ajustes à mão, confirmações, registro de atendimento e a mesma conta para os mesmos dados.
O tempo de máquina é medido e só aparece no relatório (sem limite de tempo nos testes).
"""

import pytest

from scripts.medir_escala import CENARIOS, carregar_demo, medir, relatorio

# Ajustes à mão contados em 07/10/2026 (ver docs/produto/escala_atendimento.md).
AJUSTES_PRIMEIRO = {"modelo": 0, "fabrica": 0, "mensal": 0, "supervisorio": 7, "abreviacoes": 24}
# Mês seguinte: o mapeamento salvo é reaproveitado; unidades sem nome no cabeçalho e o tipo
# de abas "Plan2/Plan3" voltam a ser confirmados a cada envio (D109, proposta pendente).
AJUSTES_SEGUINTE = {"modelo": 0, "fabrica": 0, "mensal": 0, "supervisorio": 0, "abreviacoes": 12}


@pytest.fixture(scope="module")
def resultados(tmp_path_factory):
    dfs = carregar_demo()
    raiz = tmp_path_factory.mktemp("escala")
    return {c.chave: medir(c, raiz / c.chave, dfs) for c in CENARIOS}


def test_todo_cliente_chega_ao_primeiro_e_ao_segundo_fechamento(resultados):
    for r in resultados.values():
        assert r.primeiro.fechamento["fim"] <= r.seguinte.fechamento["inicio"]
        assert r.primeiro.contagem["novos"] > 0 and r.seguinte.contagem["novos"] > 0
        assert r.primeiro.contagem["conflitos"] == r.seguinte.contagem["conflitos"] == 0


def test_ajustes_a_mao_por_formato(resultados):
    assert {k: r.primeiro.ajustes for k, r in resultados.items()} == AJUSTES_PRIMEIRO
    assert {k: r.seguinte.ajustes for k, r in resultados.items()} == AJUSTES_SEGUINTE
    assert all(
        r.primeiro.confirmacoes == 5 and r.seguinte.confirmacoes == 4 for r in resultados.values()
    )


def test_mes_seguinte_nunca_custa_mais_que_o_primeiro(resultados):
    for r in resultados.values():
        assert r.seguinte.ajustes <= r.primeiro.ajustes


def test_mesmos_dados_dao_a_mesma_conta_em_qualquer_formato(resultados):
    """Conversões da importação (kgf/cm², t, %, Data + Hora) não mudam o consumo."""
    base = resultados["modelo"]
    for r in resultados.values():
        assert r.primeiro.fechamento["consumo_t_t"] == pytest.approx(
            base.primeiro.fechamento["consumo_t_t"], rel=1e-9
        )
        assert r.seguinte.fechamento["consumo_t_t"] == pytest.approx(
            base.seguinte.fechamento["consumo_t_t"], rel=1e-9
        )


def test_sem_pci_do_laboratorio_o_efeito_da_qualidade_fica_ausente(resultados):
    """Achado da medição: sem PCI, a conta não separa o efeito do combustível (fica None,
    nunca zero) e a situação muda; ver a pergunta registrada em D109."""
    assert resultados["fabrica"].primeiro.fechamento["efeito_qualidade_pct"] is not None
    assert resultados["abreviacoes"].primeiro.fechamento["efeito_qualidade_pct"] is None


def test_registro_de_atendimento_do_cliente(resultados):
    for r in resultados.values():
        reg = r.registro
        assert reg["envios_ate_fechamento"] == 1
        assert reg["primeiro_fechamento"] is not None
        assert reg["horas_ate_primeiro_fechamento"] >= 0
        # simulação: sem tempo de tela medido, nada vira zero
        assert reg["segundos_na_tela"] is None and reg["envios_sem_medicao"] == 1
        assert reg["ajustes"] == r.primeiro.ajustes


def test_relatorio_separa_medido_contado_e_assumido(resultados):
    texto = relatorio(list(resultados.values()))
    assert "**medido**" in texto and "**contados**" in texto and "**assumido**" in texto
    assert "Não é medição" in texto
    for c in CENARIOS:
        assert c.nome in texto
