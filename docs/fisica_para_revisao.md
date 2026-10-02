# EULER · Física e cálculos para revisão científica

**Para:** doutorandos/professores revisores (termodinâmica, combustão, química).
**Objetivo:** validar cada equação, hipótese e valor de referência antes que vire código. Cada item tem um código (E1, E2…), que é citado nas docstrings do software. Quando um item for aprovado, ele vira teste automático em `tests/golden/`, que os agentes de programação não podem alterar.

**Como revisar:** para cada item, marque uma opção e, se houver correção, escreva a forma correta e a referência bibliográfica.

| Status | Significado |
|---|---|
| ☐ Aprovado | pode virar código e teste como está |
| ☐ Aprovado com ressalva | vale dentro do domínio indicado |
| ☐ Corrigir | escrever a versão correta |
| ☐ Fora do escopo | não usar no protótipo |

Convenções: frações mássicas em **base seca** (C, H, O, N, S, cinzas); umidade `w` em **base úmida** (kg de água / kg de combustível úmido); pressões em **bar absoluto**; energia em MJ; referência térmica `T_ref = 25 °C`.

---

## Bloco A · Combustão e perda nos gases

**E1 · Oxigênio estequiométrico** (kmol O₂ por kg de combustível seco)
`a = C/12 + H/4 + S/32 − O/32`
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E2 · Razão de ar λ a partir do O₂ medido em base seca** (combustão completa, ar seco 21/79)
Gases secos por kg seco: `n_CO2 = C/12`, `n_SO2 = S/32`, `n_O2 = (λ−1)a`, `n_N2 = (79/21)λa + N/28`.
`y_O2 = n_O2 / (n_CO2 + n_SO2 + n_O2 + n_N2)` → resolver para λ (forma fechada no código de referência).
Pergunta: ignorar CO e incombustos no cálculo de λ é aceitável quando CO < ~200 ppm?
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E3 · Massa de gases secos** (kg/kg seco)
`m_gs = 44·n_CO2 + 64·n_SO2 + 32·n_O2 + 28·n_N2`
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E4 · Água nos gases** (kg/kg seco)
`m_H2O = 9H + w/(1−w)`
Pergunta: incluir a umidade do ar de combustão? (hoje: não)
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E5 · PCI úmido** (MJ/kg úmido)
`PCI_u = (1−w)·PCI_seco − 2,442·w`
Pergunta: 2,442 MJ/kg a 25 °C é a convenção correta para PCI? O PCI_seco já desconta a água formada pelo H?
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E6 · Perda sensível nos gases, base PCI, por kg seco**
`q_g = [m_gs·∫cp_gs dT + m_H2O·∫cp_H2O(v) dT] (de T_ar a T_g) / (PCI_seco − 2,442·w/(1−w))`
- Modo **referência** (só para teste): cp constantes 1,05 kJ/kg·K (gases secos) e 1,90 kJ/kg·K (vapor d'água).
- Modo **motor**: cp(T) por espécie. **Fonte proposta para cp(T): a definir pelo revisor** (ex.: polinômios NASA/Shomate do NIST).
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E7 · Domínio de validade da perda nos gases**
- Não calcular se `T_g` < ponto de orvalho estimado dos gases (condensação).
- Plausibilidade: sem economizador ou pré-aquecedor, `T_g` deve ficar acima de `T_sat(p) + aproximação mínima`. Ex.: a 10 bar abs, T_sat ≈ 179,9 °C. Qual aproximação mínima (°C) usar como alerta?
Revisor: ☐ ☐ ☐ ☐ · Observações:

**Valores de referência a conferir** (composição C 50%, H 6%, O 43%, N 0,3%, S 0,05%, base seca; PCI_seco 18,5 MJ/kg; T_ar 25 °C; cp constantes):

| Caso | T_g (°C) | O₂ seco (%) | w | λ | Perda (%) |
|---|---|---|---|---|---|
| G01 referência | 180 | 8 | 0,40 | 1,611 | **11,773** |
| G02 | 150 | 8 | 0,40 | 1,611 | 9,494 |
| G03 | 210 | 8 | 0,40 | 1,611 | 14,052 |
| G04 | 250 | 8 | 0,40 | 1,611 | 17,090 |
| G05 | 180 | 4 | 0,40 | 1,234 | 9,611 |
| G06 | 180 | 6 | 0,40 | 1,397 | 10,548 |
| G07 | 180 | 10 | 0,40 | 1,903 | 13,444 |
| G08 | 180 | 8 | 0,30 | 1,611 | 10,979 |
| G09 | 180 | 8 | 0,45 | 1,611 | 12,307 |
| G10 | 180 | 8 | 0,50 | 1,611 | 12,981 |
| G11 | 180 | 8 | 0,3104 | 1,611 | 11,049 |
| G12 | 292,2 | 8 | 0,3104 | 1,611 | 19,047 |

Sensibilidades derivadas (para conferência): ≈0,076 p.p./°C; ≈0,71 p.p. por ponto de O₂ (entre 6 e 10%); ≈0,10 p.p. por ponto de umidade.
Peça ao revisor: recalcular **G01, G05 e G10 de forma independente** (planilha, EES ou à mão) e registrar o valor obtido.

---

## Bloco B · Vapor e balanço direto

**E8 · Energia útil do vapor**
`Q_s = Σ M_s · (h_s(p, T ou x) − h_a(p, T_a))`, entalpias pela IAPWS-IF97.
- Pressão manométrica → absoluta: `p_abs = p_man + p_atm(local)`. Qual `p_atm` usar sem barômetro (altitude do local)?
- Referência: 10 bar abs, vapor saturado seco, água de alimentação a 80 °C → **Δh = 2,4414 MJ/kg**; T_sat = 179,89 °C.
- Implementação atual: se `estado_vapor` for registrado como `superaquecido`, usa `t_vapor_c`; se for `umido`, exige `titulo_vapor_frac`; se o estado não for registrado, mantém x = 1 como hipótese explícita `assumido`. Estados diferentes ou registro parcial no mesmo período bloqueiam o balanço, em vez de serem combinados.
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E9 · Combustível queimado no período**
`M_f = estoque_inicial + Σ recebimentos − estoque_final` (mesma base de umidade)
Pergunta: como propagar a incerteza de estoque medido por volume (densidade aparente)?
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E10 · Energia do combustível e eficiência direta**
`E_f = Σ M_f,i · PCI_u,i` · `η_D = Q_s / E_f` (mesmo período e mesma fronteira)
Pergunta: a purga deve entrar como saída de energia útil, perda ou ficar fora da fronteira?
Revisor: ☐ ☐ ☐ ☐ · Observações:

---

## Bloco C · Extrato de energia por fornecedor (novo, motor M1)

**E11 · Energia entregue por lote e custo por energia**
- Energia do lote: `E_lote = M_lote · PCI_u(w_lote)` (MJ)
- Custo por energia: `R$/GJ = preço_total_lote / (E_lote/1000)`
- Exemplo (PCI_seco 18,5; 30 t por lote):

| Fornecedor | w | R$/t úmida | PCI_u (MJ/kg) | Energia (GJ) | R$/GJ |
|---|---|---|---|---|---|
| F1 | 0,38 | 180 | 10,542 | 316,3 | 17,07 |
| F2 | 0,45 | 170 | 9,076 | 272,3 | 18,73 |
| F3 | 0,52 | 160 | 7,610 | 228,3 | 21,02 |

O mais barato por tonelada é o mais caro por energia. Perguntas ao revisor:
- Qual a incerteza típica de umidade por estufa (ISO 18134) e por medidor portátil?
- Quantas amostras por lote para representar a umidade (amostragem)? *(Área de afinidade com a pesquisadora de pós-colheita.)*
- O PCI_seco pode ser assumido constante por fornecedor, ou precisa de amostra periódica?
Revisor: ☐ ☐ ☐ ☐ · Observações:

---

## Bloco D · Lógica de investigação (não é só fórmula)

**E12 · Independência dos dois caminhos.** Balanço direto (E8–E10) e perda nos gases (E1–E6) só contam como "duas evidências" se não compartilharem a mesma medição ou premissa (ex.: a mesma umidade assumida). O software deve marcar quando compartilham.
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E13 · Não circularidade.** A eficiência é **resultado** de E10; nunca pode ser entrada para calcular combustível ou energia útil no mesmo período.
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E14 · Decomposição do custo.** `custo = preço × intensidade` (R$/GJ × GJ/t de vapor). Variação por preço não pode ser chamada de perda de eficiência.
Revisor: ☐ ☐ ☐ ☐ · Observações:

**E15 · Incerteza e menor mudança detectável.** Propagação de primeira ordem (derivadas parciais) com incertezas declaradas dos instrumentos. Hipótese atual de menor mudança detectável na perda nos gases, 1 semana com leituras a cada 2 h: ≈0,8 p.p. com umidade medida por entrega e ≈1,4 p.p. sem medir umidade.
Pergunta: método aceitável para o protótipo (primeira ordem vs Monte Carlo)?
Revisor: ☐ ☐ ☐ ☐ · Observações:

---

## Registro da revisão

| Revisor | Área | Itens revisados | Data | Assinatura/e-mail |
|---|---|---|---|---|
| | | | | |

Toda correção aprovada vira: (1) ticket no backlog, (2) atualização de `tests/golden/`, feita **por uma pessoa**, com o nome do revisor no commit.
