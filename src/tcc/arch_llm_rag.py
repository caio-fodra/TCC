"""Arquitetura LLM+RAG (versao plana).

Base de conhecimento com o vocabulario do dominio, recuperacao por similaridade TF-IDF e
geracao condicionada pelo contexto recuperado, com o modelo qwen3:4b-instruct no Ollama local.
A saida e UM objeto JSON plano (nao uma lista de passos): a acao mais os campos que o comando
enuncia. Prompt, base e exemplos estao inteiramente em ingles, inclusive as chaves do JSON
(`_CHAVE_EN`); a saida volta para as chaves do gabarito em `_achatar`, e e normalizada (R5), com
valores fora do dominio mantidos como alucinacao (R6).

O Ollama roda na SUA maquina (OLLAMA_URL); este codigo apenas o consulta, com o modelo que voce
ja baixou. Nada e treinado aqui.
"""

from __future__ import annotations

import json
import re
import time

import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from tcc import config
from tcc.architectures import ResultadoInterpretacao
from tcc.domain import ACOES, CAMPOS, ME, Dominio
from tcc.schema import Normalizador

# ---------------------------------------------------------------------------
# Base de conhecimento
# ---------------------------------------------------------------------------

#: Chave em ingles de cada campo do gabarito: o modelo so ve estas; `_achatar` faz o caminho de volta.
_CHAVE_EN = {"acao": "action", "objeto": "object", "pessoa": "person", "origem": "source",
             "destino": "destination", "local": "location", "atributo": "attribute", "informacao": "information"}


def _en(campos) -> list[str]:
    return [_CHAVE_EN[c] for c in campos]


#: Descricao curta de cada acao (vai ao prompt). Campos sao lidos de ACOES.
_DESC_ACAO = {
    "go_to": "Move to a room or location.",
    "take": "Pick up an object, optionally from a source location.",
    "deliver": "Deliver an object to a person or location; 'bring/give me X from Y' is deliver with destination me.",
    "find_object": "Locate an object, optionally in a room.",
    "find_person": "Locate a person, optionally in a room.",
    "meet": "Meet a person, optionally at a location.",
    "greet": "Greet a person, optionally in a room.",
    "follow": "Follow a person, with optional source/destination/location.",
    "guide": "Guide a person to a destination, with optional source.",
    "count_objects": "Count the objects of a category at a location.",
    "count_people": "Count the people in a room, by pose/gesture or clothing.",
    "tell_person_info": "Tell a piece of information (name, pose, gesture) about a person.",
    "tell_object_property": "Tell a property (biggest, smallest...) of an object/category at a location.",
    "talk_info": "Say a topic to a person.",
}

_VERBOS_ACAO = {
    "go_to": ["go", "navigate", "move", "head", "walk"],
    "take": ["take", "get", "grasp", "fetch", "pick up"],
    "deliver": ["bring", "give", "deliver", "hand"],
    "find_object": ["find", "locate", "look for", "search"],
    "find_person": ["find", "locate", "look for", "meet"],
    "meet": ["meet", "greet"],
    "greet": ["greet", "salute", "say hello", "introduce yourself"],
    "follow": ["follow", "accompany"],
    "guide": ["guide", "escort", "lead", "take"],
    "count_objects": ["how many", "count"],
    "count_people": ["how many", "count", "wearing"],
    "tell_person_info": ["tell", "name", "pose", "gesture"],
    "tell_object_property": ["tell", "what is", "biggest", "smallest", "heaviest"],
    "talk_info": ["tell", "say", "talk"],
}


def construir_kb(dominio: Dominio) -> list[dict]:
    """Documentos da base: esquema(2), acao(14), objeto, categoria, comodo, local, pessoa(3)."""
    k = dominio.knowledge
    docs: list[dict] = []

    campos_fmt = ", ".join(_en(CAMPOS))
    docs.append({
        "tipo": "esquema", "nome": "formato",
        "texto": f"The output is a single JSON object with the fields: {campos_fmt}. "
                 f"'action' is required; the others are optional. Values in lower case, without "
                 f"articles, categories in the singular. Recipient of 'bring/give me' = 'me'.",
        "termos": ["format", "output", "json", "fields"] + _en(CAMPOS),
    })
    docs.append({
        "tipo": "esquema", "nome": "regras",
        "texto": "Fill a field only when the command states it. 'it' refers to the last object; "
                 "'them' to the last person. source = where from; destination = where to/to whom. "
                 "Never invent a value outside the context. Reply with the JSON only.",
        "termos": ["rules", "filling", "it", "them", "source", "destination"],
    })

    for acao, espec in ACOES.items():
        obrig = ", ".join(_en(espec.obrigatorios)) or "-"
        opc = ", ".join(_en(espec.opcionais)) or "-"
        docs.append({
            "tipo": "acao", "nome": acao,
            "texto": f"ACTION {acao}: {_DESC_ACAO[acao]} Required fields: {obrig}. Optional: {opc}.",
            "termos": [acao] + _VERBOS_ACAO.get(acao, []),
        })

    # Objetos e categorias.
    cat_do_obj = {}
    for cat_plural, objs in k.objects_by_category.items():
        for o in objs:
            cat_do_obj[o] = cat_plural
    sing_de = {c.plural: c.singular for c in k.categories}
    for o in k.objects:
        cat_p = cat_do_obj.get(o, "")
        cat_s = sing_de.get(cat_p, cat_p)
        irmaos = [x for x in k.objects_by_category.get(cat_p, []) if x != o][:6]
        docs.append({
            "tipo": "objeto", "nome": o,
            "texto": f"object {o} (category {cat_s}). Others in the category: {', '.join(irmaos)}.",
            "termos": [o, cat_s, cat_p],
        })
    for c in k.categories:
        membros = ", ".join(k.objects_by_category.get(c.plural, [])[:8])
        docs.append({
            "tipo": "categoria", "nome": c.singular,
            "texto": f"category {c.singular} (plural {c.plural}). Use the singular. Members: {membros}.",
            "termos": [c.singular, c.plural],
        })

    # Comodos e locais.
    for r in k.rooms:
        docs.append({"tipo": "comodo", "nome": r, "texto": f"room {r}.", "termos": [r]})
    for loc in k.locations:
        papel = "placement (where objects are put down)" if loc in k.placement_locations else "navigation"
        docs.append({"tipo": "local", "nome": loc, "texto": f"location {loc} ({papel}).", "termos": [loc]})

    # Pessoas (3 documentos agregados).
    g = dominio.gerador
    docs.append({
        "tipo": "pessoa", "nome": "nomes",
        "texto": f"person names: {', '.join(k.names)}. Special value 'me' = the author of the command.",
        "termos": list(k.names) + ["person", "me"],
    })
    docs.append({
        "tipo": "pessoa", "nome": "descricoes",
        "texto": "person by pose/gesture: " + ", ".join(g.gesture_person_list + g.pose_person_list) + ".",
        "termos": ["person", "waving", "pointing", "raising", "sitting", "standing", "lying"],
    })
    docs.append({
        "tipo": "pessoa", "nome": "vestuario",
        "texto": "person by clothing: 'person wearing <color> <garment>' (colors: "
                 + ", ".join(g.color_list) + "; garments: " + ", ".join(g.clothe_list) + ").",
        "termos": ["person", "wearing"] + g.color_list + g.clothe_list,
    })
    return docs


# ---------------------------------------------------------------------------
# Few-shot: ensinam R1 (nao inferir), R2 (anafora) e deliver com 'me'.
# ---------------------------------------------------------------------------
_FEWSHOT = [
    ('Give me a sponge from the bed',
     {"acao": "deliver", "objeto": "sponge", "origem": "bed", "destino": "me"}),
    # Destino que nenhum comando de teste usa: "go to the kitchen" coincidia com a para-062.
    ('go to the sofa then find a fruit',
     {"acao": "go_to", "destino": "sofa"}),
    ('tell me how many drinks there are on the sofa',
     {"acao": "count_objects", "objeto": "drink", "local": "sofa"}),
    ('greet Robin in the office',
     {"acao": "greet", "pessoa": "robin", "local": "office"}),
]


class ArquiteturaLLMRAG:
    nome = "llm_rag"

    def __init__(self, dominio: Dominio, url: str | None = None):
        self.dominio = dominio
        self.norm = Normalizador(dominio)
        self.url = (url or config.OLLAMA_URL).rstrip("/")
        self.modelo = config.MODELO_ARQUITETURA
        self.kb = construir_kb(dominio)
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        corpus = [" ".join(d["termos"]) for d in self.kb]
        self._matriz = self._vectorizer.fit_transform(corpus)
        self._system = self._montar_system()

    # -- recuperacao --------------------------------------------------------------------
    def _recuperar(self, comando: str) -> list[dict]:
        q = self._vectorizer.transform([comando])
        sims = cosine_similarity(q, self._matriz)[0]
        obrig_idx = [i for i, d in enumerate(self.kb) if d["tipo"] in ("esquema", "acao")]
        escolhidos = set(obrig_idx)

        # Match por nome no comando (objeto, categoria, comodo, local).
        cmd = f" {comando.lower()} "
        for i, d in enumerate(self.kb):
            if d["tipo"] in ("objeto", "categoria", "comodo", "local"):
                nome = d["nome"].lower()
                if re.search(r"\b" + re.escape(nome).replace(r"\ ", r"\s+(?:the\s+)?") + r"\b", cmd):
                    escolhidos.add(i)

        # Preenche por similaridade com cotas por tipo e teto total.
        cotas = dict(config.RAG_COTAS)
        contagem = {t: 0 for t in cotas}
        for i in escolhidos:
            t = self.kb[i]["tipo"]
            if t in contagem:
                contagem[t] += 1
        for i in sorted(range(len(self.kb)), key=lambda j: sims[j], reverse=True):
            if len(escolhidos) >= config.RAG_K:
                break
            if i in escolhidos or sims[i] <= 0:
                continue
            t = self.kb[i]["tipo"]
            if t in cotas and contagem[t] >= cotas[t]:
                continue
            escolhidos.add(i)
            if t in contagem:
                contagem[t] += 1
        return [self.kb[i] for i in sorted(escolhidos)]

    # -- prompt -------------------------------------------------------------------------
    def _montar_system(self) -> str:
        acoes = ", ".join(ACOES.keys())
        campos = ", ".join(_en(CAMPOS))
        ex = "\n".join(
            f'Command: "{t}"\nOutput: {json.dumps({_CHAVE_EN[c]: v for c, v in g.items()}, ensure_ascii=False)}'
            for t, g in _FEWSHOT
        )
        return (
            "You are the command interpreter of a domestic service robot competing in "
            "RoboCup@Home. You convert ONE natural-language command into a single flat JSON object.\n"
            "The environment is a CLOSED WORLD: every room, location, object, category, person and "
            "action is catalogued and given in the DOMAIN CONTEXT of the user message. Never output a "
            "value that does not appear there.\n"
            f"The {len(ACOES)} valid actions are: {acoes}\n"
            f"The fields are: {campos}\n"
            "HARD CONSTRAINTS\n"
            '- Reply with a single JSON object and nothing else.\n'
            '- The object has exactly one required key, "action". Other fields are optional and included '
            "only when the command states them.\n"
            "- Each command maps to ONE action (its main action). Do not output a list.\n"
            "- Never invent an action, object, room, location or person.\n"
            "- Write values in lower case, without articles, categories in the singular.\n"
            "- 'bring me X from Y' / 'give me X from Y' is action deliver with destination me.\n"
            "EXAMPLES\n" + ex
        )

    def _montar_user(self, comando: str, docs: list[dict]) -> str:
        contexto = "\n".join(f"- {d['texto']}" for d in docs)
        return f"DOMAIN CONTEXT\n{contexto}\n\nCOMMAND TO INTERPRET\n\"{comando}\"\nReply with the JSON object only."

    # -- chamada ao modelo --------------------------------------------------------------
    def aquecer(self) -> None:
        self._chamar("go to the kitchen")

    def _chamar(self, comando: str) -> tuple[str, dict, list[dict]]:
        docs = self._recuperar(comando)
        payload = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": self._system},
                {"role": "user", "content": self._montar_user(comando, docs)},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "seed": config.SEED, "num_ctx": config.NUM_CTX,
                        "num_predict": 1024, "top_p": 1.0},
            "think": False,
        }
        resp = requests.post(f"{self.url}/api/chat", json=payload, timeout=config.TIMEOUT_OLLAMA)
        resp.raise_for_status()
        dados = resp.json()
        conteudo = (dados.get("message") or {}).get("content", "")
        return conteudo, dados, docs

    @staticmethod
    def _extrair_json(texto: str) -> dict | None:
        texto = re.sub(r"```(?:json)?|```", "", texto).strip()
        ini, fim = texto.find("{"), texto.rfind("}")
        if ini == -1 or fim == -1 or fim < ini:
            return None
        try:
            return json.loads(texto[ini:fim + 1])
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _achatar(obj: dict) -> dict:
        """Chaves em ingles do prompt -> chaves do gabarito; tolera passo unico dentro de lista."""
        if isinstance(obj.get("passos"), list) and obj["passos"]:
            obj = obj["passos"][0]
        sinonimos = {en: pt for pt, en in _CHAVE_EN.items()} | {"info": "informacao"}
        return {sinonimos.get(ch, ch): v for ch, v in obj.items()}

    def interpretar(self, texto: str) -> ResultadoInterpretacao:
        t0 = time.perf_counter()
        tentativas = 0
        conteudo = ""
        dados: dict = {}
        docs: list[dict] = []
        obj = None
        try:
            conteudo, dados, docs = self._chamar(texto)
            tentativas = 1
            obj = self._extrair_json(conteudo)
            if obj is None:  # uma tentativa de reparo
                correcao = self._chamar(texto + "\n\n(The previous reply was not valid JSON. "
                                                "Reply with the JSON object only.)")
                conteudo, dados, _ = correcao
                tentativas = 2
                obj = self._extrair_json(conteudo)
        except Exception as exc:  # noqa: BLE001
            return ResultadoInterpretacao(latencia_s=time.perf_counter() - t0, erro=repr(exc))
        latencia = time.perf_counter() - t0

        if obj is None:
            return ResultadoInterpretacao(latencia_s=latencia, bruto=conteudo,
                                          detalhes={"tentativas": tentativas, "n_docs": len(docs)},
                                          erro="json_invalido")

        registro = {c: v for c, v in self._achatar(obj).items() if c in CAMPOS}
        registro_norm = self.norm.canonizar_registro(registro)
        alucinacoes = self.norm.alucinacoes(registro_norm)
        return ResultadoInterpretacao(
            registro=registro_norm,
            latencia_s=latencia,
            bruto=conteudo,
            detalhes={"tentativas": tentativas, "n_docs": len(docs), "alucinacoes": alucinacoes,
                      "metricas_ollama": [dados]},
        )

    def descrever(self) -> dict:
        return {"arquitetura": self.nome, "modelo": self.modelo, "url": self.url,
                "n_documentos_kb": len(self.kb), "rag_k": config.RAG_K, "cotas": config.RAG_COTAS,
                "exemplos_few_shot": [t for t, _ in _FEWSHOT]}
