"""Trava dos exemplos do prompt: comando de teste igual a uma oracao de exemplo composto e barrado."""

from tcc.domain import canon_basico
from tcc.run_experiment import _frases_do_prompt


def test_trava_compara_oracoes_dos_exemplos_compostos():
    frases = _frases_do_prompt(["go to the kitchen then find a fruit"])
    assert canon_basico("Go to the kitchen.") in frases
    assert canon_basico("find a fruit") in frases
