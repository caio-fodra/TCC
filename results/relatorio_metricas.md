# Relatorio de metricas (versao plana)

Uma secao por dimensao da Secao 3.4. Delta de acuracia/campo = canonico - parafrase (positivo = queda).

## 1. Acuracia por correspondencia exata (3.4.1)

| Arquitetura | Subconjunto | n | Acertos | Acuracia | IC 95% (Wilson) |
|---|---|---:|---:|---:|---|
| Rasa | C_original | 100 | 100 | 100.0% | [96.3; 100.0] |
| Rasa | C_parafrase | 100 | 39 | 39.0% | [30.0; 48.8] |
| LLM+RAG | C_original | 100 | 81 | 81.0% | [72.2; 87.5] |
| LLM+RAG | C_parafrase | 100 | 85 | 85.0% | [76.7; 90.7] |

**Estabilidade (delta da acuracia exata).**

| Arquitetura | Canonico | Parafrase | Delta |
|---|---:|---:|---:|
| rasa | 100.0% | 39.0% | +61.0 pp |
| llm_rag | 81.0% | 85.0% | -4.0 pp |

## 2. Desempenho por campo (3.4.2)

Acuracia = revocacao; precisao e F1 acompanham. Alinhamento por campo do registro plano.

### Campo `acao`

| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 100 | 100 | 100.0% | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |
| Rasa | C_parafrase | 100 | 78 | 78.0% | 0.780 | 0.780 | 0.780 | 22 | 0 | 0 |
| LLM+RAG | C_original | 100 | 92 | 92.0% | 0.920 | 0.920 | 0.920 | 8 | 0 | 0 |
| LLM+RAG | C_parafrase | 100 | 93 | 93.0% | 0.930 | 0.930 | 0.930 | 7 | 0 | 0 |

### Campo `objeto`

| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 35 | 35 | 100.0% | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |
| Rasa | C_parafrase | 35 | 33 | 94.3% | 0.559 | 0.943 | 0.702 | 2 | 0 | 24 |
| LLM+RAG | C_original | 35 | 31 | 88.6% | 0.816 | 0.886 | 0.849 | 4 | 0 | 3 |
| LLM+RAG | C_parafrase | 35 | 33 | 94.3% | 0.892 | 0.943 | 0.917 | 2 | 0 | 2 |

### Campo `pessoa`

| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 39 | 39 | 100.0% | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |
| Rasa | C_parafrase | 39 | 37 | 94.9% | 0.755 | 0.949 | 0.841 | 2 | 0 | 10 |
| LLM+RAG | C_original | 39 | 36 | 92.3% | 1.000 | 0.923 | 0.960 | 0 | 3 | 0 |
| LLM+RAG | C_parafrase | 39 | 38 | 97.4% | 1.000 | 0.974 | 0.987 | 0 | 1 | 0 |

### Campo `origem`

| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 27 | 27 | 100.0% | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |
| Rasa | C_parafrase | 27 | 24 | 88.9% | 0.750 | 0.889 | 0.814 | 1 | 2 | 7 |
| LLM+RAG | C_original | 27 | 25 | 92.6% | 1.000 | 0.926 | 0.962 | 0 | 2 | 0 |
| LLM+RAG | C_parafrase | 27 | 26 | 96.3% | 1.000 | 0.963 | 0.981 | 0 | 1 | 0 |

### Campo `destino`

| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 29 | 29 | 100.0% | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |
| Rasa | C_parafrase | 29 | 21 | 72.4% | 0.840 | 0.724 | 0.778 | 1 | 7 | 3 |
| LLM+RAG | C_original | 29 | 29 | 100.0% | 0.935 | 1.000 | 0.967 | 0 | 0 | 2 |
| LLM+RAG | C_parafrase | 29 | 29 | 100.0% | 0.967 | 1.000 | 0.983 | 0 | 0 | 1 |

### Campo `local`

| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 60 | 60 | 100.0% | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |
| Rasa | C_parafrase | 60 | 51 | 85.0% | 0.810 | 0.850 | 0.829 | 6 | 3 | 6 |
| LLM+RAG | C_original | 60 | 60 | 100.0% | 0.968 | 1.000 | 0.984 | 0 | 0 | 2 |
| LLM+RAG | C_parafrase | 60 | 60 | 100.0% | 0.984 | 1.000 | 0.992 | 0 | 0 | 1 |

### Campo `atributo`

| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 19 | 19 | 100.0% | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |
| Rasa | C_parafrase | 19 | 19 | 100.0% | 0.950 | 1.000 | 0.974 | 0 | 0 | 1 |
| LLM+RAG | C_original | 19 | 17 | 89.5% | 0.810 | 0.895 | 0.850 | 2 | 0 | 2 |
| LLM+RAG | C_parafrase | 19 | 17 | 89.5% | 0.850 | 0.895 | 0.872 | 2 | 0 | 1 |

### Campo `informacao`

| Arquitetura | Subconjunto | Suporte | Acertos | Acuracia | Precisao | Revocacao | F1 | Subst | Omiss | Insercoes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 11 | 11 | 100.0% | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |
| Rasa | C_parafrase | 11 | 5 | 45.5% | 0.192 | 0.455 | 0.270 | 6 | 0 | 15 |
| LLM+RAG | C_original | 11 | 9 | 81.8% | 0.818 | 0.818 | 0.818 | 2 | 0 | 0 |
| LLM+RAG | C_parafrase | 11 | 6 | 54.5% | 0.545 | 0.545 | 0.545 | 5 | 0 | 0 |

### F1 micro de entidades (todos os campos menos `acao`)

| Arquitetura | Subconjunto | Suporte | Acertos | Precisao | Revocacao | F1 |
|---|---|---:|---:|---:|---:|---:|
| Rasa | C_original | 220 | 220 | 1.000 | 1.000 | 1.000 |
| Rasa | C_parafrase | 220 | 190 | 0.693 | 0.864 | 0.769 |
| LLM+RAG | C_original | 220 | 207 | 0.924 | 0.941 | 0.932 |
| LLM+RAG | C_parafrase | 220 | 209 | 0.937 | 0.950 | 0.944 |

## 3. Latencia (3.4.3)

| Arquitetura | Subconjunto | n | Excluidos | Media | Mediana | Desvio | Minimo | Maximo | p95 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Rasa | C_original | 100 | 0 | 0.0121 s | 0.0121 s | 0.0011 s | 0.0100 s | 0.0159 s | 0.0140 s |
| Rasa | C_parafrase | 100 | 0 | 0.0123 s | 0.0123 s | 0.0013 s | 0.0100 s | 0.0168 s | 0.0142 s |
| LLM+RAG | C_original | 100 | 0 | 12.2111 s | 10.6851 s | 4.7238 s | 5.0276 s | 27.5722 s | 20.7567 s |
| LLM+RAG | C_parafrase | 100 | 0 | 9.9687 s | 9.5953 s | 3.5211 s | 4.3566 s | 19.8543 s | 15.4942 s |

## 4. Testes de significancia para amostras pareadas (3.5)

| Teste | Comparacao | n | So A | So B | p bruto | p (Holm) | Sig. 5% |
|---|---|---:|---:|---:|---:|---:|:---:|
| McNemar | Rasa vs LLM+RAG em C_original | 19 | 19 | 0 | 3.81e-06 | 7.63e-06 | sim |
| McNemar | Rasa vs LLM+RAG em C_parafrase | 50 | 2 | 48 | 2.27e-12 | 6.80e-12 | sim |
| McNemar | canonico vs parafrase (rasa) | 61 | 61 | 0 | 8.67e-19 | 3.47e-18 | sim |
| McNemar | canonico vs parafrase (llm_rag) | 14 | 5 | 9 | 4.24e-01 | 4.24e-01 | nao |
| Wilcoxon | Rasa vs LLM+RAG em C_original | 100 | -- | -- | 3.90e-18 | 7.79e-18 | sim |
| Wilcoxon | Rasa vs LLM+RAG em C_parafrase | 100 | -- | -- | 3.90e-18 | 7.79e-18 | sim |

