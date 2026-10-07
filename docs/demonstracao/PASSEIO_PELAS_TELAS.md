# Passeio pelas telas da EULER (para conhecer o app)

Tempo: uns 10 minutos, com calma. Tudo com o **caso de demonstração sintético** (dados
inventados para teste). Para a apresentação com cliques e números exatos, use
`docs/demonstracao/GUIA_DEMONSTRACAO_AO_VIVO.md`.

## Como abrir

- No seu computador: dois cliques em `ABRIR-EULER.cmd`. O navegador abre sozinho em
  http://localhost:8501 (ou 127.0.0.1:8501). Para fechar a EULER, feche a janela preta.
- À esquerda fica o **menu** (faixa escura com o logo EULER), com cinco seções. As telas de
  cada seção aparecem como **abas no topo da tela**:
  **Início**;
  **Minha planta** (Painel, Dados, Fechamentos, Ações, Histórico);
  **Análise** (Saúde da caldeira, Investigar, Oportunidades, Qualidade e limites, Relatório,
  Arquivo avulso);
  **Financeiro** (Conta do período, Fornecedores);
  **Validação** (Testes com dados reais, Diagnóstico de evidências, Calculadora de referência).
  Nenhuma tela foi removida: só ficaram agrupadas. No fim de cada tela de análise, o botão **Próximo** leva à tela seguinte.
- A linha "Dados em uso" com o selo laranja **DADOS SINTÉTICOS** mostra quais dados estão
  carregados. Recarregar a página (F5) apaga os dados e volta ao começo.
- Se abrir uma tela sem dados, ela oferece os botões **Ato 1 · caso completo** e
  **Ato 2 · dados insuficientes**.

## A demonstração em dois atos

Os dois atos usam **os mesmos registros de operação** da mesma caldeira sintética. Muda só o
cadastro de instrumentos:

- **Ato 1 · a EULER conclui:** a fábrica cadastrou a incerteza de todos os instrumentos. A
  EULER diz o que explica a subida do consumo (cavaco mais úmido e gases mais quentes) e
  descarta o excesso de ar.
- **Ato 2 · a EULER explica por que não conclui:** falta a incerteza de quatro instrumentos.
  A EULER mostra o que já dá para afirmar e qual cadastro resolveria a dúvida.

## 1. Início

- O que é: a frase da EULER e dois caminhos: **Minha planta** (painel e cadastro dos dados
  da planta) e **Analisar um período** (importar um arquivo ou explorar a demonstração).
  Embaixo, o cartão dos **testes com registros públicos de uma planta brasileira**.
- Onde clicar: **Explorar demonstração** (ato 1). Para o ato 2, abra **Sobre a demonstração e
  os limites** e clique em **Ver demonstração com dados incompletos**; o mesmo quadro traz o
  aviso de protótipo e em que pé está a EULER. Os dois atos levam à tela **Saúde da
  caldeira** (menu **Análise**).

## 2. Importar dados (Análise › Arquivo avulso)

- O que é: onde a fábrica envia os registros (CSV ou planilha).
- O que dá para fazer: informar a altitude; **Escolher arquivos** (ou arrastar) e depois
  **Importar os arquivos enviados**; baixar a planilha modelo; escolher um dos quatro
  exemplos sintéticos nos cartões de baixo (Ato 1, Ato 2, Modelos, Exemplo com problemas).
- Experimente: **Exemplo com problemas (sintético)**. A tabela **Avisos de qualidade** usa
  selos (vermelho = erro, laranja = atenção, cinza = informação) e fala a língua da fábrica:
  "Umidade = 38. Acima de 1: parece estar em %…". Nada é corrigido em silêncio.
- Os nomes técnicos dos arquivos e das colunas ficam no quadro **Detalhes técnicos: nomes
  dos arquivos e das colunas**.

## 3. Saúde da caldeira (Análise › Saúde da caldeira)

- O que é: o primeiro olhar depois de carregar os dados. Quanto combustível a caldeira gastou
  para cada tonelada de vapor, semana a semana.
- O que olhar:
  - o selo **Mudou** (laranja), **Estável** (verde) ou **Não dá para dizer** (cinza) e a
    frase: "O consumo por tonelada de vapor subiu 10,1% de 31/08 a 14/09 em relação à
    referência (03/08 a 31/08), além da incerteza das medições";
  - os dois números: referência **0,321 t/t** e mudança **0,353 t/t (+10,1%)**;
  - o gráfico: um traço por semana, com a incerteza na vertical; faixas **Referência** e
    **Mudança**; linhas tracejadas numeradas nos eventos (1 calibração, 2 medidor de vapor
    retirado, 3 · 4 medidor reinstalado e limpeza). A semana de 14/09 fica vazia: sem
    medidor de vapor, a EULER não inventa número;
  - a lista de eventos e a tabela período a período.
- Onde clicar: **Investigar esta mudança**. A Investigação abre com os períodos já
  escolhidos (agosto × 31/08 a 14/09).

## 4. Dados e limites (Análise › Qualidade e limites)

- O que é: o que dá e o que não dá para concluir com esses dados, e por quê.
- O que olhar, de cima para baixo:
  - os três cartões (no ato 2: **10 liberadas · 0 com limites · 1 bloqueada**; no ato 1:
    **11 · 0 · 0**);
  - o quadro **Qualidade dos registros**, com a lacuna no diário e o medidor zerado;
  - **Precisa de dados para concluir** (só no ato 2): a análise bloqueada, o **Por quê** e o
    que fazer para liberar;
  - **Liberadas com estes dados**;
  - a tabela **Período a período**, com 4 colunas: período, eficiência, consumo por t de
    vapor e situação (**Dá para concluir**, **Com limites** ou **Não dá para concluir**). O
    resto fica em **Ver detalhes de cada período**.

## 5. Investigação, a tela principal (Análise › Investigar)

- **Períodos comparados:** dois controles deslizantes. A faixa colorida embaixo mostra as
  semanas: cinza-azulado = referência (como era), laranja = comparação (como ficou).
- **Resultado** (logo abaixo), em até três frases:
  - ato 1 (verde): "O consumo por tonelada de vapor subiu 10,1%. Explicações compatíveis com
    os dados: combustível mais úmido (+7,8%) e mais calor saindo pela chaminé (+3,1%);
    descartado: mais excesso de ar e vapor mais exigente. Próxima verificação: …";
  - ato 2 (amarelo): "Não dá para concluir: …" e a próxima verificação, que é cadastrar a
    incerteza do método de umidade;
  - três cartões: consumo por tonelada de vapor, valor em jogo (estimado, com incerteza) e
    quantas explicações são compatíveis; embaixo, em azul, a **Próxima verificação, em
    detalhe**.
- **Detalhes**, em seções recolhidas (clique para abrir): **O que mudou · gráfico e
  indicadores** (gráfico e tabela com a incerteza de cada diferença), **O que os dados
  sustentam**, **Outras explicações possíveis**, **Dados que faltam para concluir** (dois
  grupos: **Completar o cadastro de instrumentos** e **Medir, registrar ou conferir**) e
  **Qualidade das evidências e rastreabilidade**.
- Os números técnicos ficam em **Detalhes técnicos da investigação (JSON)**, no fim.

## 6. Extrato por fornecedor (Financeiro › Fornecedores)

- O que é: quanto custa a **energia** de cada fornecedor, não só a tonelada.
- O que olhar: a frase azul (o F3 é o mais barato por tonelada e o mais caro por energia), os
  dois gráficos lado a lado, a tabela e a umidade por semana (o F3 vai ficando mais úmido).

## 7. Relatório (Análise › Relatório)

- Onde clicar: **Gerar relatório**. O topo do relatório traz as mesmas três frases do
  resultado. Aparecem **Baixar HTML** e, se houver o Chromium, **Baixar PDF**; o botão
  **Imprimir ou salvar como PDF** funciona no Windows sem instalar nada.
- O relatório usa os períodos escolhidos na Investigação e nunca mostra um relatório antigo.

## 8. Dados reais testados (Validação › Testes com dados reais)

- **Testes com dados públicos:** começa pelo quadro **O que já foi testado com dados reais**
  (caso, dados, o que a EULER fez, resultado e o que falta) e mostra um caso por aba. A
  primeira é a **planta brasileira**: 660 dias reais de duas caldeiras a casca de arroz de uma
  cervejaria em Viamão (RS), publicados no MDL da ONU. A EULER confere a planilha (os totais
  batem com o relatório oficial; acha dias com total em branco e registros acima da
  capacidade), compara dois anos com incerteza e responde "não dá para concluir" com a
  medição que separa as explicações (o estoque do galpão nas datas de corte). Depois:
  caldeiras da EPA nos EUA (registros horários de 2023), biomassa (UTFPR), custo do vapor
  (Unisanta), caldeira a carvão em três cargas e a série por minuto de Zhejiang. Nenhum é de
  cliente.
- **Diagnóstico de evidências:** para cada caldeira da EPA e cada mês, o que os dados
  sustentam, a força da evidência e a próxima verificação.

## 9. Calculadora de referência (Validação › Calculadora de referência)

- Simulação da perda de calor pela chaminé (em revisão científica; não use para decisões).
  Mexa nos três controles e veja os números mudarem.

## 10. Acompanhar a planta (seção "Minha planta": Painel, Dados, Fechamentos, Ações e Histórico)

Aqui os dados ficam **guardados por planta** e a EULER acompanha período após período. Para
conhecer sem dados reais: **Dados** (tela Atualizar dados) → digite **Seu nome** na barra lateral → abra
**Cadastrar uma planta** → **Criar planta de demonstração (sintética)**. Ela importa as 8
semanas, define a referência (agosto) e fecha o primeiro período.

- **Painel** (menu **Minha planta**): o último fechamento, os números do acompanhamento e
  **O que olhar primeiro** (desvio que persiste, ação sem verificação, investigação aberta,
  oportunidade, dado faltando): os três primeiros itens à vista e o resto em **Outros itens
  para acompanhar**; as pendências dos registros ficam num quadro recolhido. Oportunidades aparecem uma a uma, **sem soma**. "Economia verificada" só mostra
  resultado de ação avaliada pelo protocolo.
- **Atualizar dados** (Minha planta › **Dados**): envio → prévia → confirmação na mesma tela. O que já está gravado não
  se duplica; valor diferente vira **conflito** para decidir na aba **Conflitos**. Na aba
  **Configuração e preços** ficam a política de custo e a **tabela de preços**.
- **Fechamentos** (Minha planta › **Fechamentos**): a referência (com versões e motivo) e, a cada período novo, **Produzir
  fechamento**: custo observado, custo esperado pela referência ajustada, desvio em reais,
  o que mudou e a próxima verificação. **Abrir investigação deste desvio** leva o caso para a
  tela seguinte.
- **Investigações e ações** (Minha planta › **Ações**): cada investigação com evidências, situação, responsável, ações
  ligadas e encerramento (encerrar não significa causa confirmada). Na aba **Ações e
  resultados**, **Avaliar agora** compara a referência com os períodos depois da ação, em três
  níveis: diferença observada, melhoria associada e economia verificada. Os custos de medição
  e acompanhamento ficam no fim.
- **Plantas e histórico:** as plantas, as versões salvas dos arquivos e a cópia de segurança.

Seu nome fica guardado enquanto a janela estiver aberta e vai para o histórico de tudo o que
for registrado. Depois de cada gravação a tela se atualiza e mostra um aviso verde no topo.

---

## Como atualizar a sua cópia no Windows

A pasta `software-euler` que o Codex preparou **não é um checkout Git**: ela não se atualiza
sozinha. Escolha um caminho:

- **Pedir ao Codex (mais simples):** "Atualize a pasta software-euler com a versão mais nova
  do branch `claude/new-session-xytynj` do GitHub, mantendo a pasta `.venv`. Se possível,
  troque a pasta por um `git clone` desse branch, para as próximas atualizações virem com
  `git pull`."
- **Pelo navegador:**
  1. No GitHub, abra o repositório e troque o branch para `claude/new-session-xytynj`.
  2. Clique em **Code → Download ZIP** e descompacte.
  3. Copie tudo por cima da pasta `software-euler`. Não apague a pasta `.venv` dela.

Depois, feche a janela preta do app (se estiver aberta), abra o `ABRIR-EULER.cmd` (o que vem
dentro da pasta `software-euler`) e aperte F5 no navegador. Esta atualização **não** traz
dependências novas: não precisa instalar nada.
