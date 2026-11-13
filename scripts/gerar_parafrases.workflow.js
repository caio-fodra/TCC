export const meta = {
  name: 'parafrases-claude',
  description: 'Gera 1 parafrase por comando (regras de 03/11, 5 niveis) com agentes isolados e verifica sentido e nivel',
  whenToUse: 'Gerar ou refazer o C_parafrase do TCC a partir da saida de python -m tcc.paraphrase --itens',
  phases: [
    { title: 'Gerar', detail: 'um agente por nivel com os itens pendentes; reprovadas voltam com o motivo' },
    { title: 'Verificar', detail: 'lentes sentido e nivel; aprovada so com as duas' },
  ],
}

// args = saida de `python -m tcc.paraphrase --itens` ({regras, verbos_todos, itens: [{id, nivel, bloco}]}),
// mais `feedback` opcional ({id: {parafrase, motivo}}) para refazer itens reprovados pelo --finalizar.
const REGRAS = args.regras
const PH = '[cole aqui os itens]'
if (typeof REGRAS !== 'string' || !REGRAS.endsWith(PH)) throw new Error('args.regras sem o marcador dos itens')
if (!Array.isArray(args.itens) || !args.itens.length) throw new Error('args.itens vazio')
if (!Array.isArray(args.verbos_todos) || !args.verbos_todos.length) throw new Error('args.verbos_todos ausente')

const MAX_RODADA = 3      // rodada 0 = geracao; rodadas 1..3 refazem as reprovadas
const MAX_TENTATIVAS = 3  // chamada nula ou id faltando: novas chamadas que nao gastam rodada
const EFFORT = 'high'
const ISOLA = 'Responda só com base neste texto: não leia arquivos, não rode comandos e não pesquise.\n\n'
const REGRAS_SEM_ENTRADA = REGRAS.split('\nENTRADA\n')[0]
const ASCII = '^[!-~](?:[ -~]*[!-~])?$'  // ASCII imprimivel, sem espaco nas pontas

function schemaGerar(ids) {
  return { type: 'object', required: ['parafrases'], properties: { parafrases: {
    type: 'array', minItems: ids.length, maxItems: ids.length,
    items: { type: 'object', required: ['id', 'parafrase'], properties: {
      id: { type: 'string', enum: ids },
      parafrase: { type: 'string', pattern: ASCII },
    } },
  } } }
}

function schemaVerificar(ids) {
  return { type: 'object', required: ['veredictos'], properties: { veredictos: {
    type: 'array', minItems: ids.length, maxItems: ids.length,
    items: { type: 'object', required: ['id', 'aprovada', 'motivo'], properties: {
      id: { type: 'string', enum: ids },
      aprovada: { type: 'boolean' },
      motivo: { type: 'string' },
    } },
  } } }
}

function promptGerar(lote, fb) {
  const blocos = lote.map(it => fb[it.id]
    ? `${it.bloco}\n  versão anterior (reprovada): ${fb[it.id].parafrase}\n  motivo da reprovação: ${fb[it.id].motivo}`
    : it.bloco)
  return ISOLA + REGRAS.replace(PH, () => blocos.join('\n\n')) +
    '\n\nDevolva o resultado pela saída estruturada: no campo parafrases, um objeto {id, parafrase} para cada item, ' +
    'com o id do item e só caracteres ASCII (apóstrofo reto). Num item com versão anterior reprovada, escreva uma ' +
    'paráfrase nova que corrija o motivo.'
}

const LENTES = {
  sentido: 'Lente SENTIDO. Para cada item, confira só isto, no rigor:\n' +
    '(a) regra 1: a paráfrase pede exatamente a mesma tarefa do original: mesma ação, mesmos objetos, locais, pessoas e ' +
    'informações; nada acrescentado, retirado ou trocado; uma única ação, sem ação extra nem dentro de uma oração de contexto;\n' +
    '(b) regra 2: cada trecho de "trechos a copiar" aparece exatamente como está, letra por letra: sem sinônimo, sem mudar ' +
    'singular ou plural ("toys" no lugar de "toy" reprova), sem tirar artigo de dentro do trecho ("person pointing to right" ' +
    'no lugar de "person pointing to the right" reprova) e sem substantivo ou quantidade acrescentada ("a bottle of red wine" ' +
    'no lugar de "a red wine" reprova);\n' +
    '(c) regra 3: nenhum objeto, categoria, cômodo, local ou nome que não esteja no original;\n' +
    '(d) regra 4: só nos itens com ação deliver (bring me, give me), a paráfrase precisa ter "me"; nas outras ações, o ' +
    '"me" de "tell me" pode sair ou ficar, e isso não é motivo de reprovação;\n' +
    '(e) regra 6: ordem direta; sem "?", sem "please" e sem could you, can you, would you, will you, can I, could I ou do you ' +
    'em parte nenhuma da frase.\n' +
    'Não julgue o nível, o verbo nem o estilo: isso é de outro revisor.',
  nivel: 'Lente NÍVEL. Para cada item, confira só isto, no rigor:\n' +
    '(a) a paráfrase faz exatamente a transformação do nível do item, nem mais nem menos (seção NÍVEIS; no nível 3, um ' +
    'comando com um só trecho só troca o verbo);\n' +
    '(b) regra 5, como o código a aplica: a paráfrase usa pelo menos um dos "verbos permitidos" do item; e, fora dos verbos ' +
    'permitidos do item, nenhuma destas palavras ou expressões aparece como palavra inteira em parte nenhuma da frase, nem ' +
    'como substantivo, nem em expressão idiomática ou oração de contexto: ' + args.verbos_todos.join(', ') + '. ' +
    'Exemplos: "When you get a chance" reprova por "get" (fora de take); "take a moment" reprova por "take" (fora de take ' +
    'e guide); "head over" só vale em go_to; "let me know how many" reprova em count_objects e count_people;\n' +
    '(c) regra 9: inglês natural, que uma pessoa diria ao robô.\n' +
    'Não julgue a cópia dos trechos nem o sentido: isso é de outro revisor.',
}

function promptVerificar(lente, lote, par) {
  const blocos = lote.map(it => `${it.bloco}\n  paráfrase: ${par[it.id]}`)
  return ISOLA + 'Você é um revisor independente de paráfrases de comandos dados a um robô. ' +
    'As paráfrases abaixo deviam seguir estas regras:\n\n' + REGRAS_SEM_ENTRADA + '\n\n' + LENTES[lente] +
    '\n\nPARÁFRASES A REVISAR\n\n' + blocos.join('\n\n') +
    '\n\nDevolva pela saída estruturada, no campo veredictos, um objeto por item: id; aprovada (true só se o item ' +
    'cumpre tudo o que esta lente confere; na dúvida, false); motivo (uma frase; se reprovar, cite a regra e o trecho).'
}

// Devolve {id: objeto da resposta}; chama de novo, sem gastar rodada, para os ids que faltarem.
async function chamar(lote, montar, rotulo, fase, schema, campo) {
  const out = {}
  let falta = lote
  for (let t = 1; t <= MAX_TENTATIVAS && falta.length; t++) {
    const ids = falta.map(i => i.id)
    const r = await agent(montar(falta), {
      label: rotulo + (t > 1 ? ` (tentativa ${t})` : ''), phase: fase, schema: schema(ids), effort: EFFORT,
    })
    for (const x of (r && r[campo]) || []) if (ids.includes(x.id) && !(x.id in out)) out[x.id] = x
    falta = falta.filter(i => !(i.id in out))
    if (falta.length) log(`${rotulo}: ${falta.length} item(ns) sem resposta na tentativa ${t}`)
  }
  return out
}

async function nivel(n, itens) {
  const finais = [], historico = [], ultima = {}
  let pendentes = itens
  let fb = {}
  for (const it of itens) if (args.feedback && args.feedback[it.id]) fb[it.id] = args.feedback[it.id]
  for (let rodada = 0; rodada <= MAX_RODADA && pendentes.length; rodada++) {
    const ger = await chamar(pendentes, l => promptGerar(l, fb), `gerar N${n} r${rodada}`, 'Gerar', schemaGerar, 'parafrases')
    const par = {}
    for (const id in ger) par[id] = ger[id].parafrase
    const comTexto = pendentes.filter(it => it.id in par)
    let vs = {}, vn = {}
    if (comTexto.length) {
      const r = await parallel([
        () => chamar(comTexto, l => promptVerificar('sentido', l, par), `sentido N${n} r${rodada}`, 'Verificar', schemaVerificar, 'veredictos'),
        () => chamar(comTexto, l => promptVerificar('nivel', l, par), `nivel N${n} r${rodada}`, 'Verificar', schemaVerificar, 'veredictos'),
      ])
      vs = r[0] || {}
      vn = r[1] || {}
    }
    const proximoFb = {}, proximos = []
    for (const it of pendentes) {
      const p = it.id in par ? par[it.id] : null
      const s = vs[it.id], v = vn[it.id]
      historico.push({ id: it.id, nivel: n, rodada, parafrase: p,
        sentido: s ? { aprovada: s.aprovada, motivo: s.motivo } : null,
        lente_nivel: v ? { aprovada: v.aprovada, motivo: v.motivo } : null })
      if (p !== null && s && s.aprovada === true && v && v.aprovada === true) {
        finais.push({ id: it.id, parafrase: p, rodada })
        continue
      }
      const motivos = []
      if (p === null) motivos.push('o gerador não devolveu paráfrase')
      else {
        if (!s) motivos.push('sem veredito da lente sentido')
        else if (s.aprovada !== true) motivos.push(`sentido: ${s.motivo}`)
        if (!v) motivos.push('sem veredito da lente nível')
        else if (v.aprovada !== true) motivos.push(`nível: ${v.motivo}`)
      }
      ultima[it.id] = { parafrase: p, motivos }
      if (p !== null) proximoFb[it.id] = { parafrase: p, motivo: motivos.join(' | ') }
      else if (fb[it.id]) proximoFb[it.id] = fb[it.id]
      proximos.push(it)
    }
    log(`N${n} rodada ${rodada}: ${pendentes.length - proximos.length} aprovadas, ${proximos.length} pendentes`)
    pendentes = proximos
    fb = proximoFb
  }
  return { finais, historico, reprovadas: pendentes.map(it => ({ id: it.id, nivel: n, ...ultima[it.id] })) }
}

const porNivel = {}
for (const it of args.itens) (porNivel[it.nivel] = porNivel[it.nivel] || []).push(it)
const niveis = Object.keys(porNivel).map(Number).sort((a, b) => a - b)
log(`${args.itens.length} itens em ${niveis.length} níveis` +
  (args.feedback ? `, ${Object.keys(args.feedback).length} com motivo anterior` : ''))
const res = await parallel(niveis.map(n => () => nivel(n, porNivel[n])))
const finais = [], reprovadas = [], historico = []
res.forEach((r, k) => {
  const n = niveis[k]
  if (!r) {
    log(`N${n}: o laço falhou; os ${porNivel[n].length} itens ficam como reprovados`)
    for (const it of porNivel[n]) reprovadas.push({ id: it.id, nivel: n, parafrase: null, motivos: ['o laço do nível falhou'] })
    return
  }
  finais.push(...r.finais)
  reprovadas.push(...r.reprovadas)
  historico.push(...r.historico)
})
const porId = (a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
finais.sort(porId)
reprovadas.sort(porId)
log(`fim: ${finais.length} aprovadas, ${reprovadas.length} reprovadas`)
return { args, finais, reprovadas, historico }
