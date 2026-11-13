"""Gera os arquivos do projeto Rasa (versao plana) a partir de comandos de uma acao.

Cada comando de treino vira UM exemplo de NLU: a intencao e a acao do gabarito e cada campo
de entidade e anotado com seu span no texto. Nao ha segmentacao, anafora nem regra R4 -- o
Rasa recebe o comando inteiro, classifica uma intencao e extrai as entidades, que mapeiam
diretamente nos campos. Os exemplos sao gerados com semente distinta da do teste, deduplicados,
livres de coincidencia com o teste (desconsiderados caixa, pontuacao e artigos) e limitados por
intencao.

Uso:
    python -m tcc.build_rasa_data            # usa os conjuntos de teste ja gerados
    python -m tcc.build_rasa_data --n 3000
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path

from tcc import config
from tcc.annotated_generator import Comando, GeradorPlano
from tcc.domain import ACOES, CAMPOS_ENTIDADE, canon_basico
from tcc.io_utils import ler_jsonl
from tcc.surface import localizar

ENTIDADES = list(CAMPOS_ENTIDADE)  # objeto, pessoa, origem, destino, local, atributo, informacao
INTENCOES = list(ACOES.keys())


def _anotar(comando: Comando, gp: GeradorPlano) -> str:
    """Devolve o texto com as entidades marcadas no formato do Rasa: [superficie](entidade)."""
    texto = comando.texto
    marcas: list[tuple[int, int, str]] = []
    ocupados: list[tuple[int, int]] = []
    # Valores mais longos primeiro, para nao casar um prefixo dentro de outro valor.
    campos = sorted(
        ((c, v) for c, v in comando.gabarito.items() if c in ENTIDADES),
        key=lambda cv: len(str(cv[1])),
        reverse=True,
    )
    for campo, valor in campos:
        span = localizar(texto, valor, gp.dominio, ocupados)
        if span is None:
            continue  # valor preenchido por convencao sem superficie (nao ocorre na versao plana)
        marcas.append((span[0], span[1], campo))
        ocupados.append(span)
    # Reconstroi o texto inserindo as marcas, da direita para a esquerda.
    for ini, fim, campo in sorted(marcas, reverse=True):
        superficie = texto[ini:fim]
        texto = f"{texto[:ini]}[{superficie}]({campo}){texto[fim:]}"
    return texto


def gerar_exemplos(n: int, textos_teste: set[str], gp: GeradorPlano):
    random.seed(config.SEED_TREINO_RASA)
    vistos: set[str] = set()
    por_intencao: dict[str, list[str]] = {i: [] for i in INTENCOES}
    descartados_teste = 0
    duplicados = 0
    tentativas = 0
    limite = n * 50
    alvo_por_intencao = config.MAX_EXEMPLOS_POR_INTENCAO

    while sum(len(v) for v in por_intencao.values()) < n and tentativas < limite:
        tentativas += 1
        tmpl = gp._amostrar_template()
        c = gp.gerar(tmpl)
        # Sem artigos: "find the food" de teste tambem barra "find a food" no treino.
        chave = canon_basico(c.texto)
        if chave in vistos:
            duplicados += 1
            continue
        if chave in textos_teste:
            descartados_teste += 1
            continue
        intent = c.gabarito["acao"]
        if len(por_intencao[intent]) >= alvo_por_intencao:
            continue
        vistos.add(chave)
        por_intencao[intent].append(_anotar(c, gp))

    return por_intencao, {
        "duplicados_removidos": duplicados,
        "coincidentes_com_teste_removidos": descartados_teste,
        "tentativas": tentativas,
    }


def _escrever_nlu(por_intencao: dict[str, list[str]], caminho: Path) -> int:
    linhas = ['version: "3.1"', "", "nlu:"]
    total = 0
    for intent in INTENCOES:
        exemplos = por_intencao.get(intent, [])
        if not exemplos:
            continue
        linhas.append(f"  - intent: {intent}")
        linhas.append("    examples: |")
        for ex in exemplos:
            linhas.append(f"      - {ex}")
            total += 1
        linhas.append("")
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return total


def _escrever_domain(caminho: Path) -> None:
    linhas = ['version: "3.1"', "", "intents:"]
    linhas += [f"  - {i}" for i in INTENCOES]
    linhas += ["", "entities:"]
    linhas += [f"  - {e}" for e in ENTIDADES]
    linhas += ["", "slots:"]
    for e in ENTIDADES:
        linhas += [
            f"  {e}:",
            "    type: text",
            "    influence_conversation: false",
            "    mappings:",
            "      - type: from_entity",
            f"        entity: {e}",
        ]
    linhas += ["", "responses:", "  utter_noop:", '    - text: "noop"', ""]
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


_CONFIG_YML = """\
# Pipeline de NLU da versao plana. DIET faz classificacao de intencao e extracao de entidade
# em conjunto. constrain_similarities e ativado (vem desligado por padrao no Rasa 3.6) e altera
# a funcao de perda. A semente fixa o treino. Nao ha politicas de dialogo: o trabalho avalia
# apenas interpretacao.
recipe: default.v1
language: en

pipeline:
  - name: WhitespaceTokenizer
  - name: RegexFeaturizer
    case_sensitive: false
  - name: LexicalSyntacticFeaturizer
  - name: CountVectorsFeaturizer
  - name: CountVectorsFeaturizer
    analyzer: char_wb
    min_ngram: 1
    max_ngram: 4
  - name: DIETClassifier
    epochs: 150
    constrain_similarities: true
    random_seed: {seed}
  - name: EntitySynonymMapper
  - name: FallbackClassifier
    threshold: {limiar}
    ambiguity_threshold: 0.1

policies: []
"""


def escrever_projeto(por_intencao, dir_projeto: Path) -> int:
    (dir_projeto / "data").mkdir(parents=True, exist_ok=True)
    _escrever_domain(dir_projeto / "domain.yml")
    (dir_projeto / "config.yml").write_text(
        _CONFIG_YML.format(seed=config.SEED_TREINO_RASA, limiar=config.LIMIAR_CONFIANCA_RASA),
        encoding="utf-8",
    )
    return _escrever_nlu(por_intencao, dir_projeto / "data" / "nlu.yml")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gera os arquivos do projeto Rasa (versao plana)")
    parser.add_argument("--n", type=int, default=config.N_TREINO_RASA)
    parser.add_argument("--dir", default=str(config.DIR_PROJETO_RASA))
    args = parser.parse_args(argv)

    gp = GeradorPlano(str(config.DIR_DOMINIO))

    # Sem os DOIS conjuntos de teste, o treino poderia conter itens de teste: ler_jsonl falha.
    textos_teste = {canon_basico(r["texto"])
                    for arq in (config.ARQ_COMANDOS_ORIGINAL, config.ARQ_COMANDOS_PARAFRASE)
                    for r in ler_jsonl(arq)}

    por_intencao, stats = gerar_exemplos(args.n, textos_teste, gp)
    total = escrever_projeto(por_intencao, Path(args.dir))

    print(f"exemplos de treino gravados : {total}")
    print(f"duplicados removidos        : {stats['duplicados_removidos']}")
    print(f"coincidentes com teste rem. : {stats['coincidentes_com_teste_removidos']}")
    dist = {i: len(por_intencao[i]) for i in INTENCOES if por_intencao[i]}
    print(f"intencoes cobertas          : {len(dist)}/{len(INTENCOES)}")
    print(f"exemplos por intencao       : {dist}")
    faltando = [i for i in INTENCOES if not por_intencao[i]]
    if faltando:
        print(f"AVISO: intencoes sem exemplo: {faltando}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
