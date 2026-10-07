# Entenda a EULER (guia para o Adryan)

Tudo o que a EULER é e faz, em linguagem simples: para explicar na apresentação, usar no dia a
dia e criar novos exemplos. Números deste guia: caso de demonstração **sintético**, motor
da versão atual.

---

## 1. Em 30 segundos

A EULER é um software de **investigação** para caldeiras industriais. Ela usa os registros que
a fábrica **já tem** (diário do operador, combustível recebido, amostras, eventos e
instrumentos) e responde a uma pergunta:

> O consumo de combustível mudou. O que os registros sustentam, quais explicações continuam
> possíveis e qual verificação separa essas explicações?

Três coisas a tornam diferente:

1. **Ela não chuta.** Quando os dados não bastam, diz "não dá para concluir" e qual medição
   resolveria. Nunca preenche um dado que falta nem inventa um número.
2. **Ela compra energia, não toneladas.** O extrato mostra quanto custa a energia de cada
   fornecedor (R$/GJ); o mais barato por tonelada pode ser o mais caro por energia.
3. **Ela não mexe na caldeira.** Não dá ordens (abrir válvula, mudar ajuste). A saída é sempre
   uma **verificação** para uma pessoa fazer.

## 2. O problema que ela resolve

O gestor de utilidades vê a conta de cavaco subir e não sabe por quê. As explicações possíveis
são muitas: combustível mais úmido, caldeira suja, excesso de ar, medidor com defeito,
purga... Hoje ele decide no "achismo" ou contrata uma consultoria cara. A EULER cruza os
registros que já existem e separa **o que os dados sustentam** do que **ainda é hipótese**.

## 3. Como explicar na apresentação (fala de 2 minutos)

1. **O problema (15 s):** "O consumo de combustível da caldeira subiu 10%. O gestor não sabe se
   é o cavaco, a caldeira ou o medidor."
2. **O que a EULER faz (15 s):** "Ela lê os registros que a fábrica já tem e aponta os
   problemas dos próprios registros, sem corrigir nada em silêncio."
3. **O extrato (20 s):** "O fornecedor mais barato por tonelada é o mais caro por energia:
   R$ 20,05 por GJ contra R$ 17,23. A caldeira compra energia."
4. **A investigação (30 s):** "O consumo subiu 10,1%. A temperatura dos gases subiu 32 °C, e
   isso é compatível com os dados. A umidade fecharia a conta, mas falta um dado para
   confirmar. Então a EULER diz: **não dá para concluir**, e aponta o que medir."
5. **A intervenção (25 s):** "Depois da limpeza da caldeira, ela confirma: o consumo caiu
   4,5% e a queda da temperatura dos gases explica a mudança, dentro da incerteza."
6. **O relatório (15 s):** "Tudo vira um relatório em linguagem simples, com a próxima
   verificação. Nunca uma ordem para a caldeira."

**Frases-chave:** "Ela sabe quando não sabe." · "A caldeira compra energia, não toneladas." ·
"Compatível não é comprovado."

**Diga com clareza:** os dados são **sintéticos**; os cálculos são testados (315 testes
automáticos), mas a física está **em revisão** por especialistas; ainda **não** houve teste
com dados reais de uma caldeira (é a próxima fase).

**Evite:** "a IA prevê", "economia garantida", "comprovado", "a EULER controla a caldeira".

## 4. Como usar, tela por tela

Abra com `ABRIR-EULER.cmd` (Windows) ou `streamlit run app/main.py`. O menu à esquerda tem cinco
seções: **Início**, **Minha planta**, **Análise**, **Financeiro** e **Validação**. As telas de
cada seção aparecem como **abas no topo da tela** (por exemplo, Minha planta › Painel, Dados,
Fechamentos, Ações e Histórico). As telas de análise têm o botão **Próximo** no fim. Passeio
detalhado: `docs/demonstracao/PASSEIO_PELAS_TELAS.md`.

| Tela | Para que serve | O que fazer |
|---|---|---|
| **Início** | apresenta a EULER e os dois caminhos: Minha planta e Analisar um período | **Explorar demonstração** (ato 1); o ato 2 fica em **Sobre a demonstração e os limites** |
| **Importar dados** (Análise › Arquivo avulso) | recebe os arquivos da fábrica e lista os problemas deles | enviar os arquivos ou escolher um exemplo; informar a altitude |
| **Saúde da caldeira** (Análise › Saúde da caldeira) | consumo por tonelada de vapor semana a semana, eventos e o selo mudou / estável / não dá para dizer | ler o selo e a frase; **Investigar esta mudança** |
| **Dados e limites** (Análise › Qualidade e limites) | diz o que dá e o que não dá para concluir, e por quê | ler o que está bloqueado e o que cadastrar para liberar |
| **Investigação** (Análise › Investigar) | compara dois períodos: o que mudou, o que explica, o que verificar | escolher os períodos; ler as três frases do resultado; abrir os detalhes recolhidos |
| **Financeiro** (Financeiro › Conta do período) | quanto o consumo pesa no caixa: o desvio em reais em relação à referência ajustada, com a faixa de incerteza | ler o desvio; abrir **Por que a conta mudou**; seguir para as Oportunidades |
| **Extrato por fornecedor** (Financeiro › Fornecedores) | custo da energia de cada fornecedor | comparar R$/t com R$/GJ; ver a umidade semana a semana |
| **Relatório** (Análise › Relatório) | junta tudo num documento para compartilhar | **Gerar relatório** e baixar |
| **Calculadora de referência** (Validação › Calculadora de referência) | simula a perda de calor pela chaminé | mexer na temperatura, no O₂ e na umidade |
| **Painel** (Minha planta › Painel) | o que mudou no último fechamento e o que olhar primeiro | ler a fila; seguir para Fechamentos ou Investigações e ações |
| **Atualizar dados** (Minha planta › Dados) | acrescenta os dados novos da planta sem duplicar nem substituir em silêncio | enviar, conferir a prévia, confirmar; decidir conflitos; cadastrar preços |
| **Fechamentos** (Minha planta › Fechamentos) | custo observado × esperado e o que mudou, a cada período | **Produzir fechamento**; **Abrir investigação deste desvio** |
| **Investigações e ações** (Minha planta › Ações) | do desvio à verificação, com histórico | registrar evidência e ação; **Avaliar agora**; encerrar |

Para ver sem instalar nada: a **prévia interativa** (link que o Claude publicou), com as mesmas
telas e os números do motor para o caso de demonstração.

## 5. O que entra: os arquivos da fábrica

São cinco arquivos (CSV) ou uma planilha com uma aba para cada. Todos podem ter falhas: a
EULER aponta cada uma, com a linha.

| Arquivo | O que é | Exemplo de conteúdo |
|---|---|---|
| `diario.csv` | o **diário do operador**: leituras a cada poucas horas | totalizador de vapor, pressão, temperatura dos gases, O₂, temperatura da água |
| `combustivel.csv` | **combustível**: cada caminhão recebido e cada medição do estoque do pátio | data, fornecedor, lote, massa, preço; estoque medido |
| `amostras.csv` | **análises** do combustível | umidade do lote, PCI seco, composição |
| `eventos.csv` | o que aconteceu de diferente | limpeza, troca de instrumento, calibração, parada |
| `instrumentos.csv` | os **instrumentos** e a incerteza de cada um | no demo: medidor de vapor ±2% da leitura, termopar da chaminé ±2 °C, analisador de O₂ ±0,3 ponto |

O que é preciso para a investigação funcionar: pelo menos **três medições de estoque** (que
formam dois períodos para comparar), leituras do **totalizador de vapor** no início e no fim de
cada período, **umidade** dos lotes e as **incertezas** dos instrumentos. Faltou algo, a tela
Dados e limites diz o quê.

## 6. O que sai: as exportações e para que serve cada uma

| Exportação | Onde | Para que serve | Para quem |
|---|---|---|---|
| **Relatório HTML** | Relatório → Baixar HTML | o relatório completo num arquivo que abre em qualquer navegador; dá para mandar por e-mail | gerente, cliente |
| **Relatório PDF** | Relatório → Baixar PDF (precisa do Chromium instalado) | o mesmo relatório em A4 (cerca de 4 páginas), para imprimir ou anexar | gerente, cliente, banca |
| **Imprimir ou salvar como PDF** | botão em cima da prévia do relatório | gera o PDF pelo próprio navegador, sem instalar nada | quem não tem o Chromium (ex.: seu Windows) |
| **JSON da investigação** | Investigação → "Detalhes técnicos da investigação" → Baixar o JSON | todos os números, incertezas, hipóteses e critérios, num formato que outro programa lê | desenvolvedores, auditoria, revisores, integrações futuras |
| **Planilha modelo (.xlsx)** | Importar dados → Baixar a planilha modelo | modelo em branco, com uma aba por arquivo e as colunas certas, para a fábrica preencher | a fábrica (cliente) |
| **Prévia interativa** | `python scripts/gerar_previa.py` | uma página com as telas e os números do demo, que abre sem instalar nada | apresentação, investidores |

O relatório tem sempre os **5 blocos fixos**: O que mudou · O que os dados sustentam ·
Explicações possíveis · O que falta saber · Próxima verificação. E sempre leva o selo **DADOS
SINTÉTICOS** quando for o caso, a situação do modelo e o aviso de segurança.

## 7. Como ler os resultados (os rótulos que aparecem)

**"Mudou de forma detectável?"** (quatro respostas diferentes, de propósito):

| Selo | Quer dizer |
|---|---|
| **Sim** (azul) | a mudança é maior que a incerteza das medições: mudou de verdade |
| **Condicional** (laranja) | só seria uma mudança real se o erro do instrumento for o mesmo nos dois períodos; falta cadastrar uma incerteza para decidir |
| **Não** (cinza) | variação normal, dentro da incerteza |
| **Sem incerteza para dizer** (cinza) | não há incerteza cadastrada nenhuma: não dá para dizer |

**Explicações:**

| Rótulo | Quer dizer |
|---|---|
| **Compatível com os dados (não comprovada)** | os dados apoiam; precisa da verificação indicada para virar causa |
| **Mudou no sentido contrário** | mudou, mas compensou parte da mudança (empurrou para o outro lado) |
| **Continua possível** | não dá para confirmar nem descartar com os dados de hoje |
| **Não dá para avaliar** | falta o dado para sequer testar |
| **Descartada pelos dados** | os dados mostram que não foi isso |

**Valor em jogo:** quanto custou o combustível a mais no período (estimado, com incerteza).
Só aparece quando o consumo **subiu** e há base para calcular; senão, a EULER diz por que não
estimou. Nunca é promessa de economia.

## 8. O caso de demonstração: o que foi "plantado"

Caldeira **fictícia** de 20 t/h a cavaco, 8 semanas (03/08 a 28/09/2026), 3 fornecedores. Os
fatos foram colocados de propósito, para ver se a EULER os encontra:

| Semana | O que acontece | O que a EULER mostra |
|---|---|---|
| 1–4 (agosto) | operação normal | a referência ("como era") |
| 5–6 (31/08 a 14/09) | temperatura dos gases sobe 32 °C, sem explicação registrada; cavaco do F3 fica mais úmido | consumo +10,1%; gases "Sim"; umidade "Condicional" → **não dá para concluir**; próxima verificação: cadastrar a incerteza do método de umidade |
| 7 (14/09 a 21/09) | medidor de vapor fora; volta zerado | **não dá para saber** se o consumo mudou; não inventa número |
| 8 (21/09 a 28/09) | **limpeza dos tubos** em 21/09: a temperatura dos gases volta ao normal | ver a seção 9 |
| todas | F3 o mais barato por tonelada e o mais caro por energia; lacuna no diário; alguns registros atrasados | extrato e avisos de qualidade |

## 9. Mostrar uma intervenção (já dá, com o demo)

A limpeza de 21/09 é uma **intervenção**. A EULER consegue verificar o efeito dela:

- **Antes** = semanas 5–6 (caldeira suja) · **Depois** = semana 8 (depois da limpeza)
- Resultado: **o consumo caiu 4,5%** (de 0,353 para 0,337 t de combustível por t de vapor;
  incerteza ±3,5%). A temperatura dos gases caiu de 217,7 para 187,5 °C (detectável). A
  explicação "**menos calor saindo pela chaminé**" é compatível com os dados e explica −2,9%
  dos −4,5%: **fecha dentro da incerteza**.
- O valor em jogo não aparece: a EULER só estima o custo do combustível **a mais** (aqui o
  consumo caiu), e não inventa economia.

Esse é o contraponto perfeito para a apresentação: na mesma caldeira, a EULER diz "não dá para
concluir" quando falta dado e **conclui** quando os dados bastam.

**Na prévia interativa:** Investigação → atalho **Antes × depois da limpeza (intervenção)**.

**No app:** Investigação →
1. no controle **Período de comparação**, arraste as duas bolinhas até **21/09 a 28/09**;
2. no controle **Período de referência**, arraste a bolinha da direita até **07/09 a 14/09** e
   a da esquerda até **31/08 a 07/09**.
(Se aparecer "os dois períodos se sobrepõem" no meio do caminho, é só continuar.)

## 10. Como criar novos exemplos simulados

Regras: os dados têm de ser **sintéticos** (inventados) e marcados assim (coluna `origem_dado`
= `sintetico`). Dados reais de cliente **nunca** vão para o repositório.

**Caminho A · pedir a um desenvolvedor (ou ao Claude) um cenário novo.** O caso de
demonstração sai de um programa (`demo/gerar_caso_demo.py`) que tem os "botões" do cenário:
quando a caldeira suja e quanto, a umidade de cada fornecedor, quando o medidor falha, quando
é a limpeza, os preços. Copia-se o programa, mudam-se os botões e gera-se uma pasta nova (por
exemplo `demo/caso_intervencao/`). Depois é só enviar os arquivos em **Importar dados**. Leva
cerca de uma hora para um cenário novo, com o "gabarito" do que a EULER deve mostrar.

Ideias de cenários para a apresentação:

| Cenário | O que se simula | O que a EULER deveria mostrar |
|---|---|---|
| **Troca de fornecedor** | a fábrica troca o F3 (úmido) pelo F1 | custo por GJ cai e o consumo por tonelada de vapor cai; se o cenário tiver as incertezas dos instrumentos cadastradas, a umidade aparece como explicação |
| **Purga esquecida aberta** | perda que não aparece em nenhuma medição | consumo sobe e nenhuma explicação medida cobre: "Outras perdas" e a verificação das purgas |
| **Ajuste da combustão feito pela fábrica** | O₂ cai de 9% para 6% depois de uma manutenção registrada | menos excesso de ar, perda nos gases menor; a EULER verifica o efeito (ela não manda ajustar nada) |

Nesses cenários, as incertezas dos instrumentos vêm da especificação do instrumento que se
está simulando, nunca escolhidas para "fechar" uma conclusão. No caso de demonstração de 30/10
elas ficam como estão (decisão D53).

**Caminho B · preencher a planilha modelo à mão.** Bom para um exemplo pequeno (algumas
semanas). Baixe em Importar dados, preencha (lembrando das três medições de estoque e das
leituras do totalizador) e envie de volta.

**Caminho C · mexer em um arquivo do demo.** Rápido para um teste, mas fácil de errar e de
criar inconsistência. Prefira o caminho A.

## 11. O que a EULER ainda não faz (para responder com honestidade)

- Não foi testada com dados reais de caldeira.
- A física está em revisão por professores e doutorandos; nenhum item foi aprovado ainda.
- Não tem login, várias empresas, leitura de foto de papel (OCR) nem integração automática
  com sistemas da fábrica (fases seguintes).
- Não controla a caldeira e nunca vai controlar: só investiga e indica verificações.

## 12. Glossário rápido

| Termo | Em palavras simples |
|---|---|
| **Consumo específico** (t/t) | toneladas de combustível gastas para fazer uma tonelada de vapor; quanto menor, melhor |
| **PCI** | quanto de energia o combustível entrega quando queima; cavaco úmido entrega menos |
| **Umidade (base úmida)** | quanto do peso do cavaco é água |
| **Perda nos gases** | parte da energia do combustível que sai quente pela chaminé |
| **Excesso de ar (O₂)** | ar a mais na queima; ar demais esfria e leva calor embora |
| **Incerteza** | o "mais ou menos" de cada medição; a EULER só afirma uma mudança maior que ela |
| **Totalizador de vapor** | o medidor que soma o vapor produzido, como o hodômetro de um carro |
| **Estoque do pátio** | o cavaco guardado; medir o estoque é o que permite saber quanto foi queimado |
| **R$/GJ** | quanto custa cada unidade de energia comprada; a comparação justa entre fornecedores |
