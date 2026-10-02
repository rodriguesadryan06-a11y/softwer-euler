# Mapa de fontes públicas para validação externa

Pesquisa feita em 02/10/2026. O objetivo é separar **dados industriais realmente medidos**
de exemplos didáticos, simulações e falhas injetadas.

| Fonte | Natureza | Combustível | O que há de útil | Limite para a EULER | Uso agora |
|---|---|---|---|---|---|
| Hu et al., Scientific Data 2025 / Figshare 10.6084/m9.figshare.28868849 | **real industrial**, 86.400 amostras, 30 tags, 5 s | carvão | pressão/temperatura/vazão de vapor, O₂, T de gases, ar, pressão de fornalha, ΔP, vibração | sem fluxo/PCI do combustível e sem T de água de alimentação suficientes para fechar eficiência | **materializado em amostra + testes** |
| Galloway 2026, Hugging Face `cfb-boiler-synthetic-fault-dataset` | derivado: prefixo real + falha sintética posterior | carvão | cópia pequena e acessível das tags do caso industrial | a parte de falha é sintética; só usamos linhas declaradas reais | **somente linhas 0–19 reais** |
| Alitasb, Mendeley Data 10.17632/g5t4yxymy7.1 | **real medido**, Wonji Sugar Factory | biomassa/bagaço | 4 entradas (2 ares, água, stoker) + 3 saídas (T, P, nível) | não fecha combustível→vapor; arquivo bruto/unidades ainda precisam ser conferidos antes de adaptar | candidato prioritário |
| Alitasb & Salau, Energy Reports 2024, 10.1016/j.egyr.2023.11.063 | artigo associado ao caso Wonji | biomassa/bagaço | confirma que o modelo foi obtido de dados medidos da planta; ajuda a interpretar as variáveis | artigo não substitui o arquivo bruto | referência |
| Bureau of Energy Efficiency, *Energy Performance Assessment of Boilers* | benchmark publicado de ensaio direto | carvão | vazão de vapor, pressão, entalpias, carvão, GCV e eficiência publicada | eficiência está em **GCV/HHV**, enquanto a EULER atual usa **PCI/LHV** | **checagem independente das entalpias, não da eficiência** |
| OP-50, Applied Thermal Engineering (dados 2019) | dados medidos descritos no artigo, 1 min | carvão | pressão/vazão/T de vapor, água, ar, gases e O₂ por meses | série bruta não foi localizada publicamente nesta rodada | candidato se conseguirmos autorização/arquivo |

## Descobertas importantes para o desenho do produto

1. **Historiador real não significa balanço fechável.** O caso Zhejiang é rico em SCADA e
   ainda assim não possui no recorte público tudo que a EULER exige para energia do combustível.
2. **Topologia de sensores importa.** No caso Zhejiang, O₂ e temperatura de gases aparecem
   descritos em posições diferentes do economizador. Combinar os dois como se fossem o mesmo
   ponto criaria um estado físico fictício.
3. **Vazão instantânea é comum.** O dataset publica vazão principal de vapor; a EULER hoje
   usa totalizador como caminho principal. Isso deve ser tratado como requisito/adapter futuro,
   não convertido silenciosamente.
4. **Base calorífica importa.** Benchmarks em GCV/HHV não podem ser usados como golden de um
   cálculo em PCI/LHV sem conversão física documentada.
5. O primeiro piloto industrial continua necessário: nenhum conjunto público encontrado nesta
   rodada contém simultaneamente combustível medido/qualificado, vapor, água de alimentação,
   instrumentação, eventos de intervenção e M&V suficientes para validar a cadeia inteira.
