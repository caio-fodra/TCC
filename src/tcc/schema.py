"""Registro plano, normalizacao canonica e validacao de dominio.

Um registro e um dicionario com `acao` mais os campos de entidade presentes. A normalizacao
(equivalente achatada da regra R5) ignora diferencas irrelevantes -- caixa, artigos, espacos,
plural de categoria e de descricao de pessoa, marcadores de ausencia -- para que a comparacao
com o gabarito nao dependa de notacao. A validacao de dominio (regra R6) marca como alucinacao
qualquer valor fora do vocabulario do seu campo, sem corrigi-lo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tcc.domain import ACOES, CAMPOS, ME, Dominio, canon_basico

#: Valores que significam "campo ausente".
_AUSENCIA = {"", "none", "n/a", "na", "null", "unknown", "nil", "-"}
#: Formas que designam o autor do comando (ja em forma canonica basica).
_SINONIMOS_ME = {"me", "myself", "operator", "user"}


def normalizar_texto(texto: str) -> str:
    """Forma normalizada de um comando, usada para deduplicar e comparar textos."""
    t = re.sub(r"[.,;:!?]", " ", texto.strip().lower())
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class Normalizador:
    dominio: Dominio

    def canonizar_valor(self, valor) -> str | None:
        if valor is None:
            return None
        cru = canon_basico(valor)
        if cru in _AUSENCIA:
            return None
        if cru in _SINONIMOS_ME:
            return ME
        # Plural de categoria ou de descricao de pessoa -> singular.
        if cru in self.dominio.plural_para_singular:
            return self.dominio.plural_para_singular[cru]
        return cru

    def canonizar_registro(self, registro: dict) -> dict:
        """Devolve o registro so com `acao` e os campos de entidade presentes, canonizados.

        Nao filtra por acao nem corrige valores: campos fora do vocabulario permanecem, para
        serem contados como alucinacao. Campos desconhecidos (fora de CAMPOS) sao descartados.
        """
        saida: dict = {}
        acao = self.canonizar_valor(registro.get("acao")) if registro.get("acao") else None
        if acao is not None:
            saida["acao"] = acao
        for campo in CAMPOS:
            if campo == "acao":
                continue
            if campo in registro:
                v = self.canonizar_valor(registro.get(campo))
                if v is not None:
                    saida[campo] = v
        return saida

    def alucinacoes(self, registro: dict) -> list[tuple[str, str]]:
        """Pares (campo, valor) cujo valor nao pertence ao vocabulario do campo (R6)."""
        fora: list[tuple[str, str]] = []
        for campo, valor in registro.items():
            if campo not in CAMPOS or valor is None:
                continue
            if not self.dominio.valor_valido(campo, valor):
                fora.append((campo, valor))
        return fora

    def problemas_do_registro(self, registro: dict) -> list[str]:
        """Checagens de consistencia do gabarito (nao da saida das arquiteturas)."""
        problemas: list[str] = []
        acao = registro.get("acao")
        if not acao:
            problemas.append("sem acao")
            return problemas
        espec = ACOES.get(acao)
        if espec is None:
            problemas.append(f"acao desconhecida: {acao}")
            return problemas
        for obrig in espec.obrigatorios:
            if not registro.get(obrig):
                problemas.append(f"{acao}: campo obrigatorio ausente: {obrig}")
        permitidos = set(espec.campos)
        for campo in registro:
            if campo == "acao":
                continue
            if campo not in permitidos:
                problemas.append(f"{acao}: campo nao previsto: {campo}")
        problemas.extend(f"alucinacao em {c}: {v}" for c, v in self.alucinacoes(registro))
        return problemas


def registros_iguais(a: dict, b: dict) -> bool:
    """Igualdade de dois registros canonizados (mesmos campos e valores)."""
    campos = set(a) | set(b)
    return all(a.get(c) == b.get(c) for c in campos)
