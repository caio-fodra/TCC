# Rasa e LLM+RAG na interpretação de comandos da RoboCup@Home

Código, dados e resultados do Trabalho de Conclusão de Curso:

- **Título:** "Avaliação comparativa entre uma arquitetura baseada em intenção e entidade com Rasa e uma arquitetura LLM+RAG para interpretação de comandos textuais em robôs de serviço".
- **Autor:** Caio Augusto Prato Fodra.
- **Orientador:** Prof. Dr. João Alberto Fabro.
- **Curso:** Bacharelado em Sistemas de Informação, Universidade Tecnológica Federal do Paraná (UTFPR), Câmpus Curitiba, 2026.

## O que é

O trabalho compara duas arquiteturas que convertem um comando textual em um registro estruturado (ação e campos):

1. **Rasa**, com classificação de intenções e extração de entidades;
2. **LLM+RAG**, com o modelo Qwen3:4B-Instruct executado localmente pelo Ollama e uma base de conhecimento do domínio.

**Conjuntos de teste:**
- 100 comandos canônicos de uma única ação, gerados pela gramática do gerador oficial de comandos da prova GPSR;
- 100 paráfrases desses comandos, uma por comando, em cinco níveis de distância. As paráfrases foram geradas pelo modelo Claude Opus 5.5 num *workflow* descrito na Seção 3.2.4 do TCC.

**Avaliação:**
- acurácia por correspondência exata, com intervalo de Wilson;
- precisão, revocação e F1 por campo;
- latência;
- testes de McNemar e de Wilcoxon, com correção de Holm.

## Onde está cada parte do TCC

| No TCC | Neste repositório |
|---|---|
| Apêndice A (domínio experimental) e Seção 3.2.1 | arquivos do CompetitionTemplate (não incluídos, ver "Arquivos de terceiros"); leitura em `src/tcc/domain.py` |
| Apêndice B (comandos e paráfrases) e Seções 3.2.2 e 3.2.3 | `data/comandos_original.jsonl` e `data/comandos_parafrase.jsonl`; geração em `src/tcc/annotated_generator.py` e `src/tcc/generate_dataset.py` |
| Apêndice C (base de conhecimento) | `data/base_conhecimento.json`, gerado por `construir_kb` em `src/tcc/arch_llm_rag.py` |
| Apêndice D (instruções de geração e de verificação das paráfrases) e Seção 3.2.4 | `REGRAS` em `src/tcc/paraphrase.py`, `LENTES` em `scripts/gerar_parafrases.workflow.js`, `src/tcc/surface.py` e o registro das execuções em `data/parafrases_claude_registro.json` |
| Apêndice E (*prompt* da arquitetura LLM+RAG) e Seção 3.3.2 | `src/tcc/arch_llm_rag.py`; mensagem de usuário do exemplo em `data/exemplo_mensagem_usuario.txt` |
| Seção 3.3.1 (arquitetura Rasa) e quadro do *pipeline* | `rasa_project/config.yml`, `rasa_project/domain.yml`, `rasa_project/data/nlu.yml`; geração em `src/tcc/build_rasa_data.py`; cliente em `src/tcc/arch_rasa.py` |
| Seções 3.4 e 3.5 (métricas e procedimento) | `src/tcc/evaluate.py`, `src/tcc/stats.py`, `src/tcc/run_experiment.py` |
| Capítulo 4 (resultados) | `results/metricas.json`, `results/relatorio_metricas.md`, `results/divergencias.jsonl` e as saídas brutas, com a latência de cada comando, em `results/execucoes/` |
| Quadro do ambiente (Seção 4.1) | `results/ambiente_rasa.json` e `results/ambiente_llm_rag.json` |

## Versões usadas

As versões são as do quadro do ambiente de execução do TCC:

| Componente | Versão |
|---|---|
| Processador | Intel Core i5-10210U (1,6 GHz) |
| Memória | 12 GB |
| GPU | não utilizada (inferência em CPU) |
| Sistema operacional | Windows 11 |
| Python (experimento) | 3.12.4 |
| Python (servidor Rasa) | 3.10.11 |
| Rasa | 3.6.21 |
| Ollama | 0.40.14 |
| Modelo avaliado (LLM+RAG) | Qwen3-4B-Instruct-2507 (`qwen3:4b-instruct`, digest `0edcdef34593`) |
| Modelo parafraseador | Claude Opus 5.5, executado na nuvem |

## Arquivos de terceiros (não incluídos)

O gerador oficial de comandos ([RoboCupAtHome/CommandGenerator](https://github.com/RoboCupAtHome/CommandGenerator)) e os arquivos do domínio ([RoboCupAtHome/CompetitionTemplate](https://github.com/RoboCupAtHome/CompetitionTemplate)) não têm licença publicada, por isso não são redistribuídos aqui. O código espera encontrá-los nestes caminhos:

| Arquivo | Origem (commit) | Caminho neste repositório |
|---|---|---|
| `gpsr_commands.py`, `knowledge.py`, `__init__.py` | CommandGenerator, `eea62042201b8fac0127add831f2e2370c02b3c1` (16/04/2026), pasta `src/robocupathome_generator/` | `vendor/robocupathome_generator/` |
| `maps/location_names.md`, `maps/room_names.md`, `names/names.md`, `objects/objects.md` | CompetitionTemplate, `af2972f0670afbb068701f1dc5281c0efac5045c` (01/04/2026) | `data/domain/` |

Com `curl`, na raiz do repositório (Git Bash, Linux ou macOS):

```bash
GEN=eea62042201b8fac0127add831f2e2370c02b3c1
CT=af2972f0670afbb068701f1dc5281c0efac5045c
for f in gpsr_commands.py knowledge.py __init__.py; do
  curl -fL --create-dirs -o "vendor/robocupathome_generator/$f" \
    "https://raw.githubusercontent.com/RoboCupAtHome/CommandGenerator/$GEN/src/robocupathome_generator/$f"
done
for f in maps/location_names.md maps/room_names.md names/names.md objects/objects.md; do
  curl -fL --create-dirs -o "data/domain/$f" \
    "https://raw.githubusercontent.com/RoboCupAtHome/CompetitionTemplate/$CT/$f"
done
```

Os dois caminhos estão no `.gitignore`.

Os arquivos do domínio usados no experimento são idênticos, byte a byte, aos desse commit.

O código do gerador usado no experimento é o desse commit, com uma diferença: em `knowledge.py`, a função `_read_data` abre o arquivo com `open(file_path, "r", encoding="utf-8")`. Os quatro arquivos do domínio só têm caracteres ASCII, então o conteúdo lido é o mesmo com ou sem essa opção.

Além disso, a cópia usada difere do commit em pontos que não mudam o comportamento: formatação, comentários e docstrings, a falta de um `import` não usado (`cached_property`) e a falta do bloco `if __name__ == "__main__"` de `knowledge.py`. As listas, os *templates* e o sorteio de comandos são os mesmos.

## Como reproduzir

O roteiro completo, em PowerShell, está em `scripts/run_all.ps1`. São dois ambientes Python, porque o Rasa 3.6 exige Python 3.10.

**Preparação**, uma vez:

```bash
# Ambiente principal (Python 3.12)
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Ambiente do Rasa (Python 3.10), usado só para treinar e servir o modelo
py -3.10 -m venv .venv-rasa
.venv-rasa\Scripts\Activate.ps1
pip install -r requirements-rasa.txt

# Modelo do Ollama
ollama pull qwen3:4b-instruct
```

**1. Comandos canônicos** (ambiente 3.12). Os comandos gerados já estão em `data/comandos_original.jsonl`:

```bash
python -m tcc.generate_dataset -n 100 --seed 42
python -m tcc.generate_dataset --self-check -n 5000   # confere a consistência do gabarito
```

**2. Paráfrases.**
- Elas foram geradas pelo *workflow* `scripts/gerar_parafrases.workflow.js`, executado no Claude Code com agentes do modelo Claude Opus 5.5 (`PARAFRASEADOR` em `src/tcc/paraphrase.py`).
- A entrada do *workflow* é a saída de `python -m tcc.paraphrase --itens`.
- A saída está em `data/parafrases_claude.jsonl`, e o registro das duas execuções, em `data/parafrases_claude_registro.json`.
- O passo seguinte confere as regras verificáveis e grava `data/comandos_parafrase.jsonl`:

```bash
python -m tcc.paraphrase --finalizar
```

**3. Dados de treino do Rasa** (ambiente 3.12). Este passo grava `rasa_project/data/nlu.yml`, `domain.yml` e `config.yml`:

```bash
python -m tcc.build_rasa_data --n 3000
```

O `config.yml` deste repositório é o arquivo como ficou depois do `rasa train`, que o reescreve com outro recuo e acrescenta a linha `assistant_id`. O conteúdo é o mesmo que este passo gera.

**4. Treino e servidor do Rasa** (ambiente 3.10). Deixe o servidor rodando:

```bash
cd rasa_project
rasa train
rasa run --enable-api --port 5005
```

**5. Execução** (ambiente 3.12), uma arquitetura por vez, para que as duas não disputem memória durante a medição de latência:

```bash
# Passada do Rasa: servidor do Rasa no ar e Ollama parado
python -m tcc.run_experiment --arquiteturas rasa
# Passada do LLM+RAG: Ollama no ar (ollama serve) e Rasa parado
python -m tcc.run_experiment --arquiteturas llm_rag
```

**6. Avaliação:**

```bash
python -m tcc.run_experiment --consolidar   # results/metricas.json e results/divergencias.jsonl
python -m tcc.report                        # results/relatorio_metricas.md
```

**7. Testes** (ambiente 3.12, com os arquivos de terceiros no lugar):

```bash
python -m pytest
```

## Registro da geração das paráfrases

`data/parafrases_claude_registro.json` guarda as duas execuções do *workflow*: o *script* usado, as respostas de cada agente e o histórico de aprovações e reprovações.

A única mudança em relação ao arquivo original está nos dois valores de `scriptPath`. Eles traziam o caminho local do *script* na máquina do autor e foram trocados por `<caminho local omitido>`.

## Licença

Os arquivos deste repositório estão sob a licença MIT (`LICENSE`). Ela não cobre os arquivos de terceiros descritos acima, que não fazem parte do repositório.
