"""Contrato comum das arquiteturas avaliadas (versao plana).

As duas arquiteturas expoem a mesma interface -- `aquecer()` e `interpretar(texto)` -- e
devolvem um `ResultadoInterpretacao` com UM registro plano (`registro`), a latencia e
diagnosticos. O laco de medicao em `run_experiment` nao tem nenhum ramo condicional por
arquitetura: as duas passam pelo mesmo caminho.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ResultadoInterpretacao:
    registro: dict = field(default_factory=dict)  # registro plano normalizado
    latencia_s: float = 0.0
    bruto: object = None
    detalhes: dict = field(default_factory=dict)
    erro: str | None = None

    @property
    def ok(self) -> bool:
        return self.erro is None

    def como_dict(self) -> dict:
        return {
            "registro": self.registro,
            "latencia_s": self.latencia_s,
            "bruto": self.bruto,
            "detalhes": self.detalhes,
            "erro": self.erro,
        }


@runtime_checkable
class Arquitetura(Protocol):
    nome: str

    def aquecer(self) -> None: ...
    def interpretar(self, texto: str) -> ResultadoInterpretacao: ...
    def descrever(self) -> dict: ...
