# PROGRESSO da construção

## 06/10/2026 — Importação guiada e financeiro por planta

CSV e Excel com associação explícita de colunas/unidades, prévia vinculada ao conteúdo e
preservação dos arquivos originais. Financeiro separa compras, estoques e consumo; permite
consultar fechamentos salvos por planta, equipamento e período. Explicações respeitam a
política de preço registrada, sem converter desvio automaticamente em economia.
Ver [implementação, uso e limites](importacao_financeiro_2026-10-06.md).

Validação: **215 testes distintos selecionados passaram**, incluindo golden, importação,
conta, fechamento, armazém, navegação, linguagem e telas. Foram 131 testes na integração,
15 na importação, 80 na regressão e repetições pontuais após ajustes. Um teste de navegação
atingiu 30 s com execuções simultâneas; passou isolado, sem alterar timeout ou expectativas.
Ruff e formatação aprovados no repositório. Nenhum golden ou tolerância alterado.

Financeiro conferido no navegador, com demonstração sintética e caminho sem fechamento;
um problema visual com o símbolo R$ foi corrigido. Formulário de importação conferido
visualmente, e envio/confirmação testados por AppTest; o seletor de arquivos do navegador
automatizado não respondeu, portanto esse clique nativo permanece sem verificação manual.
Os testes de regressão selecionados não equivalem à execução local da suíte inteira.

## 05/10/2026 - Navegação simplificada e hipótese de assinatura

Pedido de Adryan: menos abas e texto, mais clareza para uso recorrente. Menu com seis entradas
principais, mantendo as 17 rotas; início curto, investigação e financeiro com detalhes recolhidos,
painel com três prioridades. Motor, dados e critérios científicos preservados. **59 testes de
interface e acompanhamento passaram**, além de Ruff nos arquivos alterados. Revisão visual e
responsiva manual pendente por bloqueio do navegador integrado; prévia estática não regenerada.
Ver [registro da implementação](interface_recorrencia_2026-10-05.md) e
[pesquisa da assinatura](../produto/assinatura_recorrente_2026-10-05.md).

| Etapa | Status | Data | O que funciona | Pendências |
|---|---|---|---|---|
| 0 · Preparar | concluída | 2026-10-01 | 17 arquivos da Parte 3 criados idênticos ao arquivo mestre (conferido por script); `.venv` com Python 3.11; dependências instaladas (`pip install -e ".[dev]"`); `pytest -q` → testes golden *skipped*; `ruff check .` sem erros. Checagem extra: `lab/referencia_perda_gases.py` e IAPWS reproduzem todos os valores golden (G01–G12, V01, P01–P05). | Spec v0.3 não está no repositório (citada por T02, T11, T12, T13): pedir ao Adryan antes da Etapa 3. |
| 1 · Fundação | concluída | 2026-10-01 | App abre com a tela inicial e o rodapé de segurança (texto único em `euler/textos.py`, testado contra `docs/produto/visao_produto.md`). CI no GitHub Actions (ruff + pytest), modelo de PR, README, script de prints (`scripts/prints.py`). | — |
| 2 · Física | concluída | 2026-10-01 | `euler/vapor.py` (IF97, E8), `euler/indireto.py` (E1–E7, modo constante), `euler/combustivel.py` (E5, E9, E10). **18 testes golden passando** (G01–G12, V01, P01–P05). Página "Calculadora de referência" com perda, λ, PCI úmido, sensibilidades e aviso de simulação; bloqueia com motivo fora do domínio (ex.: abaixo do orvalho). | Modo cp variável aguarda fonte de cp(T) do revisor (D08). Decisões D05–D11 aguardam aprovação. |
| 3 · Entrada de dados | concluída | 2026-10-01 | Contrato de dados em `euler/io/esquemas.py`, que gera `docs/dados/contrato_dados.md` e `templates/planilha_modelo_euler.xlsx` (`python scripts/gerar_modelos.py`). Importadores de todas as tabelas (CSV com `,` ou `;`, vírgula decimal, codificação Windows, planilha .xlsx). Avisos com linha e motivo: lacunas, duplicatas, totalizador reiniciado, registro tardio, unidades suspeitas, volume sem densidade, relações entre tabelas. Tela "Importar dados" com exemplo de problemas em `demo/qualidade/`. | Registro de correções manuais (original, novo valor, motivo, autor, data) ainda não existe: hoje nada é corrigido. Decisões D12–D18 aguardam aprovação. |
| 4 · Extrato por fornecedor | concluída | 2026-10-01 | `extrato_por_fornecedor` (E11): energia e R$/GJ por lote e fornecedor, origem de cada dado, ranking por energia × por tonelada, alerta neutro de umidade fora da faixa histórica, "energia não determinada" sem umidade medida. Reproduz a tabela F1–F3 do documento. Tela "Extrato por fornecedor" com gráficos (preço/t × custo/GJ; umidade por semana). **Dados do caso de demonstração (T18) adiantados:** `demo/caso_demo/` + `demo/gerar_caso_demo.py`, botão "Caso de demonstração" na importação. | Decisões D19–D21 aguardam aprovação. Roteiro do vídeo fica para a Etapa 7. |
| 5 · Investigação | concluída | 2026-10-01 | `periodos.py` (resumo entre medições de estoque), `direto.py` (T10: eficiência com intervalo, E13 testado), `deteccao.py` (mudança detectável), `investigacao.py` (T13: JSON com o que mudou, hipóteses, independência E12, o que falta, próxima verificação, abstenção, valor em jogo só com base, custo E14), `capacidades.py` (T11, 11 análises). Testes: casos A, B, C, contraexemplo da purga e semana sem vapor. Telas "Dados e limites" (com período a período) e "Investigação" (5 blocos, gráfico e JSON). | T12 (detecção de degrau) não feito (extra). Decisões D22–D32 aguardam aprovação; formato do JSON e tabela de capacidades a conferir com a spec v0.3. |
| 6 · Relatório | concluída | 2026-10-01 | `euler/relatorio.py`: JSON → HTML com os 5 blocos fixos, rodapé de segurança, selo "dados sintéticos", pronto para A4; PDF pelo Chromium quando disponível. Teste com lista de verbos proibidos (e trava no app). Tela "Relatório" com botão "Gerar relatório", prévia e downloads. **3 exemplos em `docs/exemplos_relatorio/`** (HTML + PDF) com guia de revisão. | **Adryan: revisar o texto dos 3 exemplos.** Decisões D33–D34. |
| 7 · Demonstração | concluída (falta só o ensaio e a narração, que dependem de pessoas) | 2026-10-01 | Caso sintético completo (`demo/caso_demo/`, D53: dados **mantidos**, abstenção preservada); fluxo inteiro no app em menos de 5 minutos; revisão de uso como usuário novo com 5 falhas reais corrigidas e testadas (resultado antigo nunca aparece com dados novos); 8 prints (`prints/`); vídeo **rascunho sem narração** de 2 min (`demo/video/rascunho_video_demo.mp4`) com o texto da narração em `docs/demonstracao/ROTEIRO_VIDEO.md`; guia de cliques da apresentação ao vivo (`docs/demonstracao/GUIA_DEMONSTRACAO_AO_VIVO.md`). | Adryan: gravar a narração; ensaiar no notebook da apresentação (ver seção abaixo). |
| 8 · Entrega aos devs | concluída (repositório já privado; falta a autoria/registro, decisão do Adryan) | 2026-10-01 | `docs/historico/ENTREGA_2026-10-01.md` (instalação, organização, o que funciona, experimental, limitações, revisão crítica do código, decisões pendentes, casos, prioridades até 30/10); README reescrito; `requirements-lock.txt`; instalação do zero conferida; PDFs para os revisores em `docs/revisao/` (física E1–E15 e as três decisões prioritárias + Q1–Q17). | **Repositório ainda público** → Adryan torna privado. T19 (tag e autoria para o INPI) → Adryan. T17 fica fora deste repositório. |

## Fase R · Revisão e validação do motor físico (pedido do Adryan em 01/10/2026)

| Item | Implementação | Aprovação científica | Onde ver |
|---|---|---|---|
| Diagnóstico (matriz de 28 cálculos, erros ER-1 a ER-9) | **concluída** | não se aplica | `docs/fisica/revisao_motor_fisico.md` §1 |
| Correções dos erros demonstráveis | **concluída** (ER-1 a ER-9) | **pendente** (revisor) | §4 do mesmo documento |
| Novas funções experimentais (cp(T) NASA, umidade do ar, CO, O₂ úmido) | **concluída**, marcada como experimental | **pendente** (Q2–Q4, Q10) | `euler/indireto.py`, `euler/propriedades_gases.py` |
| Incerteza por componentes (GUM) e correlação entre períodos | **concluída** | **pendente** (Q8, Q11, Q12, Q16) | `euler/incerteza.py` |
| Recebido × queimado (cenários do pátio) | **concluída** | **pendente** (Q7) | `euler/periodos.py` |
| Regras da investigação (vocabulário, `oposta`, fechamento) | **concluída** | **pendente** (Q9, Q17) | `euler/investigacao.py` |
| Verificação | **concluída**, mas a auditoria mostrou que "53 verificações independentes" era um resumo errado; reclassificada em categorias (ver revisão de confiabilidade) | não se aplica: verificar ≠ aprovar | `docs/fisica/matriz_validacao_fisica.md` |
| Comparação com caldeira real | **não feita** (sem dados reais no repositório) | — | matriz, P-4 |
| Perguntas aos revisores | **prontas** (Q1–Q17) | aguardando respostas | `docs/fisica/perguntas_revisores.md` |
| Decisões | D35–D50 propostas; D08, D24 e D26 substituídas | **todas pendentes** | `docs/gestao/decisoes.md` |

**Situação:** a implementação da Fase R está concluída e verificada; **nenhum item tem
aprovação científica**. Testes passando mostram que o código faz o que foi especificado, não
que a especificação esteja certa.

- Versão examinada no diagnóstico: `97ad0c6`. Versão final da fase: `01c2a4b`.
- `pytest -q`: 243 testes passando; `ruff check .` e `ruff format --check .` sem erros;
  `tests/golden/` e tolerâncias sem alteração.
- Sites bloqueados na sessão (para liberar na rede do ambiente, se quiser que a próxima
  sessão confira as fontes originais): `www.iapws.org`, `webbook.nist.gov`, `janaf.nist.gov`,
  `www.bipm.org`.
- Print `05_dados_e_limites` refeito (tabela com as colunas do pátio).

## Revisão de confiabilidade (auditoria externa de 01/10/2026)

Auditoria técnica externa da versão `2cd4dc3` (não é aprovação científica). Escopo fechado:
corrigir A1–A5, reclassificar as verificações e corrigir as referências, sem mexer nos
golden nem nos dados do demo.

| Item | Implementação | Aprovação científica | Onde ver |
|---|---|---|---|
| A1 · FIFO com massa sem qualidade conhecida | **corrigido**: FIFO indisponível com motivo; hipóteses dos cenários declaradas | **pendente** (decisão 1) | D51; V-C10, V-C11 |
| A2 · umidade duas vezes no resíduo | **corrigido**: cada fonte uma vez, conferido perturbando os dados pela cadeia inteira | **pendente** (decisão 3) | D54; V-D7, V-D8 |
| A3 · incerteza ausente virando zero | **corrigido**: orçamento completo / parcial / indisponível; nunca "sim" com orçamento incompleto | **pendente** (decisão 3) | D52; V-D9, V-D10, V-E6 |
| A4 · divisão por zero (consumo ou vapor zero) | **corrigido**: bloqueio com motivo | não se aplica | D56; V-C12, V-C13 |
| A5 · O₂ úmido fora do domínio | **corrigido**: recusa com motivo | não se aplica | D56; V-B16, V-B17 |
| Relatório: quatro estados da detecção | **corrigido** (relatório e tela) | não se aplica | V-E7 |
| Tela sem as hipóteses `oposta` (achado desta revisão) | **corrigido** | não se aplica | V-E8 |
| PCI seco e dispersão de Δh no orçamento | **implementado** | **pendente** | D55, D57 |
| Matriz reclassificada (57 linhas, 4 categorias + consistência, regressão, golden); 18 pontos reservados IF97 × IAPWS-95 | **concluída** | não se aplica | `docs/fisica/matriz_validacao_fisica.md` |
| Referências corrigidas (GUM 4.3.7 como hipótese do projeto; CODATA × JANAF; IAPWS conferido pela auditoria) | **concluída** | — | `docs/fisica/revisao_motor_fisico.md` §2 e §7 |
| Pauta de revisão humana: três decisões prioritárias + Q1–Q17 | **pronta** | aguardando reunião | `docs/fisica/perguntas_revisores.md` |
| Demo: história mudou (umidade só condicional, abstenção) sem alterar dados | **feito**; gabarito, exemplos de relatório, roteiro e prints 05/06 atualizados | — | D53 (**decisão do Adryan**) |
| Comparação externa e piloto com dados autorizados | **não feita** | — | matriz, P-4 e P-7 |

- Versão examinada pela auditoria: `2cd4dc3`. Versão desta revisão: `b124c76`.
- `pytest -q`: 299 testes passando; `ruff check .` e `ruff format --check .` sem erros;
  `tests/golden/` e `lab/` sem alteração.

**Próximo passo:** reunião com os revisores começando pelas três decisões prioritárias
(`docs/fisica/perguntas_revisores.md`); decisão do Adryan sobre o demo (D53). Depois: casos
reservados montados fora da lógica do motor e piloto com dados autorizados de uma caldeira.
Vídeo e prints 04 e 07 da Etapa 7 são apresentação do fluxo sintético, não evidência de
validação.

## Etapas 7 e 8 · demonstração de 30/10/2026 e entrega aos desenvolvedores

**Escopo fechado:** carregar dados → conferir qualidade e limites → investigar → consultar
fornecedores → gerar relatório. Login, várias empresas, OCR, API e novas funções físicas
ficam para fases posteriores. Dados do demo **não** foram alterados e nenhuma incerteza foi
acrescentada: o caso continua mostrando a EULER explicando por que não conclui (D53, decisão
do Adryan).

**Falhas de uso encontradas e corrigidas:** relatório usando a investigação dos dados
anteriores; escolha de períodos voltando ao padrão ao trocar de tela; relatório sumindo
depois de baixar; barra lateral com a origem errada dos dados (estas quatro com teste em
`tests/test_app.py`); PDF do relatório com páginas quase vazias (conferido à mão: 4
páginas). Textos: plural, unidades, nome do arquivo
nos avisos, motivo quando o valor em jogo não é estimado, selo **DADOS SINTÉTICOS** em todas
as telas e no relatório, quadro "Em que pé está a EULER" (verificado · em revisão · não feito).

| Tipo de evidência | O que foi feito | Resultado |
|---|---|---|
| **Testes automáticos** | `pytest -q` (inclui telas pelo AppTest, fluxo completo do demo, verbos proibidos, golden) e `ruff check .` / `ruff format --check .` | 308 passando; lint sem erros; `tests/golden/` e tolerâncias sem alteração |
| **Instalação do zero** | ambiente novo, só `pip install -e ".[dev]"` | 275 passando, 33 pulados (CoolProp/Cantera, extra `validacao`) |
| **Conferência manual (navegador real)** | fluxo inteiro como usuário novo: demonstração, avisos, análises bloqueadas, troca de períodos, extrato, relatório, baixar HTML e PDF, trocar os arquivos depois, ir e voltar entre telas | sem resultado antigo nos dados novos; PDF baixado (4 páginas A4) |
| **Conferência manual (materiais)** | 8 prints, quadros do vídeo em cada cena, PDF do relatório, PDFs dos revisores (5 e 7 páginas) | legíveis em 1280 px, 1280 × 720 e A4 |
| **Depende do notebook da apresentação** | ensaio com o guia ao vivo; Chromium para o botão "Baixar PDF" (ou plano B com HTML); zoom no projetor; Windows não testado | **a fazer** (Adryan + 1 dev) |
| **Depende de pessoas** | narração do vídeo (rascunho atual não tem som); revisão do texto dos exemplos de relatório | **a fazer** (Adryan) |
| **Revisão humana e validação externa** | três decisões prioritárias + Q1–Q17 (`docs/revisao/`); golden; piloto com dados reais autorizados; T17 em repositório separado | **pendentes**: nenhuma proposta foi marcada como aprovada sem resposta humana |

- Versão examinada nesta etapa: `e49338d` (a mesma da capa dos PDFs de
  `docs/revisao/` e do `docs/historico/ENTREGA_2026-10-01.md`).
- Repositório **privado** (conferido no GitHub em 01/10/2026, rodada de melhorias).

**Próximo passo até 30/10:** (1) Adryan define a autoria e o registro da versão (T19); (2) ensaio no notebook
da apresentação seguindo `docs/demonstracao/GUIA_DEMONSTRACAO_AO_VIVO.md`, duas vezes seguidas sem ajuda;
(3) narração gravada sobre o rascunho do vídeo; (4) enviar `docs/revisao/` aos revisores.
Detalhes e responsáveis: `docs/historico/ENTREGA_2026-10-01.md` §9.

## Visual do app (pedido do Adryan em 01/10/2026, depois da conferência no Windows)

O Codex abriu a EULER no computador do Adryan (cópia sem Git; PDF direto indisponível por
falta do Chromium). Pedido: conhecer o app e deixá-lo mais profissional, organizado e com
cara de aplicativo, **sem mexer em cálculos, demo, incertezas nem resultados inconclusivos**.

| Item | O que mudou | Situação |
|---|---|---|
| Identidade EULER | logo e marca (um "E" de barras sobre ferrugem), barra lateral azul-marinho, tema e cartões; faixa de abertura na tela inicial | **feito**; D58 **proposta pendente (Adryan)** |
| Organização | "Passo X de 5" e resumo no alto de cada tela; botão **Próximo** no fim; exemplos sintéticos em cartões; bloqueado antes do liberado em Dados e limites | **feito** |
| Investigação | resultado no topo (conclusão + próxima verificação lado a lado; consumo, valor em jogo e explicações em cartões); blocos 1–4 em abas; linha do tempo dos períodos; gráfico com escolha da grandeza; coluna **Diferença (± incerteza)**; selos para os quatro estados da detecção | **feito**; D59 **proposta pendente (Adryan)** |
| Relatório | botões lado a lado; **Imprimir ou salvar como PDF** na prévia (funciona sem Chromium) | **feito**; D60 **proposta pendente (Adryan)** |
| Falha encontrada | um texto interno aparecia na tela do Relatório (Streamlit mostra texto solto da página) | **corrigida**, com teste |
| Passeio escrito | `docs/demonstracao/PASSEIO_PELAS_TELAS.md` (onde clicar em cada tela + como atualizar a cópia do Windows) | **feito** |
| Guia ao vivo | `docs/demonstracao/GUIA_DEMONSTRACAO_AO_VIVO.md` refeito para o visual novo | **feito** |
| Prints e vídeo | não refeitos (pedido do Adryan: ele mesmo faz o vídeo); `prints/` mostra o visual anterior | — |

- Cálculos, JSON da investigação, relatório baixado, demo e `tests/golden/` **sem
  alteração**. Os números da tela continuam vindo do JSON.
- Evidências: testes de tela novos (resumo da Investigação, semana sem vapor sem número
  inventado, nenhum texto solto nas telas); conferência visual em navegador real de todas as
  telas; botão de impressão conferido (abre a impressão, some do papel).
- `pytest -q`: 311 passando; `ruff check .` e `ruff format --check .` sem erros.

## Acabamentos e tema escuro (pedidos do Adryan em 01/10/2026)

| Item | O que mudou | Situação |
|---|---|---|
| Visual D58–D60 | aprovado pelo Adryan | **aprovado** |
| Tema escuro e marca | fundo grafite, barra lateral mais escura, interface monocromática; marca "E" de traço fino, sem fundo cobre; relatório com a marca em tinta escura | **feito**; D61 **aprovada** (pedido do Adryan) |
| O que falta saber | dois grupos na tela: incertezas a cadastrar em instrumentos.csv e o que medir/registrar | **feito**, com teste |
| Envio de arquivos | "Escolher arquivos" em português | **feito** |
| Telas mais rápidas | investigação e período a período guardadas pela assinatura dos dados; mudar dados refaz a conta | **feito**, com teste |
| Telas sem dados | botão "Carregar o caso de demonstração" | **feito**, com teste |
| Extrato | tabela inteira, sem rolagem lateral; gráficos sem caixa a mais | **feito** |
| Windows | `ABRIR-EULER.cmd` dentro do projeto | **feito**, com teste |
| Código | formatação das telas em `app/formatacao.py` (sem Streamlit), usada também pela prévia | **feito** |

| Prévia interativa | página que abre na conversa, com o visual e as telas do app e os resultados do motor para o demo (`scripts/gerar_previa.py`) | **feito** |

- Cálculos, demo, incertezas e `tests/golden/` **sem alteração**.

## Rodada de melhorias (pedido do Adryan em 01/10/2026: sete itens, um commit por item)

| Item | O que mudou | Situação |
|---|---|---|
| 1 · Demonstração em dois atos | ato 1 (`demo/caso_demo_completo/`, todas as incertezas cadastradas: a EULER conclui) e ato 2 (o caso de antes: abstenção); botões nos dois na tela inicial; roteiro do vídeo | **feito** (`9c028e3`); D62 |
| 2 · Frase principal clara | resultado em até três frases no topo da Investigação e do relatório | **feito** (`b45f5a5`); D63 |
| 3 · Linguagem de fábrica | nenhum nome de arquivo, coluna ou código de equação fora de "Detalhes técnicos"; `tests/test_linguagem.py` percorre todas as telas e os relatórios | **feito** (`457711c`); D64 |
| 4 · Saúde da caldeira | tela nova logo depois de carregar os dados: consumo por t de vapor semana a semana, eventos, selo mudou / estável / não dá para dizer e **Investigar esta mudança**; menu com 6 passos | **feito** (`1bbeccc`); D65 (regras do selo: proposta pendente) |
| 5 · Dados e limites mais leve | tabela com período, eficiência, consumo por t de vapor e situação; o resto em "Ver detalhes de cada período" | **feito** (`fc081bc`); D66 |
| 6 · Conferir contra a especificação detalhada | o arquivo `EULER_ESPECIFICACAO_DETALHADA.md` ainda não está no repositório; retrato atual em `docs/desenvolvimento/conferencia_especificacao.md`; **nada mudado** | **aguardando o arquivo** |
| 7 · Decisões pendentes | `docs/fisica/resumo_decisoes_pendentes.md`: 10 decisões em 1 página (6 de física, 4 de produto), com recomendação | **feito** (`546da69`) |
| Prévia e guias | prévia interativa com os dois atos e as telas novas; passeio, guia ao vivo, roteiro, "Entenda a EULER", README e HANDOFF atualizados | **feito** |

- Cálculos físicos e `tests/golden/` **sem alteração**: o painel Saúde reaproveita o balanço
  direto e a regra de detecção da Investigação. Nenhuma proposta foi marcada como aprovada
  sem resposta humana.

**Modo de trabalho:** automático (pedido do Adryan em 01/10/2026): seguir as etapas sem esperar "ok"; decisões não especificadas vão para `docs/gestao/decisoes.md` como propostas pendentes.

## Notas da Etapa 0
- O arquivo mestre foi copiado para a raiz (`docs/historico/PLANO_ORIGINAL.md`) para que "continue" funcione em sessões novas.
- `pyproject.toml` mínimo criado já na Etapa 0 (necessário para instalar dependências). A Etapa 1 (T01) completa com CI e modelo de PR.
- Ruff ignora `lab/` (calculadora de referência copiada como veio, não é código do produto); `ruff format` não toca em `tests/golden/`.
- Ambiente na nuvem: o endereço `localhost:8501` não abre no computador do Adryan. Nas etapas com tela, mostrar prints (Playwright) enviados na conversa.


## Revisão física adicional · 02/10/2026

Pedido do Adryan: revisar o motor diretamente no repositório, corrigir problemas de fronteira
física identificados na leitura do código e revisar cada mudança antes de integrar.

| Item | O que mudou | Situação |
|---|---|---|
| Identidade do ponto de gases (D67) | o caminho indireto não mistura, no mesmo período, leituras identificadas em pontos físicos diferentes; o ponto usado fica explícito no JSON | **feito e testado** |
| Identidade do analisador de O₂ (D67) | se o período contém O₂ de mais de um analisador, a EULER não atribui a média à incerteza de um instrumento escolhido por moda; a análise indireta se abstém com motivo | **feito e testado** |
| Interpretação de O₂ (D67) | título passou de “mais excesso de ar” para “O₂ maior nos gases”; o texto explica que O₂ sozinho não separa excesso de ar na combustão de entrada de ar falso e indica comparação no mesmo ponto / montante-jusante | **feito e testado** |
| Estado do vapor (D68) | a hipótese atual do balanço direto — vapor saturado seco, x = 1 — passou a ser publicada estruturadamente no resultado/JSON, além do texto da fronteira | **feito e testado** |
| Escopo do produto | README e visão de produto deixaram de afirmar compatibilidade com “qualquer caldeira”; o domínio suportado passa a ser descrito como algo que cresce por validação | **feito** |
| Revisão automática | primeira rodada encontrou 2 problemas de lint; segunda encontrou 1 regressão textual; terceira encontrou o limite de 220 caracteres do resumo. Todos foram corrigidos antes da integração | **feito** |
| CI final | `ruff check .`, `ruff format --check .` e `pytest -q` com extras de validação | **342 testes passando; lint/format sem erros** |

**Não foi alterado:** `tests/golden/`, dados do demo, equações de referência, critérios de
incerteza ou números usados na demonstração.

**Continua pendente para tickets próprios, porque exige ampliar contrato de dados e validação
humana:** usar vapor superaquecido/título medido no caminho principal; normalização por carga
e baseline multivariável; tratamento explícito de regimes transitórios; quantificação de purga;
modelos de transferência/UA para fouling; primeiro ensaio com dados reais autorizados.

### Correção das contraprovas do motor — 02/10/2026

- D70: validar pressão, água de alimentação e temperatura/título do vapor úmido/superaquecido por leitura, antes das médias. Cobertura parcial, valores não finitos e estados incompatíveis bloqueiam energia e eficiência; incluir leituras de borda com massa positiva. Consumo específico preservado quando seus dados são suficientes.
- D71: pontos de gases diferentes entre períodos (ou identificado em apenas um) não geram comparação de desempenho, efeitos de gases ou resíduo dependente. Balanços individuais preservados; investigação explica o bloqueio.
- 14 testes novos em tests/test_regressao_fronteiras.py. Contraprovas inicialmente falharam; após correção, suíte completa: 360 passaram, nenhum pulado (344,39 s). Três avisos pandas provocados pelos valores infinitos dos testes de defesa, sem falha ou liberação indevida do cálculo. Ruff check e format aprovados (93 arquivos).
- Golden, tolerâncias, biblioteca de propriedades e fórmulas termodinâmicas não alterados. Não houve validação com planta. Revisão física humana pendente; ver docs/gestao/decisoes.md.

## Integração da versão completa — 02/10/2026

Esta seção atualiza o estado das extensões que apareciam como pendentes acima.

- Base preservada: `6402198` (vapor medido) e `35f2e7a` (correções da cobertura por leitura e da comparação entre pontos de gases).
- Novidades reunidas de `codex/round2-final` (`a54fc5c`), `codex/round2-physical-engine` (`2b87d2e`) e `gpt/transient-regimes` (`82fdded`): referência por carga, regime transiente, energia de purga e UA aparente do economizador. Integração seletiva, com compatibilidade e bloqueios revistos; não simples troca de branch.
- Contrato de importação, modelos CSV/Excel e JSON ampliados. Purga exige massa medida no intervalo, bordas e pressão própria. Economizador exige condições válidas em cada leitura e regime estável. Campos ausentes bloqueiam a extensão correspondente.
- Referência por carga disponível em Saúde; purga e economizador em Dados e limites. Hipóteses, cobertura e incertezas ainda não quantificadas ficam explícitas. Não se atribui causa ou ganho financeiro automaticamente.
- Inicializador Windows centralizado: evita servidores duplicados, identifica a instalação e reinicia o próprio servidor quando os arquivos mudam. CMD e atalhos apontam para a instalação `software-euler`. Abertura não executa atualização remota automática.
- Revisão estática independente concluída. Suíte completa: 378 passaram e 5 falharam na preparação das leituras artificiais (fusos misturados fora do contrato normalizado). Corrigida a preparação, os 11 testes de integração passaram, incluindo os 5 anteriores. Assim, os 383 testes foram cobertos sem falhas remanescentes; não houve nova execução integral após esse ajuste restrito aos testes. Ruff check/format aprovados (100 arquivos). Três avisos pandas são das entradas infinitas deliberadas nos testes de defesa.
- Golden e tolerâncias preservados. Decisões D72–D76 permanecem pendentes de revisão humana; sem validação em planta.

## Organização do repositório — 02/10/2026

- README principal reduzido a apresentação, primeiros passos e mapa das pastas.
- Documentação agrupada por produto, desenvolvimento, dados, física, gestão, demonstração e histórico; 17 documentos realocados com histórico Git preservado.
- Entrega antiga e plano original identificados como históricos; guia atual dos desenvolvedores criado. Dados sintéticos, modelos, scripts e capturas ganharam guias próprios.
- Caminhos de referência e geradores atualizados; mantido um redirecionamento documental para a referência antiga presente nos testes golden protegidos.
- Validação local: cinco testes de contrato/modelos/rodapé aprovados; 83 links locais verificados antes da nota dos PDFs; Ruff check e format aprovados. CI integral executado pelo GitHub no PR.
- Nenhuma equação, tolerância ou referência golden alterada. Estrutura de execução e CMD preservados.

## Reconciliação dos PRs do motor — 02/10/2026

Preservada a integração do PR #7 e a organização do PR #8. Incorporada a separação das pressões da purga e da água de referência do PR #5, com importação, bloqueio por leitura e testes. A revisão física humana permanece pendente (D77).

## Revisão crítica da camada de evidências — 04/10/2026

Pedido do Adryan: conferir a entrega `0fe589d`, corrigir contradições demonstráveis e avançar a referência operacional com validação temporal.

- **CI reativado.** Desde 03/10 a coleta do pytest falhava (`from app.financeiro`, `from diagnostico_publico`) e o CI parava antes de rodar os testes. Agora `pyproject.toml` declara `pythonpath = [".", "app"]`; `pytest -q` simples coleta tudo.
- **Contradições corrigidas (D87, commit `9c47df2`).** Robustez pública avalia o sinal antes da completude (B06, com faixas cruzando zero e auditoria incompleta, recebia nota acima de B10 fevereiro). Consistência temporal pública usa a retirada de um dia (B06 março muda de sinal: FRACA). Valorização no Diagnóstico segue a mesma regra do valor em jogo da Investigação (uma alta não confirmada aparecia como R$ 7.803 numa tela e "não estimado" na outra). Limiares publicados passam a ser os usados. Referência INSUFICIENTE não sugere "interpretar com cautela". Diagnóstico mostra 0,321 t/t (não 0,32). Resultado não escreve "o₂".
- **Referência operacional avaliada (D88).** A dimensão "Qualidade da referência" ficava sempre INSUFICIENTE na rota operacional. Agora é avaliada com a série da fábrica: um ponto por período entre medições de estoque, previsto = consumo específico da referência × vapor, último período validado pelos anteriores. Ato 1: FRACA (4 períodos, deriva de 2,85% entre metades, validação com 1,8%). Tela Diagnóstico ganhou "Como a referência foi avaliada", com a tabela período a período. `vapor_e_combustivel` (≈4× mais rápido que o resumo completo) evita recalcular a energia útil.
- **Caso público reproduzido antes e depois.** Energia, percentuais e valores condicionais idênticos nas 8 unidades/meses. B10 sem mudança: fevereiro +2,09% (robustez FRACA), março +2,96% (FORTE), referência MODERADA. Mudou só B06: robustez MODERADA → FRACA nos dois meses; consistência de março MODERADA → FRACA. Os identificadores de análise mudaram (o hash inclui o método).
- **Validação:** `pytest -q` → 487 passaram (eram 477; 10 testes novos); `ruff check .` e `ruff format --check .` limpos. Telas Diagnóstico e Investigação conferidas no navegador.
- **Fica de fora:** robustez e consistência temporal da rota operacional continuam INSUFICIENTE; limiares aplicados a períodos pendentes de revisão estatística; registro de intervenção e economia verificada não iniciados. Golden e tolerâncias intocados.

## Explicação da conta de combustível — 04/10/2026

Pedido do Adryan: estimar o impacto financeiro antes de conhecer a causa, separando "gastou mais" de "perdeu eficiência" (D89, E16).

- **Motor (`euler/conta.py`, ligado à investigação como `explicacao_conta`).** Quatro resultados: custo do combustível consumido, custo esperado nas mesmas condições, desvio ainda não explicado (estimativa central, faixa das medições e estado) e a verificação que pode identificar uma parcela evitável. A variação da conta contra a referência é decomposta em produção de vapor, condição do vapor e da água, qualidade do combustível, preço e desvio, e a soma fecha exatamente. Parcela sem dado fica misturada ao desvio, com o motivo; nada vira zero.
- **Tela Financeiro.** Frase do resultado primeiro, três cartões, "Parcela evitável: não apurada" com a próxima verificação, tabela "Por que a conta mudou", ponte com o valor em jogo da Investigação e premissas expansíveis (compra não é consumo; custo não é necessariamente caixa; frete só se estiver no preço; R$/GJ ao lado de R$/t). **O simulador "E se recuperarmos parte dessa diferença?" foi retirado**: multiplicava o desvio por um percentual escolhido.
- **Correção:** o preço por tonelada do período era calculado só quando os lotes tinham umidade e PCI medidos; sem laboratório, nada era valorizado. Agora depende só de massa e valor do lote.
- **Ato 1 (31/08–14/09 contra 03/08–31/08):** consumido R$ 293.167; esperado R$ 287.016; desvio não explicado R$ 6.151 (2,1%), faixa −R$ 3.473 a R$ 15.775: não ficou bem estabelecido. Dos R$ 26.992 de valor em jogo, R$ 20.818 vêm da umidade medida do combustível. O R$/t caiu e o R$/GJ subiu (combustível mais úmido).
- **Testes:** 19 novos em `tests/test_conta.py` (exemplo de 1.200 t × 1.100 t × R$ 350 = R$ 35.000; fechamento exato; parcela sem dado; estados; cenários do pátio que invertem o sinal; preço inválido; sem percentual de recuperação; casos A, B e C; preço sem umidade). `tests/test_financeiro.py` reescrito: os testes do simulador saíram com ele e entrou um teste da tela. Captura em `prints/09_financeiro_explicacao_conta.png`.
- **Fica de fora:** carga e regime no esperado (o baseline por carga, D73, é candidato); incerteza dos ajustes e do preço; parcela evitável por mecanismo (η atual/η alvo justificada); registro de intervenção e economia verificada; relatório e Diagnóstico ainda não mostram a explicação da conta; rota pública (B10) sem preço do combustível.

## Oportunidades: qual problema investigar primeiro — 04/10/2026

Pedido do Adryan: transformar o diagnóstico em prioridade de decisão sem passar do que os dados sustentam (D90).

- **O que já existia e foi reaproveitado:** hipóteses com efeito no consumo e situação (`euler/investigacao.py`), relevância D29, próxima verificação do motor, fechamento (soma dos efeitos × observado), rubrica ordinal de evidências (D86), explicação da conta (E16) e valor em jogo. Nenhum conceito foi duplicado.
- **Motor:** cada hipótese grava a incerteza do seu efeito (k = 2, pela mudança do indicador). `euler/oportunidades.py` produz, dentro da investigação (`oportunidades`), as oportunidades ordenadas, o resumo, os avisos de sobreposição, as regras (objetivas × propostas), a intervenção indisponível com motivo e a cadeia até a economia verificada.
- **Tela Oportunidades (menu Gestão):** resumo executivo, "Verificar primeiro", aviso para não somar, um cartão por oportunidade (impacto com faixa, evidência, complexidade da verificação, próxima verificação, o que ela distingue), as não priorizadas num expansor, a cadeia e "Como a priorização funciona". Projeção anual só com dias de operação informados. O Financeiro ganhou um atalho para a tela.
- **Ato 1:** 2 oportunidades em investigação, ambas de prioridade alta: umidade do combustível (R$ 20.818 no período, faixa R$ 5.608–36.912; verificação: amostragem de umidade do F3 e umidade do pátio) e temperatura dos gases (R$ 8.452, faixa R$ 7.575–9.332; verificação: termômetro de referência, sem parada). Total associado R$ 26.992 ± 9.624 (valor em jogo), não a soma.
- **Testes:** 17 novos em `tests/test_oportunidades.py` (sem nota nem pesos; impacto e faixa; verificação simples antes de impacto maior com verificação média; próxima do motor primeiro; enfraquecidas e sem base; nunca FORTE; ausente não vira zero; sem preço; sobreposição e resumo sem soma; complexidade não herdada; condição do vapor fora; intervenção indisponível; determinismo; projeção anual; casos A e ato 1; tela). Capturas em `prints/09_financeiro_explicacao_conta.png` e `prints/10_oportunidades.png`.
- **Fica de fora:** registro de verificações (necessário para "causa sustentada" e evidência FORTE), registro de intervenções (investimento, parada, payback), economia estimada/verificada, custo em reais de cada verificação, valor da informação quantitativo (sem base), oportunidades que o motor ainda não modela (retorno de condensado, isolamento).

## Uma única versão — 04/10/2026

Pedido do Adryan: manter só uma versão do software, sempre atualizada (D91).

- **Branches antigas conferidas, prontas para apagar.** Das 13, 7 não tinham nada fora da principal; as outras 6 tinham sido mescladas por PR com squash (#1, #2, #10), substituídas (#3 pelo #11, com o #9) ou integradas sem PR (`round2-reconciled`: todas as funções presentes na principal). Os dois únicos arquivos "ausentes" eram documentos movidos para `docs/historico/`. O histórico segue nos PRs do GitHub. A remoção foi bloqueada pela permissão do ambiente desta sessão: fica para o Adryan fazer em GitHub → Branches (ou autorizar a sessão).
- **Inicializador se atualiza.** `ABRIR-EULER.cmd` busca a versão principal a cada abertura, só por avanço rápido, e nunca descarta trabalho local (alteração não salva, commits próprios). A barra lateral mostra "Versão principal em dia", "atualizada a partir de…" ou o motivo de não ter atualizado. 5 testes novos com repositórios git reais (atualiza; preserva edição local; preserva commit divergente; troca de branch antiga integrada; sem git ou sem rede).


## Persistência local — 04/10/2026

- Integrada a principal do Claude até `e522b03` antes das alterações. Não havia banco publicado.
- SQLite por planta fora do Git, importações originais imutáveis, revisões com autoria/motivo, integridade, transações e backup/restauração.
- Nova página **Plantas e histórico**; importação como nova versão na planta ativa; investigações e períodos arquivados automaticamente depois de salvar o conjunto.
- Sessões novas reabrem os dados. Trocar planta, altitude ou motor impede reutilizar resultado incompatível. Carregar exemplos e limpar dados desvincula a sessão sem apagar o banco.
- Entrega, uso, API, validação e limites: [persistencia_local_2026-10-04.md](persistencia_local_2026-10-04.md).
- Ainda faltam perfis de colunas, diferenças por célula, conciliação incremental, referência aprovada independente, entidades de intervenção/fechamento e autenticação multiempresa. Nenhuma equação ou golden foi alterado.

## Conciliação do banco único — 04/10/2026

- Integrado o trabalho do Claude em `6e5dad9`, preservando armazém, fechamento,
  acompanhamento, painel e testes originais. Os limites da primeira entrega acima
  são históricos: a estrutura operacional está agora no mesmo banco dos arquivos.
- Esquema v2, migração dos dois formatos v1 no próprio arquivo e backup anterior;
  raiz comum, classes explícitas, originais ligados aos lotes e restauração integral.
- Tela **Acompanhamento**: equipamentos, prévia incremental, perfis de nomes,
  resolução de conflitos, série acumulada, referência e fechamentos.
- Reprodução congela configuração e preços históricos. Dados da referência alterados
  exigem nova versão. Política de preço consistente entre números do fechamento.
- Passagem para o Claude e limites atuais:
  [unificacao_banco_2026-10-04.md](unificacao_banco_2026-10-04.md).

## App reorganizado e telas de acompanhamento completas — 05/10/2026

Pedido do Adryan: "entrou muita coisa e ficou um pouco confuso usar" (D96).

- **Menu em três grupos, sempre aberto:** *Analisar um período* (as 8 telas da investigação de um período, sem a numeração "Passo X de 6"), *Acompanhar a planta* (Painel, Atualizar dados, Fechamentos, Investigações e ações, Plantas e histórico) e *Referência*. O Início mostra as duas formas de usar.
- **Atualizar dados:** envio → prévia → confirmação numa tela; colunas com outro nome escolhidas em listas (sem JSON); conflitos, configuração e **tabela de preços** em abas. Botão **Criar planta de demonstração (sintética)**: importa as 8 semanas, define a referência de agosto e fecha o primeiro período.
- **Fechamentos:** referência com versões, **Produzir fechamento**, custo observado × esperado × desvio, o que mudou, próxima verificação, conta do período, reprodução e downloads; **Abrir investigação deste desvio** leva direto à investigação.
- **Investigações e ações:** evidência, situação, responsável, ação ligada e encerramento; ações com **Avaliar agora** (diferença observada, melhoria associada, economia verificada), adoção da referência pós-ação e custos de medição e acompanhamento.
- **Painel:** último fechamento, números do acompanhamento, **O que olhar primeiro** com critérios legíveis (oportunidades uma a uma, sem soma) e resultados verificados.
- **Uso mais seguro:** o nome de quem registra é digitado uma vez e vale em todas as telas; depois de gravar, a tela se redesenha com aviso verde no topo e formulários limpos (nada é enviado duas vezes por engano); a aba escolhida continua aberta.
- **Testes:** ciclo completo pelas telas (planta de demonstração → painel → fechamento → investigação → evidência → ação → avaliação → encerramento → custo → preço) e as quatro telas abrindo sem planta. Conferido no navegador, sem erros.
- Decisões D93–D96 registradas como propostas pendentes. Guias de demonstração atualizados para o menu novo.

## App pronto para a internet — 05/10/2026

Pedido do Adryan: acessar o software pela internet, em vez de uma prévia refeita à parte.

- `requirements.txt` na raiz com só o necessário para o app, nas versões testadas, e o motor (`.`). Conferido numa cópia limpa do repositório: instalação do zero em Python 3.11 e 3.12, app aberto sem pasta de dados configurada e todas as telas percorridas no navegador sem erro (análise, Financeiro, Oportunidades, Relatório e o acompanhamento com a planta de demonstração).
- Passo a passo do Streamlit Community Cloud no README. A publicação em si precisa da conta do Adryan (login pelo GitHub); cada envio ao branch atualiza o app.
- Cuidados registrados: repositório público = link aberto a quem o tiver; só dados sintéticos; o que for gravado lá some quando o app reinicia.

## Prévia interativa atualizada — 05/10/2026

- A prévia (página que abre no navegador sem instalar nada) passou a ter o menu em três grupos, Financeiro, Oportunidades e todas as telas de **Acompanhar a planta**. Gerada por `scripts/gerar_previa.py`; dados do acompanhamento em `scripts/previa_acompanhamento.py`; telas novas em `scripts/previa_telas_novas.js`.
- Os números vêm do motor: os três fechamentos da planta de demonstração, a investigação aberta a partir de cada um e a avaliação de uma ação para cada data de 03/08 a 29/09. O que o visitante registra (evidência, ação, encerramento, preço, custo) fica só no navegador dele.
- Conferida no navegador: o ciclo completo, as telas de análise e a largura de celular, sem rolagem lateral nem erro. Publicada num link novo, que substitui a prévia de 01/10.

## Incerteza explicada e dados reais organizados — 05/10/2026

Pedidos do Adryan: "cadê a parte dos dados reais que foram testados?" e "busque melhorar essas incertezas que são muito altas".

- **Incerteza (D97).** A faixa larga do desvio vinha, no caso de demonstração, 90% do medidor de vapor (±2%), combinado como erro independente nos dois períodos. A conta agora mostra de onde vem a faixa, a faixa se o instrumento repetir o mesmo erro (no primeiro fechamento: R$ 3.182 a R$ 9.120 em vez de −R$ 3.473 a R$ 15.775, e o desvio ficaria estabelecido) e a faixa se o medidor tivesse metade da incerteza. A conclusão principal continua a cautelosa; os cenários trazem a condição e o que confirmar. Telas Financeiro e Fechamentos. Testes novos em `tests/test_incerteza_explicada.py` (a decomposição fecha exatamente com a incerteza total).
- **Dados reais (D98).** Grupo próprio no menu, quadro do que foi testado no topo da tela e um caso por aba; atalho no Início; Diagnóstico de evidências com o cabeçalho padrão. Resumo calculado em `app/resumo_publico.py`, usado pelo app e pela prévia.
- **Prévia** republicada no mesmo link com as telas de dados reais e a explicação da faixa.
- 622 testes passando; nenhum golden ou tolerância alterado.

## Primeira planta brasileira real nos dados testados — 05/10/2026

Pedido do Adryan: "trabalhe exaustivamente nisso até achar dados completos de uma planta brasileira para nossa validação!"

- **Onde estava:** teses e artigos brasileiros só publicam médias ou ensaios de horas. Os pedidos de emissão do **Mecanismo de Desenvolvimento Limpo (MDL)** da ONU trazem as planilhas de cálculo com os dados de operação. Filtrados os 42 projetos brasileiros com créditos emitidos; conferidos AmBev (cervejaria), Klabin, Solvay, Cargill (rejeitado, sem dados) e outros. Detalhes e o que cada fonte tem em `validation/public/BUSCA_PLANTA_BRASILEIRA.md`.
- **Caso importado (D99):** cervejaria AmBev em Viamão (RS), duas caldeiras a casca de arroz de 19 t/h, **660 dias seguidos** (05/11/2007 a 25/08/2009). Planilha original no repositório sem alteração (termos da UNFCCC: domínio público, cópia sem alteração com a fonte) e extração em CSV conferida célula a célula.
- **O que a EULER faz com ela** (aba **Planta brasileira · RS**, a primeira de Dados reais testados): reproduz os totais do relatório oficial de verificação (218.123 t de vapor, 49.566 t de casca); acha 3 dias com o total diário em branco, 1 dia com energia em branco e 7 registros acima da capacidade da caldeira (até 165%); mostra que a casca do dia não é a queimada no dia; confere a entalpia da planilha com a IF97 (diferença máxima 0,04%); compara dois anos no mesmo trecho do calendário: **8,5% menos casca por tonelada de vapor no 2º ano, não estabelecido** — faltam estoque nas datas de corte e incerteza dos medidores de vapor — com as seis explicações possíveis e a medição que separa cada uma.
- Testes em `tests/test_ensaio_cervejaria.py` (contas refeitas só com a biblioteca padrão e a IAPWS direta). `xlrd` entrou no grupo `validacao` para o CI conferir a planilha original.
- Prints em `prints/dados_reais_planta_brasileira_*.png`.
- **Prévia** republicada no mesmo link, com a aba da planta brasileira (resposta, conferência, hipóteses e fontes). Conferida no navegador e na largura de celular, sem erro nem rolagem lateral.
- 635 testes passando; nenhum golden ou tolerância alterado.
- **Continua faltando** para a validação completa: estoque medido, umidade/PCI da casca, água de alimentação e gases. Isso só vem de uma planta piloto autorizada.

## Navegação simplificada conferida e prévia no menu novo — 05/10/2026

Pedido do Adryan: preservar as mudanças de interface feitas com o Codex (commit `ed44ff6`) e continuar a partir delas.

- **Suíte completa** (a entrega tinha rodado só os 59 testes de interface): 635 passaram e 3 falharam. As três falhas eram testes de tela procurando rótulos antigos: os botões "Ato 1"/"Ato 2" do Início (agora **Explorar demonstração** e **Ver demonstração com dados incompletos**) e o título "Por que a conta mudou em relação à referência" (agora uma seção recolhida do Financeiro). Os testes passaram a usar os rótulos novos, com as mesmas verificações; nenhuma tela, cálculo, golden ou tolerância alterado.
- **No navegador:** seis entradas no menu e 17 telas com **Mais ferramentas** aberto; os endereços antigos (`/investigacao`, `/dados_publicos`, `/diagnostico`, `/calculadora`, `/fechamentos`, `/relatorio`) abrem sem erro; demonstração → Análise → Financeiro → Minha planta sem erro; largura de celular (390 px) sem rolagem lateral.
- **Prévia online** republicada no mesmo link com o menu novo (seis entradas e **Mais ferramentas** nos três grupos), o Início novo e os detalhes recolhidos de Investigação, Financeiro e Painel. As seções abertas continuam abertas quando a tela se redesenha.
- **Guias** (`PASSEIO_PELAS_TELAS.md` e `ENTENDA_A_EULER.md`) com o menu novo e onde fica cada tela; Financeiro entrou na tabela de telas.
- **D100** registra a navegação como proposta. Pendentes para o Adryan: os títulos dentro das telas ainda são os antigos ("Painel", "Saúde da caldeira", "Atualizar dados", "Investigações e ações") e o rótulo "Qualidade e limites dos dados" aparece cortado na barra lateral.

## Conclusão financeira em um quadro — 06/10/2026

Pedido do Adryan: continuar as cinco melhorias propostas pelo Codex, começando pelos itens 1 e 2. Antes, a entrega do Codex (`ed1c086`, importação guiada e financeiro por planta) foi conferida com a suíte completa: 677 testes passando; a única falha da primeira rodada (`test_armazenamento_app`) foi tempo esgotado com processos pesados em paralelo e passou isolada e na rodada limpa.

- **Item 1 (D101).** O Financeiro abre com um quadro único, montado por `euler.conta.conclusao_financeira` só com números da conta E16: custo do combustível consumido, esperado nas condições analisadas, diferença sem explicação com a faixa; a ponte em relação à referência (preço, produção de vapor com a nota de duração, outros ajustes e sem explicação, fechando a variação); e o que falta verificar para considerar alguma parcela evitável, com o lugar da conta onde aparece o impacto de cada verificação. "Explicado" quer dizer atribuído a um fator medido, não inevitável. O mesmo quadro aparece nos fechamentos salvos.
- Os três cartões, o quadro de oportunidade/economia e a ponte separada saíram da tela (o conteúdo está no quadro); a faixa de incerteza, a composição detalhada e compras e estoque continuam.
- Testes: `tests/test_conclusao_financeira.py` (10, contas refeitas à mão); testes de tela do Financeiro atualizados para o quadro, com as mesmas verificações. Nenhum golden ou tolerância alterado.

## Caminho único da planta — 06/10/2026

- **Item 2 (D102).** `euler/percurso.py` diz, para o equipamento escolhido, em que pé estão os cinco passos (enviar registros → conferir a conta → investigar → registrar ação → verificar resultado) e qual é o próximo, lendo só o que está gravado. Minha planta mostra o percurso completo com atalho para o próximo passo; Dados, Fechamentos, Ações e o Financeiro dos fechamentos mostram em que passo a tela está.
- **Salvo × temporário.** As telas da planta dizem "Dados salvos da planta: o que você confirmar aqui fica gravado no histórico". As telas de análise dizem "Análise temporária · dados desta sessão" e se a versão está salva. Sem arquivos na sessão, o Financeiro abre nos fechamentos da planta.
- Correção: o campo de altitude em Dados quebrava quando a altitude estava gravada como número inteiro.
- Testes: `tests/test_percurso.py` (5) e `tests/test_percurso_telas.py` (5); um teste de tela ajustado ao novo padrão do Financeiro sem dados. Conferido no navegador com a planta de demonstração.

## Linha do tempo financeira — 06/10/2026

- **Item 3 (D103).** `euler/linha_do_tempo.py` reúne os fechamentos gravados, período a período: duração, vapor, combustível, consumo específico, custo, esperado, desvio com faixa, situação, qualidade da conta e as ações registradas no período, com a avaliação de cada uma. Custo e desvio também por tonelada de vapor e por dia (o mesmo valor dividido pelo vapor medido ou pela duração).
- **Leitura da série.** Diz se o desvio "está se repetindo" (dois ou mais fechamentos seguidos acima, além da incerteza), "apareceu agora" ou cabe na incerteza; avisa quando a referência muda de versão, quando as durações são diferentes e quando há conta incompleta. "Melhorou depois da ação" só vem da avaliação registrada da ação.
- **Tela.** Financeiro → Fechamentos da planta, acima do fechamento escolhido: leitura, gráfico do desvio com a faixa de incerteza e as ações como linhas tracejadas (total do período ou por tonelada de vapor) e a tabela dos fechamentos. Fechamento sem conta fica fora do gráfico, sem zero, e aparece na tabela com o motivo.
- Testes: `tests/test_linha_do_tempo.py` (9). Conferido no navegador com uma planta sintética de seis fechamentos.

## Entrega a cada fechamento — 06/10/2026

- **Item 5 (D104).** `euler/entrega.py` monta a entrega de um fechamento em cinco partes: a conta do período (mesmo quadro da conclusão) e o que mudou; pendências relevantes; verificações abertas e ações sem avaliação; resultados já demonstrados (só avaliações registradas e economia verificada pelo protocolo). A conta vem preservada do fechamento; o restante é o registrado até a data da entrega, escrita no documento. Termina com o aviso de que a EULER recomenda verificações e não comanda a caldeira.
- **Tela.** Financeiro → Fechamentos da planta mostra o resumo da entrega (contagens), o texto completo e o botão "Baixar a entrega do fechamento"; a tela Fechamentos tem o mesmo botão ao lado do relatório. Nada é enviado automaticamente.
- **Item 4.** Roteiro do teste com uma planilha real autorizada em `docs/produto/teste_planilha_real.md`: objetivos, cuidados antes da reunião (sem presumir acesso; autorização por escrito), pedido de amostra para o Adryan adaptar, roteiro de 45–60 minutos com a pergunta central e ficha de observação sem dados do cliente.
- Testes: `tests/test_entrega.py` (7).

## Prévia online atualizada — 06/10/2026

- A prévia interativa (`scripts/gerar_previa.py`) mostra as melhorias D101–D104 com os números calculados pelo motor: o quadro da conclusão financeira no Financeiro e em Fechamentos; o percurso de cinco passos em Minha planta e o marcador de passo nas telas da planta; o Financeiro com "Dados desta sessão" e "Fechamentos da planta" (linha do tempo, conta salva e entrega do fechamento); "Análise temporária" × "Dados salvos da planta". Republicada no mesmo endereço.

## Menu compacto — 07/10/2026

- **D105.** O menu lateral passou de seis entradas + "Mais ferramentas" (onze telas escondidas) para **cinco seções**: Início, Minha planta, Análise, Financeiro e Validação. As telas de cada seção viram **abas no topo da tela** (por exemplo, Minha planta › Painel, Dados, Fechamentos, Ações, Histórico). A seção aberta fica destacada no menu.
- Nenhuma funcionalidade saiu: as 17 telas, os cálculos e os links antigos continuam iguais; só mudou a forma de chegar a elas (`app/navegacao.py`, `app/main.py`). No celular, as abas quebram em linhas e o topo ganhou espaço para o botão do menu.
- Testes: `tests/test_navegacao_simples.py` (4): todas as rotas registradas uma única vez, cada tela numa seção, menu com até cinco entradas e, em cada seção, as abas das telas irmãs com a seção destacada.
- Guias (`ENTENDA_A_EULER.md`, `PASSEIO_PELAS_TELAS.md`) e a prévia online atualizados para o menu novo; prévia republicada no mesmo endereço. Prints: `prints/15_menu_compacto_painel.png` e `prints/16_menu_compacto_celular.png`.

## Planilha de fábrica como ela chega — 07/10/2026

- **D106.** A importação guiada (Análise › Arquivo avulso e Minha planta › Dados) agora lê uma planilha de fábrica sem retrabalho:
  - **sugere as colunas pelo vocabulário de fábrica** (`app/vocabulario_fabrica.py`), com o motivo de cada sugestão; cabeçalhos ambíguos continuam sem sugestão, e O₂ sem base, pressão absoluta, peso bruto e preço por tonelada nunca são associados (aparece uma nota explicando);
  - **lê a unidade escrita no cabeçalho** e já marca a conversão quando ela é exata; novas conversões: kgf/cm², psi e MPa → bar; °F → °C; t/dia → t/h;
  - **acha o cabeçalho abaixo de títulos** (linha ajustável) e mantém o número da linha do arquivo original;
  - **junta Data + Hora** de colunas separadas; sem data ou sem hora, a hora fica ausente;
  - mostra **"O que a EULER entendeu"**: o que entra e de onde vem, o que fica de fora (guardado no original) e as colunas usadas pelas análises que não vieram.
- O leitor, o contrato, o motor e o armazém não mudaram. O perfil por fonte continua guardando o mapeamento; as unidades continuam conferidas a cada envio.
- Testes: `tests/test_planilha_real.py` (20) com uma planilha de fábrica sintética (título em cima, Data e Hora separadas, kgf/cm², peso em toneladas, valor total) e um teste de tela que importa essa planilha pela interface. Os testes antigos da importação guiada continuam passando sem mudança.
- Falta: revisar o vocabulário com a primeira planilha real autorizada.


## Escala do atendimento, abas por mês e prévia no Painel — 07/10/2026

Pedido do Adryan: "faça os 3 pontos, principalmente o terceiro: descubra com testes quanto tempo levaria para cada cliente, do envio até o primeiro fechamento, para provar a escala".

- **Medição de escala (D109).** `scripts/medir_escala.py` leva cinco clientes sintéticos do envio ao segundo fechamento pelo mesmo caminho das telas (conferência, prévia, confirmação, referência, fechamento) e gera `docs/produto/escala_atendimento.md`. Resultado:
  - máquina (**medido**): 11 a 14 s por cliente até o primeiro fechamento; 8 a 13 s nos meses seguintes;
  - ajustes à mão (**contado**): modelo EULER 0, planilha de fábrica 0, mês por aba 0, supervisório 7 (as tags PT-101, TT-102… só a pessoa sabe o que são), abreviações sem unidade 24; no mês seguinte, 0 em todos, menos 12 re-confirmações de unidade no pior caso;
  - pessoa (**assumido**, rotulado): 4 a 23 min no primeiro envio; 3 a 14 min por mês depois; a medir com o registro de atendimento.
- **O que o teste encontrou.** Na primeira rodada a planilha de fábrica pedia 11 ajustes, o mês por aba 13 e o supervisório 16; corrigido com regras gerais (D107). Ficaram para decisão: lembrar a unidade junto do mapeamento salvo; e a frase do fechamento quando falta o PCI do laboratório (sem PCI, o mesmo período aparece "acima da referência", porque o efeito do combustível mais úmido não pode ser separado). Também ficou claro que, sem cadastro de instrumentos, o fechamento não classifica a diferença: o cadastro entra na implantação.
- **Registro de atendimento (T16, D109).** Cada envio confirmado em Minha planta › Dados grava o tempo na tela e os ajustes à mão; em Dados › Histórico › "Atendimento desta caldeira" aparecem o caminho até o primeiro fechamento (calendário, envios, tempo de tela, ajustes) e o lançamento das horas da equipe (dia, tarefa, minutos), com total por mês e `atendimento.csv`. Sem medição aparece "sem medição", nunca zero.
- **Planilha de fábrica parte 2 (D107).** Várias abas para a mesma tabela (um mês por aba; recebimentos e estoque separados) se juntam; o mesmo registro igual entra uma vez e fica anotado; com valores diferentes, a importação para e mostra as duas abas e linhas. Cabeçalho em duas linhas (células mescladas) vira "Temperaturas · Gases", com a opção na tela.
- **Prévia no Painel (D108).** Com período completo depois do último fechamento, o Painel mostra "Prévia · ainda não fechado" e se o consumo saiu, voltou ou continua na faixa; a conta é a do fechamento, mas nada é gravado. Na planta de demonstração aparece o período de 14/09 a 21/09, que não pode ser fechado porque o medidor de vapor estava em manutenção (motivo exibido).
- Testes novos: `tests/test_escala_atendimento.py` (7, cerca de 2 min), `tests/test_atendimento.py` (24), `tests/test_previa_fechamento.py` (10), mais 5 em `tests/test_planilha_real.py`, 1 em `tests/test_tela_importacao_guiada.py` e 1 em `tests/test_telas_acompanhamento.py`. O teste antigo que esperava a recusa de duas fontes na mesma tabela foi atualizado para a regra nova (D107).
- Falta: medir clientes reais com o registro (o tempo de pessoa só deixa de ser assumido assim); decisões pendentes D107–D109.
