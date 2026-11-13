"""Relatorio de metricas em Markdown, a partir de metricas.json.

Uma secao por dimensao da Secao 3.4. Nenhuma metrica fora das tres dimensoes e reportada.
"""

from __future__ import annotations

import sys

from tcc import config
from tcc.domain import CAMPOS
from tcc.io_utils import ler_json

ORDEM = ["rasa_original", "rasa_parafrase", "llm_rag_original", "llm_rag_parafrase"]
ROTULO = {"rasa_original": ("Rasa", "C_original"), "rasa_parafrase": ("Rasa", "C_parafrase"),
          "llm_rag_original": ("LLM+RAG", "C_original"), "llm_rag_parafrase": ("LLM+RAG", "C_parafrase")}


def _pct(x):
    return f"{100 * x:.1f}%" if x is not None else "--"


def _s(x, casas=4):
    return f"{x:.{casas}f} s" if x is not None else "--"


def gerar(m: dict) -> str:
    L = ["# Relatorio de metricas (versao plana)", "",
         "Uma secao por dimensao da Secao 3.4. Delta de acuracia/campo = canonico - parafrase "
         "(positivo = queda).", ""]
    pe = m["por_execucao"]
    presentes = [e for e in ORDEM if e in pe]

    # 1. Acuracia exata
    L += ["## 1. Acuracia por correspondencia exata (3.4.1)", "",
          "| Arquitetura | Subconjunto | n | Acertos | Acuracia | IC 95% (Wilson) |",
          "|---|---|---:|---:|---:|---|"]
    for e in presentes:
        a, s = ROTULO[e]
        ex = pe[e]["exata"]
        ic = ex["ic95_wilson"]
        L.append(f"| {a} | {s} | {ex['n']} | {ex['acertos']} | {_pct(ex['acuracia'])} | "
                 f"[{ic[0]:.1f}; {ic[1]:.1f}] |")
    L.append("")
    if m.get("estabilidade"):
        L += ["**Estabilidade (delta da acuracia exata).**", "",
              "| Arquitetura | Canonico | Parafrase | Delta |", "|---|---:|---:|---:|"]
        for arq, d in m["estabilidade"].items():
            ac = d["acuracia_exata"]
            L.append(f"| {arq} | {_pct(ac['original'])} | {_pct(ac['parafrase'])} | "
                     f"{ac['delta_pp']:+.1f} pp |")
        L.append("")

    # 2. Por campo
    L += ["## 2. Desempenho por campo (3.4.2)", "",
          "Acuracia = revocacao; precisao e F1 acompanham. Alinhamento por campo do registro plano.", ""]
    for campo in CAMPOS:
        L += [f"### Campo `{campo}`", "",
              "| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for e in presentes:
            a, s = ROTULO[e]
            c = pe[e]["por_campo"][campo]
            L.append(f"| {a} | {s} | {c['suporte']} | {c['acertos']} | {_pct(c['acuracia'])} | "
                     f"{c['precisao']:.3f} | {c['revocacao']:.3f} | {c['f1']:.3f} | "
                     f"{c['substituicoes']} | {c['omissoes']} | {c['insercoes']} |")
        L.append("")
    L += ["### F1 micro de entidades (todos os campos menos `acao`)", "",
          "| Arquitetura | Subconjunto | Suporte | Acertos | Precisao | Revocacao | F1 |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for e in presentes:
        a, s = ROTULO[e]
        mic = pe[e]["por_campo"]["_f1_micro_entidades"]
        L.append(f"| {a} | {s} | {mic['suporte']} | {mic['acertos']} | {mic['precisao']:.3f} | "
                 f"{mic['revocacao']:.3f} | {mic['f1']:.3f} |")
    L.append("")

    # 3. Latencia
    L += ["## 3. Latencia (3.4.3)", "",
          "| Arquitetura | Subconjunto | n | Excluidos | Media | Mediana | Desvio | Minimo | Maximo | p95 |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for e in presentes:
        a, s = ROTULO[e]
        lt = pe[e]["latencia"]
        if lt.get("n"):
            L.append(f"| {a} | {s} | {lt['n']} | {lt['excluidos']} | {_s(lt['media'])} | "
                     f"{_s(lt['mediana'])} | {_s(lt['desvio_padrao'])} | {_s(lt['minimo'])} | "
                     f"{_s(lt['maximo'])} | {_s(lt['p95'])} |")
    L.append("")

    # 4. Testes
    t = m.get("testes", {})
    if t.get("correspondencia_exata") or t.get("latencia"):
        L += ["## 4. Testes de significancia para amostras pareadas (3.5)", "",
              "| Teste | Comparacao | n | So A | So B | p bruto | p (Holm) | Sig. 5% |",
              "|---|---|---:|---:|---:|---:|---:|:---:|"]
        for teste in t.get("correspondencia_exata", []):
            sig = "sim" if teste.get("significativo_5pct") else "nao"
            L.append(f"| McNemar | {teste['comparacao']} | {teste['n_pares']} | {teste['so_a']} | "
                     f"{teste['so_b']} | {teste['p_bruto']:.2e} | {teste['p_holm']:.2e} | {sig} |")
        for teste in t.get("latencia", []):
            sig = "sim" if teste.get("significativo_5pct") else "nao"
            L.append(f"| Wilcoxon | {teste['comparacao']} | {teste['n']} | -- | -- | "
                     f"{teste['p_bruto']:.2e} | {teste['p_holm']:.2e} | {sig} |")
        L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    mpath = config.DIR_RESULTADOS / "metricas.json"
    if not mpath.exists():
        print(f"sem {mpath}; rode run_experiment --consolidar antes.", file=sys.stderr)
        return 1
    m = ler_json(mpath)
    saida = config.DIR_RESULTADOS / "relatorio_metricas.md"
    saida.write_text(gerar(m), encoding="utf-8")
    print(f"relatorio gravado em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
