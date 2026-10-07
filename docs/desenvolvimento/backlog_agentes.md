# EULER · Backlog para agentes (Codex / Claude Code) · Fase 0 (edital, até 15/11/2026)

Cada ticket cabe numa sessão de agente (≈1–4 h de trabalho humano equivalente). Formato: **Objetivo · Arquivos · Aceite · Não fazer · Revisão**.
Responsáveis sugeridos: **P1** física/core · **P2** benchmark (repo separado) · **P3** dados/app · **AD** Adryan (produto) · **REV** doutorandos.
Se algum ticket já foi feito na semana 1, marque como concluído e siga.

Legenda de status: ☐ a fazer · ◐ em andamento · ☑ pronto (testes passando + revisão humana)

---

## Bloco 1 · Fundação

**T01 · Repositório e CI** — P3 ☐
- Objetivo: `euler-core` com `pyproject.toml`, ruff, pytest, CI no GitHub Actions; copiar `AGENTS.md`, `CLAUDE.md`, `docs/`, `tests/golden/` deste kit.
- Aceite: `pytest -q` e `ruff check .` rodam no CI; PR template com seções "O que mudou / Como testar / Fora do escopo / Dúvidas".
- Não fazer: nenhum código de física.

**T02 · Contrato de dados e planilhas modelo** — AD + P3 ☐
- Objetivo: `docs/dados/contrato_dados.md` (da spec v0.3) + `templates/*.csv` (deste kit) + uma planilha modelo .xlsx com abas iguais aos CSVs e instruções para o operador.
- Aceite: cada coluna com unidade, obrigatoriedade e exemplo; planilha abre no Excel/Google Sheets e exporta CSV que o importador aceita.
- Não fazer: colunas sem unidade no nome.

## Bloco 2 · Entrada de dados (o software se vira sozinho)

**T03 · Importador de `diario.csv` com qualidade** — P3 ☐
- Objetivo: `euler/io/diario.py` + `euler/qualidade.py`: lê, normaliza, preserva original, detecta lacunas, duplicatas, totalizador reiniciado, registro tardio, unidades suspeitas.
- Aceite: testes com CSV sintético contendo cada problema; relatório de importação legível (lista de avisos com linha e motivo).
- Não fazer: preencher ou interpolar valores.

**T04 · Mapeamento inteligente de colunas** — P3 ☐ *(novo, reduz horas de atendimento)*
- Objetivo: `euler/io/mapeamento.py`: reconhece sinônimos de colunas ("Temp. chaminé", "T gases", "temperatura fumaça" → `t_gases_c`) por dicionário + regras; o que não reconhecer vira pergunta na tela ("Esta coluna é…?"). Salva o mapeamento por cliente para reuso.
- Aceite: 20 cabeçalhos realistas de teste, ≥ 80% mapeados automaticamente, 0 mapeamentos errados silenciosos (na dúvida, pergunta).
- Não fazer: usar IA generativa no protótipo (fica para a Fase 1).

**T05 · Importador de `combustivel.csv`, `amostras.csv`, `eventos.csv`, `instrumentos.csv`** — P3 ☐
- Aceite: mesmas regras do T03; volume sem densidade declarada gera aviso e bloqueia conversão para massa.

## Bloco 3 · Motor físico

**T06 · `vapor.py` (IF97)** — P1 ☐
- Objetivo: entalpia do vapor e da água de alimentação; conversão manométrica → absoluta com `p_atm` configurável.
- Aceite: passa `tests/golden/vapor_referencia.csv` (E8).

**T07 · `indireto.py` · perda nos gases** — P1 ☐
- Objetivo: E1–E7 com dois modos: `modelo_cp="constante"` (reproduz o golden) e `modelo_cp="variavel"` (cp(T), fonte definida pelo REV).
- Aceite: modo constante passa `tests/golden/casos_referencia.csv` com tolerância 0,01 p.p.; modo variável difere do constante em < 0,5 p.p. nos casos G01–G10 (até o REV aprovar outro critério); bloqueia cálculo fora do domínio (E7) com motivo.
- Não fazer: copiar código do `euler-bench`.

**T08 · `combustivel.py` · queimado no período e energia** — P1 ☐
- Objetivo: E5, E9, E10 (parte da energia).
- Aceite: passa `tests/golden/pci_umido_referencia.csv`; sem estoque final → análise bloqueada com motivo.

**T09 · Extrato de energia por fornecedor (M1)** — P1 ☐ *(novo, principal argumento de valor)*
- Objetivo: E11. Para cada lote/fornecedor: energia entregue, R$/GJ, umidade e origem do dado; ranking por R$/GJ; alerta quando a umidade do lote foge da faixa histórica do fornecedor.
- Aceite: reproduz a tabela F1–F3 de `docs/fisica/fisica_para_revisao.md`; lote sem umidade medida aparece como "energia não determinada" (nunca assume).
- Não fazer: acusar fornecedor; texto neutro ("umidade acima da faixa histórica").

**T10 · `direto.py` · eficiência direta** — P1 ☐
- Objetivo: E10 + E13 (não circularidade) + incerteza de primeira ordem (E15).
- Aceite: teste que falha se a eficiência for usada como entrada; resultado com intervalo.

**T11 · `capacidades.py`** — P1 ☐
- Objetivo: tabela da seção 4 da spec v0.3 como regras testáveis; inclui "Extrato por fornecedor" (requer recebimentos + umidade por lote + preço).
- Aceite: um teste por linha da tabela (habilita quando tem, bloqueia com motivo quando falta).

**T12 · `deteccao.py` · degrau e comparação de períodos** — P1 ☐
- Aceite: critérios da seção 8 da spec v0.3 (degrau +30 °C em ≤ 3 leituras em ≥ 95/100; falsos alertas ≤ 5/100), medidos pelo P2 no benchmark.

## Bloco 4 · Investigação e entrega automática

**T13 · `investigacao.py` · JSON de investigação** — P1 ☐
- Objetivo: regras → JSON da seção 7 da spec v0.3, com E12 (marcar evidências que compartilham medição).
- Aceite: caso A/B/C sintético gera hipóteses corretas; contraexemplo (purga não medida) gera abstenção; `valor_em_jogo` só preenchido com base.

**T14 · `relatorio.py` · relatório automático em linguagem simples** — P3 + AD ☐ *(novo, reduz horas)*
- Objetivo: JSON → HTML (e PDF) com 5 blocos fixos: **O que mudou · O que os dados sustentam · Explicações possíveis · O que falta saber · Próxima verificação**. Rodapé de segurança obrigatório.
- Aceite: AD aprova o texto de 3 relatórios gerados; nenhum relatório contém comando operacional (teste com lista de verbos proibidos).

**T15 · App Streamlit** — P3 ☐
- Telas: (1) Importar e mapear, (2) Dados e limites (capacidades), (3) Investigação, (4) **Extrato por fornecedor**, (5) Relatório.
- Aceite: fluxo completo com o caso de demonstração em < 5 min, sem ajuda.

**T16 · Registro de horas de atendimento** — P3 ◐ *(novo, métrica de escala)*
- Objetivo: tabela simples `atendimento.csv` (cliente, data, tarefa, minutos) + resumo "horas por cliente por mês".
- Aceite: existe e é usada desde o primeiro piloto.
- Feito em 07/10/2026 (D109): lançamento das horas em Dados › Histórico, total por mês e `atendimento.csv`; tempo de tela e ajustes à mão medidos em cada envio; caminho até o primeiro fechamento por equipamento; medição de escala com cinco clientes sintéticos (`scripts/medir_escala.py`, `docs/produto/escala_atendimento.md`). Falta: usar desde o primeiro piloto.

## Bloco 5 · Prova e edital

**T17 · Benchmark cego** — P2 (repo `euler-bench`) ☐
- Objetivo: gerador com modelo "verdade" mais completo + casos reservados + gabarito com SHA-256 publicado antes da rodada.
- Aceite: relatório de acertos/erros/abstenções do `euler-core` contra o gabarito.

**T18 · Caso de demonstração ponta a ponta** — AD + P3 ☐
- Objetivo: caldeira sintética de 20 t/h a cavaco, claramente marcada como sintética: 3 fornecedores, 8 semanas, um degrau de temperatura, um fornecedor com umidade subindo, um período sem dado (abstenção).
- Aceite: roteiro de 2 minutos para o vídeo do edital usando o app.

**T19 · Congelar versão para o INPI** — P3 + AD ☐
- Objetivo: tag de versão, hash do código, lista de autores (commits com nome real), README da versão.

---

## Fase 1 (depois do edital, só listado)
Alertas automáticos · registro de ações e verificação do resultado (M4) · fechamento mensal do custo do vapor (M5) · várias caldeiras e plantas · login e nuvem · API para parceiros · foto do caderno (OCR) · assistente de dúvidas com base nos dados do cliente · comparação anônima entre plantas · base de qualidade por fornecedor.
