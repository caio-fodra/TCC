"""Leitura e escrita de JSONL/JSON e coleta das condicoes de medicao."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

import requests


def ler_jsonl(caminho) -> list[dict]:
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(
            f"arquivo nao encontrado: {caminho}\nVerifique se a etapa anterior rodou."
        )
    registros = []
    with caminho.open("r", encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            linha = linha.strip()
            if not linha:
                continue
            try:
                registros.append(json.loads(linha))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{caminho}:{n}: JSON invalido: {exc}") from exc
    return registros


def gravar_jsonl(caminho, registros) -> int:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with caminho.open("w", encoding="utf-8") as f:
        for registro in registros:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            n += 1
    return n


def gravar_json(caminho, dados) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


def ler_json(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def _executar(comando) -> str | None:
    try:
        saida = subprocess.run(comando, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout.strip() or None


def descrever_hardware() -> dict:
    """Modelo do processador e memoria instalada (Windows); None onde nao houver como ler.

    `platform.processor()` so traz a familia ("Intel64 Family 6 Model 142"), que nao identifica o modelo.
    """
    modelo = memoria = None
    if sys.platform == "win32":
        import ctypes
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as chave:
                modelo = winreg.QueryValueEx(chave, "ProcessorNameString")[0].strip()
        except OSError:
            pass
        kb = ctypes.c_ulonglong(0)
        if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kb)):
            memoria = round(kb.value / 1024 ** 2)
    return {"processador_modelo": modelo, "memoria_instalada_gb": memoria}


def descrever_ambiente() -> dict:
    """Condicoes de medicao (Secao 3.4.3): hardware e versoes, gravadas junto aos resultados."""
    from tcc import config

    ambiente: dict = {
        "sistema": {
            "so": platform.platform(),
            "arquitetura": platform.machine(),
            "processador": platform.processor(),
            "python": sys.version.split()[0],
            **descrever_hardware(),
        },
        "configuracao": {
            "seed": config.SEED,
            "seed_treino_rasa": config.SEED_TREINO_RASA,
            "modelo_arquitetura": config.MODELO_ARQUITETURA,
            "num_ctx": config.NUM_CTX,
            "rag_k": config.RAG_K,
            "ollama_url": config.OLLAMA_URL,
            "rasa_url": config.RASA_URL,
        },
        "versao_experimento": "plana-a2",
    }
    # Pela API, nao pelo CLI: no Windows o `ollama` reabre o aplicativo, que herda a saida do
    # subprocesso e trava a coleta (e poe o Ollama no ar durante a passada do Rasa).
    try:
        versao = requests.get(f"{config.OLLAMA_URL}/api/version", timeout=5).json()["version"]
        modelos = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5).json()["models"]
    except (requests.RequestException, ValueError, KeyError):
        versao = None
    if versao:
        configurados = {config.MODELO_ARQUITETURA}
        ambiente["ollama"] = {"versao": versao, "modelos": [
            {"nome": m["name"], "digest": m["digest"][:12]}  # 12 caracteres, como no `ollama list`
            for m in modelos
            if m["name"] in configurados or m["name"].removesuffix(":latest") in configurados]}
    gpu = _executar(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    ambiente["sistema"]["gpu"] = gpu or "nao detectada"
    return ambiente
