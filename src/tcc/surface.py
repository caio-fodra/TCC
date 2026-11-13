"""Localizacao da forma de superficie de um valor do dominio em um comando.

O gabarito guarda valores canonicos (minusculas, sem artigo, categoria no singular), mas o
texto os escreve como a lingua pede (`Robin`, `drinks`, `persons pointing to the right`). Dois
pontos precisam reconciliar as duas formas: a anotacao dos exemplos de treino do Rasa (que
precisa do span exato) e a validacao das parafrases (que confere se a reformulacao preservou
os elementos do dominio). Reunir a regra aqui garante que os dois usem o mesmo criterio.
"""

from __future__ import annotations

import re

from tcc.domain import Dominio

#: Entre dois tokens de um valor canonico pode haver um artigo no texto.
_MEIO = r"\s+(?:a\s+|an\s+|the\s+)?"


def _candidatos(valor: str, dominio: Dominio) -> list[str]:
    """Formas de superficie plausiveis para um valor canonico.

    Cobre a categoria no plural (`drink`->`drinks`) e a descricao de pessoa no plural
    (`person pointing to right`->`persons pointing to the right`), as duas divergencias de
    plural que a gramatica GPSR produz.
    """
    cands = [valor]
    sing_para_plural = {s: p for p, s in dominio.plural_para_singular.items()}
    if valor in sing_para_plural:
        cands.append(sing_para_plural[valor])
    if "person" in valor:
        cands.append(valor.replace("person", "persons"))
    return cands


def regex_de_valor(valor: str) -> re.Pattern:
    """Regex que casa o valor no texto, tolerando artigos entre os tokens."""
    tokens = valor.split()
    if not tokens:
        return re.compile(r"(?!x)x")
    corpo = _MEIO.join(re.escape(t) for t in tokens)
    return re.compile(r"\b" + corpo + r"\b", flags=re.IGNORECASE)


def _colide(span, ocupados) -> bool:
    ini, fim = span
    return any(ini < o_fim and o_ini < fim for o_ini, o_fim in ocupados)


def localizar(texto: str, valor: str, dominio: Dominio, ocupados=None):
    """Primeiro trecho de `texto` que expressa `valor` e ainda nao foi consumido."""
    ocupados = ocupados or []
    for cand in _candidatos(valor, dominio):
        for m in regex_de_valor(cand).finditer(texto):
            if not _colide(m.span(), ocupados):
                return m.span()
    return None


def presente(texto: str, valor: str, dominio: Dominio) -> bool:
    return localizar(texto, valor, dominio) is not None
