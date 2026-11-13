# Roteiro de execucao (Windows / PowerShell). Rode os blocos na ordem, em DOIS ambientes.
# Ajuste os caminhos conforme a sua maquina. Nao e para rodar tudo de uma vez: os passos de
# Rasa e de Ollama acontecem em ambientes/janelas diferentes.

# ======================================================================
# PREPARO (uma vez)
# ----------------------------------------------------------------------
# Ambiente principal (Python 3.12):
#   py -3.12 -m venv .venv
#   .\.venv\Scripts\Activate.ps1
#   pip install -r requirements.txt
#
# Ambiente do Rasa (Python 3.10):
#   py -3.10 -m venv .venv-rasa
#   .\.venv-rasa\Scripts\Activate.ps1
#   pip install -r requirements-rasa.txt
#
# Dominio: fixo em data\domain (CompetitionTemplate, commit af2972f). Nao ha variavel de ambiente.

# ======================================================================
# 1. DADOS (ambiente principal 3.12)
# ----------------------------------------------------------------------
# Gera os 100 comandos canonicos (uma acao, gabarito plano):
python -m tcc.generate_dataset -n 100 --seed 42
python -m tcc.generate_dataset --self-check -n 5000      # confere a consistencia do gabarito

# Parafrases: geradas por agentes Claude no workflow scripts\gerar_parafrases.workflow.js, com a
# entrada de "python -m tcc.paraphrase --itens"; saida em data\parafrases_claude.jsonl.
# Confere as regras verificaveis e grava data\comandos_parafrase.jsonl:
python -m tcc.paraphrase --finalizar

# Dados de treino do Rasa (uma acao, anotados; remove coincidencia com o teste):
python -m tcc.build_rasa_data --n 3000

# ======================================================================
# 2. TREINO DO RASA (ambiente 3.10)
# ----------------------------------------------------------------------
#   .\.venv-rasa\Scripts\Activate.ps1
#   cd rasa_project
#   rasa train
#   rasa run --enable-api --port 5005        (deixe rodando; e o servico consultado por HTTP)

# ======================================================================
# 3. EXECUCAO (ambiente principal 3.12) -- em DUAS passadas
# ----------------------------------------------------------------------
# Passada A: Rasa no ar (porta 5005). Pare o Ollama para a latencia nao competir por memoria.
python -m tcc.run_experiment --arquiteturas rasa

# Passada B: Ollama no ar (qwen3:4b-instruct baixado). Pode parar o Rasa.
#   ollama serve
python -m tcc.run_experiment --arquiteturas llm_rag

# ======================================================================
# 4. AVALIACAO
# ----------------------------------------------------------------------
python -m tcc.run_experiment --consolidar     # metricas.json, divergencias.jsonl

python -m tcc.report                            # results\relatorio_metricas.md
