"""Entrada do workflow (--itens) e validacao/conversao das parafrases dos agentes Claude (--finalizar)."""

from tcc import config, paraphrase
from tcc.domain import ME
from tcc.io_utils import gravar_jsonl, ler_jsonl
from tcc.surface import presente


def test_validar_ignora_artigos_na_identidade():
    dominio = paraphrase.carregar_dominio(str(config.DIR_DOMINIO))
    gabarito = {"acao": "go_to", "destino": "shelf"}
    assert "identica ao original" in paraphrase.validar("go to the shelf", "go to shelf", gabarito, dominio)
    assert "identica ao original" not in paraphrase.validar("go to the shelf", "head to the shelf", gabarito, dominio)


def test_finalizar_converte_e_recusa_igual_a_outro_canonico(tmp_path, monkeypatch):
    gab = {"acao": "go_to", "destino": "bed"}
    originais = [{"id": "orig-001", "texto": "go to the bed", "gabarito": gab},
                 {"id": "orig-002", "texto": "navigate to the bed", "gabarito": gab}]
    for nome, arq in [("ARQ_COMANDOS_ORIGINAL", "orig.jsonl"), ("ARQ_PARAFRASES_CLAUDE", "claude.jsonl"),
                      ("ARQ_COMANDOS_PARAFRASE", "para.jsonl")]:
        monkeypatch.setattr(config, nome, tmp_path / arq)
    gravar_jsonl(config.ARQ_COMANDOS_ORIGINAL, originais)

    # A 002 repete o texto do canonico 001: recusada, e nada e gravado.
    gravar_jsonl(config.ARQ_PARAFRASES_CLAUDE, [{"id": "orig-001", "parafrase": "head to the bed"},
                                                {"id": "orig-002", "parafrase": "go to the bed"}])
    assert paraphrase.finalizar() == 1
    assert not config.ARQ_COMANDOS_PARAFRASE.exists()

    # Id duplicado (a 001 duas vezes, a 002 faltando): recusado.
    gravar_jsonl(config.ARQ_PARAFRASES_CLAUDE, [{"id": "orig-001", "parafrase": "head to the bed"},
                                                {"id": "orig-001", "parafrase": "walk to the bed"}])
    assert paraphrase.finalizar() == 1
    assert not config.ARQ_COMANDOS_PARAFRASE.exists()

    gravar_jsonl(config.ARQ_PARAFRASES_CLAUDE, [{"id": "orig-001", "parafrase": "head to the bed", "rodada": 0},
                                                {"id": "orig-002", "parafrase": "walk to the bed", "rodada": 1}])
    assert paraphrase.finalizar() == 0
    assert ler_jsonl(config.ARQ_COMANDOS_PARAFRASE)[1] == {
        "id": "para-002", "texto": "walk to the bed", "gabarito": gab, "origem_id": "orig-002",
        "nivel": 2, "parafraseador": "claude-opus-5-5"}


def test_termos_a_copiar_usa_a_forma_do_texto():
    dominio = paraphrase.carregar_dominio(str(config.DIR_DOMINIO))
    assert paraphrase.termos_a_copiar("tell me how many dishes there are on the shelf",
                                      {"acao": "count_objects", "objeto": "dish", "local": "shelf"},
                                      dominio) == ["dishes", "shelf"]
    assert paraphrase.termos_a_copiar("bring me a sugar from the shelf",
                                      {"acao": "deliver", "objeto": "sugar", "origem": "shelf", "destino": ME},
                                      dominio) == ["me", "sugar", "shelf"]


def test_regras_nao_trazem_item_de_teste():
    # O gerador copiaria um exemplo do prompt que fosse item de teste (o prompt de 03/11 tinha 7).
    dominio = paraphrase.carregar_dominio(str(config.DIR_DOMINIO))
    regras = paraphrase.REGRAS.lower()
    linhas = paraphrase.REGRAS.splitlines()
    janelas = [" ".join(linhas[i:i + 2]) for i in range(len(linhas))]  # 2 linhas: exemplo quebrado ao meio
    for r in ler_jsonl(config.ARQ_COMANDOS_ORIGINAL):
        assert r["texto"].lower() not in regras, r["id"]
        valores = [v for c, v in r["gabarito"].items() if c != "acao" and v != ME]
        if len(valores) >= 2:  # fragmento com todos os valores do item, como "refrigerator, get a toy"
            assert not any(all(presente(j, v, dominio) for v in valores) for j in janelas), r["id"]
