"""Arquitetura baseada em Rasa (versao plana).

Envia o comando INTEIRO ao servidor NLU do Rasa (um POST por comando), le a intencao e as
entidades e monta um registro plano: a intencao da a acao; cada entidade preenche o campo de
mesmo nome (prevalecendo a de maior confianca quando ha repeticao). Nao ha segmentador, nao ha
resolucao de anafora e nao ha regra R4 -- a saida e diretamente o que o classificador produz,
normalizada (R5) e com valores fora do dominio mantidos como alucinacao (R6).

O servidor roda na SUA maquina (Python 3.10, `rasa run --enable-api`), em RASA_URL. Este codigo
apenas o consulta.
"""

from __future__ import annotations

import time

import requests

from tcc import config
from tcc.architectures import ResultadoInterpretacao
from tcc.domain import ACOES, CAMPOS_ENTIDADE, Dominio
from tcc.schema import Normalizador


class ArquiteturaRasa:
    nome = "rasa"

    def __init__(self, dominio: Dominio, url: str | None = None):
        self.dominio = dominio
        self.norm = Normalizador(dominio)
        self.url = (url or config.RASA_URL).rstrip("/")
        self.limiar = config.LIMIAR_CONFIANCA_RASA
        self.sessao = requests.Session()

    def aquecer(self) -> None:
        self._parse("go to the kitchen")

    def _parse(self, texto: str) -> dict:
        resp = self.sessao.post(
            f"{self.url}/model/parse", json={"text": texto}, timeout=config.TIMEOUT_RASA
        )
        resp.raise_for_status()
        return resp.json()

    def interpretar(self, texto: str) -> ResultadoInterpretacao:
        t0 = time.perf_counter()
        try:
            dados = self._parse(texto)
        except Exception as exc:  # noqa: BLE001
            return ResultadoInterpretacao(latencia_s=time.perf_counter() - t0, erro=repr(exc))
        latencia = time.perf_counter() - t0

        intent = (dados.get("intent") or {}).get("name")
        confianca = (dados.get("intent") or {}).get("confidence", 0.0)

        registro: dict = {}
        if intent in ACOES and confianca >= self.limiar:
            registro["acao"] = intent

        # Melhor entidade por campo (maior confianca).
        melhores: dict[str, tuple[float, str]] = {}
        for ent in dados.get("entities", []):
            campo = ent.get("entity")
            valor = ent.get("value")
            conf = ent.get("confidence_entity", ent.get("confidence", 1.0)) or 1.0
            if campo in CAMPOS_ENTIDADE and valor:
                if campo not in melhores or conf > melhores[campo][0]:
                    melhores[campo] = (conf, valor)
        for campo, (_, valor) in melhores.items():
            registro[campo] = valor

        registro_norm = self.norm.canonizar_registro(registro)
        alucinacoes = self.norm.alucinacoes(registro_norm)
        return ResultadoInterpretacao(
            registro=registro_norm,
            latencia_s=latencia,
            bruto=dados,
            detalhes={
                "confianca_intencao": confianca,
                "intencao_prevista": intent,
                "alucinacoes": alucinacoes,
            },
        )

    def descrever(self) -> dict:
        return {"arquitetura": self.nome, "url": self.url, "limiar_confianca": self.limiar}
