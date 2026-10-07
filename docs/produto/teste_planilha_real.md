# Teste com uma planilha real da indústria

Roteiro para o item 4 das melhorias propostas em 06/10/2026: observar alguém da indústria usando
um arquivo autorizado, com nomes e formatos próprios. Este documento é um roteiro interno.
Nada aqui é enviado automaticamente; o pedido de amostra é feito pelo Adryan, na reunião.

## O que queremos aprender

1. **Onde a pessoa trava** ao levar a planilha dela para a EULER (aba **Dados → Adaptar minha
   planilha**).
2. **Quais registros realmente existem** na fábrica e com que frequência: vapor, combustível,
   estoque, umidade, água de alimentação, gases, eventos.
3. **Quanto trabalho a EULER exige**: tempo até a primeira prévia, colunas associadas à mão,
   unidades confirmadas, registros que precisaram ser corrigidos fora da EULER.
4. **Qual resposta ajudaria numa decisão real**, com os registros que eles já têm.

## Antes da reunião

- **Não presumir acesso.** Pedir uma amostra **anonimizada ou autorizada**; aceitar um "não".
- Combinar por escrito quem autoriza, o que pode ser usado, onde fica guardado e quando é
  apagado. Dados de cliente nunca entram no repositório do código.
- Na EULER, a amostra entra numa planta da classe **cliente autorizado**, com a autorização
  registrada no cadastro. Sem isso, usar só a conversa e anotações, sem o arquivo.
- Levar a demonstração curta do percurso: Dados → conta → investigação → ação → resultado.

**Pedido sugerido (para o Adryan adaptar e falar ou enviar ele mesmo):**

> Para testarmos se a EULER funciona com a rotina de vocês, poderiam nos ceder uma amostra de
> um a dois meses dos registros da caldeira, como vocês já guardam hoje (diário do operador,
> recebimentos de combustível, estoque do pátio, análises de umidade e eventos)? Pode ser
> anonimizada. Usaremos só para este teste, guardada fora do nosso código, e apagaremos ao
> final, conforme combinarmos por escrito. Se preferirem, fazemos o teste ao vivo, com o
> arquivo na máquina de vocês.

## Durante o teste (45 a 60 minutos)

| Tempo | O que acontece | O que observar |
|---|---|---|
| 5 min | Contexto: o que a EULER faz e o que não faz (não comanda a caldeira) | Expectativas da pessoa |
| 20 min | A pessoa abre a própria planilha e a importa em **Dados**, pensando em voz alta. Não ajudar, a menos que trave por mais de 3 minutos | Onde para, o que pergunta, que nomes de coluna não reconhece, unidades confusas |
| 10 min | Abrir **Financeiro** e **Minha planta** com os dados importados (ou a demonstração, se a importação não fechar) | O que entende do quadro da conta e do percurso sem explicação |
| 10 min | Pergunta central: "Com os registros que vocês possuem hoje, qual destas respostas ajudaria numa decisão real?" | Qual resposta, que decisão, quem decide |
| 5 min | Fechamento: o que faltou, o que faria abandonar a ferramenta, próximo passo concreto | Compromisso real × elogio |

## Registro da observação

Preencher logo depois, sem dados do cliente (só contagens e descrições):

| Campo | Anotação |
|---|---|
| Data, empresa (código), cargo de quem usou | |
| Formato do arquivo (CSV, Excel, abas, células mescladas) | |
| Tempo até a primeira prévia (min) | |
| Colunas associadas automaticamente / à mão / sem correspondência | |
| Unidades confirmadas ou corrigidas | |
| Registros que existem (diário, recebimentos, estoque, umidade, água, gases, eventos) e frequência | |
| Registros que não existem e travam análises (ex.: estoque nas datas de corte) | |
| Onde travou e por quê | |
| Resposta que ajudaria numa decisão real, e qual decisão | |
| Disposição a continuar (piloto, pagamento, nenhum) | |

## Limites atuais que vale conferir no teste

Da importação guiada (`docs/desenvolvimento/importacao_financeiro_2026-10-06.md`, D106 e D107):
CSV ou `.xlsx`; não lê PDF de notas nem planilhas de apresentação (gráficos, quadros soltos); o
mapeamento exige revisão humana. Já reconhece título acima do cabeçalho, cabeçalho em duas linhas
(células mescladas), um mês por aba, recebimentos e estoque em abas separadas, Data e Hora
separadas, nomes comuns de fábrica e unidades como kgf/cm², psi, °F e t/h. Anotar quais colunas a
EULER não sugeriu sozinha: é o que falta no vocabulário de fábrica. Em Minha planta › Dados ›
Histórico › "Atendimento desta caldeira" ficam o tempo na tela e os ajustes à mão de cada envio
(D109): anotar também esses números, que substituem as faixas assumidas de
`docs/produto/escala_atendimento.md`. Se a planilha
real esbarrar nesses limites, anotar exatamente como ela é, para virar tarefa.

## Depois do teste

- Registrar o resultado em `docs/produto/` sem dados do cliente e abrir as tarefas que surgirem.
- Apagar o arquivo da amostra conforme o combinado e registrar a data.
- Atualizar as decisões D101 e D102 com o que a pessoa entendeu, ou não, do quadro da conta e do
  percurso.
