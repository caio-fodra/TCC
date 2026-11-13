"""Gerador instrumentado da versao plana (estrategia A2).

Usa os TEMPLATES e as LISTAS do gerador oficial GPSR (`robocupathome_generator`), mas NAO
expande followups: produz apenas a oracao-cabeca de cada template, que e um comando de uma
unica acao, e devolve, junto com o texto, o gabarito plano correspondente (um registro com
`acao` e os campos que a oracao enuncia).

Como o texto e o gabarito sao construidos a partir dos MESMOS valores sorteados, o gabarito
corresponde exatamente ao comando, sem anotacao manual e sem interpretacao do texto (o que
tornaria a avaliacao circular). Nao ha resolucao de anafora nem regra R4: `bring me X from Y`
e um comando de uma acao, representado como `deliver` com destino `me`.

Cobertura: 14 acoes. `place` e `put_in_trash` so existem como segunda acao (followup) e, por
isso, nao aparecem -- ver `tcc.domain.ACOES_FORA_DO_ESCOPO`.
"""

from __future__ import annotations

import random
import warnings
from dataclasses import dataclass, field

from tcc.domain import ME, carregar_dominio
from tcc.schema import Normalizador

# ---------------------------------------------------------------------------
# Comando gerado
# ---------------------------------------------------------------------------


@dataclass
class Comando:
    texto: str
    gabarito: dict  # registro plano: {"acao": ..., campos...}
    template: str
    id: str = ""

    def como_dict(self) -> dict:
        return {"id": self.id, "texto": self.texto, "template": self.template, "gabarito": self.gabarito}


def _art(palavra: str) -> str:
    return "an" if palavra[:1].lower() in "aeiou" else "a"


class GeradorPlano:
    """Produz comandos de uma acao com gabarito plano, a partir do gerador GPSR."""

    def __init__(self, data_dir: str):
        self.dominio = carregar_dominio(data_dir)
        self.g = self.dominio.gerador
        self.norm = Normalizador(self.dominio)
        self.templates = list(_CONSTRUTORES.keys())

    # -- sorteadores de valores (espelham insert_placeholders do gerador) --------------
    def _nome(self):
        return random.choice(self.g.knowledge.names)

    def _comodo(self):
        return random.choice(self.g.knowledge.rooms)

    def _local(self):
        return random.choice(self.g.knowledge.locations)

    def _placement(self):
        return random.choice(self.g.knowledge.placement_locations)

    def _objeto(self):
        return random.choice(self.g.knowledge.objects)

    def _cat_sing(self):
        return random.choice(self.g.knowledge.object_categories_singular)

    def _cat_plur(self):
        return random.choice(self.g.knowledge.object_categories_plural)

    def _obj_ou_cat(self):
        return self._objeto() if random.choice(("obj", "singCat")) == "obj" else self._cat_sing()

    def _loc_ou_comodo(self):
        return self._local() if random.choice(("loc", "room")) == "loc" else self._comodo()

    def _gest_pose(self):
        lista = self.g.gesture_person_list if random.choice(("g", "p")) == "g" else self.g.pose_person_list
        return random.choice(lista)

    def _gest_pose_plural(self):
        lista = self.g.gesture_person_plural_list if random.choice(("g", "p")) == "g" else self.g.pose_person_plural_list
        return random.choice(lista)

    def _gesto(self):
        return random.choice(self.g.gesture_person_list)

    def _persinfo(self):
        return random.choice(self.g.person_info_list)

    def _objcomp(self):
        return random.choice(self.g.object_comp_list)

    def _talk(self):
        return random.choice(self.g.talk_list)

    def _cor_roupa(self):
        return random.choice(self.g.color_clothe_list)

    def _cor_roupas(self):
        return random.choice(self.g.color_clothes_list)

    def _verbo(self, chave):
        return random.choice(self.g.verb_dict[chave])

    # -- geracao ------------------------------------------------------------------------
    def gerar(self, template: str) -> Comando:
        texto, gab = _CONSTRUTORES[template](self)
        # Gabarito ja e construido em forma canonica; canonizar aqui so confirma idempotencia.
        gab = self.norm.canonizar_registro(gab)
        return Comando(texto=texto.strip(), gabarito=gab, template=template)

    def _amostrar_template(self) -> str:
        """Replica a selecao do gerador: escolhe uma lista e sorteia por peso."""
        lista = self.g.person_cmd_list if random.random() > 0.5 else self.g.object_cmd_list
        itens, pesos = zip(*lista)
        return random.choices(itens, weights=pesos, k=1)[0]


# ---------------------------------------------------------------------------
# Um construtor por template-cabeca. Cada um devolve (texto, gabarito_plano).
# ---------------------------------------------------------------------------


def _c_goToLoc(s: GeradorPlano):
    destino = s._loc_ou_comodo()
    v = s._verbo("goVerb")
    return f"{v} to the {destino}", {"acao": "go_to", "destino": destino}


def _c_takeObjFromPlcmt(s: GeradorPlano):
    obj = s._obj_ou_cat()
    origem = s._placement()
    v = s._verbo("takeVerb")
    return f"{v} {_art(obj)} {obj} from the {origem}", {"acao": "take", "objeto": obj, "origem": origem}


def _c_findPrsInRoom(s: GeradorPlano):
    pessoa = s._gest_pose()
    local = s._comodo()
    v = s._verbo("findVerb")
    return f"{v} a {pessoa} in the {local}", {"acao": "find_person", "pessoa": pessoa, "local": local}


def _c_findObjInRoom(s: GeradorPlano):
    obj = s._obj_ou_cat()
    local = s._comodo()
    v = s._verbo("findVerb")
    return f"{v} {_art(obj)} {obj} in the {local}", {"acao": "find_object", "objeto": obj, "local": local}


def _c_meetPrsAtBeac(s: GeradorPlano):
    pessoa = s._nome()
    local = s._comodo()
    v = s._verbo("meetVerb")
    return f"{v} {pessoa} in the {local}", {"acao": "meet", "pessoa": pessoa, "local": local}


def _c_countObjOnPlcmt(s: GeradorPlano):
    plur = s._cat_plur()
    local = s._placement()
    # objeto canonico = categoria no singular (normalizacao fara o mapeamento).
    return (
        f"tell me how many {plur} there are on the {local}",
        {"acao": "count_objects", "objeto": plur, "local": local},
    )


def _c_countPrsInRoom(s: GeradorPlano):
    plur = s._gest_pose_plural()
    local = s._comodo()
    return (
        f"tell me how many {plur} are in the {local}",
        {"acao": "count_people", "pessoa": plur, "local": local},
    )


def _c_tellPrsInfoInLoc(s: GeradorPlano):
    info = s._persinfo()
    if random.choice(("inRoom", "atLoc")) == "inRoom":
        local = s._comodo()
        texto = f"tell me the {info} of the person in the {local}"
    else:
        local = s._local()
        texto = f"tell me the {info} of the person at the {local}"
    return texto, {"acao": "tell_person_info", "informacao": info, "local": local}


def _c_tellObjPropOnPlcmt(s: GeradorPlano):
    attr = s._objcomp()
    local = s._placement()
    return (
        f"tell me what is the {attr} object on the {local}",
        {"acao": "tell_object_property", "atributo": attr, "local": local},
    )


def _c_talkInfoToGestPrsInRoom(s: GeradorPlano):
    info = s._talk()
    pessoa = s._gesto()
    local = s._comodo()
    v = s._verbo("talkVerb")
    return (
        f"{v} {info} to the {pessoa} in the {local}",
        {"acao": "talk_info", "informacao": info, "pessoa": pessoa, "local": local},
    )


def _c_followNameFromBeacToRoom(s: GeradorPlano):
    pessoa = s._nome()
    origem = s._local()
    destino = s._comodo()
    v = s._verbo("followVerb")
    return (
        f"{v} {pessoa} from the {origem} to the {destino}",
        {"acao": "follow", "pessoa": pessoa, "origem": origem, "destino": destino},
    )


def _c_guideNameFromBeacToBeac(s: GeradorPlano):
    pessoa = s._nome()
    origem = s._local()
    destino = s._loc_ou_comodo()
    v = s._verbo("guideVerb")
    return (
        f"{v} {pessoa} from the {origem} to the {destino}",
        {"acao": "guide", "pessoa": pessoa, "origem": origem, "destino": destino},
    )


def _c_guidePrsFromBeacToBeac(s: GeradorPlano):
    pessoa = s._gest_pose()
    origem = s._local()
    destino = s._loc_ou_comodo()
    v = s._verbo("guideVerb")
    return (
        f"{v} the {pessoa} from the {origem} to the {destino}",
        {"acao": "guide", "pessoa": pessoa, "origem": origem, "destino": destino},
    )


def _c_guideClothPrsFromBeacToBeac(s: GeradorPlano):
    cc = s._cor_roupa()
    pessoa = f"person wearing {cc}"
    origem = s._local()
    destino = s._loc_ou_comodo()
    v = s._verbo("guideVerb")
    return (
        f"{v} the person wearing {_art(cc)} {cc} from the {origem} to the {destino}",
        {"acao": "guide", "pessoa": pessoa, "origem": origem, "destino": destino},
    )


def _c_bringMeObjFromPlcmt(s: GeradorPlano):
    obj = s._objeto()
    origem = s._placement()
    v = s._verbo("bringVerb")
    return (
        f"{v} me {_art(obj)} {obj} from the {origem}",
        {"acao": "deliver", "objeto": obj, "origem": origem, "destino": ME},
    )


def _c_tellCatPropOnPlcmt(s: GeradorPlano):
    attr = s._objcomp()
    cat = s._cat_sing()
    local = s._placement()
    return (
        f"tell me what is the {attr} {cat} on the {local}",
        {"acao": "tell_object_property", "atributo": attr, "objeto": cat, "local": local},
    )


def _c_greetClothDscInRm(s: GeradorPlano):
    cc = s._cor_roupa()
    pessoa = f"person wearing {cc}"
    local = s._comodo()
    v = s._verbo("greetVerb")
    return (
        f"{v} the person wearing {_art(cc)} {cc} in the {local}",
        {"acao": "greet", "pessoa": pessoa, "local": local},
    )


def _c_greetNameInRm(s: GeradorPlano):
    pessoa = s._nome()
    local = s._comodo()
    v = s._verbo("greetVerb")
    return f"{v} {pessoa} in the {local}", {"acao": "greet", "pessoa": pessoa, "local": local}


def _c_meetNameAtLocThenFindInRm(s: GeradorPlano):
    pessoa = s._nome()
    local = s._local()
    v = s._verbo("meetVerb")
    # Cabeca apenas: "meet NAME at the LOC" (a continuacao "then find them..." e descartada).
    return f"{v} {pessoa} at the {local}", {"acao": "meet", "pessoa": pessoa, "local": local}


def _c_countClothPrsInRoom(s: GeradorPlano):
    local = s._comodo()
    attr = s._cor_roupas()
    return (
        f"tell me how many people in the {local} are wearing {attr}",
        {"acao": "count_people", "local": local, "atributo": attr},
    )


def _c_tellPrsInfoAtLocToPrsAtLoc(s: GeradorPlano):
    info = s._persinfo()
    origem = s._local()
    destino = s._local()
    while destino == origem and len(s.g.knowledge.locations) > 1:
        destino = s._local()
    return (
        f"tell the {info} of the person at the {origem} to the person at the {destino}",
        {"acao": "tell_person_info", "informacao": info, "origem": origem, "destino": destino},
    )


def _c_followPrsAtLoc(s: GeradorPlano):
    pessoa = s._gest_pose()
    if random.choice(("inRoom", "atLoc")) == "inRoom":
        local = s._comodo()
        texto = f"follow the {pessoa} in the {local}"
    else:
        local = s._local()
        texto = f"follow the {pessoa} at the {local}"
    return texto, {"acao": "follow", "pessoa": pessoa, "local": local}


_CONSTRUTORES = {
    "goToLoc": _c_goToLoc,
    "takeObjFromPlcmt": _c_takeObjFromPlcmt,
    "findPrsInRoom": _c_findPrsInRoom,
    "findObjInRoom": _c_findObjInRoom,
    "meetPrsAtBeac": _c_meetPrsAtBeac,
    "countObjOnPlcmt": _c_countObjOnPlcmt,
    "countPrsInRoom": _c_countPrsInRoom,
    "tellPrsInfoInLoc": _c_tellPrsInfoInLoc,
    "tellObjPropOnPlcmt": _c_tellObjPropOnPlcmt,
    "talkInfoToGestPrsInRoom": _c_talkInfoToGestPrsInRoom,
    "followNameFromBeacToRoom": _c_followNameFromBeacToRoom,
    "guideNameFromBeacToBeac": _c_guideNameFromBeacToBeac,
    "guidePrsFromBeacToBeac": _c_guidePrsFromBeacToBeac,
    "guideClothPrsFromBeacToBeac": _c_guideClothPrsFromBeacToBeac,
    "bringMeObjFromPlcmt": _c_bringMeObjFromPlcmt,
    "tellCatPropOnPlcmt": _c_tellCatPropOnPlcmt,
    "greetClothDscInRm": _c_greetClothDscInRm,
    "greetNameInRm": _c_greetNameInRm,
    "meetNameAtLocThenFindInRm": _c_meetNameAtLocThenFindInRm,
    "countClothPrsInRoom": _c_countClothPrsInRoom,
    "tellPrsInfoAtLocToPrsAtLoc": _c_tellPrsInfoAtLocToPrsAtLoc,
    "followPrsAtLoc": _c_followPrsAtLoc,
}
