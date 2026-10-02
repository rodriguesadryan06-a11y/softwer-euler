# Contrato de dados · EULER

> Gerado automaticamente a partir de `euler/io/esquemas.py` por `python scripts/gerar_modelos.py`. **Não edite à mão**: mude o esquema e gere de novo.
> Derivado dos modelos de CSV do kit de construção; a spec v0.3 não estava disponível (ver D12 em `docs/decisoes.md`).

## Regras gerais

- **Um arquivo por tabela**, com o nome exato (`diario.csv`, `combustivel.csv`, `amostras.csv`,
  `eventos.csv`, `instrumentos.csv`), **ou** uma planilha `.xlsx` com uma aba por tabela
  (modelo: `templates/planilha_modelo_euler.xlsx`).
- **Separador:** vírgula (`,`) ou ponto-e-vírgula (`;`, padrão do Excel em português). Com
  ponto-e-vírgula, números podem usar vírgula decimal (`182,5`). Codificação UTF-8 ou Windows.
- **Vazio = não medido.** Nunca escreva 0 para "não medido". `-`, `s/d` e `n/a` também são
  lidos como vazio (com aviso).
- **Datas e horas:** ISO 8601 com fuso (`2026-10-05T08:00:00-03:00`). Também é aceito
  `05/10/2026 08:00` (dia/mês/ano); sem fuso, assume-se o horário de Brasília, com aviso.
- **Unidade no nome da coluna.** A pressão do diário é **manométrica** (`p_vapor_bar_man`); a
  EULER converte para absoluta com a pressão atmosférica do local (altitude ou barômetro).
- **Umidade em fração, base úmida** (`0,38` = 38%). Composição em fração, base seca.
- **`origem_dado`:** `sintetico`, `publico` ou `real`. Dados reais de clientes nunca entram no
  repositório do código.
- **O que o importador faz:** guarda o arquivo original; converte unidades; lista avisos com
  linha e motivo (lacunas, duplicatas, totalizador reiniciado, registro tardio, unidades
  suspeitas, volume sem densidade). **Nada é preenchido, interpolado ou corrigido em silêncio.**

## Tabelas

### `diario.csv` · Diário do operador

Uma linha por leitura do operador (ou do sistema) na caldeira.

| Coluna | Unidade | Obrigatória | Descrição | Exemplo | Faixa plausível (só aviso) |
|---|---|---|---|---|---|
| `caldeira_id` | — | sim | Identificação da caldeira. | `CALD-SINT-01` |  |
| `instante_observado` | data e hora com fuso | sim | Quando a leitura foi feita (ISO 8601). | `2026-10-05T08:00:00-03:00` |  |
| `instante_registrado` | data e hora com fuso | não | Quando a leitura foi anotada. Serve para detectar registro tardio. | `2026-10-05T08:05:00-03:00` |  |
| `turno` | — | não | Turno (A, B, C…). | `A` |  |
| `operador_id` | — | não | Código do operador. | `OP-01` |  |
| `regime` | — | não | Situação da caldeira na leitura. Valores: `estavel`, `transitorio`, `partida`, `parada`. | `estavel` |  |
| `p_vapor_bar_man` | bar manométrico | não | Pressão do vapor lida no manômetro. | `9.0` | 0 a 40 |
| `t_gases_c` | °C | não | Temperatura dos gases na chaminé. | `182` | 50 a 450 |
| `ponto_gases_id` | — | não | Ponto onde a temperatura dos gases é medida. | `CHAMINE-1` |  |
| `o2_seco_pct` | % em base seca | não | Oxigênio nos gases secos. | `8.1` | 1 a 20,50 |
| `instrumento_o2_id` | — | não | Analisador usado na leitura de O₂ (ver instrumentos.csv). | `ANALIS-01` |  |
| `co_ppm` | ppm | não | Monóxido de carbono nos gases. |  | 0 a 20.000 |
| `t_agua_alim_c` | °C | não | Temperatura da água de alimentação. | `80` | 5 a 180 |
| `t_ar_c` | °C | não | Temperatura do ar de combustão. | `28` | -10 a 60 |
| `purgas_n` | contagem | não | Número de purgas desde a leitura anterior. | `1` | 0 a 50 |
| `purgas_s` | s | não | Duração total das purgas desde a leitura anterior. | `20` | 0 a 3.600 |
| `totalizador_vapor_t` | t (acumulado) | não | Leitura do totalizador de vapor (acumulado desde a instalação). | `15234.5` | 0 a 1.000.000.000 |
| `producao` | — | não | Observação livre sobre a produção da fábrica no momento. |  |  |
| `ocorrencia` | — | não | Ocorrência anotada pelo operador. |  |  |
| `flag_instrumento_indisponivel` | true/false | não | Marque true se algum instrumento estava fora de serviço nesta leitura. | `false` |  |
| `origem_dado` | — | não | De onde vem o dado. Dados reais de clientes nunca entram no repositório. Valores: `sintetico`, `publico`, `real`. | `sintetico` |  |
| `estado_vapor` | — | não | Estado termodinâmico do vapor na linha medida. Se vazio, a EULER mantém a hipótese conservadora atual de vapor saturado seco e marca essa hipótese como assumida. Valores: `saturado_seco`, `umido`, `superaquecido`. |  |  |
| `t_vapor_c` | °C | não | Temperatura do vapor quando o estado registrado é superaquecido. |  | 50 a 650 |
| `titulo_vapor_frac` | fração | não | Título x do vapor úmido (0 a 1). Só é usado quando o estado registrado é umido. |  | 0 a 1 |

### `combustivel.csv` · Combustível: recebimentos e estoques

Uma linha por recebimento de combustível (tipo = recebimento) ou por medição de estoque no pátio (tipo = estoque).

| Coluna | Unidade | Obrigatória | Descrição | Exemplo | Faixa plausível (só aviso) |
|---|---|---|---|---|---|
| `data` | data e hora com fuso | sim | Quando o recebimento ou a medição de estoque aconteceu. | `2026-10-05T10:30:00-03:00` |  |
| `tipo` | — | sim | recebimento ou estoque. Valores: `recebimento`, `estoque`. | `recebimento` |  |
| `fornecedor_id` | — | não | Código do fornecedor. | `F1` |  |
| `lote_id` | — | não | Código do lote; liga o recebimento às amostras. | `L-0001` |  |
| `massa_kg` | kg (como recebido, úmido) | não | Massa pesada na balança (ou estoque medido em massa). | `30000` | 100 a 1.000.000 |
| `volume_m3` | m³ | não | Volume, quando não há balança. Só vira massa com densidade declarada. |  | 0 a 5.000 |
| `densidade_kg_m3` | kg/m³ | não | Densidade aparente do combustível para converter volume em massa. |  | 100 a 1.200 |
| `origem_densidade` | — | não | De onde veio a densidade. Valores: `medida`, `declarada_fornecedor`, `assumida`. |  |  |
| `preco_brl` | R$ (total do lote) | não | Preço total pago pelo lote. | `5400.00` | 0 a 10.000.000 |
| `origem_dado` | — | não | De onde vem o dado. Dados reais de clientes nunca entram no repositório. Valores: `sintetico`, `publico`, `real`. | `sintetico` |  |

### `amostras.csv` · Amostras de combustível

Uma linha por amostra analisada (umidade e, quando houver, PCI e composição).

| Coluna | Unidade | Obrigatória | Descrição | Exemplo | Faixa plausível (só aviso) |
|---|---|---|---|---|---|
| `amostra_id` | — | sim | Código da amostra. | `A-0001` |  |
| `lote_id` | — | sim | Lote de onde a amostra foi tirada. | `L-0001` |  |
| `data` | data e hora com fuso | sim | Quando a amostra foi coletada. | `2026-10-05T11:00:00-03:00` |  |
| `umidade_bu_frac` | fração, base úmida | não | kg de água por kg de combustível úmido (0,38 = 38%). | `0.38` | 0,02 a 0,75 |
| `pci_seco_mj_kg` | MJ/kg seco | não | Poder calorífico inferior em base seca. | `18.5` | 10 a 35 |
| `C` | fração, base seca | não | Fração mássica de carbono em base seca. | `0.50` | 0 a 1 |
| `H` | fração, base seca | não | Fração mássica de hidrogênio em base seca. | `0.06` | 0 a 1 |
| `O` | fração, base seca | não | Fração mássica de oxigênio em base seca. | `0.43` | 0 a 1 |
| `N` | fração, base seca | não | Fração mássica de nitrogênio em base seca. | `0.003` | 0 a 1 |
| `S` | fração, base seca | não | Fração mássica de enxofre em base seca. | `0.0005` | 0 a 1 |
| `cinzas` | fração, base seca | não | Fração mássica de cinzas em base seca. | `0.0065` | 0 a 1 |
| `metodo` | — | não | Método de análise. | `estufa_ISO18134` |  |
| `laboratorio` | — | não | Quem analisou. | `interno` |  |
| `origem_dado` | — | não | De onde vem o dado. Dados reais de clientes nunca entram no repositório. Valores: `sintetico`, `publico`, `real`. | `sintetico` |  |

### `eventos.csv` · Eventos

Manutenções, limpezas, trocas de instrumento e outros fatos que mudam a caldeira.

| Coluna | Unidade | Obrigatória | Descrição | Exemplo | Faixa plausível (só aviso) |
|---|---|---|---|---|---|
| `instante` | data e hora com fuso | sim | Quando o evento aconteceu. | `2026-10-12T14:00:00-03:00` |  |
| `tipo` | — | sim | Tipo do evento. Valores: `limpeza`, `manutencao`, `troca_instrumento`, `calibracao`, `parada`, `partida`, `mudanca_combustivel`, `outro`. | `limpeza` |  |
| `descricao` | — | sim | O que foi feito. | `Limpeza dos tubos de fumaça` |  |
| `autorizado_por` | — | não | Quem autorizou. | `SUP-01` |  |
| `origem_dado` | — | não | De onde vem o dado. Dados reais de clientes nunca entram no repositório. Valores: `sintetico`, `publico`, `real`. | `sintetico` |  |

### `instrumentos.csv` · Instrumentos

Cadastro dos instrumentos usados nas leituras e sua incerteza declarada.

| Coluna | Unidade | Obrigatória | Descrição | Exemplo | Faixa plausível (só aviso) |
|---|---|---|---|---|---|
| `instrumento_id` | — | sim | Código do instrumento. | `ANALIS-01` |  |
| `tipo` | — | sim | Tipo do instrumento. | `analisador_o2` |  |
| `ponto` | — | não | Onde está instalado. | `CHAMINE-1` |  |
| `unidade` | — | sim | Unidade da leitura do instrumento (vale para resolução e incerteza). | `pct_seco` |  |
| `resolucao` | na unidade do instrumento | não | Menor variação que o instrumento mostra. | `0.1` | 0 a 1.000.000 |
| `incerteza_declarada` | na unidade do instrumento | não | Incerteza declarada pelo fabricante ou pela calibração. | `0.3` | 0 a 1.000.000 |
| `ultima_verificacao` | data | não | Data da última verificação ou calibração. | `2026-09-01` |  |
| `observacao` | — | não | Observação livre. | `sintetico` |  |
| `incerteza_tipo` | — | não | Como a incerteza foi declarada (padrao, expandida ou limite). Sem esta informação, a EULER supõe que o valor é um limite ±a (hipótese do projeto, D35) e usa u = a/√3 (modelo retangular do GUM 4.3.7); informe o tipo para evitar essa suposição. Valores: `padrao`, `expandida`, `limite`. |  |  |
| `incerteza_k` | — | não | Fator de abrangência k, quando a incerteza é expandida (ex.: 2). |  | 1 a 4 |
