# Validação com dados públicos reais

Esta pasta existe para responder a uma pergunta simples: **o motor continua fisicamente coerente quando recebe telemetria industrial que não foi criada por nós?**

## Caso materializado: Zhejiang, China

O arquivo `zhejiang_real_sample.csv` contém 20 linhas do prefixo **real operacional** de um conjunto público de uma caldeira industrial a carvão. A publicação original descreve uma caldeira de uma planta química em Zhejiang, 30 variáveis, amostragem a cada 5 s e 86.400 amostras entre 27/03/2022 e 01/04/2022. O repositório original do artigo no Figshare é CC0.

Para facilitar uma amostra pequena e reprodutível no CI, materializamos as linhas 0–19 do espelho/derivado público no Hugging Face. O cartão desse conjunto declara que as linhas 0–599 são operação real e que a janela posterior de falha é sintética. **Nenhuma linha de falha sintética foi incluída aqui.**

### O que este caso testa

- conversão explícita de psig → bar(g) → bar(a);
- °F → °C e kpph → t/h;
- coerência do estado de vapor superaquecido com IAPWS-IF97;
- compatibilidade do importador da EULER com uma fatia de telemetria real;
- invariantes físicos simples: O₂ em 0–21%, vazão/pressão positivas e T do vapor acima da saturação;
- consistência independente com a faixa normal de 530–545 °C publicada no artigo.

### O que este caso **não** prova

Ele **não valida a eficiência global da EULER**. Esse dataset não entrega massa/qualidade do combustível nem temperatura da água de alimentação suficientes para fechar o balanço direto do produto. Também não valida causa raiz, economia ou M&V.

Há ainda uma limitação real descoberta pelo dataset: o O₂ é descrito na **entrada do economizador**, enquanto a temperatura de gases usada no recorte vem da **saída do economizador**. A EULER não deve fingir que essas duas medições pertencem ao mesmo estado termodinâmico do gás. Por isso, este fixture não é usado para calcular perda de chaminé.

## Benchmark externo de propriedades: Bureau of Energy Efficiency

Também foi materializado `bee_direct_method_benchmark.json`, baseado no exemplo medido publicado pelo Bureau of Energy Efficiency da Índia. Usamos esse caso **somente** para conferir as entalpias de vapor e água calculadas pela IF97 contra os valores publicados.

A eficiência de 72,5% publicada **não é usada como golden da EULER**, porque aquele exemplo está em base GCV/HHV enquanto o caminho direto atual da EULER foi definido em PCI/LHV. Misturar as bases produziria uma validação falsa.

## Segundo candidato real: Wonji Sugar Factory

Também foi localizado o dataset público **31.5 MW Wonji sugar factory steam drum data** (Mendeley Data, DOI 10.17632/g5t4yxymy7.1, CC BY 4.0), medido numa caldeira de biomassa e descrito como 4 entradas / 3 saídas. Ele é especialmente interessante por ser biomassa, mas não foi materializado aqui sem obter e conferir o arquivo bruto e suas unidades. A ausência de um arquivo local é deliberada: **não inventamos colunas nem unidades para fazer o teste caber.**

## Regra

Dados reais públicos podem provar compatibilidade, revelar lacunas e falsificar hipóteses do motor. Eles não substituem o primeiro caso industrial autorizado da EULER.
