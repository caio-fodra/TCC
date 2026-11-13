"""Consolidacao: canonico x parafrase casados pelo numero do comando, latencias pareadas sem erro."""

from tcc import config, run_experiment
from tcc.io_utils import gravar_jsonl, ler_json

GAB = {"acao": "go_to", "destino": "bed"}


def _execucao(prefixo: str, erro_em: int, desloc: float) -> list[dict]:
    return [{"id": f"{prefixo}-{i:03d}", "texto": "go to the bed", "gabarito": GAB,
             "saida": {"registro": {} if i == erro_em else GAB, "latencia_s": i + desloc,
                       "erro": "json_invalido" if i == erro_em else None}}
            for i in range(1, 6)]


def test_consolidar_pareia_pelo_numero_e_sem_erro(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIR_RESULTADOS", tmp_path)
    monkeypatch.setattr(config, "DIR_EXECUCOES", tmp_path / "execucoes")
    for nome, prefixo, erro_em, desloc in [("rasa_original", "orig", 2, 0), ("rasa_parafrase", "para", 3, 1),
                                           ("llm_rag_original", "orig", 4, 10), ("llm_rag_parafrase", "para", 0, 11)]:
        gravar_jsonl(tmp_path / "execucoes" / f"{nome}.jsonl", _execucao(prefixo, erro_em, desloc))

    run_experiment.consolidar()
    testes = ler_json(tmp_path / "metricas.json")["testes"]

    mcnemar = {t["comparacao"]: t for t in testes["correspondencia_exata"]}
    assert len(mcnemar) == 4  # os dois canonico x parafrase entram na familia de Holm
    assert (mcnemar["canonico vs parafrase (rasa)"]["so_a"], mcnemar["canonico vs parafrase (rasa)"]["so_b"]) == (1, 1)

    wilcoxon = {t["comparacao"]: t["n"] for t in testes["latencia"]}
    assert wilcoxon["Rasa vs LLM+RAG em C_original"] == 3  # comandos 1, 3 e 5: sem erro nos dois lados
    assert set(wilcoxon) == {"Rasa vs LLM+RAG em C_original", "Rasa vs LLM+RAG em C_parafrase"}
