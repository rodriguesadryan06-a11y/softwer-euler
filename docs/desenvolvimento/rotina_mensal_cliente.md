# Rotina mensal do cliente — 07/10/2026

O acompanhamento recorrente entrega uma conta conferível, uma próxima verificação e memória
das decisões. A existência desse fluxo sustenta uma proposta de assinatura; retenção e
disposição a pagar ainda precisam ser medidas em uso com clientes.

## Mudanças

- Um único mês selecionado alimenta o cabeçalho e os valores. Mês sem fechamento fica sem
  números; não busca automaticamente um mês anterior com conta disponível.
- Próximo passo conforme a situação: atualizar dados, conferir/aprovar, revisar ou acompanhar ações.
- Contas parciais e períodos sem aprovação ficam explícitos. Ausência de preço tem motivo;
  não se transforma em zero. A soma mensal não recebe classificação estatística inventada.
- Autoria, data, revisão dos dados e vínculo com versão anterior disponíveis no resumo.
- Histórico mensal com custo atribuído ao consumo, custo esperado, diferença estimada,
  situação e responsáveis; exportação CSV. Somente fechamentos vigentes entram na tabela.
- O cache considera a data local para que a virada de mês atualize a situação.

## Limites preservados

A atribuição de períodos ao mês segue D111: cada período entre estoques pertence ao mês em
que termina. Cobertura dentro do calendário e dias de outro mês ficam identificados. Não
há rateio inventado dos dias sem estoque. O nome do autor é informado localmente, não uma
assinatura autenticada. A aprovação registra a conta, não confirma causa física ou economia.
Não foram alteradas equações físicas, golden ou tolerâncias.

## Verificação

- 85 testes da base: mensal, condições, dia a dia, preço, fechamento/prévia, acompanhamento,
  armazém e persistência. Todos passaram; não equivale à suíte inteira do projeto.
- 10 testes de interface/seleção de mês passaram, incluindo outubro sem fechamento e retorno
  a setembro sem reutilizar valores de outro mês.
- 11 testes finais de seleção e resumo mensal passaram: autoria, revisão, preço ausente,
  cobertura parcial e versões vigentes. Há sobreposição entre essas baterias.
- O ensaio integrado único de vários meses mencionado no PDF continua pendente. Os testes
  separados não devem ser apresentados como execução desse ensaio.

## Validação comercial sugerida

Observar com um usuário da planta se ele identifica sozinho o mês, a cobertura, os valores
e a próxima ação. Medir tempo para preparar/conferir o fechamento, frequência de retorno,
ações acompanhadas e renovação. Não atribuir economia ao software sem verificação da ação.

## Correção dos cliques nas abas

O cabeçalho fixo e transparente do Streamlit ocupava os primeiros 60 px da tela.
As abas começavam em 34,4 px, e a barra interceptava os cliques. O espaço superior
agora é de 4,75 rem, inclusive em telas estreitas; as abas começam abaixo da barra.

Verificação: falha reproduzida no navegador antes da alteração; depois, abertura de
Investigação e Financeiro por clique, além de teste da área clicável das seis abas
de Análise em tela normal e de 390 px (menu lateral recolhido). Os quatro testes
de navegação e o lint/formatação do arquivo alterado passaram. AppTest verifica as
rotas, mas não detecta sobreposição visual; o teste no navegador é necessário.
