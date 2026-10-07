# Importação guiada e conta da planta

Implementação de 06/10/2026. Continuação da organização da interface, com foco em entrada de dados e explicação financeira. Reaproveita o banco por planta, o contrato de dados, o motor e os fechamentos existentes.

## Como usar

**Para acompanhar uma empresa:** abra **Dados**, selecione a planta e o equipamento, envie CSV ou Excel e mantenha **Adaptar minha planilha** habilitado. Confira o tipo de registro, a associação das colunas, as unidades e a origem. Prepare a prévia e confirme os registros novos. Dados de cliente continuam exigindo uma planta autorizada; repetições e conflitos seguem as regras do armazém.

**Para uma análise avulsa:** no Início, use **Importar um arquivo**. O mesmo guia prepara uma prévia com qualidade e análises disponíveis. Confirme para substituir os dados da sessão. Sem salvar na planta, a importação continua temporária.

**Para consultar a conta salva:** abra **Financeiro → Fechamentos da planta** e escolha planta, equipamento e fechamento. A tela lê o resultado gravado; não recalcula o passado com preços atuais e não mistura os dados da sessão. Para comparar arquivos temporários, escolha **Dados desta sessão**.

## Entrada mais simples, com original preservado

- Nomes próprios de arquivos e abas são aceitos. As sugestões de colunas usam nomes, rótulos e aliases explícitos do contrato, sem adivinhação por IA.
- Conversões dimensionais permitidas precisam de confirmação: por exemplo, toneladas para kg, kg/h para t/h e K para °C. Pressão absoluta não é confundida com manométrica, e preço por tonelada não vira valor total de nota.
- Ausentes permanecem ausentes. Origem e identificação de caldeira já declaradas no arquivo não podem ser substituídas silenciosamente.
- Prévia e confirmação dependem do conteúdo, das escolhas e da altitude. Trocar o conteúdo de um arquivo com o mesmo nome invalida a prévia anterior.
- O lote guarda os bytes originais, CSVs adaptados e manifesto com arquivo, aba, linha original, mapeamento, unidades, constantes declaradas e hashes. A persistência existente guarda esses anexos no mesmo banco da planta.
- Perfis reaproveitam o mapeamento de cabeçalhos por fonte e equipamento; unidades voltam a ser conferidas em cada envio.

## Financeiro mais legível

- Custo observado, custo esperado e desvio monetizado vêm do motor existente.
- Na análise da sessão, a variação é apresentada em três grupos: preço, produção/ajustes disponíveis e parcela ainda não explicada. A soma é conferida contra a decomposição original; inconsistência bloqueia o resumo.
- Compras usam o mesmo intervalo da comparação (`início < data ≤ fim`). Recebimentos, estoques, consumo e pagamento aparecem separados.
- Nota sem preço gera valor parcial identificado. Não vira gasto zero nem soma completa. Massa estimada permanece identificada.
- Fechamentos salvos exibem a próxima verificação, premissas, compras/estoques, rastreabilidade e download do relatório. Economia verificada aparece separadamente, no histórico inteiro do equipamento, com a proteção existente contra períodos sobrepostos.
- Textos da decomposição agora respeitam a política realmente usada: recebimentos do período, FIFO ou tabela de preços. Preço por energia originado de recebimentos não é herdado silenciosamente por outra política.

## Limites que permanecem

O guia exige uma fonte por tabela em cada envio e formatos CSV ou `.xlsx`. (Atualizado em 07/10/2026, D106: o cabeçalho pode estar abaixo de títulos, Data e Hora separadas são combinadas e há um vocabulário de fábrica explícito para as sugestões.) Não lê PDF de notas fiscais, não interpreta planilhas de apresentação com células mescladas e não calcula valores ausentes. Arquivos devem respeitar as grandezas disponíveis no contrato. O mapeamento exige revisão humana.

O desvio monetizado não demonstra, sozinho, prejuízo recuperável, causa física ou economia. Os critérios científicos e o protocolo proposto de verificação continuam sujeitos à revisão especializada. Os testes desta entrega verificam implementação e preservação de comportamento; não validam um piloto industrial.

Fechamentos antigos permanecem com seu resultado original. A correção de rótulos não regrava o histórico. Um novo fechamento usa as explicações atualizadas; a reprodução de um fechamento gerado por código anterior pode acusar diferença de hash, que deve permanecer visível.

Esta entrega não implementa servidor compartilhado, autenticação ou isolamento entre usuários online. O banco continua local, fora do repositório.

## Arquivos principais

- `app/importacao_guiada.py`: leitura, associação explícita, conversões, manifesto e formulário compartilhado.
- `app/paginas/importar.py` e `acompanhamento.py`: guia e prévia nos dois fluxos existentes.
- `app/financeiro.py` e `app/paginas/financeiro.py`: resumos de variação e compras, movimentação de estoque e escolha da origem da conta.
- `app/blocos/financeiro_planta.py`: consulta aos fechamentos por planta e equipamento.
- `euler/conta.py`, `fechamento.py`, `painel.py`: política de preço explícita e notas parciais no relatório.
- Novos testes de importação, financeiro, persistência e telas; extensões dos testes de conta e fechamento. Nenhum golden ou tolerância alterado.

## Validação

Resultados finais e revisão visual registrados em `PROGRESSO.md`. Os testes usam dados sintéticos e bancos temporários; não gravam nem corrigem dados de clientes.
