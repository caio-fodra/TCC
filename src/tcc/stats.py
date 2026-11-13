"""Testes de significancia para amostras pareadas (Secao 3.5).

McNemar exato (binomial sobre os pares discordantes) para a correspondencia exata; Wilcoxon dos
postos sinalizados para a latencia. A correcao de Holm-Bonferroni e aplicada DENTRO de cada
familia de hipoteses (correspondencia exata de um lado, latencia do outro), porque as familias
respondem a perguntas distintas sobre grandezas de unidades distintas.
"""

from __future__ import annotations

from scipy.stats import binomtest, wilcoxon


def mcnemar_exato(acertos_a: list[bool], acertos_b: list[bool]) -> dict:
    """McNemar exato pareado para dois vetores de acerto/erro (mesma ordem de comandos)."""
    so_a = sum(1 for a, b in zip(acertos_a, acertos_b) if a and not b)
    so_b = sum(1 for a, b in zip(acertos_a, acertos_b) if b and not a)
    n = so_a + so_b
    p = float(binomtest(so_a, n, 0.5).pvalue) if n > 0 else 1.0
    return {"teste": "mcnemar", "n_pares": n, "so_a": so_a, "so_b": so_b, "p_bruto": p}


def wilcoxon_pareado(latencias_a: list[float], latencias_b: list[float]) -> dict:
    """Wilcoxon dos postos sinalizados para latencias pareadas."""
    try:
        stat, p = wilcoxon(latencias_a, latencias_b)
    except ValueError:
        stat, p = float("nan"), 1.0
    return {"teste": "wilcoxon", "n": len(latencias_a), "estatistica": float(stat), "p_bruto": float(p)}


def holm_bonferroni(pvalores: list[float]) -> list[float]:
    """p-valores corrigidos por Holm dentro de uma familia (mesma ordem da entrada)."""
    m = len(pvalores)
    ordem = sorted(range(m), key=lambda i: pvalores[i])
    corrigidos = [0.0] * m
    maior = 0.0
    for posicao, i in enumerate(ordem):
        valor = (m - posicao) * float(pvalores[i])
        maior = max(maior, valor)
        corrigidos[i] = float(min(1.0, maior))
    return corrigidos


def aplicar_familia(testes: list[dict], chave_p: str = "p_bruto", saida: str = "p_holm") -> list[dict]:
    """Acrescenta a cada teste da familia o p-valor corrigido por Holm."""
    corr = holm_bonferroni([t[chave_p] for t in testes])
    for t, p in zip(testes, corr):
        t[saida] = float(p)
        t["significativo_5pct"] = bool(p < 0.05)
    return testes
