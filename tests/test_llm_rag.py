"""LLM+RAG: tudo o que vai ao modelo esta em ingles, inclusive as chaves; a saida volta as chaves do gabarito."""

import re

from tcc import config
from tcc.arch_llm_rag import ArquiteturaLLMRAG
from tcc.domain import CAMPOS, carregar_dominio


def test_prompt_em_ingles_e_chaves_de_volta_ao_gabarito():
    arq = ArquiteturaLLMRAG(carregar_dominio(str(config.DIR_DOMINIO)))  # nao chama o Ollama
    enviado = "\n".join([arq._system, arq._montar_user("bring me a sugar from the shelf", arq.kb)])  # base inteira
    assert not re.search(r"[^\x00-\x7f]", enviado)
    assert [c for c in CAMPOS if re.search(rf"\b{c}\b", enviado)] == []
    assert arq._achatar({"action": "deliver", "object": "sugar", "source": "shelf", "destination": "me"}) == {
        "acao": "deliver", "objeto": "sugar", "origem": "shelf", "destino": "me"}
