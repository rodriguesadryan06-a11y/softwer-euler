"""Fluxo completo do caso de demonstração (T15 + T18), como um usuário faria.

Aceite do T15: fluxo completo em menos de 5 minutos, sem ajuda. Aqui medimos o tempo
de processamento do app (o tempo humano de leitura fica no roteiro do vídeo).
"""

import time
from pathlib import Path

from streamlit.testing.v1 import AppTest
from test_app import intervalo_escolhido

from euler.textos import RODAPE_SEGURANCA

APP = Path(__file__).resolve().parents[1] / "app" / "main.py"


def _rodape_ok(at: AppTest) -> bool:
    return any(c.value == RODAPE_SEGURANCA for c in at.caption)


def test_fluxo_completo_do_caso_de_demonstracao():
    inicio = time.perf_counter()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    # Início (navegação simplificada): o ato 2 fica em "Sobre a demonstração e os limites"
    at.button(key="ato2").click().run()
    assert not at.exception, at.exception
    # o botão leva à Saúde da caldeira (D65): o consumo das semanas de setembro mudou
    assert any("Mudança detectada" in m.value for m in at.markdown)
    assert {m.label: m.value for m in at.metric}["Período em destaque"] == "353,2 kg/t de vapor"
    assert any("31/08 a 14/09" in c.value for c in at.caption)
    assert _rodape_ok(at)

    # "Investigar esta mudança" abre a Investigação com os períodos já escolhidos. O AppTest
    # não acompanha st.switch_page entre execuções: a página atual é fixada antes do clique.
    at.switch_page("paginas/saude.py").run()
    at.button(key="investigar_mudanca").click().run()
    assert not at.exception, at.exception
    assert intervalo_escolhido(at, "ref") == (0, 3)
    assert intervalo_escolhido(at, "comp") == (4, 5)
    # auditoria A3: abstenção com o que cadastrar (antes: "Explicações compatíveis")
    assert any("Não dá para concluir" in w.value for w in at.warning)
    assert _rodape_ok(at)

    # Além da incerteza, as novas extensões purga/UA não têm medições no demo.
    at.switch_page("paginas/limites.py").run()
    assert not at.exception, at.exception
    assert {m.label: m.value for m in at.metric}.get("Bloqueadas") == "3"

    at.switch_page("paginas/extrato.py").run()
    assert not at.exception, at.exception
    assert any(i.value.startswith("F3 tem o menor preço") for i in at.info)

    at.switch_page("paginas/relatorio.py").run()
    next(b for b in at.button if b.label == "Gerar relatório").click().run()
    assert not at.exception, at.exception
    assert _rodape_ok(at)

    assert time.perf_counter() - inicio < 60


def test_ato_1_caso_completo_conclui():
    """Ato 1 (D62): os mesmos registros, com a incerteza de todos os instrumentos cadastrada.
    A investigação principal conclui; purga/UA continuam sem as medições opcionais."""
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.button(key="ato1").click().run()  # "Explorar demonstração" no Início
    assert not at.exception, at.exception
    at.switch_page("paginas/limites.py").run()
    assert {m.label: m.value for m in at.metric}.get("Bloqueadas") == "2"
    at.switch_page("paginas/investigacao.py").run()
    assert not at.exception, at.exception
    assert not any("Não dá para concluir" in w.value for w in at.warning)
    assert any("combustível mais úmido" in s.value for s in at.success)
    assert _rodape_ok(at)
