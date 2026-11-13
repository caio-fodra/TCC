"""Filtro do treino do Rasa: exemplo igual a um comando de teste sai, mesmo com outro artigo."""

from tcc import config
from tcc.annotated_generator import GeradorPlano
from tcc.build_rasa_data import gerar_exemplos
from tcc.domain import canon_basico


def test_filtro_de_teste_ignora_artigos():
    # Na execucao de 2026-11-02, "Find the food in the bathroom." (teste) estava no treino com "a".
    teste = {canon_basico("Find the food in the bathroom.")}
    por_intencao, _ = gerar_exemplos(3000, teste, GeradorPlano(str(config.DIR_DOMINIO)))
    assert "find a [food](objeto) in the [bathroom](local)" not in por_intencao["find_object"]
