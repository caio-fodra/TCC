"""Metricas de avaliacao (Secao 3.4) sobre registros planos.

Tres dimensoes: acuracia por correspondencia exata (com intervalo de Wilson), desempenho por
campo (acuracia = revocacao, mais precisao e F1) e latencia (descritivas). `divergencias` lista os
casos em que a saida difere do gabarito, para a analise de erros. A estabilidade frente a
parafrases e um indicador derivado (delta), nao uma metrica a parte.

Registro de execucao esperado (um por comando):
    {"id", "texto", "gabarito": {...}, "saida": {"registro": {...}, "latencia_s", "erro", ...}}
"""

from __future__ import annotations

import math
import statistics

from tcc.domain import CAMPOS
from tcc.schema import registros_iguais

Z = 1.959963984540054  # 95%


def wilson(acertos: int, n: int, z: float = Z) -> tuple[float, float]:
    """Intervalo de Wilson a 95% para uma proporcao (em pontos percentuais)."""
    if n == 0:
        return (0.0, 0.0)
    p = acertos / n
    denom = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denom
    margem = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, (centro - margem)) * 100, min(1.0, (centro + margem)) * 100)


def _validos(registros: list[dict]) -> list[dict]:
    return [r for r in registros if not r["saida"].get("erro")]


def acertos_por_comando(registros: list[dict]) -> list[bool]:
    """Acerto por correspondencia exata, comando a comando (base da acuracia e do McNemar)."""
    return [not r["saida"].get("erro") and registros_iguais(r["saida"].get("registro", {}), r["gabarito"])
            for r in registros]


def avaliar_exata(registros: list[dict]) -> dict:
    """Proporcao de comandos cuja saida coincide integralmente com o gabarito."""
    n = len(registros)
    acertos = sum(acertos_por_comando(registros))
    low, high = wilson(acertos, n)
    return {"n": n, "acertos": acertos, "acuracia": (acertos / n if n else 0.0),
            "ic95_wilson": [low, high]}


def avaliar_por_campo(registros: list[dict]) -> dict:
    """Para cada campo: suporte, acertos, acuracia(=revocacao), precisao, F1 e tipos de erro."""
    saida: dict = {}
    micro = {"acertos": 0, "subst": 0, "omiss": 0, "insercoes": 0, "suporte": 0}
    for campo in CAMPOS:
        acertos = subst = omiss = insercoes = suporte = 0
        for r in registros:
            gab = r["gabarito"]
            pred = {} if r["saida"].get("erro") else r["saida"].get("registro", {})
            g = gab.get(campo)
            p = pred.get(campo)
            if g is not None:
                suporte += 1
                if p is None:
                    omiss += 1
                elif p == g:
                    acertos += 1
                else:
                    subst += 1
            else:
                if p is not None:
                    insercoes += 1
        preditos = acertos + subst + insercoes
        precisao = acertos / preditos if preditos else 0.0
        revocacao = acertos / suporte if suporte else 0.0
        f1 = (2 * precisao * revocacao / (precisao + revocacao)) if (precisao + revocacao) else 0.0
        saida[campo] = {"suporte": suporte, "acertos": acertos, "acuracia": revocacao,
                        "precisao": precisao, "revocacao": revocacao, "f1": f1,
                        "substituicoes": subst, "omissoes": omiss, "insercoes": insercoes}
        if campo != "acao":
            micro["acertos"] += acertos
            micro["subst"] += subst
            micro["omiss"] += omiss
            micro["insercoes"] += insercoes
            micro["suporte"] += suporte
    preditos = micro["acertos"] + micro["subst"] + micro["insercoes"]
    prec = micro["acertos"] / preditos if preditos else 0.0
    rev = micro["acertos"] / micro["suporte"] if micro["suporte"] else 0.0
    f1 = (2 * prec * rev / (prec + rev)) if (prec + rev) else 0.0
    saida["_f1_micro_entidades"] = {"suporte": micro["suporte"], "acertos": micro["acertos"],
                                    "precisao": prec, "revocacao": rev, "f1": f1}
    return saida


def avaliar_latencia(registros: list[dict]) -> dict:
    """Descritivas da latencia por comando; comandos com erro ficam de fora."""
    validos = _validos(registros)
    lat = [r["saida"]["latencia_s"] for r in validos if r["saida"].get("latencia_s") is not None]
    excluidos = len(registros) - len(lat)
    if not lat:
        return {"n": 0, "excluidos": excluidos}
    o = sorted(lat)

    def pct(p):
        if len(o) == 1:
            return o[0]
        pos = (len(o) - 1) * p / 100
        inf = int(pos)
        sup = min(inf + 1, len(o) - 1)
        return o[inf] * (1 - (pos - inf)) + o[sup] * (pos - inf)

    return {"n": len(o), "excluidos": excluidos, "media": statistics.fmean(o),
            "mediana": statistics.median(o),
            "desvio_padrao": statistics.stdev(o) if len(o) > 1 else 0.0,
            "minimo": o[0], "maximo": o[-1], "p95": pct(95)}


def divergencias(registros: list[dict]) -> list[dict]:
    """Casos cuja saida divergiu do gabarito (para a analise de erros)."""
    fora = []
    for r in registros:
        pred = {} if r["saida"].get("erro") else r["saida"].get("registro", {})
        if not registros_iguais(pred, r["gabarito"]):
            fora.append({"id": r["id"], "texto": r["texto"], "gabarito": r["gabarito"],
                         "saida": pred, "erro": r["saida"].get("erro")})
    return fora


def delta(valor_original: float, valor_parafrase: float) -> float:
    return valor_original - valor_parafrase
