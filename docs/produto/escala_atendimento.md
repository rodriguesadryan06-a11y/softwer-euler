# Escala do atendimento: do envio ao primeiro fechamento

> Gerado por `python scripts/medir_escala.py` (D109). Dados **sintéticos**, feitos a partir do caso de demonstração. Tempo de máquina **medido**; ajustes e confirmações **contados**; tempo de pessoa **assumido** (faixa explícita abaixo), até o registro de atendimento medir clientes reais.

Máquina da medição: Linux · 4 núcleos · Python 3.11.15.

## Resposta curta

- **Máquina (medido):** do envio ao primeiro fechamento, 11 a 14 s por cliente; no mês seguinte, 8 a 13 s.
- **Ajustes à mão no primeiro envio (contado):** Modelo EULER 0, Planilha de fábrica 0, Um mês por aba 0, Supervisório + balança 7, Abreviações sem unidade 24.
- **Ajustes à mão no mês seguinte (contado):** Modelo EULER 0, Planilha de fábrica 0, Um mês por aba 0, Supervisório + balança 0, Abreviações sem unidade 12.
- **Pessoa (assumido, não medido):** 4 a 23 min no primeiro envio; 3 a 14 min nos meses seguintes.
- **Conta simples sobre o tempo medido:** com 9 s de máquina por cliente por mês (mediana), 100 clientes somam cerca de 15 min de máquina por mês, um cliente por vez, num computador como o da medição.

## Primeiro envio → primeiro fechamento

| Cliente (formato) | Arquivos/abas | Colunas | Usadas | Ajustes à mão | Confirmações | Máquina (s) | Pessoa (min, assumido) | Fechamento |
|---|---|---|---|---|---|---|---|---|
| Modelo EULER | 5 | 59 | 59 | 0 | 5 | 11.3 | 4–11 | Diferença dentro da incerteza: sem mudança de desempenho estabelecida. |
| Planilha de fábrica | 6 | 54 | 52 | 0 | 5 | 13.3 | 4–13 | Diferença dentro da incerteza: sem mudança de desempenho estabelecida. |
| Um mês por aba | 6 | 61 | 60 | 0 | 5 | 14.0 | 4–13 | Diferença dentro da incerteza: sem mudança de desempenho estabelecida. |
| Supervisório + balança | 5 | 41 | 40 | 7 | 5 | 13.1 | 5–15 | Diferença dentro da incerteza: sem mudança de desempenho estabelecida. |
| Abreviações sem unidade | 5 | 34 | 33 | 24 | 5 | 11.0 | 8–23 | Consumo acima da referência ajustada (estabelecido pelas medições). |

## Envio do mês seguinte → próximo fechamento

O cliente manda o mesmo arquivo, atualizado. O que já estava gravado é reconhecido e ignorado; o mapeamento salvo no primeiro envio é reaproveitado.

| Cliente (formato) | Ajustes à mão | Confirmações | Registros novos | Máquina (s) | Pessoa (min, assumido) |
|---|---|---|---|---|---|
| Modelo EULER | 0 | 4 | 287 | 8.2 | 3–8 |
| Planilha de fábrica | 0 | 4 | 287 | 13.1 | 3–10 |
| Um mês por aba | 0 | 4 | 284 | 9.1 | 3–10 |
| Supervisório + balança | 0 | 4 | 284 | 11.0 | 3–8 |
| Abreviações sem unidade | 12 | 4 | 284 | 9.1 | 5–14 |

## Tempo de máquina por etapa (s)

| Cliente | Envio | leitura e lote | prévia | confirmação | referência | fechamento |
|---|---|---|---|---|---|---|
| Modelo EULER | primeiro | 0.1 | 1.4 | 0.1 | 2.1 | 7.5 |
| Modelo EULER | seguinte | 0.2 | 1.4 | 0.0 | — | 6.6 |
| Planilha de fábrica | primeiro | 1.4 | 1.2 | 0.1 | 2.5 | 8.1 |
| Planilha de fábrica | seguinte | 2.1 | 1.9 | 0.1 | — | 9.0 |
| Um mês por aba | primeiro | 1.7 | 1.3 | 0.1 | 2.3 | 8.6 |
| Um mês por aba | seguinte | 1.6 | 1.5 | 0.0 | — | 6.0 |
| Supervisório + balança | primeiro | 0.7 | 1.3 | 0.1 | 2.0 | 9.0 |
| Supervisório + balança | seguinte | 1.4 | 2.1 | 0.1 | — | 7.4 |
| Abreviações sem unidade | primeiro | 0.9 | 1.2 | 0.1 | 1.9 | 6.9 |
| Abreviações sem unidade | seguinte | 1.1 | 1.4 | 0.0 | — | 6.6 |

## Onde estão os ajustes à mão

- **Modelo EULER**, primeiro envio: nenhum.
- **Modelo EULER**, mês seguinte: nenhum.
- **Planilha de fábrica**, primeiro envio: nenhum.
- **Planilha de fábrica**, mês seguinte: nenhum.
- **Um mês por aba**, primeiro envio: nenhum.
- **Um mês por aba**, mês seguinte: nenhum.
- **Supervisório + balança**, primeiro envio: “export_scada_caldeira1.csv” (colunas 7).
- **Supervisório + balança**, mês seguinte: nenhum.
- **Abreviações sem unidade**, primeiro envio: “leituras.xlsx::Plan1” (tabela 1, colunas 7, unidades 7); “leituras.xlsx::Plan2” (colunas 3, unidades 1, valores_unicos 1); “leituras.xlsx::Plan3” (colunas 1, valores_unicos 1); “leituras.xlsx::Plan4” (colunas 1, unidades 1).
- **Abreviações sem unidade**, mês seguinte: “leituras.xlsx::Plan1” (tabela 1, unidades 7); “leituras.xlsx::Plan2” (unidades 1, valores_unicos 1); “leituras.xlsx::Plan3” (valores_unicos 1); “leituras.xlsx::Plan4” (unidades 1).

## Achados da medição (07/10/2026)

1. **Corrigido na importação.** Na primeira rodada, a planilha de fábrica pedia 11 ajustes, o mês por aba 13 e o supervisório 16. Causas: a hora dos recebimentos e das amostras se perdia ("Data" era associada sozinha e a junção Data + Hora não era oferecida); "(s)" e contagem sem unidade sugerida; "Estoque medido (t)" sem regra; o tipo (recebimento ou estoque) não vinha do nome da aba; o cadastro de instrumentos não tinha vocabulário ("Tag", "Incerteza"). As regras novas valem para qualquer planilha, não só para estes cenários.
2. **Sem cadastro de instrumentos, o fechamento não classifica a diferença** ("sem faixa de incerteza"). O cadastro entra uma vez, na implantação.
3. **Unidade que não está escrita no cabeçalho é confirmada a cada envio** (pior caso: 12 re-confirmações por mês). Lembrar a unidade junto do mapeamento salvo zeraria esse custo, mas é decisão de produto: proposta pendente em D109.
4. **Sem PCI do laboratório, a mesma operação muda de situação.** Com PCI, a conta separa o efeito do combustível mais úmido e o resto fica dentro da incerteza; só com a umidade, esse efeito fica ausente e o período aparece como "acima da referência ajustada (estabelecido)". A conta está coerente com o que foi medido, mas a frase pode ser lida como problema da caldeira: pergunta para a revisão em D109.
5. **Os mesmos dados dão a mesma conta em qualquer formato**: o consumo por tonelada de vapor é igual nos cinco clientes (as conversões de unidade e Data + Hora não mudam a conta).

## Cenários

- **Modelo EULER**: CSVs com os nomes do modelo (diário, combustível, amostras, eventos, instrumentos).
- **Planilha de fábrica**: Um Excel com título em cima, nomes de fábrica com unidade, Data e Hora separadas; recebimentos, estoque, laboratório, ocorrências e instrumentos em abas.
- **Um mês por aba**: Diário com uma aba por mês e cabeçalho em duas linhas (células mescladas); lenha em outro arquivo, com recebimentos e estoque em abas separadas; instrumentos à parte.
- **Supervisório + balança**: CSV exportado do supervisório com tags de instrumento (PT-101, TT-102…), ";" e vírgula decimal; lenha e instrumentos em planilhas à parte.
- **Abreviações sem unidade**: Abas "Plan1…Plan4" com cabeçalhos curtos ("Press", "T1", "T2", "O2", "Kg") e nenhuma unidade escrita: o pior caso realista para o reconhecimento automático.

## Como ler

- **Ajuste à mão**: cada campo que a pessoa precisou mudar ou preencher na conferência (tabela, linha do cabeçalho, junção Data + Hora, associação de coluna, unidade, valor único como o tipo dos registros). Contado comparando o que a tela traz preenchido com o gabarito do cenário.
- **Confirmações**: cliques fixos do caminho (Conferi as colunas, as unidades e a origem; Preparar prévia; Confirmar registros novos; Definir a referência (período e motivo); Produzir o fechamento). No mês seguinte não há referência a definir.
- **Pessoa (assumido)**: faixa calculada com tempos ASSUMIDOS por ação — ajuste 10–30 s; fonte 30–90 s; confirmacao 3–10 s; referencia 60–180 s. Não é medição; serve só para ordem de grandeza até o registro de atendimento (Dados → Histórico → Atendimento) medir clientes reais.
- O tempo de calendário até o primeiro fechamento depende de o cliente já ter semanas suficientes de dados (referência + um período novo). Aqui, ele já tinha: tudo acontece no mesmo dia.

## Limites

- Dados sintéticos e formatos montados a partir do que fábricas costumam mandar; planilhas reais trazem variações que estes cenários não cobrem.
- Tempo de máquina medido num único computador, um cliente por vez; não inclui envio pela rede nem espera de servidor.
- Nos formatos de fábrica não há cadastro de instrumentos: o fechamento sai, mas com a incerteza dos instrumentos desconhecida, como no uso real.
