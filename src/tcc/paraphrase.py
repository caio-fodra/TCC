"""Construcao do conjunto de parafrases (C_parafrase), gerado por agentes Claude.

Uma parafrase por comando canonico, escrita por agentes Claude (`PARAFRASEADOR`) num workflow do
Claude Code (`scripts/gerar_parafrases.workflow.js`). O workflow recebe `REGRAS` e os itens de
`python -m tcc.paraphrase --itens`; outros agentes conferem o sentido e o nivel, e as reprovadas
voltam ao gerador com o motivo. A saida fica em `data/parafrases_claude.jsonl`
(`{"id": "orig-XXX", "parafrase": ..., "rodada": ..., "workflow": ...}`), gravada a partir do
registro do workflow, sem edicao manual.

Cada comando recebe um NIVEL de distancia do original (1 = proxima, 5 = mais distante), em rodizio
sobre os comandos ordenados por acao: 20 comandos por nivel, e cada acao espalhada pelos niveis.

`python -m tcc.paraphrase --finalizar` confere as regras verificaveis (`validar`, mais a diferenca
em relacao a todo C_original) e grava `comandos_parafrase.jsonl` no formato do experimento, com o
gabarito e o nivel do comando canonico. A validacao e lexical: a transformacao do nivel, o sentido
e a naturalidade ficam com os agentes verificadores.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from tcc import config
from tcc.domain import ME, canon_basico, carregar_dominio
from tcc.io_utils import gravar_jsonl, ler_jsonl
from tcc.schema import normalizar_texto
from tcc.surface import localizar, presente

N_NIVEIS = 5

#: Modelo dos agentes do workflow que gerou C_parafrase (o da sessao do Claude Code).
PARAFRASEADOR = "claude-opus-5-5"

#: Prompt dos agentes geradores: as regras de 2026-11-03, com exemplos fora do C_original (um
#: exemplo que fosse item de teste seria copiado pelo gerador). O workflow troca a ultima linha
#: pelos blocos de `formatar_item`.
REGRAS = """\
Você vai escrever paráfrases de comandos dados a um robô de serviço doméstico (RoboCup@Home).
Cada paráfrase precisa pedir ao robô exatamente a mesma tarefa que o comando original, com uma
transformação de forma definida pelo nível do item. Escreva em inglês.

REGRAS GERAIS (valem para todos os níveis)

1. Mesmo sentido. A mesma ação, os mesmos objetos, locais, pessoas e informações. Nada é
   acrescentado, retirado ou trocado. Uma única ação: não acrescente outra ação (como "check the
   sofa and ...") nem junte ações.
2. Termos do domínio copiados ao pé da letra. Os trechos listados em "trechos a copiar" devem
   aparecer exatamente como estão, sem sinônimo, sem mudar singular ou plural e sem acrescentar
   substantivo ou quantidade. Errado: "a bottle of red wine" no lugar de "a red wine".
3. Nenhum elemento novo do domínio. Não mencione objeto, categoria, cômodo, local ou nome que não
   esteja no original.
4. Se o original tem "me" como destinatário (bring me, give me), a paráfrase também tem "me".
5. Verbo. Use um dos "verbos permitidos" do item e nenhum verbo de outra ação, nem como verbo
   auxiliar. Verbos por ação:
   go_to: go, navigate, head, move, proceed, walk
   take: take, get, grasp, fetch, grab, pick up
   deliver: bring, give, hand
   find_object / find_person: find, locate, look for, search for
   meet: meet, get to know, get acquainted with
   greet: greet, salute, say hello to, introduce yourself to, say hi to
   follow: follow, go after
   guide: guide, escort, take, lead
   count_objects / count_people: tell me how many, count, how many
   tell_person_info / tell_object_property: tell, say, report, let me know
   talk_info: tell, say, inform
6. Ordem direta ao robô. Sem ponto de interrogação e sem fórmula de pedido polido: não comece
   com could you, can you, would you, will you, can I, could I, do you, e não use please. As
   molduras dos níveis 4 e 5 são permitidas.
7. Diferente do original. A paráfrase não pode ser igual ao original quando se ignoram caixa,
   pontuação e artigos. Errado: "get a lemon" -> "get the lemon".
8. Tamanho entre a metade e o triplo do número de palavras do original.
9. Inglês natural, que uma pessoa diria ao robô. Errado: "Storage rack contains the objects;
   report the heaviest object."

NÍVEIS (faça exatamente a transformação do nível do item, nem mais nem menos)

Nível 1: troque só o verbo principal por outro verbo permitido. Todas as outras palavras e a
  ordem ficam iguais.
  locate a standing person in the office -> search for a standing person in the office
Nível 2: troque o verbo e as palavras funcionais (artigos, preposições). Pode acrescentar um
  advérbio neutro (now, right away, immediately). A ordem fica igual, e nenhum substantivo é
  acrescentado.
  get a lemon from the side tables -> grab a lemon off the side tables
Nível 3: troque o verbo e mude a posição do trecho de local ou de pessoa, levando junto a sua
  preposição, por exemplo para o início da frase, seguido de vírgula.
  tell me what is the smallest fruit on the refrigerator -> On the refrigerator, report the smallest fruit.
  Errado: "side tables, take a drink" (perdeu o "from").
  Se o comando tem um só trecho (go to the X), não há o que mover: troque só o verbo.
  navigate to the coatrack -> Proceed to the coatrack.
  Errado: "at the entrance go" (a entrada deixa de ser destino).
Nível 4: reescreva a ordem dentro de uma moldura declarativa (I need you to ..., Your task is
  to ..., You should ...), com outro verbo permitido.
  take a snack from the side tables -> I need you to pick up the snack from the side tables.
Nível 5: comece com uma oração de contexto curta seguida de vírgula (When you have a moment,
  When you're ready,), sem termo do domínio e sem ação. Depois, a ordem em estilo coloquial.
  give me a tuna from the sofa ->
  when you have a moment, hand me a tuna from the sofa
  Errado: "When you enter the bathroom, ..." (o contexto tem termo do domínio e uma ação).

ENTRADA
Cada item vem neste formato:
  id: exemplo-1
  nível: 5
  ação: find_object
  original: find a cleanser in the bedroom
  trechos a copiar: cleanser | bedroom
  verbos permitidos: find, locate, look for, search for

SAÍDA
Uma linha JSON por item, sem nenhum outro texto:
{"id": "exemplo-1", "parafrase": "..."}

ITENS
[cole aqui os itens]"""

#: Verbos admitidos por acao, para que a parafrase nao mude a acao: a lista da propria gramatica
#: GPSR (`verb_dict` do gerador) mais os sinonimos declarados em _VERBOS_EXTRA.
_CHAVE_VERBO_GPSR = {
    "go_to": "goVerb", "take": "takeVerb", "deliver": "bringVerb", "find_object": "findVerb",
    "find_person": "findVerb", "meet": "meetVerb", "greet": "greetVerb", "follow": "followVerb",
    "guide": "guideVerb", "count_objects": "countVerb", "count_people": "countVerb",
    "tell_person_info": "tellVerb", "tell_object_property": "tellVerb", "talk_info": "talkVerb",
}
_VERBOS_EXTRA = {
    "go_to": ["head", "move", "proceed", "walk"],
    "take": ["grab", "pick up"],
    "deliver": ["hand"],
    "find_object": ["search for"],
    "find_person": ["search for"],
    "meet": ["get to know", "get acquainted with"],  # da rememberVerb da propria gramatica
    "greet": ["say hi to"],
    "follow": ["go after"],
    "guide": [],
    "count_objects": ["count", "how many"],
    "count_people": ["count", "how many"],
    "tell_person_info": ["say", "report", "let me know"],
    "tell_object_property": ["say", "report", "let me know"],
    "talk_info": ["inform"],
}


def verbos_admitidos(acao: str, dominio) -> list[str]:
    return dominio.gerador.verb_dict[_CHAVE_VERBO_GPSR[acao]] + _VERBOS_EXTRA[acao]


def todos_os_verbos(dominio) -> set[str]:
    """Toda palavra que a validacao trata como verbo de alguma acao (gramatica GPSR e extras)."""
    return {v for vs in dominio.gerador.verb_dict.values() for v in vs} | {v for vs in _VERBOS_EXTRA.values() for v in vs}


def problemas_de_verbo(texto: str, acao: str, dominio) -> list[str]:
    """Exige um verbo da acao e nenhum verbo de outra acao (que mudaria ou somaria acoes).

    shortcut: confere palavras, nao a sintaxe; "get" numa oracao de contexto passaria por take.
    A revisao manual continua sendo a garantia final do sentido.
    """
    admitidos = verbos_admitidos(acao, dominio)
    resto = texto.lower()
    for v in sorted(admitidos, key=len, reverse=True):  # remove "tell me how many" antes de "tell"
        resto = re.sub(rf"\b{re.escape(v)}\b", " ", resto)
    if resto == texto.lower():
        return [f"verbo fora da lista da acao {acao}"]
    outros = sorted(v for v in todos_os_verbos(dominio) - set(admitidos) if re.search(rf"\b{re.escape(v)}\b", resto))
    return [f"verbo de outra acao: {', '.join(outros)}"] if outros else []


def atribuir_niveis(originais: list[dict]) -> dict[str, int]:
    ordenados = sorted(originais, key=lambda r: (r["gabarito"]["acao"], r["id"]))
    return {r["id"]: i % N_NIVEIS + 1 for i, r in enumerate(ordenados)}


def _valores_dominio(gabarito: dict) -> list[str]:
    return [v for c, v in gabarito.items() if c != "acao" and v and v != ME]


def _entidades_nominais(dominio) -> set[str]:
    k = dominio.knowledge
    # O parser devolve nomes com maiuscula ("Paris"); a comparacao e feita em minusculas.
    return {e.lower() for e in (*k.objects, *k.object_categories_singular, *k.rooms, *k.locations, *k.names)}


def termos_a_copiar(texto: str, gabarito: dict, dominio) -> list[str]:
    """Trechos do comando (forma de superficie) que a parafrase precisa repetir literalmente."""
    spans = [localizar(texto, v, dominio) for v in _valores_dominio(gabarito)]
    if ME in gabarito.values():
        m = re.search(r"\bme\b", texto, flags=re.IGNORECASE)
        spans.append(m.span() if m else None)
    if None in spans:
        raise ValueError(f"valor do gabarito sem trecho no texto: {texto!r} {gabarito}")
    return [texto[a:b] for a, b in sorted(spans)]


def formatar_item(comando: dict, nivel: int, dominio) -> str:
    """Bloco de um item no formato ENTRADA de `REGRAS`."""
    acao = comando["gabarito"]["acao"]
    return "\n".join([
        f"  id: {comando['id']}",
        f"  nível: {nivel}",
        f"  ação: {acao}",
        f"  original: {comando['texto']}",
        f"  trechos a copiar: {' | '.join(termos_a_copiar(comando['texto'], comando['gabarito'], dominio))}",
        f"  verbos permitidos: {', '.join(verbos_admitidos(acao, dominio))}",
    ])


def itens() -> dict:
    """Entrada do workflow: as regras, o bloco de cada comando de C_original e, para o verificador,
    as palavras que a validacao trata como verbo (a regra 5 como o codigo a aplica)."""
    dominio = carregar_dominio(str(config.DIR_DOMINIO))
    originais = ler_jsonl(config.ARQ_COMANDOS_ORIGINAL)
    niveis = atribuir_niveis(originais)
    return {"regras": REGRAS, "verbos_todos": sorted(todos_os_verbos(dominio)),
            "itens": [{"id": r["id"], "nivel": niveis[r["id"]], "bloco": formatar_item(r, niveis[r["id"]], dominio)}
                      for r in originais]}


def validar(original: str, parafrase: str, gabarito: dict, dominio) -> list[str]:
    """Checagens automaticas; devolve lista de problemas (vazia = ok)."""
    problemas = []
    p = parafrase.strip()
    if not p:
        return ["vazia"]
    # Sem artigos: "get the toy" no lugar de "get a toy" nao e parafrase (a avaliacao ignora artigos).
    if canon_basico(p) == canon_basico(original):
        problemas.append("identica ao original")
    baixo = p.lower().lstrip()
    if baixo.endswith("?") or any(baixo.startswith(x) for x in
            ("could you", "can you", "would you", "will you", "can i", "could i", "do you")):
        problemas.append("forma de pedido/pergunta (use imperativo)")
    for valor in _valores_dominio(gabarito):
        if not presente(p, valor, dominio):
            problemas.append(f"termo do dominio perdido: {valor}")
    if ME in gabarito.values() and not re.search(r"\bme\b", p.lower()):
        problemas.append(f"termo do dominio perdido: {ME}")
    problemas += problemas_de_verbo(p, gabarito["acao"], dominio)
    # Razao de tamanho.
    no, npf = len(original.split()), len(p.split())
    if npf and not (0.5 <= npf / no <= 3.0):
        problemas.append(f"tamanho fora do intervalo (razao {npf/no:.2f})")
    # Entidades nominais novas (ausentes do original).
    nominais = _entidades_nominais(dominio)
    orig_norm = f" {normalizar_texto(original)} "
    par_norm = f" {normalizar_texto(p)} "
    for ent in nominais:
        if f" {ent} " in par_norm and f" {ent} " not in orig_norm:
            problemas.append(f"entidade nova introduzida: {ent}")
    return problemas


def finalizar() -> int:
    dominio = carregar_dominio(str(config.DIR_DOMINIO))
    originais = ler_jsonl(config.ARQ_COMANDOS_ORIGINAL)
    niveis = atribuir_niveis(originais)
    lidas = ler_jsonl(config.ARQ_PARAFRASES_CLAUDE)
    # Exatamente os ids de C_original: num dict, um id duplicado sobrescreveria o outro calado.
    ids, esperados = [r["id"] for r in lidas], [r["id"] for r in originais]
    if sorted(ids) != sorted(esperados):
        print(f"ATENCAO: {config.ARQ_PARAFRASES_CLAUDE.name} precisa ter uma parafrase para cada um dos "
              f"{len(esperados)} ids de C_original. Faltando: {sorted(set(esperados) - set(ids))}; "
              f"sobrando: {sorted(set(ids) - set(esperados))}; "
              f"duplicados: {sorted({i for i in ids if ids.count(i) > 1})}")
        return 1
    escritas = {r["id"]: r["parafrase"] for r in lidas}
    # Uma parafrase igual a outro comando canonico tambem nao mede generalizacao.
    canonicos = {canon_basico(r["texto"]) for r in originais}
    comandos = []
    falhas = []
    for r in originais:
        p = escritas[r["id"]]
        problemas = validar(r["texto"], p, r["gabarito"], dominio)
        if canon_basico(p) in canonicos and "identica ao original" not in problemas:
            problemas.append("igual a outro comando de C_original")
        if problemas:
            falhas.append((r["id"], problemas))
        comandos.append({"id": r["id"].replace("orig", "para"), "texto": p, "gabarito": r["gabarito"],
                         "origem_id": r["id"], "nivel": niveis[r["id"]], "parafraseador": PARAFRASEADOR})
    if falhas:
        print(f"ATENCAO: {len(falhas)} parafrases falham a validacao automatica:")
        for id_, probs in falhas:
            print(f"   {id_}: {probs}")
        print("Gere esses itens de novo no workflow, com o motivo, antes de finalizar (sem edicao manual).")
        return 1
    total = gravar_jsonl(config.ARQ_COMANDOS_PARAFRASE, comandos)
    print(f"{total} parafrases validadas gravadas em {config.ARQ_COMANDOS_PARAFRASE}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Entrada do workflow de parafrases (--itens) e validacao "
                                                 "das parafrases dos agentes Claude, que grava C_parafrase (--finalizar)")
    parser.add_argument("--itens", action="store_true", help="imprime o JSON {regras, itens} do workflow")
    parser.add_argument("--finalizar", action="store_true")
    args = parser.parse_args(argv)
    if args.itens:
        print(json.dumps(itens()))  # ASCII (ensure_ascii): o console do Windows nao quebra os acentos
        return 0
    if args.finalizar:
        return finalizar()
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
