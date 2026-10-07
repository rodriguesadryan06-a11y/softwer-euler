# Abas e escolha de datas — 07/10/2026

A versão principal 0c90f68 ainda usava espaçamento superior menor que o cabeçalho
fixo transparente. A barra cobria a faixa das abas e interceptava cliques. O
conteúdo agora começa abaixo do cabeçalho, também em telas estreitas.

Na Investigação, os dois controles de arrastar foram substituídos por seletores
de início e fim para referência e comparação. Cada opção mostra data completa e
horário e continua correspondendo a uma medição de estoque. Se um novo início
ultrapassar o fim atual, o fim passa para a primeira medição seguinte com aviso
explícito. Períodos sobrepostos continuam bloqueados.

A escolha permanece no mesmo contrato persistido (`periodos_escolhidos`):
assinatura dos dados e pares de índices. Os controles são limpos ao trocar dados
ou ao abrir uma mudança pela Saúde da caldeira. Escolhas salvas inválidas não
geram controles fora dos limites. Não há alteração de cálculo ou de golden.

Os testes de interface existentes foram adaptados à interação por seletores,
mantendo as expectativas numéricas, de abstenção, de relatório e de navegação.
Novos testes cobrem mudança de datas, reabertura, sobreposição, troca de dados e
índices inválidos. A verificação visual no navegador não foi realizada nesta
correção porque a ferramenta de navegador bloqueou o acesso à prévia local.

Validação: 77 testes passaram em `test_periodos_investigacao_ui.py`, `test_app.py`,
`test_fluxo_demo.py`, `test_navegacao_simples.py`, `test_interface_saude.py` e
`test_armazenamento_app.py`. Ruff check e format de todo o repositório passaram.
O servidor local respondeu HTTP 200 no endpoint de saúde.
