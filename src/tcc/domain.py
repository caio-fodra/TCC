"""Dominio fechado da versao plana: vocabulario por campo e repertorio de 14 acoes.

A versao plana usa um gabarito de UM registro por comando (nao uma lista de passos). Os
campos sao os mesmos oito da saida estruturada -- acao (obrigatorio) mais objeto, pessoa,
origem, destino, local, atributo e informacao (opcionais) --, conforme a proposta admite
("quando aplicavel, poderao ser incluidos campos adicionais").

Repertorio de acoes: 14, nao 16. `place` e `put_in_trash` so aparecem no gerador GPSR como
SEGUNDA acao (followups `placeObjOnPlcmt` e `putObjInTrash`), nunca como cabeca de um
comando. Como a estrategia A2 fica com a acao-cabeca de cada comando gerado puramente pelo
GPSR, essas duas nao ocorrem. Mante-las exigiria comandos atomicos escritos a mao, fora do
gerador. Isso e um ponto de delimitacao e esta registrado aqui para ficar explicito.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# A copia vendorizada do gerador precisa estar importavel.
_VENDOR = Path(__file__).resolve().parents[2] / "vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

from robocupathome_generator.gpsr_commands import CommandGenerator  # noqa: E402
from robocupathome_generator.knowledge import parse_data  # noqa: E402

#: Os oito campos de um registro plano, nesta ordem.
CAMPOS = ("acao", "objeto", "pessoa", "origem", "destino", "local", "atributo", "informacao")

#: Campos de entidade (todos menos a acao). Usados pela metrica por campo e pelo Rasa.
CAMPOS_ENTIDADE = tuple(c for c in CAMPOS if c != "acao")

#: Valor especial que designa o autor do comando (o destinatario de "bring me ...").
ME = "me"

_ARTIGOS = {"a", "an", "the"}


def canon_basico(valor) -> str:
    """Forma canonica basica de um valor: minusculas, sem pontuacao nem artigos.

    E a base da regra R5 (achatada). Usada tanto para canonizar o vocabulario do dominio
    quanto, em `tcc.schema`, para canonizar valores das saidas antes de compara-los.
    """
    t = re.sub(r"[.,;:!?]", " ", str(valor).strip().lower())
    tokens = [tok for tok in t.split() if tok not in _ARTIGOS]
    return " ".join(tokens).strip()


@dataclass(frozen=True)
class EspecAcao:
    obrigatorios: tuple[str, ...]
    opcionais: tuple[str, ...]

    @property
    def campos(self) -> tuple[str, ...]:
        return self.obrigatorios + self.opcionais


#: Repertorio de 14 acoes. Derivado da Tabela 1 do trabalho, restrito as acoes que podem ser
#: a CABECA de um comando GPSR e ajustado para a leitura plana (uma acao por comando).
#: `bring me X from Y` e representado como uma unica acao `deliver` com destino `me` e a
#: origem Y -- sem a decomposicao take+deliver da regra R4 (que nao existe nesta versao).
ACOES: dict[str, EspecAcao] = {
    "go_to": EspecAcao(("destino",), ()),
    "take": EspecAcao(("objeto",), ("origem",)),
    "deliver": EspecAcao(("objeto", "destino"), ("origem", "local")),
    "find_object": EspecAcao(("objeto",), ("local",)),
    "find_person": EspecAcao(("pessoa",), ("local",)),
    "meet": EspecAcao(("pessoa",), ("local",)),
    "greet": EspecAcao(("pessoa",), ("local",)),
    "follow": EspecAcao(("pessoa",), ("origem", "destino", "local")),
    "guide": EspecAcao(("pessoa", "destino"), ("origem",)),
    "count_objects": EspecAcao(("objeto", "local"), ()),
    "count_people": EspecAcao(("local",), ("pessoa", "atributo")),
    "tell_person_info": EspecAcao(("informacao",), ("local", "origem", "destino")),
    "tell_object_property": EspecAcao(("atributo", "local"), ("objeto",)),
    "talk_info": EspecAcao(("informacao",), ("pessoa", "local")),
}

#: Acoes do gerador GPSR que nunca sao cabeca e, por isso, ficam de fora da versao plana.
ACOES_FORA_DO_ESCOPO = ("place", "put_in_trash")


@dataclass
class Dominio:
    """Vocabulario admitido por campo (regra R6) e mapeamentos de normalizacao."""

    knowledge: object
    gerador: CommandGenerator
    vocab: dict[str, set[str]]
    plural_para_singular: dict[str, str]

    def valor_valido(self, campo: str, valor: str) -> bool:
        if valor == ME and campo in ("destino", "origem", "pessoa"):
            return True
        return valor in self.vocab.get(campo, set())


def _singularizar_maps(k, g: CommandGenerator) -> dict[str, str]:
    """Plural -> singular para categorias e para descricoes de pessoa.

    Sao as unicas divergencias de plural que a gramatica GPSR produz de fato (categorias
    no plural em `count_objects`; descricoes de pessoa no plural em `count_people`).
    """
    m: dict[str, str] = {}
    for c in k.categories:
        m[canon_basico(c.plural)] = canon_basico(c.singular)
    for plural, singular in zip(g.gesture_person_plural_list, g.gesture_person_list):
        m[canon_basico(plural)] = canon_basico(singular)
    for plural, singular in zip(g.pose_person_plural_list, g.pose_person_list):
        m[canon_basico(plural)] = canon_basico(singular)
    return m


def _construir_vocab(k, g: CommandGenerator) -> dict[str, set[str]]:
    def cs(valores) -> set[str]:
        return {canon_basico(v) for v in valores}

    rooms = cs(k.rooms)
    locs = cs(k.locations)
    lugares = rooms | locs
    nomes = cs(k.names)
    gest_pose = cs(g.gesture_person_list) | cs(g.pose_person_list)
    vestuario_pessoa = cs(f"person wearing {cc}" for cc in g.color_clothe_list)
    descricoes_pessoa = gest_pose | vestuario_pessoa
    objetos = cs(k.objects) | cs(k.object_categories_singular)
    atributos = cs(g.object_comp_list) | cs(g.color_clothes_list)
    informacoes = cs(g.person_info_list) | cs(g.talk_list)
    return {
        "acao": set(ACOES.keys()),
        "objeto": objetos,
        "pessoa": nomes | descricoes_pessoa,
        "origem": lugares,
        "destino": lugares | nomes | {ME},
        "local": lugares,
        "atributo": atributos,
        "informacao": informacoes,
    }


@lru_cache(maxsize=4)
def carregar_dominio(data_dir: str) -> Dominio:
    k = parse_data(data_dir)
    g = CommandGenerator(k)
    return Dominio(
        knowledge=k,
        gerador=g,
        vocab=_construir_vocab(k, g),
        plural_para_singular=_singularizar_maps(k, g),
    )
