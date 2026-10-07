/* ---------------------------------------------- Financeiro e Oportunidades (análise de um período) */
const md = (s) => e(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
const rs = (v) => (v === null || v === undefined ? "—" : (v < 0 ? "−" : "") + "R$ " + nf(Math.abs(v), 0));
const link = (tela, rotulo, ic = "seta") => `<button class="link" data-ir="${tela}">${icone(ic)} ${e(rotulo)}</button>`;

function telaFinanceiro() {
  const origem = estado.finOrigem || "sessao";
  const seletor = `${abas(["Dados desta sessão", "Fechamentos da planta"], origem === "sessao" ? 0 : 1, "fin-origem")}
    <p class="legenda">Dados desta sessão: análise temporária do arquivo carregado. Fechamentos da planta: a conta gravada de cada período.</p>`;
  if (origem === "planta") return cabecalho("Analisar um período", "Financeiro", "Entenda a conta do combustível e o que merece verificação.", false) + seletor + financeiroPlanta();
  const topo = cabecalho("Analisar um período", "Financeiro", "Entenda a conta do combustível e o que merece verificação.") + seletor;
  const c = combo();
  if (!c) return topo + periodosHtml() + foraDaPrevia();
  const f = c.fin;
  let h = `${topo}<p class="legenda">${e(f.cab)}</p><div>${link("investigacao", "Escolher períodos e ver investigação", "busca")}</div>`;
  if (f.motivo) {
    h += `<div class="alerta info">${icone("busca")}<div>${e(f.motivo)}</div></div>`;
  } else {
    const preco = f.quadro.consumido.preco_brl_t;
    h += `${quadroHtml(f.quadro)}
      <p class="legenda">${preco !== null && preco !== undefined ? `Preço do combustível: R$ ${nf(preco, 2)}/t · média ponderada dos recebimentos com preço e massa válidos. Custo atribuído não é pagamento confirmado.` : "Preço do combustível não informado no período: informe o valor total e a massa dos recebimentos para expressar a diferença em reais."}</p>
      <details><summary>Entender a faixa de incerteza</summary><div class="grade">${incertezaHtml(f.incerteza)}</div></details>
      <div>${link("oportunidades", "Ver as oportunidades em ordem de prioridade", "oportunidades")}</div>
      <details><summary>Por que a conta mudou · composição e premissas</summary><div class="grade"><p class="legenda">${e(f.variacao)}</p>
      ${tabela(["Parcela", "Pergunta", "Combustível", "Valor"], f.parcelas.map((l) => l.map(e)), [2, 3])}
      ${f.separacao ? `<p class="legenda">${e(f.separacao)}</p>` : ""}
      <details><summary>Premissas, faixas e cenários</summary><div class="grade" style="gap:8px">${f.premissas.map((x) => `<p>${md(x)}</p>`).join("")}${f.notas.map((x) => `<p class="legenda">${md(x)}</p>`).join("")}<p class="legenda">Economia comprovada: ainda não apurada. Depende de intervenção registrada e comparação posterior com a referência ajustada.</p></div></details></div></details>`;
  }
  const cp = A().compras;
  if (cp) {
    const max = Math.max(...cp.grupos.map((g) => g[1])) * 1.25;
    h += `<h3>Compras registradas</h3><p class="legenda">Todos os recebimentos carregados: ${e(cp.periodo)}. Este período pode ser diferente da comparação acima.</p>
      <div class="grade g2"><div class="cartao metrica"><div class="rotulo">${e(cp.rotulo)}</div><div class="valor">${e(cp.total)}</div><p class="legenda">${e(cp.contagem)} Compra não equivale a consumo nem a pagamento confirmado.</p></div>
      <div class="cartao"><b style="font-size:15px">Compras por fornecedor (R$)</b><div class="barras">${cp.grupos.map(([forn, v, rot]) => `<div class="barra"><span>${e(forn)}</span><div class="trilho"><div class="cheia" style="width:${(100 * v) / max}%;background:#7f9ab4" data-dica="${e(forn)} · ${e(rot)}"></div><span>${e(rot)}</span></div></div>`).join("")}</div></div></div>
      <div>${link("extrato", "Comparar fornecedores por custo da energia", "extrato")}</div>`;
  }
  return h;
}

function telaOportunidades() {
  const topo = cabecalho("Analisar um período", "Oportunidades", "Onde vale colocar tempo e dinheiro primeiro — sem passar do que os dados sustentam.");
  const c = combo();
  if (!c) return topo + periodosHtml() + foraDaPrevia();
  const o = c.op;
  if (o.vazio) return `${topo}<div class="alerta info">${icone("busca")}<div>${e(o.vazio)}</div></div>`;
  const ano = estado.diasAno;
  const proj = (v) => (ano && v !== null && v !== undefined && o.dias ? (v / o.dias) * ano : null);
  const cartao = (x) => {
    const legenda = [...x.legenda];
    if (ano && x.custo !== null) {
      const par = x.faixa ? x.faixa.map(proj) : null;
      legenda.push(`${rs(proj(x.custo))}/ano` + (par ? ` (${rs(par[0])} a ${rs(par[1])})` : "") + " na projeção informada");
    }
    if (x.motivo) legenda.push(x.motivo);
    return `<div class="cartao"><b>${x.ordem}. ${e(x.titulo)}</b><div>${selo(x.prioridade[1], x.prioridade[0])}</div>
      <div class="grade g3">
        <div class="metrica"><div class="rotulo">Impacto potencial associado</div><div class="valor">${e(x.impacto)}</div><p class="legenda">${e(legenda.join(" · "))}</p></div>
        <div class="metrica"><div class="rotulo">Evidência</div><div class="valor">${e(x.evidencia[0])}</div><p class="legenda">${e(x.evidencia[1])}</p></div>
        <div class="metrica"><div class="rotulo">Complexidade da verificação</div><div class="valor">${e(x.complexidade[0])}</div><p class="legenda">${e(x.complexidade[1])}</p></div>
      </div>
      <p>${md("**Próxima verificação:** " + x.acao)}</p>${x.detalhes.map((d) => `<p class="legenda">${md(d)}</p>`).join("")}</div>`;
  };
  const pAno = proj(o.assoc.custo);
  return `${topo}<p class="legenda">${e(o.cab)}</p><div>${link("investigacao", "Escolher períodos e ver investigação", "busca")}</div>
    <h3>${e(o.frase)}</h3>
    <div class="grade g2">
      <div class="cartao metrica"><div class="rotulo">${e(o.assoc.rotulo)}</div><div class="valor">${e(o.assoc.valor)}</div><p class="legenda">${md(o.assoc.legenda)}</p></div>
      <div class="cartao"><label class="campo" for="dias-ano">Dias de operação por ano (informado pela fábrica, opcional)<input type="number" id="dias-ano" min="1" max="366" step="1" value="${ano || ""}"></label>
        <p class="legenda">${pAno !== null ? e(`Projeção linear: ${rs(pAno)}/ano, dadas as premissas informadas. Não é economia recuperável confirmada.`) : "Só para projetar o valor do período para um ano, supondo o mesmo regime, carga e preço. Sem esse dado, a EULER não projeta."}</p></div>
    </div>
    ${o.primeira ? `<div class="cartao"><b>Verificar primeiro: ${e(o.primeira.titulo)}</b><p>${e(o.primeira.acao)}</p></div>` : ""}
    ${o.sobreposicao.map((x) => `<div class="alerta aviso">${icone("busca")}<div>${md(x)}</div></div>`).join("")}
    ${o.ativos.length ? `<h3>Em investigação</h3>${o.ativos.map(cartao).join("")}` : ""}
    ${o.outros.length ? `<details><summary>Não priorizadas agora (${o.outros.length})</summary>${tabela(["Hipótese", "Situação", "Por quê"], o.outros.map((l) => l.map(e)))}</details>` : ""}
    <h3>Intervenção</h3><div class="alerta info">${icone("busca")}<div>${e(o.intervencao)}</div></div><p class="legenda">${e(o.cadeia)}</p>
    <details><summary>Como a priorização funciona</summary><div class="grade" style="gap:8px">
      <b>Critérios objetivos (calculados pelo motor)</b><ul>${o.objetivos.map((x) => `<li>${e(x)}</li>`).join("")}</ul>
      <b>Regras de triagem propostas (pendentes de revisão, D90)</b><ul>${o.propostos.map((x) => `<li>${e(x)}</li>`).join("")}</ul>
      <b>Termos que não são sinônimos</b><ul><li>Desvio monetizado: diferença de consumo em reais (Financeiro).</li><li>Impacto potencial associado: o efeito de uma hipótese em reais, se ela se confirmar.</li><li>Parcela evitável: o que uma ação concreta evitaria; ainda não apurada.</li><li>Economia estimada: depende de intervenção definida; ainda não disponível.</li><li>Economia verificada: medida depois da intervenção; ainda não disponível.</li></ul></div></details>`;
}

/* ---------------------------------------------- Acompanhar a planta (registros guardados nesta página) */
const AC = D.acomp;
const GUARDA = "euler-previa-acompanhamento-v1";
const ACOMP = ["atualizar", "fechamentos", "acoes"]; // telas que pedem o nome de quem registra
const TIPOS_EVENTO = { criada: "Aberta", ocorrencia: "Nova ocorrência", evidencia: "Evidência", estado: "Situação", acao: "Ação registrada", verificacao: "Verificação", responsavel: "Responsável", encerrada: "Encerrada" };
const RESULTADO_ACAO = { positivo: ["Melhoria associada à ação", "green"], negativo: ["Piora detectável depois da ação", "red"], inconclusivo: ["Inconclusivo", "gray"], nao_avaliavel: ["Ainda não avaliável", "gray"] };
const CORES_FILA = { desvio_persistente: "red", acao_sem_verificacao: "orange", desvio_novo: "orange", investigacao_aberta: "blue", oportunidade: "violet", dados: "gray" };
const SITUACAO_CURTA = { acima: "desvio estabelecido", nao_estabelecido: "desvio não estabelecido", abaixo: "abaixo da referência", sem_faixa: "sem faixa de incerteza" };
const ROTULO_CRITERIO = { persistencia_fechamentos: "fechamentos seguidos acima", magnitude_pct: "% do esperado", faixa_brl: "faixa", avaliacao: "avaliação", ocorrencias: "ocorrências", responsavel: "responsável", estado: "situação", evidencia: "evidência", prioridade_investigacao: "prioridade da investigação", complexidade_verificacao: "complexidade da verificação" };
const ORDEM_FILA = Object.keys(AC.categorias);

function novoAcomp() {
  return { versao: D.versao, criada: false, autor: "", criadaEm: null, nFech: 0, fechInfo: {}, fechSel: null, invs: [], acoes: [], custos: [], precos: [], eventos: [], erro: null, abaAtualizar: 0, abaAcoes: 0, abaInv: {}, invSel: null, abriu: null };
}
let ac = (() => {
  try {
    const salvo = JSON.parse(localStorage.getItem(GUARDA) || "null");
    if (salvo && salvo.versao === D.versao) return salvo;
  } catch (_) { /* sem armazenamento: começa do zero */ }
  return novoAcomp();
})();
function guardar() { try { localStorage.setItem(GUARDA, JSON.stringify(ac)); } catch (_) { /* segue sem guardar */ } }

const pad = (n) => String(n).padStart(2, "0");
const quando = (x) => {
  if (!x) return "—";
  const d = x.length === 10 ? new Date(x + "T00:00") : new Date(x);
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
};
const nome = () => (ac.autor || "").trim();
const autorDe = (x) => (x === "__AUTOR__" ? nome() || "—" : x || "—");
const agora = () => new Date().toISOString();
const fechs = () => AC.fechamentos.slice(0, ac.nFech);
const proxId = (lista) => lista.reduce((m, x) => Math.max(m, x.id), 0) + 1;

function toast(texto) {
  const el = document.getElementById("toast");
  el.textContent = texto;
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => { el.hidden = true; }, 4000);
}
function evento(oque, acao) { ac.eventos.push({ quando: agora(), o_que: oque, acao, autor: nome() }); }
// erro de um formulário: aparece junto dele, como no app
function erroEm(onde, texto, tipo = "erro") { ac.erro = { onde, texto, tipo }; mostrar(); }
const erroDe = (onde) => (ac.erro && ac.erro.onde === onde ? `<div class="alerta ${ac.erro.tipo}">${icone(ac.erro.tipo === "aviso" ? "mao" : "bloqueio")}<div>${e(ac.erro.texto)}</div></div>` : "");
function exigirNome(onde) {
  if (nome()) return true;
  erroEm(onde, "Informe seu nome na barra lateral para registrar alterações.", "aviso");
  return false;
}
function gravou(texto) { ac.erro = null; guardar(); mostrar(); if (texto) toast(texto); }

function cobertura() {
  const dias = Math.floor((Date.now() - new Date(AC.diario[1])) / 864e5);
  return dias > AC.limite_dias
    ? { ok: false, frase: `Acompanhamento desatualizado: a última leitura do diário tem ${dias} dias (limite configurado: ${AC.limite_dias}). As análises descrevem o passado, não o momento atual.` }
    : { ok: true, frase: `Dados atualizados: última leitura do diário há ${dias} dias.` };
}

function semPlanta() {
  return `<div class="alerta info">${icone("busca")}<div>Nenhuma planta cadastrada nesta instalação. Comece em <b>Atualizar dados</b> (cadastro e primeira importação) ou crie a planta de demonstração lá.</div></div><div>${link("atualizar", "Ir para Atualizar dados", "atualizar")}</div>`;
}
function seletores(passos = []) {
  return `<div class="grade g2"><label class="campo">Planta<select disabled><option>${e(AC.planta)}</option></select></label>
    <label class="campo">Equipamento<select disabled><option>${e(AC.equipamento.nome)} · ${e(AC.equipamento.caldeira_id)}</option></select></label></div>
    <p class="legenda"><b>Dados salvos da planta.</b> O que você confirmar aqui fica gravado no histórico, com autor e data (nesta prévia, só neste navegador).</p>
    ${passos.length ? marcador(passos) : ""}
    <p class="legenda"><span style="color:var(--t-orange)">DADOS SINTÉTICOS</span> · não representam uma planta real.</p>`;
}
function faixaSituacao(sit, frase) {
  const tipo = sit === "acima" ? "aviso" : sit === "abaixo" ? "ok" : "info";
  return `<div class="alerta ${tipo}">${icone(sit === "acima" ? "cima" : sit === "abaixo" ? "ok" : "busca")}<div>${md(frase)}</div></div>`;
}
const abas = (lista, atual, acao, extra = "") => `<div class="abas" role="tablist">${lista.map((t, i) => `<button class="aba" role="tab" data-acao="${acao}" data-i="${i}" ${extra} aria-selected="${i === atual}">${e(t)}</button>`).join("")}</div>`;

/* criar a planta de demonstração: o mesmo que o botão do app, já calculado pelo motor */
function criarDemo() {
  if (!exigirNome("demo")) return;
  ac.criada = true;
  ac.criadaEm = agora();
  ac.nFech = 1;
  ac.fechInfo = { 1: { autor: nome(), em: agora(), acoes: [] } };
  ac.fechSel = 1;
  ac.eventos = AC.eventos.map((x) => ({ ...x, quando: agora(), autor: nome() }));
  gravou("Planta de demonstração criada, com referência e primeiro fechamento. Veja o resultado em Painel e Fechamentos.");
}

function telaAtualizar() {
  const topo = cabecalho("Acompanhar a planta", "Atualizar dados", "Acrescente os dados novos da planta: nada se duplica e nada é substituído em silêncio.", false);
  const cadastro = `<details ${ac.criada ? "" : "open"}><summary>Cadastrar uma planta</summary><div class="grade">
      <p class="legenda">Na prévia, o cadastro de plantas da fábrica fica desligado: use a planta de demonstração. No app, aqui entram o nome da planta, a origem dos dados (sintéticos, públicos ou de cliente, com o registro da autorização) e depois o equipamento.</p>
      <p class="legenda">Para conhecer o fluxo sem dados reais:</p>
      <div>${ac.criada ? `<span class="legenda">Planta de demonstração já criada nesta página.</span>` : `<button class="botao" data-acao="criar-demo">${icone("ciencia")} Criar planta de demonstração (sintética)</button>`}</div>${erroDe("demo")}</div></details>`;
  if (!ac.criada) return topo + cadastro;
  const cob = cobertura();
  const i = AC.importacao;
  let aba = "";
  if (ac.abaAtualizar === 0) {
    aba = `<div class="campo">Origem dos arquivos<div class="lado-a-lado"><span>◉ Enviar arquivos novos</span><span class="legenda">○ Usar versão já salva em Plantas e histórico</span></div></div>
      <div class="cartao"><div class="linha-botoes"><button class="botao" disabled>${icone("importar")} Escolher arquivos</button><span class="legenda">ou arraste para cá · CSV ou planilha .xlsx</span></div>
      <p class="legenda">Na prévia, o envio fica desligado. No app, os arquivos passam por uma prévia antes de gravar: novos, já gravados (ignorados), conflitos, recusados e tardios. Nada é gravado antes da sua confirmação.</p></div>
      <h3>Como foi a importação da demonstração</h3>${tabela(i.colunas, i.contagem.map((l) => l.map((v) => e(v))), [1, 2, 3, 4, 5, 6])}
      <p class="legenda">Registros já gravados não se duplicam. Valores diferentes ficam pendentes de decisão.</p>`;
  } else if (ac.abaAtualizar === 1) {
    aba = `<p class="legenda">Nenhum conflito pendente.</p>`;
  } else if (ac.abaAtualizar === 2) {
    aba = `${tabela(["Configuração", "Valor"], AC.config.map((l) => l.map(e)))}
      <p class="legenda">Configuração por equipamento, sem mudar código. Fechamentos antigos guardam a que usaram. Na prévia, só leitura.</p>
      <h3>Tabela de preços</h3>
      ${ac.precos.length ? tabela(["Combustível", "Fornecedor", "R$/t", "Adicional R$/t", "Adicional", "De", "Até", "Origem"], ac.precos.map((p) => [p.combustivel, p.fornecedor || "—", nf(p.preco, 2), p.adicional === null ? "—" : nf(p.adicional, 2), p.desc || "—", quando(p.de), quando(p.ate), p.origem].map(e)), [2, 3]) : ""}
      <form class="form" data-form="preco">
        <div class="grade g3"><label class="campo">Combustível<input type="text" id="preco-comb"></label><label class="campo">Fornecedor (opcional)<input type="text" id="preco-forn"></label><label class="campo">Preço (R$/t)<input type="number" id="preco-valor" min="0" step="0.01"></label></div>
        <div class="grade g3"><label class="campo">Válido de<input type="date" id="preco-de"></label><label class="campo">Válido até (opcional)<input type="date" id="preco-ate"></label><label class="campo">Origem (contrato, nota, cotação)<input type="text" id="preco-origem"></label></div>
        <div class="grade g2"><label class="campo">Custo adicional (R$/t, opcional)<input type="number" id="preco-adic" min="0" step="0.01"></label><label class="campo">Descrição do adicional (ex.: frete)<input type="text" id="preco-desc"></label></div>
        <div><button class="botao" type="submit">Registrar preço</button></div>${erroDe("preco")}</form>
      <p class="legenda">Usada só com a política "tabela de preços". Mais de um preço vigente no mesmo período deixa o custo ausente até haver regra de rateio; nada é escolhido em silêncio.</p>`;
  } else {
    aba = `${tabela(["Quando", "Quem", "Fonte", "Modo", "Novos", "Corrigidos", "Conflitos"], [[quando(ac.criadaEm), nome() || "—", "Importação de arquivos", "incremental", String(i.novas), String(i.corrigidas ?? 0), String(i.conflitos)]].map((l) => l.map(e)), [4, 5, 6])}
      <details><summary>Todas as alterações (auditoria)</summary>${tabela(["Quando", "O quê", "Ação", "Quem"], [...ac.eventos].reverse().map((x) => [quando(x.quando), x.o_que, x.acao, autorDe(x.autor)].map(e)))}</details>`;
  }
  return `${topo}${cadastro}${seletores(["registros"])}
    <details><summary>Cadastrar equipamento</summary><p class="legenda">Na prévia, o equipamento é o da demonstração. No app: identificador, nome, código da caldeira no diário e altitude do local.</p></details>
    <p class="legenda">${cob.ok ? "✓ " : ""}${e(cob.frase)}</p>
    <div class="grade g3">${metrica("Diário desde", quando(AC.diario[0]))}${metrica("até", quando(AC.diario[1]))}${metrica("Última importação", quando(ac.criadaEm))}</div>
    ${abas(["Novos dados", "Conflitos", "Configuração e preços", "Histórico"], ac.abaAtualizar, "aba-atualizar")}
    <div class="grade">${aba}</div>
    <div class="grade g2" style="border-top:1px solid var(--linha);padding-top:16px">
      <div class="grade" style="gap:4px">${link("fechamentos", "Fechar o período", "fechamentos")}<p class="legenda">Próximo passo do acompanhamento: custo, desvio e o que mudou.</p></div>
      <div class="grade" style="gap:4px"><div><button class="botao" data-acao="serie">${icone("investigacao")} Analisar série acumulada</button></div><p class="legenda">Leva os registros desta revisão para as telas de análise de um período.</p></div>
    </div>`;
}

/* Fechamentos */
function telaFechamentos() {
  const topo = cabecalho("Acompanhar a planta", "Fechamentos", "Quanto custou, quanto seria esperado e o que mudou — a cada período, com histórico.", false);
  if (!ac.criada) return topo + semPlanta();
  const r = AC.referencia;
  const pend = AC.pendentes[ac.nFech - 1] || [];
  const validos = pend.filter((p) => p.valido).length;
  const lista = fechs();
  const sel = lista.find((f) => f.id === ac.fechSel) || lista[lista.length - 1];
  const info = ac.fechInfo[sel.id] || {};
  const abriu = ac.abriu && ac.abriu.fech === sel.id ? ac.abriu : null;
  const inv = abriu ? ac.invs.find((x) => x.id === abriu.inv) : null;
  const acoesAntes = info.acoes || [];
  return `${topo}${seletores(["conta"])}
    <p>${md(`**Referência v${r.versao}** · ${r.periodo} · ${r.tipo} · ${r.consumo} t de combustível por t de vapor`)}</p>
    ${blocoMensal()}
    <h2>Fechamentos por período</h2>
    <details><summary>Definir nova versão da referência</summary><div class="grade"><p class="legenda">Na prévia, a referência fica em agosto. No app: escolher os períodos, o tipo (mudança estrutural ou correção de dados) e o motivo. Uma referência pior que a anterior só entra como mudança estrutural confirmada.</p>
      <p class="legenda">Versões anteriores nunca mudam; fechamentos antigos continuam reproduzíveis.</p>
      ${tabela(["Versão", "Período", "Tipo", "Motivo", "Por", "Em"], [[String(r.versao), r.periodo, "inicial", r.motivo, nome() || "—", quando(ac.criadaEm)].map(e)])}</div></details>
    ${pend.length ? `<p>${md(`**${pend.length} período(s) novo(s) para fechar** (${validos} com vapor e combustível conhecidos).`)}</p>
      ${pend.filter((p) => !p.valido).map((p) => `<p class="legenda">${e(p.rotulo)}: ${e(p.motivo)}</p>`).join("")}
      <div><button class="botao primario" data-acao="produzir">Produzir fechamento</button></div>${erroDe("produzir")}`
      : `<p class="legenda">Nenhum período novo desde o último fechamento: importe dados novos para continuar.</p>`}
    <h2>Fechamento #${sel.id} · ${e(sel.periodo)}</h2>
    ${faixaSituacao(sel.situacao, sel.frase)}
    ${sel.metricas ? `${quadroHtml(sel.quadro)}<p class="legenda">${e(sel.politica)}</p>${incertezaHtml(sel.incerteza, true)}` : ""}
    <div><button class="link" data-acao="ver-entrega">${icone("seta")} Ver a entrega deste fechamento (Financeiro · fechamentos da planta)</button></div>
    <p>${md("**O que mudou desde o fechamento anterior:** " + sel.mudanca)}</p>
    ${sel.persistencia ? `<p>${md("**Persistência:** " + sel.persistencia)}</p>` : ""}
    <p>${md("**Próxima verificação:** " + sel.proxima)}</p>
    <p class="legenda">${e(sel.forca)}</p>
    <div><button class="botao" data-acao="abrir" data-fech="${sel.id}">Abrir investigação deste desvio</button></div>${erroDe("abrir-" + sel.id)}
    ${inv ? `<div class="alerta ok">${icone("ok")}<div>Investigação #${inv.id}: ${e(inv.titulo)} (${e(AC.estados[inv.estado])}).</div></div><div>${link("acoes", "Abrir em Investigações e ações", "acoes")}</div>` : ""}
    <details><summary>Conta do período: compra, estoque, consumo e custo</summary>${tabela(["Item", "Quantidade", "Valor"], sel.conta_periodo.map((l) => l.map(e)), [1, 2])}<p class="legenda">${e(sel.nota_pagamento)}</p><p class="legenda">${e(sel.energia)}</p></details>
    ${sel.variacao ? `<details><summary>Por que a conta mudou: produção, condição do vapor, qualidade, preço</summary>${tabela(["Parcela", "Pergunta", "Valor"], sel.variacao.map((l) => l.map(e)), [2])}${sel.nao_ajustado.map((x) => `<p class="legenda">${e(x)}</p>`).join("")}</details>` : ""}
    <details><summary>O que investigar e ações anteriores</summary><div class="grade" style="gap:6px">
      ${sel.oportunidades.length ? `<ul>${sel.oportunidades.map((x) => `<li>${md(x)}</li>`).join("")}</ul>` : ""}
      ${sel.sobreposicao.map((x) => `<p class="legenda">${e(x)}</p>`).join("")}
      ${acoesAntes.length ? `<ul>${acoesAntes.map((x) => `<li>Ação #${x.id} (${quando(x.data)}) ${e(x.descricao)}: ${e(x.frase)}</li>`).join("")}</ul>` : '<p class="legenda">Nenhuma ação registrada até este fechamento.</p>'}</div></details>
    <details><summary>Rastreabilidade e reprodução</summary><p class="legenda">${e(sel.rastro)} · por ${e(info.autor || nome() || "—")} em ${quando(info.em)}</p><p class="legenda">Reproduzir o cálculo, baixar o relatório e os dados (JSON): disponíveis no app.</p></details>
    <h3>Histórico de fechamentos</h3><p class="legenda">Todos os períodos ficam: favoráveis, desfavoráveis e inconclusivos.</p>
    ${tabela(["#", "Período", "Situação", "Desvio", "Referência", "Em"], [...lista].reverse().map((f) => [String(f.id), f.periodo, f.situacao_frase, rs(f.desvio_brl), "v" + f.ref_versao, quando((ac.fechInfo[f.id] || {}).em)].map(e)), [0, 3])}
    ${lista.length > 1 ? `<label class="campo" style="max-width:320px">Ver outro fechamento<select id="ver-fech">${[...lista].reverse().map((f) => `<option value="${f.id}" ${f.id === sel.id ? "selected" : ""}>#${f.id}</option>`).join("")}</select></label>` : ""}`;
}

function produzir() {
  if (!exigirNome("produzir")) return;
  ac.nFech += 1;
  const id = ac.nFech;
  ac.fechInfo[id] = { autor: nome(), em: agora(), acoes: ac.acoes.map((x) => ({ id: x.id, data: x.data, descricao: x.descricao, frase: x.avaliacao ? x.avaliacao.frase : "Ainda não avaliada." })) };
  ac.fechSel = id;
  evento(`fechamento ${id}`, "produzido");
  gravou(`Fechamento #${id} gravado.`);
}

function abrirInvestigacao(fid) {
  if (!exigirNome("abrir-" + fid)) return;
  const r = AC.abrir[fid - 1];
  if (!r.ok) return erroEm("abrir-" + fid, r.erro);
  const aberta = ac.invs.find((x) => x.chave === r.chave && x.estado !== "encerrada");
  let inv;
  if (aberta) {
    inv = aberta;
    inv.eventos.push({ quando: agora(), tipo: "ocorrencia", autor: nome(), texto: r.desvio.frase });
    inv.atualizada = agora();
  } else {
    inv = { id: proxId(ac.invs), chave: r.chave, titulo: r.titulo, estado: r.estado, responsavel: null, criada: agora(), atualizada: agora(), desvio: r.desvio, proxima: r.proxima_verificacao, hipoteses: r.hipoteses, limitacoes: r.limitacoes, resultado: null, motivoEnc: null, eventos: [{ quando: agora(), tipo: "criada", autor: nome(), texto: r.desvio.frase }] };
    ac.invs.push(inv);
  }
  inv.fechs = [...(inv.fechs || []), fid];
  evento(`investigacao ${inv.id}`, "ocorrencia");
  ac.abriu = { fech: fid, inv: inv.id };
  ac.invSel = inv.id;
  gravou("Investigação atualizada.");
}

/* Investigações e ações */
function telaAcoes() {
  const topo = cabecalho("Acompanhar a planta", "Investigações e ações", "Do desvio à verificação: o que a equipe investigou, decidiu e qual foi o resultado.", false);
  if (!ac.criada) return topo + semPlanta();
  const abertas = ac.invs.filter((x) => x.estado !== "encerrada").length;
  return `${topo}${seletores(["investigar", "acao", "resultado"])}
    <div class="grade g2">${metrica("Investigações abertas", String(abertas))}${metrica("Ações registradas", String(ac.acoes.length))}</div>
    ${abas(["Investigações", "Ações e resultados"], ac.abaAcoes, "aba-acoes")}
    <div class="grade">${ac.abaAcoes === 0 ? abaInvestigacoes() : abaAcoesResultados()}</div>`;
}

function formAcao(chave, invId = null) {
  return `<form class="form" data-form="acao" data-chave="${chave}" ${invId ? `data-inv="${invId}"` : ""}>
    <div class="grade g2"><label class="campo">Data da ação<input type="date" id="${chave}-data" min="2026-07-01" max="2026-12-31"></label>
      <label class="campo">Tipo<select id="${chave}-tipo">${Object.entries(AC.tipos).map(([k, v]) => `<option value="${k}">${e(v)}</option>`).join("")}</select></label></div>
    <label class="campo">O que foi feito<input type="text" id="${chave}-desc"></label>
    <div class="grade g3"><label class="campo">Responsável (opcional)<input type="text" id="${chave}-resp"></label><label class="campo">Custo da ação (R$, opcional)<input type="number" id="${chave}-custo" min="0" step="0.01"></label><label class="campo">Origem do custo (nota, orçamento)<input type="text" id="${chave}-origem"></label></div>
    <label class="campo">Outras mudanças no mesmo período (uma por linha)<textarea id="${chave}-conc" title="Ex.: troca de fornecedor, mudança de carga. Elas impedem associar o resultado só a esta ação."></textarea></label>
    <div><button class="botao" type="submit">Registrar ação</button></div>${erroDe(chave)}</form>`;
}

function abaInvestigacoes() {
  if (!ac.invs.length) return `<div class="alerta info">${icone("busca")}<div>Nenhuma investigação ainda. Elas são abertas a partir de um fechamento com desvio ou hipótese a verificar.</div></div><div>${link("fechamentos", "Ir para Fechamentos", "fechamentos")}</div>`;
  const ordem = [...ac.invs].sort((a, b) => (a.estado === "encerrada") - (b.estado === "encerrada") || b.id - a.id);
  const inv = ac.invs.find((x) => x.id === ac.invSel) || ordem[0];
  const tabelaInv = tabela(["#", "Investigação", "Situação", "Ocorrências", "Responsável", "Atualizada"], ordem.map((x) => [String(x.id), x.titulo, AC.estados[x.estado], String(x.eventos.filter((v) => v.tipo === "criada" || v.tipo === "ocorrencia").length), x.responsavel || "—", quando(x.atualizada)].map(e)), [0, 3]);
  const seletor = `<label class="campo">Abrir investigação<select id="inv-sel">${ordem.map((x) => `<option value="${x.id}" ${x.id === inv.id ? "selected" : ""}>#${x.id} · ${e(x.titulo)}</option>`).join("")}</select></label>`;
  const hist = tabela(["Quando", "O quê", "Quem", "Detalhe"], inv.eventos.map((v) => [quando(v.quando), TIPOS_EVENTO[v.tipo] || v.tipo, autorDe(v.autor), v.texto || ""].map(e)));
  let corpo = `<h3>#${inv.id} · ${e(inv.titulo)}</h3><div>${selo(inv.estado === "encerrada" ? "gray" : "blue", AC.estados[inv.estado])}</div>
    ${inv.estado === "encerrada" ? `<div class="alerta info">${icone("busca")}<div>${md(`Encerrada como **${AC.resultados[inv.resultado] || inv.resultado}**: ${inv.motivoEnc}. Encerrar não significa causa confirmada.`)}</div></div>` : ""}
    ${inv.desvio && inv.desvio.frase ? `<p>${md("**Desvio que motivou:** " + inv.desvio.frase)}</p>` : ""}
    ${inv.proxima && inv.proxima.acao ? `<div class="cartao"><p>${md("**Próxima verificação:** " + inv.proxima.acao)}</p>${inv.proxima.porque ? `<p class="legenda">${e(inv.proxima.porque)}</p>` : ""}</div>` : ""}
    <p class="legenda">Responsável: ${e(inv.responsavel || "não informado")} · aberta em ${quando(inv.criada)}</p>
    <details><summary>Hipóteses, evidências e limitações</summary><ul>${inv.hipoteses.map((h) => `<li>${md(`**${h.titulo}** · evidência ${h.evidencia.toLowerCase()} · ${rs(h.impacto_brl)} associado (não somar) · ${h.verificacao}`)}</li>`).join("")}</ul>${inv.limitacoes.map((x) => `<p class="legenda">${e(x)}</p>`).join("")}</details>
    <details><summary>Histórico (${inv.eventos.length})</summary>${hist}</details>`;
  if (inv.estado === "encerrada") {
    corpo += `<form class="form" data-form="reabrir" data-inv="${inv.id}"><label class="campo">Motivo da reabertura<input type="text" id="reabrir-motivo"></label><div><button class="botao" type="submit">Reabrir investigação</button></div>${erroDe("reabrir")}</form>`;
    return tabelaInv + seletor + corpo;
  }
  const a = ac.abaInv[inv.id] || 0;
  const opcoes = AC.transicoes[inv.estado].filter((s) => s !== "encerrada");
  let sub = "";
  if (a === 0) sub = `<form class="form" data-form="evidencia" data-inv="${inv.id}"><label class="campo">O que foi verificado ou medido<textarea id="evid-texto"></textarea></label><label class="campo">Onde está o documento ou a medição (opcional)<input type="text" id="evid-ref"></label><div><button class="botao" type="submit">Adicionar evidência</button></div>${erroDe("evidencia")}</form>`;
  else if (a === 1) sub = `<form class="form" data-form="estado" data-inv="${inv.id}"><label class="campo">Nova situação<select id="estado-novo">${opcoes.map((s) => `<option value="${s}">${e(AC.estados[s])}</option>`).join("")}</select></label><label class="campo">Motivo<input type="text" id="estado-motivo"></label><div><button class="botao" type="submit">Mudar situação</button></div>${erroDe("estado")}</form>
      <form class="form" data-form="responsavel" data-inv="${inv.id}"><label class="campo">Responsável<input type="text" id="resp-nome" value="${e(inv.responsavel || "")}"></label><div><button class="botao" type="submit">Definir responsável</button></div>${erroDe("responsavel")}</form>`;
  else if (a === 2) sub = `<p class="legenda">A ação fica ligada a esta investigação; o resultado vem da avaliação posterior.</p>${formAcao("acao-inv", inv.id)}`;
  else sub = `<form class="form" data-form="encerrar" data-inv="${inv.id}"><label class="campo">Resultado<select id="enc-resultado">${Object.entries(AC.resultados).map(([k, v]) => `<option value="${k}">${e(v)}</option>`).join("")}</select></label><label class="campo">Motivo do encerramento<input type="text" id="enc-motivo"></label><p class="legenda">Inconclusiva é um resultado válido. Encerrar não significa causa confirmada.</p><div><button class="botao" type="submit">Encerrar investigação</button></div>${erroDe("encerrar")}</form>`;
  return tabelaInv + seletor + corpo + abas(["Evidência", "Situação e responsável", "Registrar ação", "Encerrar"], a, "aba-inv", `data-inv="${inv.id}"`) + `<div class="grade">${sub}</div>`;
}

function avaliacaoHtml(it) {
  const r = it.avaliacao;
  if (!r) return '<p class="legenda">Ainda não avaliada.</p>';
  const [rot, cor] = RESULTADO_ACAO[r.resultado];
  const m = r.melhoria;
  const ev = r.economia;
  let econ;
  if (ev && ev.valor_brl !== null && ev.valor_brl !== undefined) econ = md(`**Economia verificada (${ev.protocolo}):** ${rs(ev.valor_brl)} no período avaliado. ${ev.nota_custos || ""}`);
  else if (ev) econ = md("**Economia verificada:** critérios do protocolo não atendidos.") + (ev.criterios_nao_atendidos || []).map((x) => `<br><span class="legenda">• ${e(x)}</span>`).join("");
  else econ = md("**Economia verificada:** não se aplica sem melhoria associada.");
  const detalhes = [...r.motivos, ...r.excluidos, ...r.faltam];
  return `<div>${selo(cor, rot)}</div><p>${e(r.frase)}</p>
    ${r.dif ? `<p>${md(`**Diferença observada** (${r.dif.periodo}): consumo por tonelada de vapor ${r.dif.antes} → ${r.dif.depois} t/t; desvio da referência ajustada ${r.dif.desvio}.`)}</p>` : ""}
    <p>${m && m.custo_brl !== null ? md(`**Melhoria associada à ação:** ${rs(m.custo_brl)} (faixa ${rs(m.faixa_brl[0])} a ${rs(m.faixa_brl[1])}). ${m.nota}`) : md("**Melhoria associada à ação:** não estabelecida.")}</p>
    <p>${econ}</p>
    ${detalhes.length ? `<details><summary>Por que não foi possível associar ou verificar</summary>${detalhes.map((x) => `<p class="legenda">• ${e(x)}</p>`).join("")}</details>` : ""}`;
}

function abaAcoesResultados() {
  const cards = [...ac.acoes].reverse().map((it) => `<div class="cartao">
    <p>${md(`**#${it.id} · ${quando(it.data)} · ${AC.tipos[it.tipo]}** · ${it.descricao}`)}</p>
    <p class="legenda">Responsável: ${e(it.responsavel || "não informado")} · custo ${it.custo !== null ? `${e(rs(it.custo))} (${e(it.origem)})` : "não informado"}${it.inv ? ` · investigação #${it.inv}` : ""}</p>
    ${it.concomitantes.length ? `<p class="legenda">Mudanças no mesmo período: ${e(it.concomitantes.join("; "))}</p>` : ""}
    <div class="linha-botoes"><button class="botao" data-acao="avaliar" data-id="${it.id}">Avaliar agora</button>${it.avaliacao && it.avaliacao.dif ? `<button class="botao" disabled title="Disponível no app">Adotar a referência depois desta ação</button>` : ""}</div>${erroDe("avaliar-" + it.id)}
    ${avaliacaoHtml(it)}</div>`).join("");
  return `<details><summary>Registrar uma ação</summary>${formAcao("acao")}</details>
    ${cards || '<p class="legenda">Nenhuma ação registrada.</p>'}
    <details><summary>Custos de medição e acompanhamento</summary><div class="grade">
      <p class="legenda">Entram no benefício líquido das ações verificadas na mesma janela. Horas de equipe não viram dinheiro aqui.</p>
      ${ac.custos.length ? tabela(["Data", "Tipo", "Descrição", "Valor", "Origem"], ac.custos.map((c) => [quando(c.data), c.tipoRot, c.descricao, rs(c.valor), c.origem].map(e)), [3]) : ""}
      <form class="form" data-form="custo"><div class="grade g3"><label class="campo">Data<input type="date" id="custo-data"></label><label class="campo">Tipo<select id="custo-tipo"><option value="medicao">Medição</option><option value="acompanhamento">Acompanhamento</option><option value="outro">Outro</option></select></label><label class="campo">Valor (R$)<input type="number" id="custo-valor" min="0" step="0.01"></label></div>
        <label class="campo">Descrição<input type="text" id="custo-desc"></label><label class="campo">Origem (nota, contrato)<input type="text" id="custo-origem"></label>
        <div><button class="botao" type="submit">Registrar custo</button></div>${erroDe("custo")}</form></div></details>`;
}

/* avaliação: o resultado do motor para a data da ação (a página só aplica as regras de
   outras ações na mesma janela e de mudanças declaradas, como euler/acompanhamento.py) */
function avaliar(id) {
  if (!exigirNome("avaliar-" + id)) return;
  const it = ac.acoes.find((x) => x.id === id);
  const datas = Object.keys(AC.avaliacoes).sort();
  let chave = it.data, troca = null;
  if (chave < datas[0]) chave = datas[0];
  if (chave > datas[datas.length - 1]) { chave = datas[datas.length - 1]; troca = quando(it.data); }
  const r = JSON.parse(JSON.stringify(AC.avaliacoes[chave]));
  if (troca) {
    const de = quando(chave);
    r.frase = r.frase.split(de).join(troca);
    r.faltam = r.faltam.map((x) => x.split(de).join(troca));
  }
  if (r.dif && r.ref_fim) {
    const dataDe = (x) => new Date(x + "T00:00");
    const outras = ac.acoes.filter((x) => x.id !== id && new Date(r.ref_fim) < dataDe(x.data) && dataDe(x.data) <= new Date(r.dif.fim));
    const bloqueios = [];
    if (outras.length) bloqueios.push("outra intervenção registrada na mesma janela: " + outras.map((x) => `#${x.id} ${x.descricao} (${quando(x.data).slice(0, 5)})`).join(", "));
    if (it.concomitantes.length) bloqueios.push("mudanças concomitantes declaradas: " + it.concomitantes.join("; "));
    r.motivos = [...bloqueios, ...r.motivos];
    if (r.resultado === "positivo" && bloqueios.length) {
      r.resultado = "inconclusivo";
      r.frase = "Consumo abaixo da referência ajustada, mas não é possível associar à ação: " + r.motivos.join("; ") + ".";
      r.melhoria = null;
      r.economia = null;
    }
  }
  it.avaliacao = r;
  evento(`avaliacao ${id}`, r.resultado);
  const inv = it.inv ? ac.invs.find((x) => x.id === it.inv) : null;
  if (inv) {
    inv.eventos.push({ quando: agora(), tipo: "verificacao", autor: nome(), texto: r.frase });
    if (inv.estado === "acao_registrada" && r.resultado !== "nao_avaliavel") {
      inv.estado = "em_verificacao";
      inv.eventos.push({ quando: agora(), tipo: "estado", autor: nome(), texto: "Avaliação posterior registrada." });
    }
    inv.atualizada = agora();
  }
  gravou("Avaliação registrada.");
}

/* Painel: mesmas regras de euler/painel.py, lidas dos registros desta página */
function filaDeAtencao() {
  const itens = [];
  const fs = fechs();
  const ultimo = fs[fs.length - 1];
  const abertas = ac.invs.filter((x) => x.estado !== "encerrada");
  const chaves = new Set(abertas.map((x) => x.chave));
  let persist = 0;
  for (let k = fs.length - 1; k >= 0 && fs[k].situacao === "acima" && fs[k].ref_id === ultimo.ref_id; k--) persist++;
  if (ultimo && ultimo.situacao === "acima") itens.push({ categoria: persist >= 2 ? "desvio_persistente" : "desvio_novo", titulo: `Consumo acima da referência ajustada (${nf(ultimo.desvio_pct, 1)}%)`, valor: ultimo.desvio_brl, criterios: { persistencia_fechamentos: persist, magnitude_pct: ultimo.desvio_pct, faixa_brl: ultimo.desvio_faixa }, proxima: ultimo.proxima });
  for (const it of ac.acoes) {
    const av = it.avaliacao;
    if (!av || av.resultado === "nao_avaliavel") itens.push({ categoria: "acao_sem_verificacao", titulo: `Verificar o resultado: ${it.descricao} (${quando(it.data)})`, valor: null, criterios: { avaliacao: av ? av.frase : "nenhuma" }, proxima: av ? "Completar os dados que faltam e avaliar de novo." : "Avaliar a ação quando houver período completo depois dela." });
  }
  for (const x of abertas) itens.push({ categoria: "investigacao_aberta", titulo: `${x.titulo} · ${AC.estados[x.estado]}`, valor: (x.desvio || {}).custo_brl ?? null, criterios: { ocorrencias: x.eventos.filter((v) => v.tipo === "criada" || v.tipo === "ocorrencia").length, situacao_do_desvio: (x.desvio || {}).situacao, responsavel: x.responsavel || "não informado", estado: AC.estados[x.estado] }, proxima: (x.proxima || {}).acao });
  if (ultimo) for (const o of ultimo.ops) if (!chaves.has(`${AC.equipamento.id}:${o.id}`)) itens.push({ categoria: "oportunidade", titulo: o.titulo, valor: o.impacto_brl, criterios: { evidencia: o.evidencia, prioridade_investigacao: o.prioridade, complexidade_verificacao: o.complexidade, faixa_brl: o.faixa_brl }, proxima: o.verificacao });
  const cob = cobertura();
  if (!cob.ok) itens.push({ categoria: "dados", titulo: cob.frase, valor: null, criterios: {}, proxima: "Importar os dados mais recentes da planta." });
  itens.sort((a, b) => ORDEM_FILA.indexOf(a.categoria) - ORDEM_FILA.indexOf(b.categoria) || (a.valor === null) - (b.valor === null) || (b.valor ?? 0) - (a.valor ?? 0) || a.titulo.localeCompare(b.titulo));
  itens.forEach((x, i) => { x.ordem = i + 1; });
  return itens;
}

function itemFila(i) {
  const c = i.criterios || {};
  let extra = "";
  if (i.valor !== null && i.categoria === "oportunidade") extra = ` · ${rs(i.valor)} associado (não somar)`;
  else if (i.valor !== null) extra = ` · desvio de ${rs(i.valor)}` + (SITUACAO_CURTA[c.situacao_do_desvio] ? ` (${SITUACAO_CURTA[c.situacao_do_desvio]})` : "");
  const val = (v) => (Array.isArray(v) ? `${rs(v[0])} a ${rs(v[1])}` : typeof v === "number" && !Number.isInteger(v) ? nf(v, 1) : String(v) === String(v).toUpperCase() ? String(v).toLowerCase() : String(v));
  const crit = Object.entries(c).filter(([k, v]) => v !== null && v !== undefined && v !== "" && k !== "situacao_do_desvio").map(([k, v]) => `${ROTULO_CRITERIO[k] || k.replace(/_/g, " ")}: ${val(v)}`);
  return `<div class="cartao"><div>${selo(CORES_FILA[i.categoria], AC.categorias[i.categoria])}</div><p>${md(`**${i.ordem}. ${i.titulo}**`)}${e(extra)}</p>
    ${i.proxima ? `<p class="legenda">Próximo passo: ${e(i.proxima)}</p>` : ""}${crit.length ? `<p class="legenda">${e(crit.join(" · "))}</p>` : ""}</div>`;
}

function telaPainel() {
  const topo = cabecalho("Acompanhar a planta", "Painel", "Como a caldeira está no dia a dia e o mês em cinco respostas: custo, esperado, diferença, próxima verificação e resultado das ações.", false);
  if (!ac.criada) return topo + semPlanta();
  const fs = fechs();
  const u = fs[fs.length - 1];
  const fila = filaDeAtencao();
  const abertas = ac.invs.filter((x) => x.estado !== "encerrada");
  const encerradas = ac.invs.filter((x) => x.estado === "encerrada");
  const cob = cobertura();
  const outras = u.ops.filter((o) => !fila.some((i) => i.titulo === o.titulo));
  const pend = [];
  if (!cob.ok) pend.push(cob.frase);
  abertas.filter((x) => x.estado === "aguardando_dados").forEach((x) => pend.push(`Investigação aguardando dados: ${x.titulo}`));
  ac.acoes.filter((x) => !x.avaliacao).forEach((x) => pend.push(`Ação sem avaliação: ${x.descricao}`));
  return `${topo}${topoPainel()}
    <p class="legenda"><span style="color:var(--t-orange)">DADOS SINTÉTICOS</span> · não representam uma planta real.</p>
    ${diaADiaHtml()}
    ${cincoRespostas()}
    <h2>Histórico e detalhes</h2>
    ${percursoHtml()}
    ${cob.ok ? "" : `<div class="alerta aviso">${icone("mao")}<div>${e(cob.frase)}</div></div>`}
    <h3>Último fechamento · ${e(u.periodo)} · referência v${u.ref_versao}</h3>
    ${faixaSituacao(u.situacao, u.frase)}
    <p>${md("**O que mudou:** " + u.mudanca)}</p>${u.persistencia ? `<p>${md("**Persistência:** " + u.persistencia)}</p>` : ""}
    <div class="grade g4">${metrica("Investigações abertas", String(abertas.length))}${metrica("Encerradas", String(encerradas.length))}${metrica("Ações acompanhadas", String(ac.acoes.length))}${metrica("Economia verificada", "nenhuma", '<p class="legenda">Só entra aqui o resultado de ação avaliada pelo protocolo de verificação.</p>')}</div>
    <div class="lado-a-lado">${link("atualizar", "Atualizar dados", "atualizar")}${link("fechamentos", "Fechamentos", "fechamentos")}${link("acoes", "Investigações e ações", "acoes")}</div>
    <h2>O que olhar primeiro</h2>
    ${fila.length ? fila.slice(0, 3).map(itemFila).join("") : '<p class="legenda">Nada pendente: sem desvio estabelecido, ação sem verificação ou dado faltando.</p>'}
    ${fila.length > 3 ? `<details><summary>Outros itens para acompanhar (${fila.length - 3})</summary><div class="grade">${fila.slice(3).map(itemFila).join("")}</div></details>` : ""}
    ${fila.some((i) => i.categoria === "oportunidade") ? '<p class="legenda">Oportunidades aparecem uma a uma, sem soma: podem representar a mesma perda e nenhuma é ganho antes de verificada.</p>' : ""}
    <details><summary>Como a ordem é definida</summary><p class="legenda">${e(AC.criterios)}</p></details>
    ${outras.length ? `<details><summary>Outras oportunidades ainda não confirmadas (${outras.length})</summary><p class="legenda">Uma a uma, sem soma: podem representar a mesma perda.</p><ul>${outras.map((o) => `<li>${md(`**${o.titulo}** · evidência ${o.evidencia.toLowerCase()} · ${rs(o.impacto_brl)} associado`)}</li>`).join("")}</ul></details>` : ""}
    ${ac.acoes.length ? `<details><summary>Ações acompanhadas (${ac.acoes.length})</summary><ul>${ac.acoes.map((x) => `<li>${quando(x.data)} · ${e(x.descricao)}: ${e(x.avaliacao ? x.avaliacao.frase : "Ainda não avaliada.")}</li>`).join("")}</ul></details>` : ""}
    ${pend.length ? `<details><summary>Pendências dos registros (${pend.length})</summary><ul>${pend.map((x) => `<li>${e(x)}</li>`).join("")}</ul></details>` : ""}
    <p class="legenda">Desvio monetizado não é economia; oportunidade não confirmada não é ganho; só a economia verificada pelo protocolo entra como resultado. O benefício é das ações da planta.</p>`;
}

function telaPlantas() {
  const topo = cabecalho("Acompanhar a planta", "Plantas e histórico", "Guarde os dados no computador e retome a análise em outra sessão.", false);
  if (!ac.criada) return topo + semPlanta();
  return `${topo}${tabela(["Planta", "Origem dos dados", "Equipamentos", "Criada em"], [[AC.planta, "Dados sintéticos", "1", quando(ac.criadaEm)].map(e)], [2])}
    <p class="legenda">Cada planta tem um banco próprio, fora da pasta do código: arquivos originais, versões com autor e motivo, e todo o acompanhamento. Salvar versões, reabrir dados, cópia de segurança e restauração: disponíveis no app.</p>
    <div class="linha-botoes"><button class="botao" data-acao="recomecar">Apagar a demonstração desta página</button></div>${erroDe("recomecar")}`;
}

/* formulários do acompanhamento */
const val = (id) => (document.getElementById(id)?.value ?? "").trim();
const numero = (id) => (val(id) === "" ? null : Number(val(id)));
const FORMS = {
  preco() {
    if (!exigirNome("preco")) return;
    const p = { combustivel: val("preco-comb"), fornecedor: val("preco-forn") || null, preco: numero("preco-valor"), de: val("preco-de"), ate: val("preco-ate") || null, origem: val("preco-origem"), adicional: numero("preco-adic"), desc: val("preco-desc") || null };
    if (p.preco === null || !p.combustivel || !p.origem) return erroEm("preco", "Informe preço, combustível, origem e autor.");
    if (p.preco < 0 || (p.adicional !== null && p.adicional < 0)) return erroEm("preco", "Preço e custo adicional devem ser finitos e não negativos.");
    if (p.adicional && !p.desc) return erroEm("preco", "Descreva o custo adicional (ex.: frete).");
    if (!p.de) return erroEm("preco", "Informe a data de início da validade.");
    if (p.ate && p.ate <= p.de) return erroEm("preco", "O fim da validade precisa ser depois do início.");
    ac.precos.push(p);
    evento("preco " + ac.precos.length, "registrado");
    gravou("Preço registrado.");
  },
  acao(form) {
    const chave = form.dataset.chave;
    if (!exigirNome(chave)) return;
    const invId = form.dataset.inv ? Number(form.dataset.inv) : null;
    const it = { id: proxId(ac.acoes), data: val(chave + "-data"), tipo: val(chave + "-tipo"), descricao: val(chave + "-desc"), responsavel: val(chave + "-resp") || null, custo: numero(chave + "-custo"), origem: val(chave + "-origem") || null, concomitantes: val(chave + "-conc").split("\n").map((x) => x.trim()).filter(Boolean), inv: invId, avaliacao: null };
    if (!it.data) return erroEm(chave, "Informe a data da ação.");
    if (!it.descricao) return erroEm(chave, "Campo obrigatório: descricao.");
    if (it.custo !== null && (it.custo < 0 || !it.origem)) return erroEm(chave, "Custo da intervenção precisa ser não negativo e ter origem declarada.");
    ac.acoes.push(it);
    evento(`intervencao ${it.id}`, "registrada");
    const inv = invId ? ac.invs.find((x) => x.id === invId) : null;
    if (inv) {
      inv.eventos.push({ quando: agora(), tipo: "acao", autor: nome(), texto: it.descricao });
      if (AC.transicoes[inv.estado].includes("acao_registrada")) {
        inv.estado = "acao_registrada";
        inv.eventos.push({ quando: agora(), tipo: "estado", autor: nome(), texto: "Ação registrada." });
      }
      inv.atualizada = agora();
    }
    gravou("Ação registrada. Avalie quando houver períodos completos depois dela.");
  },
  evidencia(form) {
    if (!exigirNome("evidencia")) return;
    const inv = ac.invs.find((x) => x.id === Number(form.dataset.inv));
    const texto = val("evid-texto");
    if (!texto) return erroEm("evidencia", "Campo obrigatório: texto.");
    inv.eventos.push({ quando: agora(), tipo: "evidencia", autor: nome(), texto: texto + (val("evid-ref") ? ` (${val("evid-ref")})` : "") });
    inv.atualizada = agora();
    evento(`investigacao ${inv.id}`, "evidencia");
    gravou("Evidência registrada.");
  },
  estado(form) {
    if (!exigirNome("estado")) return;
    const inv = ac.invs.find((x) => x.id === Number(form.dataset.inv));
    const novo = val("estado-novo"), motivo = val("estado-motivo");
    if (!motivo) return erroEm("estado", "Campo obrigatório: motivo.");
    inv.eventos.push({ quando: agora(), tipo: "estado", autor: nome(), texto: motivo });
    inv.estado = novo;
    inv.atualizada = agora();
    evento(`investigacao ${inv.id}`, "estado:" + novo);
    gravou("Situação atualizada.");
  },
  responsavel(form) {
    if (!exigirNome("responsavel")) return;
    const inv = ac.invs.find((x) => x.id === Number(form.dataset.inv));
    const resp = val("resp-nome");
    if (!resp) return erroEm("responsavel", "Campo obrigatório: responsavel.");
    inv.eventos.push({ quando: agora(), tipo: "responsavel", autor: nome(), texto: resp });
    inv.responsavel = resp;
    inv.atualizada = agora();
    gravou("Responsável definido.");
  },
  encerrar(form) {
    if (!exigirNome("encerrar")) return;
    const inv = ac.invs.find((x) => x.id === Number(form.dataset.inv));
    const motivo = val("enc-motivo");
    if (!motivo) return erroEm("encerrar", "Campo obrigatório: motivo.");
    inv.resultado = val("enc-resultado");
    inv.motivoEnc = motivo;
    inv.estado = "encerrada";
    inv.eventos.push({ quando: agora(), tipo: "encerrada", autor: nome(), texto: motivo });
    inv.atualizada = agora();
    evento(`investigacao ${inv.id}`, "encerrada");
    gravou("Investigação encerrada.");
  },
  reabrir(form) {
    if (!exigirNome("reabrir")) return;
    const inv = ac.invs.find((x) => x.id === Number(form.dataset.inv));
    const motivo = val("reabrir-motivo");
    if (!motivo) return erroEm("reabrir", "Campo obrigatório: motivo.");
    inv.eventos.push({ quando: agora(), tipo: "estado", autor: nome(), texto: motivo });
    inv.estado = "em_investigacao";
    inv.atualizada = agora();
    evento(`investigacao ${inv.id}`, "estado:em_investigacao");
    gravou("Reaberta.");
  },
  custo() {
    if (!exigirNome("custo")) return;
    const c = { data: val("custo-data"), tipo: val("custo-tipo"), valor: numero("custo-valor"), descricao: val("custo-desc"), origem: val("custo-origem") };
    if (!c.data || c.valor === null) return erroEm("custo", "Informe data e valor.");
    if (!c.descricao || !c.origem) return erroEm("custo", `Campo obrigatório: ${[!c.descricao && "descricao", !c.origem && "origem"].filter(Boolean).join(", ")}.`);
    if (c.valor < 0) return erroEm("custo", "Tipo de custo desconhecido ou valor negativo.");
    c.tipoRot = { medicao: "medicao", acompanhamento: "acompanhamento", outro: "outro" }[c.tipo];
    ac.custos.push(c);
    evento("custo " + ac.custos.length, "registrado");
    gravou("Custo registrado.");
  },
};
const ACOES = {
  "criar-demo": criarDemo,
  produzir,
  abrir: (el) => abrirInvestigacao(Number(el.dataset.fech)),
  avaliar: (el) => avaliar(Number(el.dataset.id)),
  "aba-atualizar": (el) => { ac.abaAtualizar = Number(el.dataset.i); ac.erro = null; guardar(); mostrar(); },
  "aba-acoes": (el) => { ac.abaAcoes = Number(el.dataset.i); ac.erro = null; guardar(); mostrar(); },
  "aba-inv": (el) => { ac.abaInv[el.dataset.inv] = Number(el.dataset.i); ac.erro = null; guardar(); mostrar(); },
  serie: () => { estado.ato = "1"; toast("Série carregada: abra Investigação, Saúde ou Financeiro para analisar."); ir("saude"); },
  recomecar: () => { const autor = ac.autor; ac = novoAcomp(); ac.autor = autor; gravou("Demonstração apagada desta página."); },
  "fin-origem": (el) => { estado.finOrigem = el.dataset.i === "1" ? "planta" : "sessao"; mostrar(); },
  "lt-modo": (el) => { estado.ltModo = Number(el.dataset.i); mostrar(); },
  "ver-entrega": () => { estado.finOrigem = "planta"; estado.abrirEntrega = true; ir("financeiro"); },
};

/* ---------------------------------------------- incerteza da faixa (D97) */
function incertezaHtml(inc, recolhido = false) {
  if (!inc) return "";
  const titulo = "Por que a faixa é larga e o que a estreita";
  const corpo = `${inc.frase_origem ? `<p>${md(inc.frase_origem)}</p>` : ""}${["condicional", "melhor"].filter((k) => inc[k]).map((k) => `<p>• ${md(inc[k].frase)}</p>`).join("")}<p class="legenda">${e(inc.nota)}</p>`;
  return recolhido
    ? `<details><summary>${titulo}</summary><div class="grade" style="gap:8px">${corpo}</div></details>`
    : `<div class="cartao"><b>${titulo}</b>${corpo}</div>`;
}

/* ---------------------------------------------- Dados reais testados (casos públicos) */
const PUB = D.publicos;
estado.pubAba = 0;
estado.pubUn = "B10";
estado.pubSub = 0;
estado.diagUn = "B10";
estado.diagMes = 0;
const fonteLink = (href, rotulo) => `<a class="link" href="${e(href)}" target="_blank" rel="noopener">${icone("seta")} ${e(rotulo)}</a>`;
const tabelaLonga = (cab, linhas) => `<div class="tabela-rolagem quebra">${tabela(cab, linhas).replace('<div class="tabela-rolagem">', "").replace(/<\/div>$/, "")}</div>`;

function graficoDiario(pontos) {
  const W = 760, H = 230, m = { l: 44, r: 10, t: 12, b: 26 };
  const vals = pontos.map((p) => p[1]);
  const hi = Math.max(1, ...vals) * 1.15, lo = Math.min(-1, ...vals) * 1.15;
  const Y = (v) => m.t + ((hi - v) / (hi - lo)) * (H - m.t - m.b);
  const larg = (W - m.l - m.r) / pontos.length;
  const passo = passoBonito(hi - lo);
  let grade = "";
  for (let v = Math.ceil(lo / passo) * passo; v <= hi; v += passo) grade += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#333333"/><text x="${m.l - 7}" y="${Y(v) + 4}" text-anchor="end" fill="#A3A3A3" font-size="12">${nf(Math.abs(v) < 1e-9 ? 0 : v, 0)}%</text>`;
  const barras = pontos.map(([d, v], i) => {
    const x = m.l + i * larg + 1, y0 = Y(0), y = Y(v);
    return `<rect x="${x.toFixed(1)}" y="${Math.min(y, y0).toFixed(1)}" width="${Math.max(larg - 2, 1).toFixed(1)}" height="${Math.max(Math.abs(y - y0), 1).toFixed(1)}" rx="2" fill="${v >= 0 ? "#F6AD6B" : "#7FB2F0"}" data-dica="${e(d)} · ${nf(v, 1)}%"/>`;
  }).join("");
  const rotulos = pontos.map(([d], i) => (i % 7 === 0 ? `<text x="${m.l + i * larg + larg / 2}" y="${H - 6}" text-anchor="middle" fill="#A3A3A3" font-size="12">${e(d)}</text>` : "")).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Diferença de energia por dia, em %">${grade}<line x1="${m.l}" x2="${W - m.r}" y1="${Y(0)}" y2="${Y(0)}" stroke="#8A8A8A"/>${barras}${rotulos}</svg>`;
}

function abaEpa() {
  const u = PUB.epa[estado.pubUn];
  let sub = "";
  if (estado.pubSub === 0) {
    sub = `<div class="cartao metrica"><div class="rotulo">Valor estimado do desvio</div><div class="valor">${e(u.valor)}</div><p class="legenda">Estimativa a preço de referência regional do gás · somente horas comparáveis. Não é prejuízo confirmado nem economia garantida. Combustível efetivo e contrato da planta ainda precisam ser confirmados.</p></div>
      <div class="grade g2">${u.meses.map(([n, v]) => metrica(n, v)).join("")}</div>
      <p class="legenda">Diferença de energia frente à referência, ajustada à produção de vapor. Janeiro = referência.</p>
      <p>${md(`**${u.energia} de diferença energética** nas ${u.horas} horas comparadas.`)}</p>
      <div class="cartao"><b style="font-size:15px">O resultado ao longo dos dias (diferença de energia, %)</b><div class="grafico">${graficoDiario(u.diario)}</div>
        <p class="legenda">Acima de zero: mais energia que a referência para aquela produção. Abaixo: menos energia. Dias sem horas comparáveis não são preenchidos.</p></div>
      <div class="cartao"><b>O que já sabemos — e o que continua em aberto</b><p>${md("**Calculado:** diferença de consumo ajustada à carga e seu valor a preço declarado.")}</p><p>${md("**Em aberto:** se há perda térmica, qual é a causa e quanto seria recuperável. As incertezas dos instrumentos ainda não foram informadas.")}</p></div>
      <b>Cobertura da comparação</b>${u.cobertura.map(([n, c, v]) => `<div class="grade" style="gap:4px"><span class="legenda">${e(n)}: ${c} de ${v} horas válidas comparadas</span><div style="height:8px;border-radius:4px;background:var(--campo)"><div style="height:8px;border-radius:4px;width:${(100 * c) / v}%;background:var(--serie)"></div></div></div>`).join("")}
      <p class="legenda">${u.fora_faixa} horas válidas ficaram fora da faixa de carga de janeiro e foram excluídas. Os resultados não cobrem essas horas nem devem ser extrapolados para o ano.</p>`;
  } else if (estado.pubSub === 1) {
    sub = `<h3>O que fazer com este resultado</h3>
      <div class="alerta info">${icone("busca")}<div>${u.investigar ? md("**Verificação indicada.** Encaminhar o desvio ao responsável técnico e conferir os registros abaixo antes de decidir uma intervenção.") : md("**Acompanhar e conferir a comparação.** Este resultado não sustenta uma intervenção por aumento persistente de consumo.")}</div></div>
      <p class="legenda">Orientação de investigação para este caso histórico; não é um alarme ao vivo. Não altera setpoints nem substitui os procedimentos de segurança da planta.</p>
      ${u.verificacoes.map(([onde, conferir, para], i) => `<div class="cartao"><b>${i + 1}. ${e(onde)}</b><p>${e(conferir)}</p><p class="legenda">${e(para)}</p></div>`).join("")}
      <details><summary>Se o desvio persistir: onde aprofundar a investigação</summary><div class="grade" style="gap:8px"><p class="legenda">Frentes possíveis, sem causa atribuída nem ordem de prioridade. O responsável técnico escolhe a próxima verificação conforme os registros disponíveis.</p>${PUB.investigacoes.map(([o, d, r]) => `<div><b>${e(o)}</b><p>${e(d)}</p><p class="legenda">${e(r)}</p></div>`).join("")}</div></details>
      <p>${md("**Quando uma intervenção poderá ser indicada?** Quando as verificações sustentarem uma causa e uma avaliação técnica justificar a ação. Depois, comparar antes e depois sob condições equivalentes para medir a economia efetiva. Este ensaio ainda não chegou a essa etapa.")}</p>`;
  } else {
    sub = `<h3>Um resultado que pode ser conferido</h3>
      <p>${md("**Origem:** registros horários públicos EPA/CAMPD, preservados pela PUDL. Recorte de 8.034 registros com vapor informado, em quatro caldeiras.")}</p>
      <p>${md("**Integridade:** o arquivo é conferido por uma verificação de integridade a cada execução. Isso verifica se o recorte mudou; não certifica os instrumentos da planta.")}</p>
      <p>${md("**Comparação:** referência ajustada em janeiro; fevereiro e março somente na faixa de produção já observada. Dados ausentes, substituídos e horas parciais não são completados.")}</p>
      ${u.sensibilidade ? `<div class="alerta info">${icone("busca")}<div>O aumento também aparece usando faixas de produção de 5 e 10 t/h. É uma conferência de consistência; não é intervalo de confiança nem prova de causa.</div></div>` : ""}
      <b>Como o dinheiro foi calculado</b><p>Diferença de energia × preço por unidade de energia = valor estimado do desvio.</p>
      ${tabela(["Mês", "Diferença (GJ)", "Preço (US$/GJ)", "Valor (US$)"], u.tabela.map((l) => l.map(e)), [1, 2, 3])}
      <p class="legenda">Preço médio industrial do gás em Illinois: US$ 8,02 por mil pés cúbicos em fevereiro e US$ 6,54 em março de 2023. Poder calorífico regional anual: 1,040 MMBtu por mil pés cúbicos.</p>
      <div class="alerta aviso">${icone("mao")}<div>A B10 registra carvão secundário no cadastro EPA, sem participação horária disponível. A valorização integral como gás é condicional. Não temos a fatura nem o contrato da planta.</div></div>
      <p class="legenda">Janeiro não é uma operação certificada como ideal. Faltam condições da água e do vapor, eventos e incertezas. A B10 foi destacada depois de examinar as quatro unidades: estudo retrospectivo, sem validação prospectiva nem endosso da empresa.</p>
      <div class="lado-a-lado">${fonteLink(PUB.epa_fonte.url, "Registros originais · EPA/PUDL")}${fonteLink(PUB.epa_fonte.preco_fonte, "Preço publicado · EIA")}${fonteLink(PUB.epa_fonte.calor_fonte, "Poder calorífico · EIA")}</div>
      <details><summary>Detalhes técnicos · método</summary><p class="legenda">${e(u.referencia)} Referência E(V) = a + b·V ajustada só em janeiro; ΔE = soma de (E observada − E referência) nas horas comparáveis. Não é balanço térmico de eficiência.</p></details>`;
  }
  return `<h3>Registros horários reais · do consumo à investigação</h3>
    <p class="legenda">CASO PÚBLICO · Ingredion Argo, EUA · janeiro a março de 2023 · sem vínculo com a instalação</p>
    <label class="campo" style="max-width:320px">Caldeira do conjunto público<select id="pub-un">${Object.keys(PUB.epa).map((k) => `<option ${k === estado.pubUn ? "selected" : ""}>${k}</option>`).join("")}</select></label>
    <div class="cartao"><h3>${e(estado.pubUn)} · ${e(u.titulo)}</h3><p>${e(u.conclusao)}</p><div><button class="link" data-acao="abrir-diag">${icone("ok")} Abrir Diagnóstico de evidências</button></div></div>
    ${abas(["Resultado", "O que verificar", "Fontes e cálculo"], estado.pubSub, "pub-sub")}<div class="grade">${sub}</div>`;
}

function abaUtfpr() {
  const x = PUB.utfpr;
  return `<h3>Consumo aumentou: teste real com biomassa</h3><p class="legenda">Diniz · UTFPR, 2014 · indústria de papel · comparação de médias entre seca e chuva.</p>
    <p>${md("**Este é um caso de aumento publicado, sem inverter os períodos.** Os valores entram no motor de comparação e valorização da EULER.")}</p>
    ${tabela(["Entrada publicada", "Valor"], [["Consumo na seca", "0,30 t de biomassa por t de vapor"], ["Consumo na chuva", "0,35 t de biomassa por t de vapor"], ["Vapor produzido", "1.200 t/dia"], ["Preço histórico", "US$ 26,53 por t de biomassa"]].map((l) => l.map(e)))}
    <div class="grade g3">${x.metricas.map(([r, v]) => metrica(r, v)).join("")}</div>
    <p class="legenda">Valores com sinal: positivo = aumento; negativo = redução. Não há conversão cambial.</p><p>${e(x.conta)}</p>
    <div class="alerta ok">${icone("ok")}<div>Conferência independente: (0,35 − 0,30) × 1.200 × 26,53 = US$ 1.591,80/dia. O motor reproduz essa conta. O texto publicado dá US$ 1.591/dia pela diferença de custos sem casas decimais: a divergência é de US$ 0,80/dia (0,05%).</div></div>
    <div class="alerta info">${icone("busca")}<div>O número acima é uma diferença aritmética a preço constante. Sem incertezas dos instrumentos, a mudança não é confirmada metrologicamente. A fonte associa o aumento à chuva e à umidade, mas este recorte não permite à EULER separar umidade, carga e outras causas. Não é economia garantida.</div></div>
    <details><summary>Rastreabilidade, limites e próxima verificação</summary><ul><li>O preço é histórico, em dólares; a unidade por tonelada é inferida da aritmética da fonte.</li><li>São médias publicadas, sem séries brutas. Não criamos estoques, horários ou leituras.</li><li>Esta rota testa comparação de consumo e valorização (E13); não faz balanço térmico completo, atribuição de causa nem comprovação de recuperação.</li><li>Próxima verificação: conferir o medidor de vapor, as incertezas, a carga e as condições do vapor; medir a umidade dos lotes queimados nos dois períodos.</li></ul>${fonteLink(x.url, "Fonte do aumento · UTFPR, página 33 do PDF")}</details>
    <p class="legenda">No app, as entradas podem ser editadas para um cenário separado.</p>`;
}

function abaUnisanta() {
  const x = PUB.unisanta;
  return `<h3>Quanto isso representa em dinheiro?</h3><p class="legenda">Caso brasileiro publicado pela Unisanta (2015) · médias de 2010 e 2011 · gás natural.</p>
    <p>${md("A publicação adota **R$ 1,10/kg** nos dois períodos: assim dá para comparar o custo de combustível por tonelada de vapor sem buscar preço de outro mercado. É um preço histórico da publicação, não uma cotação atual nem uma fatura auditada.")}</p>
    <div class="grade g3">${x.metricas.map(([r, v]) => metrica(r, v)).join("")}</div>
    <div class="alerta ok">${icone("ok")}<div>Diferença de ${e(x.diferenca)} por tonelada de vapor. É uma redução calculada a partir das médias publicadas; não é economia gerada pela EULER.</div></div>
    <details><summary>Ver a conta e o que ela permite concluir</summary><div class="grade" style="gap:8px">${tabela(["Período", "Combustível (kg/h)", "Vapor (t/h)", "Consumo (kg/t vapor)", "Combustível (R$/h)"], x.tabela.map((l) => l.map(e)), [1, 2, 3, 4])}
      <p>${md(`**Diferença bruta:** R$ ${x.bruta}/h, mas a produção aumentou. **À mesma produção de 123,85 t/h:** a diferença seria R$ ${x.normalizada}/h se a intensidade anterior permanecesse constante; projeção linear para comparação, não dinheiro recuperado.`)}</p>
      <div class="alerta info">${icone("busca")}<div>Há uma intervenção relatada (retirada de pré-aquecedor ar/vapor), mas também mudou o combustível de partida. Sem registros brutos e incertezas, não dá para isolar a contribuição de cada mudança. Médias não são anualizadas sem as horas efetivas.</div></div>
      ${fonteLink(x.url, "Consultar dissertação · tabelas 6, 7, 14 e 15")}</div></details>
    <p class="legenda">No app, dá para refazer a comparação com outro preço.</p>`;
}

function abaCargas() {
  const x = PUB.cargas;
  return `<h3>Caldeira a carvão em três condições de carga</h3><p class="legenda">Médias operacionais publicadas por Ohijeagbon e colaboradores (2026), caldeira subcrítica a carvão. Não são três dias nem um histórico antes/depois.</p>
    <div class="alerta aviso">${icone("mao")}<div>Cálculos térmicos condicionais: a fonte informa pressão estática em MPa sem dizer se é absoluta ou manométrica. A conferência interpreta os valores como absolutos. Não há preços nem incerteza instrumental documentados.</div></div>
    <div class="grade g3">${metrica("Estados de água e vapor conferidos", "15")}${metrica("Maior diferença entre bibliotecas", x.maior)}${metrica("Economia comprovada", "Não apurada")}</div>
    <p class="legenda">Comparação numérica: EULER/IAPWS-IF97 contra CoolProp/HEOS (IAPWS-95). A concordância verifica a implementação para estes pontos; não certifica os sensores da planta.</p>
    ${tabela(["Carga publicada", "Vapor (t/h)", "Combustível por vapor (kg/t)", "Potência transferida ao vapor (MW)*"], x.tabela.map((l) => l.map(e)), [1, 2, 3])}
    <p class="legenda">*Estimativa a partir das médias publicadas de vazão e das entalpias calculadas pela EULER.</p>
    <div class="alerta info">${icone("busca")}<div>O consumo específico varia de 126,74 a 128,04 kg/t entre cargas diferentes. A EULER devolve a diferença, mas não confirma mudança detectável sem incerteza. Essa variação não demonstra desperdício nem justifica intervenção.</div></div>
    <details><summary>Conferir cálculos, referências e divergências</summary>${tabela(["Carga (%)", "Ponto", "EULER (kJ/kg)", "Fonte (kJ/kg)", "HEOS (kJ/kg)", "Diferença EULER/fonte (%)"], x.estados.map((l) => l.map(e)), [2, 3, 4, 5])}
      <p class="legenda">Pontos a revisar na fonte: divergência de até 0,99% em entalpias; oxigênio do combustível escrito como 7,9% e fração 0,078; pressões crescentes ao longo do economizador. Os dados ficam preservados, sem correção silenciosa. O poder calorífico publicado é PCS e não foi usado como PCI.</p>${fonteLink(x.url, "Consultar a fonte e o manual")}</details>`;
}

function abaZhejiang() {
  const x = PUB.zhejiang;
  return `<h3>Série de uma caldeira em uma indústria química</h3>
    <p>${md(`**${x.linhas} registros originais**, de 27/03 a 01/04/2022, Zhejiang, China. A EULER usa o arquivo com as lacunas preservadas, sem preenchimento por modelo.`)}</p>
    <div class="grade g3">${metrica("Menor temperatura do vapor", x.tmin)}${metrica("Maior temperatura do vapor", x.tmax)}${metrica("Registros prontos para importar", x.importados)}</div>
    <p>${md("**A importação real passou:** leituras por minuto com os valores de temperatura preservados. O recorte seleciona uma em cada 12 linhas; não cria médias nem preenche lacunas. O fuso +08:00 foi inferido da localização e está declarado no arquivo.")}</p>
    <p class="legenda">Pressão e vazão não foram mapeadas por falta de confirmação das unidades. Sem combustível, preço, água de entrada e pressão confirmada, eficiência e perdas financeiras ficam bloqueadas.</p>
    <div class="cartao"><b>Experimente no aplicativo</b><p class="legenda">No app, um botão carrega esse recorte público nas telas de análise; depois, Dados e limites mostra o que ficou bloqueado e por quê.</p></div>
    <details><summary>O que este ensaio comprova — e o que falta</summary><ul><li>${md("**Verificado:** origem pública rastreável, importação, preservação das temperaturas, cálculos termodinâmicos condicionais e bloqueios por falta de dados.")}</li><li>${md("**Ainda não demonstrado:** causa de perda, economia recuperável, custo por fornecedor e desempenho completo em uma planta brasileira a biomassa.")}</li><li>${md("**Próxima evidência necessária:** histórico sincronizado de combustível, vapor, condições da água e do vapor, qualidade do combustível, preços e eventos, com unidades e incertezas.")}</li></ul>${fonteLink(x.url, "Fonte original de Zhejiang · CC0")}</details>`;
}

/* série mensal: uma escala por gráfico; ponto com dica ao passar o mouse */
function graficoLinha(pontos, unidade, casas) {
  const W = 380, H = 200, m = { l: 48, r: 10, t: 12, b: 26 };
  const vals = pontos.map((p) => p[1]);
  const hi = Math.max(...vals) * 1.1, lo = 0;
  const passo = passoBonito(hi - lo);
  const X = (i) => m.l + (i * (W - m.l - m.r)) / Math.max(pontos.length - 1, 1);
  const Y = (v) => m.t + ((hi - v) / (hi - lo)) * (H - m.t - m.b);
  let grade = "";
  for (let v = 0; v <= hi; v += passo) grade += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#333333"/><text x="${m.l - 7}" y="${Y(v) + 4}" text-anchor="end" fill="#A3A3A3" font-size="11">${nf(v, casas)}</text>`;
  const linha = pontos.map(([, v], i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  const marcas = pontos.map(([d, v], i) => `<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="4" fill="var(--serie)" stroke="var(--fundo)" stroke-width="2" data-dica="${e(d)} · ${nf(v, casas)} ${e(unidade)}"/>`).join("");
  const rotulos = pontos.map(([d], i) => (i % 4 === 0 ? `<text x="${X(i)}" y="${H - 6}" text-anchor="middle" fill="#A3A3A3" font-size="11">${e(d)}</text>` : "")).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Série mensal, em ${e(unidade)}">${grade}<path d="${linha}" fill="none" stroke="var(--serie)" stroke-width="2"/>${marcas}${rotulos}</svg>`;
}

estado.pubCervSub = 0;
function abaCervejaria() {
  const x = PUB.cervejaria;
  let sub = "";
  if (estado.pubCervSub === 0) {
    sub = `<div class="grade g4">${x.metricas.map(([r, v]) => metrica(r, v)).join("")}</div>
      <p class="legenda">Consumo aparente = casca registrada ÷ vapor das duas caldeiras (t de casca por t de vapor). Mesmo trecho do calendário nos dois anos: 05/11 a 25/08. A incerteza conhecida é só a da balança (2%), com k = 2; o que falta não entra como zero.</p>
      ${tabela(["Período", "Dias", "Vapor (t)", "Casca (t)", "Consumo aparente (t/t)", "Vapor médio (t/dia)", "Dias sem vapor registrado"], x.periodos.map((l) => l.map(e)), [1, 2, 3, 4, 5, 6])}
      <div class="grade g2"><div class="cartao"><b>Consumo aparente por mês (t/t)</b><div class="grafico">${graficoLinha(x.mensal.map(([mes, c]) => [mes, c]), "t/t", 2)}</div></div>
        <div class="cartao"><b>Vapor médio por mês (t/dia)</b><div class="grafico">${graficoLinha(x.mensal.map(([mes, , v]) => [mes, v]), "t/dia", 0)}</div></div></div>
      <p class="legenda">Mês a mês, a casca registrada inclui o que entrou ou saiu do estoque, que não foi publicado: as oscilações mensais não são da caldeira.</p>
      <div class="cartao"><b>Outros cortes do mesmo registro</b>${tabela(["Corte", "Trecho", "Dias", "Consumo aparente (t/t)"], x.cortes.map((l) => l.map(e)), [2, 3])}<p class="legenda">${e(x.cortes_frase)}</p></div>
      <b>O que a EULER bloqueia neste caso</b><ul>${x.bloqueado.map((b) => `<li>${e(b)}</li>`).join("")}</ul>`;
  } else if (estado.pubCervSub === 1) {
    sub = `<b>Totais: soma da EULER × relatório de verificação publicado</b>
      ${tabela(["Grandeza", "Soma da EULER (t)", "Relatório (t)"], x.totais.map((l) => l.map(e)), [1, 2])}
      ${x.totais_conferem ? `<div class="alerta ok">${icone("ok")}<div>As três somas reproduzem os totais do relatório de verificação, arredondados à tonelada. Isso confere a leitura da planilha, não os instrumentos da planta.</div></div>` : ""}
      <p>${md(x.calendario)}</p><p>${md(x.lacunas)}</p>
      <div class="cartao"><b>O que a conferência encontrou</b><ul>${x.achados.map((a) => `<li>${md(a)}</li>`).join("")}</ul>
        ${tabela(["Data", "Caldeira", "Horas", "Vapor (t)", "Média (t/h)", "% da capacidade"], x.acima.map((l) => l.map(e)), [1, 2, 3, 4, 5])}
        <p class="legenda">Nada foi corrigido. Quem tem o registro original (totalizador e livro de turno) confere se foi digitação, troca de caldeira ou leitura do medidor.</p></div>
      <b>A casca do dia não é a casca queimada no dia</b>
      ${tabela(["Soma de", "Vapor por t de casca · baixo (5%)", "Mediana", "Alto (95%)"], x.janelas.map((l) => l.map(e)), [1, 2, 3])}
      <p class="legenda">${e(x.janelas_frase)}</p>
      <b>Física: entalpia do vapor</b><p>${e(x.entalpia)}</p><p class="legenda">${e(x.entalpia_legenda)}</p>`;
  } else if (estado.pubCervSub === 2) {
    sub = `<h3>Explicações que continuam possíveis</h3><p class="legenda">Nenhuma é causa atribuída. Cada uma vem com a verificação que a separa das outras.</p>
      ${x.hipoteses.map(([t, mostra, verif], i) => `<div class="cartao"><b>${i + 1}. ${e(t)}</b><p>${e(mostra)}</p><p class="legenda">Verificação: ${e(verif)}</p></div>`).join("")}
      <div class="alerta info">${icone("busca")}<div>${md("**Próxima medição que mais separa as explicações:** o estoque de casca do galpão nas datas de corte. Com ele, a EULER calcula a casca queimada em cada período e a diferença deixa de depender de entrega e estoque.")}</div></div>
      <p class="legenda">${e(x.projeto)}</p>
      <p class="legenda">A EULER recomenda verificações, nunca mudanças na operação da caldeira. Qualquer ação fica com os responsáveis técnicos da planta.</p>`;
  } else {
    sub = `<p>${md("**Origem:** registros diários do projeto 1202 do Mecanismo de Desenvolvimento Limpo (MDL), publicados pela ONU (UNFCCC) no pedido de emissão de créditos. A planilha está no repositório sem nenhuma alteração; o CSV só extrai as colunas diárias, sem mudar valores.")}</p>
      <p>${md(`**Termos de uso:** ${x.termos}`)}</p><p>${md(`**Aviso:** ${x.aviso}`)}</p>
      <p class="legenda">Consumo aparente c = Σ casca ÷ Σ (vapor da caldeira 1 + vapor da caldeira 2); variação = c₂/c₁ − 1. A incerteza da balança (2% sem tipo, lido como limite: u = 2%/√3, D35) entra por época de calibração; a época comum aos dois períodos é o mesmo erro (D37). Estoque e medidores de vapor entram como incertezas que faltam.</p>
      <div class="lado-a-lado">${x.links.map(([r, u]) => fonteLink(u, r)).join("")}</div>
      <details><summary>Detalhes técnicos · integridade</summary>${x.sha256.map(([n, h]) => `<p><code>${e(n)}</code><br><span class="legenda">${e(h)}</span></p>`).join("")}<p class="legenda">SHA-256 conferido nos testes. Arquivo sem alteração não comprova exatidão da medição.</p></details>`;
  }
  return `<h3>Planta brasileira real · 660 dias de duas caldeiras a casca de arroz</h3>
    <p class="legenda">CASO PÚBLICO · cervejaria em Viamão (RS) · 05/11/2007 a 25/08/2009 · registros publicados no MDL da ONU · sem vínculo com a empresa</p>
    <div class="cartao"><h3>O consumo de casca por tonelada de vapor mudou?</h3><p>${e(x.conclusao)}</p></div>
    ${abas(["Resposta", "Conferência dos registros", "Hipóteses e próximas medições", "Fontes"], estado.pubCervSub, "pub-cerv")}<div class="grade">${sub}</div>`;
}

function telaPublicos() {
  const topo = cabecalho("Dados reais testados", "Testes com dados públicos", "Dados reais publicados por empresas, governos e universidades, executados no motor atual. Medições ausentes continuam ausentes.", false);
  const corpo = [abaCervejaria, abaEpa, abaUtfpr, abaUnisanta, abaCargas, abaZhejiang][estado.pubAba]();
  return `${topo}<h2>O que já foi testado com dados reais</h2>
    ${tabelaLonga(["Caso", "Dados", "O que a EULER fez", "Resultado", "O que falta"], PUB.resumo.map((l) => [l.Caso, l.Dados, l["O que a EULER fez"], l.Resultado, l["O que falta"]].map(e)))}
    <p class="legenda">${e(PUB.aviso)}</p>
    ${abas(["Planta brasileira · RS", "Caldeiras EPA · EUA", "Biomassa · UTFPR", "Custo do vapor · Unisanta", "Três cargas · carvão", "Série · Zhejiang"], estado.pubAba, "pub-aba")}
    <div class="grade">${corpo}</div>`;
}

function telaDiagnostico() {
  const topo = cabecalho("Dados reais testados", "Diagnóstico de evidências", "O que foi observado, o que os dados sustentam e qual verificação vem a seguir.", false);
  const u = PUB.epa[estado.diagUn];
  const d = u.diagnosticos[estado.diagMes];
  return `${topo}<p class="legenda">DADOS PÚBLICOS · Ingredion Argo, EUA · 2023 · análise histórica, sem vínculo com a instalação</p>
    <div class="grade g2"><label class="campo">Equipamento<select id="diag-un">${Object.keys(PUB.epa).map((k) => `<option ${k === estado.diagUn ? "selected" : ""}>${k}</option>`).join("")}</select></label>
      <label class="campo">Período comparado<select id="diag-mes">${u.diagnosticos.map((x, i) => `<option value="${i}" ${i === estado.diagMes ? "selected" : ""}>${e(x.periodo)}</option>`).join("")}</select></label></div>
    <div class="alerta info">${icone("busca")}<div>${e(d.conclusao)}</div></div>
    <div class="grade g3">${d.metricas.map(([r, v]) => metrica(r, v)).join("")}</div>
    <p class="legenda">Causa confirmada: não · Avaliações qualitativas independentes, sem nota global de confiança.</p>
    ${d.proximas.length ? `<div class="cartao"><b>Próxima verificação recomendada</b><p>${e(d.proximas[0][0])}</p><p class="legenda">${e(d.proximas[0][1])}</p></div>` : ""}
    <details><summary>Por que a EULER recomenda isso?</summary><div class="grade" style="gap:8px">${d.dimensoes.map(([n, nv, ms]) => `<div><b>${e(n)} · ${e(nv)}</b>${ms.map((x) => `<p>${e(x)}</p>`).join("")}</div>`).join("")}<p class="legenda">${e(d.escopo)}</p></div></details>
    <div class="grade g3">${d.observacao.map(([r, v]) => metrica(r, v)).join("")}</div>
    <p class="legenda">Comparação restrita às condições e horas declaradas; referência não significa operação ideal.</p>
    <h3>Explicações a investigar</h3>${tabela(["Hipótese", "Situação"], d.hipoteses.map(([t, s]) => [t, s].map(e)))}
    <details><summary>Evidências e próximas medições</summary><div class="grade" style="gap:8px">${d.hipoteses.map(([t, , ev]) => `<div><b>${e(t)}</b>${ev.map((x) => `<p>${e(x)}</p>`).join("")}</div>`).join("")}${d.proximas.map(([a, p], i) => `<div><b>${i + 1}. ${e(a)}</b><p>${e(p)}</p></div>`).join("")}</div></details>
    <h3>O que o dinheiro significa</h3>${metrica("Valorização do desvio observado", d.valor)}
    <p class="legenda">Oportunidade recuperável: não apurada · Economia verificada: não apurada</p>${d.premissas.map((x) => `<p class="legenda">${e(x)}</p>`).join("")}
    <details><summary>Limitações</summary>${d.limitacoes.map((x) => `<p>${e(x)}</p>`).join("")}</details>
    <p class="legenda">${e(d.analise)}</p>`;
}

Object.assign(ACOES, {
  "pub-aba": (el) => { estado.pubAba = Number(el.dataset.i); mostrar(); },
  "pub-sub": (el) => { estado.pubSub = Number(el.dataset.i); mostrar(); },
  "pub-cerv": (el) => { estado.pubCervSub = Number(el.dataset.i); mostrar(); },
  "abrir-diag": () => { estado.diagUn = estado.pubUn; estado.diagMes = 0; ir("diagnostico"); },
});

/* ---------------------------------------------- Conclusão financeira em um quadro (D101) */
// mesmo objeto de euler.conta.conclusao_financeira, calculado pelo motor ao gerar a página
const ESTADO_Q = { acima: "acima do esperado, além da incerteza", abaixo: "abaixo do esperado, além da incerteza", nao_estabelecido: "dentro da incerteza: não estabelecida", sem_faixa: "sem faixa de incerteza" };
const temValor = (v) => v !== null && v !== undefined;
const rsQ = (v, sinal = false) => (!temValor(v) ? "—" : (v < 0 ? "−" : sinal && v > 0 ? "+" : "") + "R$ " + nf(Math.abs(v), 0));
const faixaQ = (f) => (!f ? "não determinada" : `${rsQ(f[0])} a ${rsQ(f[1])}`);

function quadroHtml(q) {
  if (!q) return "";
  if (!q.disponivel) return `<div class="alerta info">${icone("busca")}<div>${e(q.motivo || "Conta indisponível.")}</div></div>`;
  const c = q.consumido, x = q.esperado, s = q.sem_explicacao, p = q.ponte, ev = q.evitavel;
  const preco = temValor(c.preco_brl_t) ? `${nf(c.combustivel_t, 1)} t × R$ ${nf(c.preco_brl_t, 2)}/t` : `${nf(c.combustivel_t, 1)} t`;
  let h = `<div class="cartao quadro"><h3>Conclusão financeira</h3><p><b>${e(q.frase)}</b></p>
    ${tabela(["A conta do período", "Valor", "Como foi obtido"], [
      [e("Custo do combustível consumido"), e(rsQ(c.custo_brl)), e(`${preco} · consumo calculado pelos estoques e recebimentos`)],
      [e("Esperado nas condições analisadas"), e(rsQ(x.custo_brl)), e(`referência ajustada por ${x.ajustado_por.join(", ")}`)],
      ["<b>Diferença sem explicação</b>", `<b>${e(rsQ(s.custo_brl, true))}</b>`, e(`faixa das medições: ${faixaQ(s.faixa_brl)} · ${ESTADO_Q[s.estado]}`)],
    ], [1])}`;
  if (p.disponivel) {
    const d = p.dias || {};
    const dur = d.referencia && d.comparacao ? ` (${nf(d.referencia, 0)} dias → ${nf(d.comparacao, 0)} dias)` : "";
    h += `<p><b>Por que o custo mudou em relação à referência</b>${e(dur)}: ${e(`${rsQ(p.referencia_brl)} → ${rsQ(p.periodo_brl)}, variação de ${rsQ(p.variacao_brl, true)}.`)}</p>
      ${tabela(["Parcela", "Valor"], p.grupos.map((g) => [e(g.titulo + (g.nota ? " · " + g.nota : "")), e(temValor(g.custo_brl) ? rsQ(g.custo_brl, true) : "não separado")]), [1])}
      <p class="legenda">As parcelas fecham a variação. Explicado quer dizer atribuído a um fator medido, não inevitável: a qualidade do combustível, por exemplo, pode ter parte evitável.${p.nao_separados.length ? " Ainda dentro da diferença: " + e(p.nao_separados.join("; ").toLowerCase()) + "." : ""}</p>`;
  } else {
    h += `<p class="legenda">${md("Comparação com a referência: " + p.motivo)}</p>`;
  }
  const itens = [
    ...ev.antes.map(md),
    ...ev.verificacoes.map((v) => `<b>${e(v.titulo)}</b>`
      + (temValor(v.impacto_brl) ? e(` · impacto associado ${rsQ(v.impacto_brl)}` + (v.faixa_brl ? ` (faixa ${faixaQ(v.faixa_brl)})` : "")) : "")
      + e(v.onde ? `, ${v.onde}` : "") + ". " + md(v.acao) + (v.distingue ? e(` Separa: ${v.distingue}.`) : "")),
  ];
  h += `<p><b>${e(ev.situacao)}.</b> O que falta verificar:</p>
    ${itens.length ? `<ol class="verificar">${itens.map((t) => `<li>${t}</li>`).join("")}</ol>` : '<p class="legenda">Nenhuma verificação priorizada nesta comparação.</p>'}
    <p class="legenda">${e(ev.condicao)}</p>
    <p class="legenda">Economia verificada: só depois de uma ação registrada e avaliada em Ações. A diferença acima não é economia nem prejuízo recuperável confirmado.</p></div>`;
  return h;
}

/* ---------------------------------------------- Percurso da planta em cinco passos (D102) */
// mesmas regras de euler/percurso.py, lidas dos registros desta página
const PASSOS = [["registros", "Enviar registros", "atualizar"], ["conta", "Conferir a conta", "fechamentos"], ["investigar", "Investigar", "acoes"], ["acao", "Registrar ação", "acoes"], ["resultado", "Verificar resultado", "acoes"]];
const ESTADO_PASSO = { feito: ["Feito", "green"], andamento: ["Em andamento", "blue"], pendente: ["Pendente", "orange"], bloqueado: ["Aguarda o passo anterior", "gray"] };

function percurso() {
  const p = {};
  if (!ac.criada) {
    p.registros = ["pendente", "Nenhum registro enviado para este equipamento."];
    p.conta = ["bloqueado", "Depende dos registros."];
    p.investigar = ["bloqueado", "Depende do primeiro fechamento."];
    p.acao = ["bloqueado", "Depende de uma investigação aberta."];
    p.resultado = ["bloqueado", "Depende de uma ação registrada."];
  } else {
    const cob = cobertura();
    p.registros = cob.ok ? ["feito", `1 envio(s); último em ${quando(ac.criadaEm)}. ${cob.frase}`] : ["pendente", cob.frase];
    const prontos = (AC.pendentes[ac.nFech - 1] || []).filter((x) => x.valido);
    const fs = fechs();
    const u = fs[fs.length - 1];
    p.conta = prontos.length ? ["pendente", `${prontos.length} período(s) com dados completos ainda sem fechamento.`] : ["feito", `Último fechamento: ${u.periodo}. ${u.situacao_frase}`];
    const abertas = ac.invs.filter((x) => x.estado !== "encerrada");
    const ligadas = new Set(ac.invs.flatMap((x) => x.fechs || []));
    if ((u.situacao === "acima" || u.ops.length) && !ligadas.has(u.id)) p.investigar = ["pendente", "O último fechamento tem verificação a fazer e ainda não virou investigação."];
    else if (abertas.length) p.investigar = ["andamento", `${abertas.length} investigação(ões) aberta(s).`];
    else p.investigar = ["feito", "Nada aberto para investigar neste momento."];
    const comAcao = new Set(ac.acoes.map((x) => x.inv).filter(Boolean));
    const semAcao = abertas.filter((x) => x.estado === "em_investigacao" && !comAcao.has(x.id));
    const ultima = ac.acoes.map((x) => x.data).sort().pop();
    if (semAcao.length) p.acao = ["pendente", `${semAcao.length} investigação(ões) sem ação registrada: registre o que a equipe verificou ou fez.`];
    else if (ac.acoes.length) p.acao = ["feito", `${ac.acoes.length} ação(ões) registrada(s); última em ${quando(ultima)}.`];
    else if (abertas.length) p.acao = ["andamento", "Investigações aguardando dados ou verificação."];
    else p.acao = ["bloqueado", "Depende de uma investigação aberta."];
    const semAv = ac.acoes.filter((x) => !x.avaliacao);
    if (semAv.length) p.resultado = ["pendente", `${semAv.length} ação(ões) ainda sem avaliação do resultado.`];
    else if (ac.acoes.length) p.resultado = ["feito", "Todas as ações registradas já foram avaliadas."];
    else p.resultado = ["bloqueado", "Depende de uma ação registrada."];
  }
  return PASSOS.map(([id, titulo, destino]) => ({ id, titulo, destino, estado: p[id][0], frase: p[id][1] }));
}

function percursoHtml() {
  const itens = percurso();
  const prox = itens.find((x) => x.estado === "pendente");
  return `<div class="cartao"><b>Percurso da planta</b>
    <p class="legenda">Enviar registros → conferir a conta → investigar → registrar ação → verificar resultado. Tudo aqui usa os dados salvos desta planta.</p>
    <div class="passos">${itens.map((x, i) => `<div class="passo"><div>${selo(ESTADO_PASSO[x.estado][1], ESTADO_PASSO[x.estado][0])}</div><b>${i + 1}. ${e(x.titulo)}</b><p class="legenda">${e(x.frase)}</p></div>`).join("")}</div>
    ${prox ? `<div>${link(prox.destino, "Próximo passo: " + prox.titulo.toLowerCase())}</div>` : '<p class="legenda">Nada pendente no percurso agora.</p>'}</div>`;
}

function marcador(passos) {
  return `<p class="legenda">Percurso: ${PASSOS.map(([k, t], i) => (passos.includes(k) ? `<b>${i + 1}. ${e(t)}</b>` : `${i + 1}. ${e(t)}`)).join(" › ")}</p>`;
}

/* ---------------------------------------------- Linha do tempo dos fechamentos (D103) */
// valores e leitura da série calculados pelo motor (euler/linha_do_tempo.py) para cada fechamento;
// a página só acrescenta as linhas das ações que o visitante registrou, com a avaliação de cada uma
const ESTADO_LT = { acima: ["Acima do esperado", "#efbd80"], abaixo: ["Abaixo do esperado", "#9cb5ca"], nao_estabelecido: ["Dentro da incerteza", "#a3a3a3"], sem_faixa: ["Sem faixa de incerteza", "#a3a3a3"] };
const estadoLT = (x) => ESTADO_LT[x] || ["Conta indisponível", "#a3a3a3"];
const rs2 = (v) => (!temValor(v) ? "—" : (v < 0 ? "−" : "") + "R$ " + nf(Math.abs(v), 2));
const diaDe = (x) => new Date(x.length === 10 ? x + "T12:00" : x);

function acoesNoPeriodo(f) {
  return ac.acoes.filter((x) => new Date(f.inicio) < diaDe(x.data) && diaDe(x.data) <= new Date(f.fim));
}
function leituraSerie(fs) {
  const linhas = [...fs[fs.length - 1].padrao];
  const acoes = fs.flatMap((f) => acoesNoPeriodo(f).map((x) => `Ação em ${quando(x.data)} (${x.descricao}): ` + (x.avaliacao ? x.avaliacao.frase : "ainda não avaliada; a melhora só é afirmada pela avaliação.")));
  linhas.splice(1, 0, ...acoes);
  return linhas;
}

function graficoLinhaDoTempo(fs, porVapor) {
  const campo = porVapor ? "desvio_por_t_vapor_brl" : "desvio_brl";
  const campoF = porVapor ? "faixa_por_t_vapor_brl" : "faixa_brl";
  const fmt = porVapor ? rs2 : rs;
  const pts = fs.filter((f) => temValor(f.lt[campo]));
  if (!pts.length) return "";
  const acoes = fs.flatMap(acoesNoPeriodo);
  const W = 760, H = 250, xa = 70, xb = 740, ya = 14, yb = 214;
  const t = (x) => diaDe(x).getTime();
  const tMin = Math.min(...pts.map((f) => t(f.inicio)));
  const tMax = Math.max(...pts.map((f) => t(f.fim)));
  const X = (v) => xa + ((v - tMin) / (tMax - tMin || 1)) * (xb - xa);
  const vals = pts.flatMap((f) => [f.lt[campo], ...(f.lt[campoF] || [])]).concat([0]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const passo = passoBonito(hi - lo || 1);
  lo = Math.floor(lo / passo) * passo; hi = Math.ceil(hi / passo) * passo;
  const Y = (v) => yb - ((v - lo) / (hi - lo || 1)) * (yb - ya);
  const casas = porVapor ? 2 : 0;
  let g = "";
  for (let v = lo; v <= hi + passo / 2; v += passo) g += `<line x1="${xa}" x2="${xb}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" stroke="#333"/><text x="${xa - 8}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end" fill="#A3A3A3" font-size="12">${nf(v, casas)}</text>`;
  g += `<line x1="${xa}" x2="${xb}" y1="${Y(0).toFixed(1)}" y2="${Y(0).toFixed(1)}" stroke="#A3A3A3"/>`;
  const marcasX = [...new Set([...pts.map((f) => f.inicio), pts[pts.length - 1].fim])];
  g += marcasX.map((d) => `<text x="${X(t(d)).toFixed(1)}" y="${yb + 20}" text-anchor="middle" fill="#A3A3A3" font-size="12">${quando(d).slice(0, 5)}</text>`).join("");
  const acoesHtml = acoes.map((x) => {
    const xx = X(diaDe(x.data).getTime()).toFixed(1);
    const dicaA = `Ação registrada: ${quando(x.data)} · ${x.descricao} · ${x.avaliacao ? x.avaliacao.frase : "Ainda não avaliada"}`;
    return `<line x1="${xx}" x2="${xx}" y1="${ya}" y2="${yb}" stroke="#A3A3A3" stroke-width="1.5" stroke-dasharray="4 4"/><line x1="${xx}" x2="${xx}" y1="${ya}" y2="${yb}" stroke="transparent" stroke-width="12" data-dica="${e(dicaA)}"/>`;
  }).join("");
  const marcas = pts.map((f) => {
    const v = f.lt[campo], fx = f.lt[campoF], [rot, cor] = estadoLT(f.lt.estado);
    const meio = (t(f.inicio) + t(f.fim)) / 2;
    const dica = `Fechamento #${f.id} · ${f.periodo} · desvio ${fmt(v)} · faixa ${fx ? `${fmt(fx[0])} a ${fmt(fx[1])}` : "não determinada"} · ${rot} · conta ${f.lt.qualidade}`;
    return (fx ? `<line x1="${X(meio).toFixed(1)}" x2="${X(meio).toFixed(1)}" y1="${Y(fx[0]).toFixed(1)}" y2="${Y(fx[1]).toFixed(1)}" stroke="#d5dce2" stroke-width="1.5"/>` : "")
      + `<line x1="${(X(t(f.inicio)) + 2).toFixed(1)}" x2="${(X(t(f.fim)) - 2).toFixed(1)}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" stroke="${cor}" stroke-width="3" stroke-linecap="round"/>`
      + `<circle cx="${X(meio).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="5" fill="${cor}" stroke="#262626" stroke-width="2"/>`
      + `<rect x="${X(t(f.inicio)).toFixed(1)}" y="${ya}" width="${(X(t(f.fim)) - X(t(f.inicio))).toFixed(1)}" height="${yb - ya}" fill="transparent" data-dica="${e(dica)}"/>`;
  }).join("");
  const fora = fs.length - pts.length;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Desvio de cada fechamento com a faixa de incerteza">
      <text x="14" y="${(ya + yb) / 2}" fill="#A3A3A3" font-size="12" transform="rotate(-90 14 ${(ya + yb) / 2})" text-anchor="middle">${porVapor ? "R$ por t de vapor" : "R$ no período"}</text>${g}${acoesHtml}${marcas}</svg>
    <p class="legenda">Cada segmento é o desvio de um fechamento (custo consumido − esperado); a barra vertical é a faixa de incerteza. Âmbar: acima do esperado além da incerteza; azul: abaixo; cinza: dentro da incerteza ou sem faixa. Linhas tracejadas: ações registradas. Os mesmos valores estão na tabela abaixo.${fora ? ` ${fora} fechamento(s) sem esse valor ficam fora do gráfico, sem zero.` : ""}</p>`;
}

function linhaDoTempoHtml(fs) {
  const porVapor = estado.ltModo === 1;
  const linhas = fs.map((f) => {
    const l = f.lt;
    return [`#${f.id} · ${f.periodo}`, nf(l.dias, 0), temValor(l.vapor_t) ? `${nf(l.vapor_t, 0)} t` : "—", temValor(l.consumo_t_t) ? `${nf(l.consumo_t_t * 1000, 1)} kg/t` : "—", rs(l.custo_brl), rs2(l.custo_por_t_vapor_brl), rs(l.custo_por_dia_brl), rs(l.desvio_brl), l.faixa_brl ? `${rs(l.faixa_brl[0])} a ${rs(l.faixa_brl[1])}` : "—", estadoLT(l.estado)[0], l.qualidade, acoesNoPeriodo(f).map((x) => x.descricao).join("; ") || "—"].map(e);
  });
  const grafico = graficoLinhaDoTempo(fs, porVapor);
  return `<h3>Linha do tempo dos fechamentos</h3>
    <p class="legenda">Cada fechamento gravado, em ordem: o desvio apareceu agora, está se repetindo ou mudou depois de uma ação? Valores preservados de cada fechamento.</p>
    <ul>${leituraSerie(fs).map((x) => `<li>${e(x)}</li>`).join("")}</ul>
    ${abas(["Total do período (R$)", "Por tonelada de vapor (R$/t)"], porVapor ? 1 : 0, "lt-modo")}
    <p class="legenda">Períodos com duração ou produção diferentes se comparam melhor por tonelada de vapor.</p>
    ${grafico || '<div class="alerta info">' + icone("busca") + "<div>Nenhum fechamento tem esse valor calculado. Veja os motivos na tabela abaixo.</div></div>"}
    <details ${fs.length <= 3 ? "open" : ""}><summary>Tabela dos fechamentos</summary>
      ${tabela(["Fechamento", "Dias", "Vapor", "Consumo", "Custo", "Custo por t de vapor", "Custo por dia", "Desvio", "Faixa do desvio", "Situação", "Qualidade da conta", "Ações no período"], linhas, [1, 2, 3, 4, 5, 6, 7])}
      <p class="legenda">Qualidade da conta: completa (preço e faixa), preço incompleto, sem faixa ou conta indisponível. Custo atribuído ao consumo não é pagamento confirmado.</p></details>`;
}

/* ---------------------------------------------- Entrega de cada fechamento (D104) */
// mesmas cinco partes de euler/entrega.py: a conta vem do fechamento; o resto, dos registros desta página
function entrega(sel) {
  const cob = cobertura();
  const pend = cob.ok ? [] : [cob.frase];
  const novos = (AC.pendentes[ac.nFech - 1] || []).filter((p) => p.valido).length;
  if (novos) pend.push(`${novos} período(s) com dados completos ainda sem fechamento.`);
  if (sel.lt.qualidade !== "completa") pend.push(`Conta deste fechamento: ${sel.lt.qualidade} (${sel.lt.qualidade_motivo})`);
  const abertas = ac.invs.filter((x) => x.estado !== "encerrada");
  const andamento = ac.acoes.filter((x) => !x.avaliacao || x.avaliacao.resultado === "nao_avaliavel");
  const avaliadas = ac.acoes.filter((x) => x.avaliacao && x.avaliacao.resultado !== "nao_avaliavel");
  return { pend, abertas, andamento, avaliadas };
}

function entregaHtml(sel) {
  const { pend, abertas, andamento, avaliadas } = entrega(sel);
  const lista = (itens, vazio) => (itens.length ? `<ul>${itens.map((x) => `<li>${x}</li>`).join("")}</ul>` : `<p class="legenda">${e(vazio)}</p>`);
  const hoje = new Date().toISOString().slice(0, 10);
  const verificadas = avaliadas.filter((x) => x.avaliacao.economia && temValor(x.avaliacao.economia.valor_brl));
  return `<div class="cartao" id="entrega"><b>Entrega do fechamento #${sel.id}</b>
    <p class="legenda">O resumo de cada fechamento para a gestão: a conta e o que mudou, as pendências, as verificações e ações em andamento e os resultados já demonstrados. A conta vem preservada do fechamento; o restante é o registrado até hoje.</p>
    <div class="grade g4">${metrica("Pendências", String(pend.length))}${metrica("Verificações abertas", String(abertas.length))}${metrica("Ações sem avaliação", String(andamento.length))}${metrica("Ações avaliadas", String(avaliadas.length))}</div>
    <p class="legenda">No app, o botão “Baixar a entrega do fechamento” gera o mesmo texto em arquivo, para enviar à gestão. Nada é enviado automaticamente.</p>
    <details ${estado.abrirEntrega ? "open" : ""}><summary>Ver a entrega completa</summary><div class="grade entrega" style="gap:10px">
      <h3>Entrega do fechamento #${sel.id} · ${e(AC.equipamento.nome)}</h3>
      <p class="legenda">Período: ${e(sel.periodo)} · referência v${sel.ref_versao} · entrega gerada em ${quando(hoje)}. A conta é a preservada no fechamento. Pendências, verificações e resultados são os registrados até a data da entrega.</p>
      <h4>1. A conta do período</h4>${sel.quadro && sel.quadro.disponivel ? quadroHtml(sel.quadro) : `<p>${e((sel.quadro && sel.quadro.motivo) || sel.frase)}</p>`}
      <h4>2. O que mudou</h4><p>${md(sel.mudanca)}</p>${lista(sel.padrao.map(e), "")}
      <h4>3. Pendências relevantes</h4>${lista(pend.map(e), "Nenhuma pendência registrada.")}
      <h4>4. Verificações e ações em andamento</h4>${lista([
        ...abertas.map((v) => e(`Verificação: ${v.titulo} · estado: ${AC.estados[v.estado].toLowerCase()} · responsável: ${v.responsavel || "não informado"}` + ((v.proxima || {}).acao ? ` · próximo passo: ${v.proxima.acao}` : ""))),
        ...andamento.map((x) => e(`Ação em ${quando(x.data)}: ${x.descricao} · ${x.avaliacao ? "avaliação sem conclusão: " + x.avaliacao.frase : "ainda não avaliada"}`)),
      ], "Nenhuma verificação ou ação em andamento.")}
      <h4>5. Resultados já demonstrados</h4>${lista(avaliadas.map((x) => e(`${quando(x.data)} · ${x.descricao}: ${x.avaliacao.frase}`)), "Nenhuma ação avaliada até esta entrega.")}
      <p>${e(verificadas.length ? "Economia verificada pelo protocolo: " + verificadas.map((x) => `${x.descricao} · ${rs(x.avaliacao.economia.valor_brl)}`).join("; ") + ". No app, a soma exclui janelas sobrepostas." : "Economia verificada no histórico: não apurada (nenhuma avaliação cumpriu o protocolo).")}</p>
      <p class="legenda">Só entram economias verificadas pelo protocolo, uma por intervenção, sem janelas sobrepostas. É benefício das ações da planta (equipe, fornecedores, projetos), não um valor atribuído à EULER.</p>
      <p class="legenda">A EULER investiga e recomenda verificações; não comanda a caldeira. Qualquer ajuste operacional é avaliado e decidido pelos responsáveis técnicos da planta.</p>
    </div></details></div>`;
}

/* Financeiro · fechamentos da planta: linha do tempo, conta salva e entrega */
function financeiroPlanta() {
  if (!ac.criada) {
    return `<div class="alerta info">${icone("busca")}<div>Ainda não há conta fechada para este equipamento. Defina a referência e produza o primeiro fechamento.</div></div>
      <div>${link("atualizar", "Criar a planta de demonstração em Dados", "atualizar")}</div>`;
  }
  const fs = fechs();
  const sel = fs.find((f) => f.id === ac.fechSel) || fs[fs.length - 1];
  const h = `${seletores(["conta"])}${linhaDoTempoHtml(fs)}<hr>
    <label class="campo" style="max-width:360px">Fechamento salvo<select id="ver-fech">${[...fs].reverse().map((f) => `<option value="${f.id}" ${f.id === sel.id ? "selected" : ""}>#${f.id} · ${e(f.periodo)}</option>`).join("")}</select></label>
    <h3>Conta do período · ${e(sel.periodo)}</h3>
    <p class="legenda">Referência v${sel.ref_versao}. Valores preservados no fechamento; preços e registros novos não reescrevem esta conta.</p>
    ${faixaSituacao(sel.situacao, sel.frase)}
    ${sel.quadro && sel.quadro.disponivel ? quadroHtml(sel.quadro) + incertezaHtml(sel.incerteza, true) : `<div class="alerta info">${icone("busca")}<div>${e((sel.quadro && sel.quadro.motivo) || "Comparação financeira ainda não disponível.")}</div></div>`}
    <p>${md("**Próxima verificação:** " + sel.proxima)}</p>
    ${entregaHtml(sel)}
    <div class="lado-a-lado">${link("acoes", "Acompanhar verificações e ações", "acoes")}${link("fechamentos", "Gerenciar referência e fechamentos", "fechamentos")}</div>`;
  estado.abrirEntrega = false;
  return h;
}

/* ---------------------------------------------- Painel novo e fechamento do mês (D111–D114) */
const MEN = D.mensal;
const SET = MEN.meses.find((m) => m.mes === "2026-09");
const COR_MES = { referencia: "blue", sem_periodo: "gray", em_andamento: "gray", aguarda_anterior: "yellow", pronto: "orange", fechado: "green", revisar: "red" };
const ESTADO_DESVIO = { acima: ["orange", "Acima do esperado (estabelecido)"], abaixo: ["blue", "Abaixo do esperado (estabelecido)"], nao_estabelecido: ["gray", "Diferença não estabelecida"], sem_faixa: ["gray", "Sem faixa de incerteza"] };
const seloDesvio = (s) => { const [c, t] = ESTADO_DESVIO[s] || ["gray", "Sem conta (lacuna)"]; return selo(c, t); };
function estadoMes(m) {
  if (m.mes !== "2026-09") return m.estado;
  return ac.mesFechado ? "fechado" : "pronto";
}
const rotuloEstadoMes = (m) => (m.mes === "2026-09" && ac.mesFechado ? "Fechado" : m.estado_rotulo);

function graficoDia(serie, campo, faixa, unidade, casas, titulo) {
  const pts = serie.map((r) => [r.dia, r[campo]]);
  const vals = pts.map((p) => p[1]).filter((v) => v !== null && v !== undefined);
  if (!vals.length) return `<p class="legenda">${e(titulo)}: sem leituras no período mostrado.</p>`;
  const W = 380, H = 190, m = { l: 46, r: 10, t: 12, b: 26 };
  let lo = Math.min(...vals, ...(faixa || [])), hi = Math.max(...vals, ...(faixa || []));
  const folga = (hi - lo) * 0.25 || 1; lo -= folga; hi += folga;
  const passo = passoBonito(hi - lo);
  lo = Math.floor(lo / passo) * passo; hi = Math.ceil(hi / passo) * passo;
  const X = (i) => m.l + (i * (W - m.l - m.r)) / Math.max(pts.length - 1, 1);
  const Y = (v) => m.t + ((hi - v) / (hi - lo)) * (H - m.t - m.b);
  let g = "";
  for (let v = lo; v <= hi + 1e-9; v += passo) g += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#333333"/><text x="${m.l - 7}" y="${Y(v) + 4}" text-anchor="end" fill="#A3A3A3" font-size="11">${nf(v, casas)}</text>`;
  if (faixa) g += `<rect x="${m.l}" width="${W - m.l - m.r}" y="${Y(faixa[1])}" height="${Math.max(Y(faixa[0]) - Y(faixa[1]), 2)}" fill="#8A8A8A" opacity=".22"><title>Comum na referência: ${nf(faixa[0], casas)} a ${nf(faixa[1], casas)} ${unidade}</title></rect>`;
  let d = "", novo = true;
  pts.forEach(([, v], i) => { if (v === null || v === undefined) { novo = true; return; } d += `${novo ? "M" : "L"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`; novo = false; });
  const marcas = pts.map(([dia, v], i) => (v === null || v === undefined ? "" : `<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="3.5" fill="var(--serie)" stroke="var(--fundo)" stroke-width="2" data-dica="${e(dia)} · ${nf(v, casas)} ${e(unidade)}"/>`)).join("");
  const rot = pts.map(([dia], i) => (i % 6 === 0 ? `<text x="${X(i)}" y="${H - 6}" text-anchor="middle" fill="#A3A3A3" font-size="11">${e(dia)}</text>` : "")).join("");
  return `<div class="cartao"><b>${e(titulo)}</b><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${e(titulo)}, em ${e(unidade)}">${g}<path d="${d}" fill="none" stroke="var(--serie)" stroke-width="2"/>${marcas}${rot}</svg></div>`;
}

function diaADiaHtml() {
  const d = MEN.dia;
  const quadros = d.quadros.map((q) => {
    const v = q.media_7d === null ? "—" : `${nf(q.media_7d, q.casas)} ${q.unidade}`;
    const sinal = q.fora_da_faixa === null ? "ⓘ" : q.fora_da_faixa ? "⚠" : "✓";
    return metrica(q.nome, v, `<p class="legenda">${sinal} ${e(q.frase)}</p>`);
  }).join("");
  return `<h2>Dia a dia</h2>
    <p class="legenda">Últimos 7 dias com registro (até ${e(d.ultimo_dia)}), comparados com o que era comum na referência. Combustível consumido só se conhece no fechamento, entre medições de estoque.</p>
    <div class="grade g4">${quadros}</div>
    <div class="grade g2">${graficoDia(d.serie, "vazao_t_h", d.faixas.vazao_t_h, "t/h", 1, "Vapor · vazão média do dia")}${graficoDia(d.serie, "t_gases_c", d.faixas.t_gases_c, "°C", 0, "Temperatura dos gases · média do dia")}</div>
    <p class="legenda">Faixa cinza: do 10º ao 90º percentil dos dias da referência (o comum na base de comparação, não um limite de projeto). ${e(d.frases.join(" "))}</p>`;
}

function topoPainel() {
  const cob = cobertura();
  return `<div class="cartao"><div class="grade g3">
    <div><b>${e(AC.planta)}</b><p class="legenda">${e(AC.equipamento.nome)} · ${e(AC.equipamento.caldeira_id)}</p></div>
    <div><b>${cob.ok ? "✓" : "⟳"} Dados até ${quando(AC.diario[1])}</b><p class="legenda">${e(cob.frase)}</p></div>
    <div><b>Mês: ${e(SET.rotulo)}</b><p>${selo(COR_MES[estadoMes(SET)], rotuloEstadoMes(SET))}</p></div></div></div>`;
}

function cincoRespostas() {
  const r = MEN.resumo;
  const previa = !ac.mesFechado;
  const fila = filaDeAtencao();
  const cartao = (pergunta, corpo) => `<div class="cartao"><b>${e(pergunta)}</b>${corpo}</div>`;
  const lacunas = r.trechos.filter((t) => !t.situacao).map((t) => `${t.periodo} sem conta`).join("; ");
  const c1 = cartao("1 · Quanto custou o combustível consumido?", `<div class="metrica"><div class="rotulo">No mês (trechos com conta)</div><div class="valor">${e(r.consumido)}</div></div><p class="legenda">${e(r.combustivel_t)} t queimadas</p>${lacunas ? `<p class="legenda">⛔ ${e(lacunas)}.</p>` : ""}`);
  const c2 = cartao("2 · Quanto seria esperado nas condições comparadas?", `<div class="metrica"><div class="rotulo">No mês (trechos com conta)</div><div class="valor">${e(r.esperado)}</div></div><p class="legenda">Ajustado por ${e(MEN.ajustado_por.join(", "))}.</p>`);
  const c3 = cartao("3 · Qual diferença ficou estabelecida e o que falta saber?", `<div class="metrica"><div class="rotulo">No mês (soma dos trechos)</div><div class="valor">${e(r.diferenca)}</div></div>
    ${r.trechos.map((t) => `<p class="legenda">${seloDesvio(t.situacao)} ${e(t.periodo)}</p>`).join("")}
    <details><summary>Condições comparadas e o que ficou no desvio</summary><ul>${MEN.condicoes.frases.map((x) => `<li>${md(x)}</li>`).join("")}</ul><p class="legenda">${e(MEN.condicoes.nao_ajustado || "")}</p>${MEN.ainda_no_desvio.map((x) => `<p class="legenda">• ${md(x)}</p>`).join("")}</details>`);
  const ponte = MEN.ponte ? `<div class="cartao fin-total"><b>Por que a conta mudou · ${e(MEN.ultimo_trecho)}</b><p>${md(MEN.ponte)}</p></div>` : "";
  const c4 = cartao("4 · Qual é a próxima verificação, quem faz e em que pé está?", (fila.length ? fila.slice(0, 2).map((i) => `<p>${md(`**${i.titulo}**`)}</p>${i.proxima ? `<p class="legenda">Próximo passo: ${e(i.proxima)}</p>` : ""}<p class="legenda">Quem: ${e((i.criterios || {}).responsavel || "responsável ainda não definido")} · Situação: ${e((i.criterios || {}).estado || "não aberta como investigação")}</p>`).join("") : "<p>Nada pendente: sem desvio estabelecido, ação sem verificação ou dado faltando.</p>") + `<div>${link("acoes", "Investigações e ações", "acoes")}</div>`);
  const c5 = cartao("5 · O que aconteceu depois das ações anteriores?", (ac.acoes.length ? ac.acoes.slice(-3).reverse().map((x) => `<p>${md(`**${quando(x.data)} · ${x.descricao}**`)}</p><p class="legenda">${e(x.avaliacao ? x.avaliacao.frase : "Ainda não avaliada.")}</p>`).join("") : "<p>Nenhuma ação registrada ainda.</p>") + '<p class="legenda">Economia verificada pelo protocolo: nenhuma até agora.</p>');
  return `<h2>O mês em cinco respostas</h2>
    <p class="legenda">${e(r.rotulo.charAt(0).toUpperCase() + r.rotulo.slice(1))} (${r.trechos.length} trechos) · referência v${AC.referencia.versao}</p>
    ${previa ? `<div class="alerta aviso">${icone("mao")}<div><b>Prévia:</b> setembro ainda não foi aprovado. Os números abaixo são os mesmos que serão gravados ao aprovar. ${link("fechamentos", "Aprovar em Fechamentos", "fechamentos")}</div></div>` : ""}
    <div class="grade g3">${c1}${c2}${c3}</div>${ponte}<div class="grade g2">${c4}${c5}</div>`;
}

function blocoMensal() {
  const sel = MEN.meses.find((m) => m.mes === (estado.mesSel || "2026-09")) || SET;
  const est = estadoMes(sel);
  const linhas = MEN.meses.map((m) => [m.rotulo, rotuloEstadoMes(m), m.mes === "2026-09" && ac.mesFechado ? "Mês fechado: 3 trecho(s), 1 lacuna registrada." : m.frase].map(e));
  let acoes = "";
  if (sel.mes === "2026-09") {
    if (!ac.mesFechado) {
      acoes = `<div class="linha-botoes"><button class="botao" data-acao="mes-previa">Ver prévia do mês</button><button class="botao primario" data-acao="mes-aprovar">Aprovar fechamento do mês</button></div>${erroDe("mes")}`;
      if (estado.mesPrevia) acoes += `<div class="alerta info">${icone("busca")}<div>Prévia: nada foi gravado. Ao aprovar, estes resultados ficam no histórico.</div></div>${tabela(["Trecho", "Resultado", "Consumido", "Diferença"], MEN.previas.map((p) => [p.periodo, p.frase, p.consumido, p.diferenca].map(e)), [2, 3])}`;
    } else {
      acoes = `<div class="alerta ok">${icone("ok")}<div>Setembro aprovado por ${e(autorDe(ac.mesFechado.autor))} em ${quando(ac.mesFechado.em)}. Consumido ${e(MEN.resumo.consumido)}, esperado ${e(MEN.resumo.esperado)}, diferença ${e(MEN.resumo.diferenca)}.</div></div>
        <details><summary>Revisar o mês (quando um dado antigo for corrigido)</summary><p class="legenda">No app: se um registro do mês for corrigido depois da aprovação, o mês aparece como "Revisar". A revisão pede um motivo e gera uma nova versão só dos trechos afetados; a versão antiga fica no histórico.</p></details>`;
    }
  } else if (est === "referencia") acoes = '<p class="legenda">Agosto é a base de comparação: não se fecha contra si mesmo.</p>';
  else acoes = '<p class="legenda">Só prévia quando houver período completo: o mês ainda não terminou.</p>';
  return `<h2>Fechamento do mês</h2>
    <p class="legenda">Cada período entre medições de estoque pertence ao mês em que termina. Os meses são fechados na ordem; um trecho sem dados vira lacuna registrada, nunca consumo inventado.</p>
    ${tabela(["Mês", "Situação", "O que falta"], linhas)}
    <label class="campo" style="max-width:320px">Mês<select id="mes-sel">${MEN.meses.map((m) => `<option value="${m.mes}" ${m.mes === sel.mes ? "selected" : ""}>${e(m.rotulo)}</option>`).join("")}</select></label>
    <p>${selo(COR_MES[est], rotuloEstadoMes(sel))} ${md(sel.frase)}</p>
    ${sel.cobertura.length ? `<ul>${sel.cobertura.map((x) => `<li>${e(x)}</li>`).join("")}</ul>` : ""}
    ${sel.trechos.length ? tabela(["Trecho", "Períodos", "Conta"], sel.trechos.map((t) => [t.periodo, String(t.periodos), t.valido ? "com conta" : "lacuna: " + t.motivo].map(e)), [1]) : ""}
    ${acoes}`;
}

ACOES["mes-previa"] = () => { estado.mesPrevia = !estado.mesPrevia; mostrar(); };
ACOES["mes-aprovar"] = () => {
  if (!exigirNome("mes")) return;
  ac.mesFechado = { autor: nome(), em: agora() };
  estado.mesPrevia = false;
  evento("mês 2026-09", "fechado");
  gravou("Setembro fechado: 3 trechos gravados (1 lacuna). Veja o Painel.");
};
document.addEventListener("change", (ev) => { if (ev.target.id === "mes-sel") { estado.mesSel = ev.target.value; mostrar(); } });
