"""Execucao do experimento e consolidacao das metricas (versao plana).

Duas arquiteturas (rasa, llm_rag) sobre dois subconjuntos (original, parafrase). O laco de
medicao nao tem ramo por arquitetura: as duas passam pelo mesmo caminho e gravam o mesmo tipo
de registro. A latencia so e comparavel com um servico residente por vez; por isso cada
arquitetura pode ser medida em uma passada separada (util em maquina com pouca RAM):

    python -m tcc.run_experiment --arquiteturas rasa      # 1a passada (Rasa no ar)
    python -m tcc.run_experiment --arquiteturas llm_rag   # 2a passada (Ollama no ar)
    python -m tcc.run_experiment --consolidar             # metricas, testes e divergencias

Registro de execucao (results/execucoes/<arq>_<sub>.jsonl), um por comando:
    {"id","texto","gabarito","saida":{"registro","latencia_s","erro","detalhes"},"execucao"}
"""

from __future__ import annotations

import argparse
import re
import sys
import time

from tcc import config
from tcc.domain import canon_basico, carregar_dominio
from tcc.evaluate import (acertos_por_comando, avaliar_exata, avaliar_latencia, avaliar_por_campo,
                          delta, divergencias)
from tcc.io_utils import descrever_ambiente, gravar_json, gravar_jsonl, ler_jsonl
from tcc.stats import aplicar_familia, mcnemar_exato, wilcoxon_pareado

SUBCONJUNTOS = {"original": config.ARQ_COMANDOS_ORIGINAL, "parafrase": config.ARQ_COMANDOS_PARAFRASE}


def _construir_arquitetura(nome: str, dominio):
    if nome == "rasa":
        from tcc.arch_rasa import ArquiteturaRasa
        return ArquiteturaRasa(dominio)
    if nome == "llm_rag":
        from tcc.arch_llm_rag import ArquiteturaLLMRAG
        return ArquiteturaLLMRAG(dominio)
    raise ValueError(f"arquitetura desconhecida: {nome}")


def _frases_do_prompt(exemplos: list[str]) -> set[str]:
    """Exemplos do prompt e cada oracao dos compostos ("go to X then find Y"), sem artigos."""
    # So o comando inteiro deixava passar "go to the kitchen" (teste) dentro de um exemplo composto.
    return {canon_basico(p) for t in exemplos for p in [t, *re.split(r"\s+(?:then|and)\s+", t)]}


def rodar(arquiteturas: list[str], subconjuntos: list[str]) -> None:
    config.criar_diretorios()
    dominio = carregar_dominio(str(config.DIR_DOMINIO))
    for nome in arquiteturas:
        arq = _construir_arquitetura(nome, dominio)
        print(f"[{nome}] aquecendo...")
        arq.aquecer()
        no_prompt = _frases_do_prompt(arq.descrever().get("exemplos_few_shot", []))
        for sub in subconjuntos:
            comandos = ler_jsonl(SUBCONJUNTOS[sub])
            contaminados = [c["id"] for c in comandos if canon_basico(c["texto"]) in no_prompt]
            if contaminados:
                raise SystemExit(f"[{nome}/{sub}] comandos de teste iguais a exemplos do prompt: {contaminados}")
            registros = []
            erros = 0
            t0 = time.perf_counter()
            for i, c in enumerate(comandos, 1):
                res = arq.interpretar(c["texto"])
                # json_invalido e erro do modelo; qualquer outro e do servico e nao pode virar metrica.
                if res.erro and res.erro != "json_invalido":
                    raise SystemExit(f"[{nome}/{sub}] {c['id']}: falha do servico, nada gravado: {res.erro}")
                if res.erro:
                    erros += 1
                registros.append({"id": c["id"], "texto": c["texto"], "gabarito": c["gabarito"],
                                  "saida": res.como_dict(), "execucao": f"{nome}_{sub}"})
                if i % 20 == 0:
                    print(f"  [{nome}/{sub}] {i}/{len(comandos)}")
            dur = time.perf_counter() - t0
            caminho = config.DIR_EXECUCOES / f"{nome}_{sub}.jsonl"
            gravar_jsonl(caminho, registros)
            print(f"[{nome}/{sub}] {len(registros)} comandos, {erros} erros, {dur:.1f}s -> {caminho.name}")
        gravar_json(config.DIR_RESULTADOS / f"descricao_{nome}.json", arq.descrever())
    # Um arquivo por passada: com um nome so, a passada seguinte apagava o registro da anterior.
    gravar_json(config.DIR_RESULTADOS / f"ambiente_{'_'.join(arquiteturas)}.json", {**descrever_ambiente(),
                "arquiteturas_medidas": arquiteturas, "subconjuntos": subconjuntos})


def consolidar() -> None:
    execucoes = {}
    for p in sorted(config.DIR_EXECUCOES.glob("*.jsonl")):
        execucoes[p.stem] = ler_jsonl(p)
    if not execucoes:
        print("nenhuma execucao em results/execucoes/", file=sys.stderr)
        return

    metricas = {"por_execucao": {}}
    for nome, regs in execucoes.items():
        metricas["por_execucao"][nome] = {
            "exata": avaliar_exata(regs),
            "por_campo": avaliar_por_campo(regs),
            "latencia": avaliar_latencia(regs),
        }

    # Indicador de estabilidade (delta = original - parafrase), so da acuracia exata.
    estab = {}
    for arq in ("rasa", "llm_rag"):
        o, p = f"{arq}_original", f"{arq}_parafrase"
        if o in metricas["por_execucao"] and p in metricas["por_execucao"]:
            mo, mp = metricas["por_execucao"][o], metricas["por_execucao"][p]
            estab[arq] = {
                "acuracia_exata": {"original": mo["exata"]["acuracia"], "parafrase": mp["exata"]["acuracia"],
                                   "delta_pp": 100 * delta(mo["exata"]["acuracia"], mp["exata"]["acuracia"])},
            }
    metricas["estabilidade"] = estab

    # Testes pareados, por familia.
    familia_exata, familia_lat = [], []

    def par(a, b):
        # Casa pelo numero do comando: "para-007" e a parafrase de "orig-007".
        num = lambda r: r["id"].replace("para-", "orig-", 1)  # noqa: E731
        rb = {num(r): r for r in execucoes.get(b, [])}
        ra = [r for r in execucoes.get(a, []) if num(r) in rb]
        return ra, [rb[num(r)] for r in ra]

    comparacoes = [
        ("rasa_original", "llm_rag_original", "Rasa vs LLM+RAG em C_original"),
        ("rasa_parafrase", "llm_rag_parafrase", "Rasa vs LLM+RAG em C_parafrase"),
        ("rasa_original", "rasa_parafrase", "canonico vs parafrase (rasa)"),
        ("llm_rag_original", "llm_rag_parafrase", "canonico vs parafrase (llm_rag)"),
    ]
    for a, b, desc in comparacoes:
        if a not in execucoes or b not in execucoes:
            continue
        ra, rb = par(a, b)
        if not ra:
            continue
        mc = mcnemar_exato(acertos_por_comando(ra), acertos_por_comando(rb))
        mc["comparacao"] = desc
        familia_exata.append(mc)
        # Latencia so entre arquiteturas no mesmo subconjunto (decisao de 2026-11-02: a diferenca
        # canonico x parafrase nao responde a pergunta do trabalho).
        if a.split("_")[-1] != b.split("_")[-1]:
            continue
        # Pareado: so os comandos sem erro nos DOIS lados.
        sem_erro = [(x, y) for x, y in zip(ra, rb) if not x["saida"].get("erro") and not y["saida"].get("erro")]
        if sem_erro:
            wc = wilcoxon_pareado([x["saida"]["latencia_s"] for x, _ in sem_erro],
                                  [y["saida"]["latencia_s"] for _, y in sem_erro])
            wc["comparacao"] = desc
            familia_lat.append(wc)
    if familia_exata:
        aplicar_familia(familia_exata)
    if familia_lat:
        aplicar_familia(familia_lat)
    metricas["testes"] = {"correspondencia_exata": familia_exata, "latencia": familia_lat}

    gravar_json(config.DIR_RESULTADOS / "metricas.json", metricas)

    # Divergencias para a analise de erros (com a marca da execucao de origem).
    todas = []
    for nome, regs in execucoes.items():
        for d in divergencias(regs):
            todas.append({**d, "execucao": nome})
    gravar_jsonl(config.DIR_RESULTADOS / "divergencias.jsonl", todas)
    print(f"metricas.json e divergencias.jsonl gravados ({len(todas)} divergencias).")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Executa e consolida o experimento (versao plana)")
    parser.add_argument("--arquiteturas", nargs="+", default=[], choices=["rasa", "llm_rag"])
    parser.add_argument("--subconjuntos", nargs="+", default=["original", "parafrase"],
                        choices=["original", "parafrase"])
    parser.add_argument("--consolidar", action="store_true")
    args = parser.parse_args(argv)

    if args.arquiteturas:
        rodar(args.arquiteturas, args.subconjuntos)
    if args.consolidar:
        consolidar()
    if not args.arquiteturas and not args.consolidar:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
