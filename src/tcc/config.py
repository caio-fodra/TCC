"""Configuracao central do experimento (versao plana).

Tudo pode ser sobrescrito por variavel de ambiente, e os valores efetivos sao gravados em
`results/ambiente_<arquiteturas>.json`, um por passada. O Ollama e o Rasa sao SERVICOS da sua maquina: o codigo os consulta
por HTTP, nos enderecos abaixo. Nenhum modelo e treinado neste codigo (o `rasa train` roda no
seu ambiente 3.10).
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# --- Caminhos ---------------------------------------------------------------
DIR_DADOS = RAIZ / "data"
# Dominio: RoboCupAtHome/CompetitionTemplate, commit af2972f (2026-04-01), sem alteracao.
# Fixo de proposito (sem variavel de ambiente): na execucao de 2026-10-22 a variavel valia so
# em parte das sessoes, e o Rasa foi treinado num dominio diferente do usado no teste.
DIR_DOMINIO = DIR_DADOS / "domain"
DIR_RESULTADOS = Path(os.environ.get("TCC_DIR_RESULTADOS", RAIZ / "results"))
DIR_EXECUCOES = DIR_RESULTADOS / "execucoes"
DIR_PROJETO_RASA = Path(os.environ.get("TCC_DIR_RASA", RAIZ / "rasa_project"))

ARQ_COMANDOS_ORIGINAL = DIR_DADOS / "comandos_original.jsonl"
ARQ_COMANDOS_PARAFRASE = DIR_DADOS / "comandos_parafrase.jsonl"
# Saida dos agentes Claude ({id, parafrase, rodada, workflow}), gravada a partir do registro do workflow.
ARQ_PARAFRASES_CLAUDE = DIR_DADOS / "parafrases_claude.jsonl"

# --- Aleatoriedade ----------------------------------------------------------
SEED = int(os.environ.get("TCC_SEED", "42"))
# Semente distinta para o treino do Rasa. Quem garante que nenhum exemplo coincide com o teste e
# o filtro de build_rasa_data.
SEED_TREINO_RASA = int(os.environ.get("TCC_SEED_TREINO", "20260622"))

N_COMANDOS = int(os.environ.get("TCC_N_COMANDOS", "100"))
N_TREINO_RASA = int(os.environ.get("TCC_N_TREINO_RASA", "3000"))
MAX_EXEMPLOS_POR_INTENCAO = int(os.environ.get("TCC_MAX_EX_INTENCAO", "200"))

# --- Ollama / modelos -------------------------------------------------------
OLLAMA_URL = os.environ.get("TCC_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
# Modelo avaliado na arquitetura LLM+RAG (o seu, ja baixado no Ollama).
MODELO_ARQUITETURA = os.environ.get("TCC_MODELO_ARQ", "qwen3:4b-instruct")
TIMEOUT_OLLAMA = float(os.environ.get("TCC_TIMEOUT_OLLAMA", "300"))
# Janela de contexto declarada: o padrao do servidor (4096) truncaria o prompt do RAG.
NUM_CTX = int(os.environ.get("TCC_NUM_CTX", "8192"))

# --- Rasa -------------------------------------------------------------------
RASA_URL = os.environ.get("TCC_RASA_URL", "http://127.0.0.1:5005").rstrip("/")
TIMEOUT_RASA = float(os.environ.get("TCC_TIMEOUT_RASA", "60"))
LIMIAR_CONFIANCA_RASA = float(os.environ.get("TCC_LIMIAR_RASA", "0.3"))

# --- RAG --------------------------------------------------------------------
RAG_K = int(os.environ.get("TCC_RAG_K", "34"))
# Cotas por tipo de documento no contexto recuperado (esquema e acoes entram sempre).
RAG_COTAS = {
    "esquema": 2,
    "acao": 14,
    "objeto": 6,
    "categoria": 3,
    "comodo": 3,
    "local": 4,
    "pessoa": 3,
}


def criar_diretorios() -> None:
    for d in (DIR_DADOS, DIR_RESULTADOS, DIR_EXECUCOES):
        d.mkdir(parents=True, exist_ok=True)
