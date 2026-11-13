"""Gera o conjunto de 100 comandos canonicos (C_original) com gabarito plano.

Amostragem estratificada: primeiro um comando por template da gramatica (cobertura), depois
o restante pelo sorteio ponderado do proprio gerador, com rejeicao de duplicatas e semente
fixa. Cada comando e de UMA acao (cabeca do template) e traz o gabarito plano.

Uso:
    python -m tcc.generate_dataset -n 100 --seed 42
    python -m tcc.generate_dataset --self-check -n 5000
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter

from tcc import config
from tcc.annotated_generator import GeradorPlano
from tcc.io_utils import gravar_jsonl
from tcc.paraphrase import problemas_de_verbo
from tcc.schema import normalizar_texto

_TENTATIVAS_POR_COMANDO = 200


def gerar_conjunto(n: int, seed: int, prefixo: str = "orig") -> list[dict]:
    random.seed(seed)
    gp = GeradorPlano(str(config.DIR_DOMINIO))
    vistos: set[str] = set()
    comandos = []

    def tentar(c) -> bool:
        chave = normalizar_texto(c.texto)
        if chave in vistos:
            return False
        vistos.add(chave)
        comandos.append(c)
        return True

    # Estratificacao: ao menos um comando por template.
    for tmpl in gp.templates:
        for _ in range(_TENTATIVAS_POR_COMANDO):
            if tentar(gp.gerar(tmpl)):
                break

    # Restante por sorteio ponderado do gerador.
    tentativas = 0
    while len(comandos) < n and tentativas < n * _TENTATIVAS_POR_COMANDO:
        tentativas += 1
        tentar(gp.gerar(gp._amostrar_template()))

    comandos = comandos[:n]
    largura = max(3, len(str(len(comandos))))
    registros = []
    for i, c in enumerate(comandos, 1):
        c.id = f"{prefixo}-{i:0{largura}d}"
        registros.append(c.como_dict())
    return registros


def self_check(n: int, seed: int) -> int:
    random.seed(seed)
    gp = GeradorPlano(str(config.DIR_DOMINIO))
    falhas = []
    acoes: Counter = Counter()
    for i in range(n):
        c = gp.gerar(gp._amostrar_template())
        acoes[c.gabarito["acao"]] += 1
        problemas = gp.norm.problemas_do_registro(c.gabarito)
        if problemas:
            falhas.append(f"{c.texto!r}: {problemas}")
        recanon = gp.norm.canonizar_registro(c.gabarito)
        if recanon != c.gabarito:
            falhas.append(f"gabarito nao canonico: {c.texto!r}")
        # A lista de verbos das parafrases precisa aceitar todo comando da propria gramatica.
        falhas += [f"{c.texto!r}: {p}" for p in problemas_de_verbo(c.texto, c.gabarito["acao"], gp.dominio)]
    print(f"comandos verificados : {n}")
    print(f"acoes cobertas       : {len(acoes)}/14  {dict(acoes.most_common())}")
    print(f"falhas               : {len(falhas)}")
    for f in falhas[:20]:
        print("   ", f)
    if falhas:
        print("\nSELF-CHECK FALHOU")
        return 1
    print("\nSELF-CHECK OK")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gera comandos GPSR de uma acao com gabarito plano")
    parser.add_argument("-n", "--num", type=int, default=config.N_COMANDOS)
    parser.add_argument("-o", "--output", default=str(config.ARQ_COMANDOS_ORIGINAL))
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)

    if args.self_check:
        return self_check(args.num, args.seed)

    config.criar_diretorios()
    registros = gerar_conjunto(args.num, args.seed)
    total = gravar_jsonl(args.output, registros)
    acoes = Counter(r["gabarito"]["acao"] for r in registros)
    n_pal = [len(r["texto"].split()) for r in registros]
    print(f"{total} comandos gravados em {args.output}")
    print(f"acoes cobertas   : {len(acoes)}/14")
    print(f"distribuicao     : {dict(acoes.most_common())}")
    print(f"palavras/comando : media {sum(n_pal)/len(n_pal):.1f} (min {min(n_pal)}, max {max(n_pal)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
