# dataset_ignis_alert – preparação do dataset (Ignis Alert)

**Site do projeto:** https://mariadlribeiro.github.io/dataset_ignis_alert/

**Benchmark parametrizável (LEAS):** [`benchmark/`](benchmark/README.md) — escolha uma campanha de experimentos e rode com `python benchmark/rodar.py --campanha <nome>`.

O site fica na pasta `docs/` (página, vídeo da retrospectiva e imagem de capa) e é publicado pelo GitHub Pages a partir dela.

Pipeline reprodutível, um dataset por vez. Originais nunca são modificados; imagens ficam fora do git
(`data/` no `.gitignore`) e a rastreabilidade vem dos manifestos SHA-256 e dos CSVs em `relatorios/`.

Hoje o dataset tem **1.388 imagens**: as da fonte 1 (`fire-dataset`, 999 arquivos) mais **400 imagens de floresta**
escolhidas entre os 11.034 arquivos da fonte 2 (`forest-fire-image-dataset`). Fogo = chamas visíveis; fumaça sozinha não conta como fogo.
Cada grupo de duplicatas fica inteiro em uma só parte (treino, validação ou teste).

Revisão humana da 2ª fonte (25/11/2026): 184 das 400 imagens novas passaram por revisão humana cega. O fogo bateu com a revisão por IA em todas, exceto uma marcada como incerta, que ficou em "outros" e sem fogo (`decisoes_pendencias.csv`); nenhum rótulo de fogo do teste mudou. O ambiente estava errado em 81 delas, quase sempre "outros" no lugar de floresta. Com a correção, a floresta tem **511 imagens com fogo e 578 sem fogo** (antes: 510 e 510). Detalhes em `relatorios/10_nova_fonte/rotulos_humanos_A/resumo.txt`.

| Etapa | Script(s) | O que faz |
|---|---|---|
| 1. Origem | `01_origem.py` | Inventário e manifesto SHA-256 dos originais |
| 2. Validação | `02_validacao.py` | Arquivos corrompidos, formatos e tamanhos |
| 3. Duplicatas | `03_duplicatas.py`, `04b_pagina_pares.py` | Exatas (SHA) e quase iguais (dHash, limiar 6) |
| 4. Divisão | `04_divisao.py` | Treino/validação/teste por grupo, nunca por imagem |
| 5. Revisão | `05a`–`05d` | Sugestões do CLIP; a decisão final é humana e vira CSV |
| 6. Plano | `06_plano.py` | Plano da organização, aprovado antes de copiar |
| 7. Cópia | `07_organizar.py` | Cópia conferida por SHA para `data/dataset_organizado/` |
| 8. Equilíbrio | `08_equilibrio.py` | Pesos do sampler por classe, estrato ou ambiente |
| 9. Condições | `09a`–`09e` | Medidas de luz, tamanho, formato, nitidez, cor e moldura |
| 10. Segunda fonte | `10a`–`10j` | Inventário, sugestões, seleção por diversidade, integração, revisão humana cega das rotuladas por IA, desempate, aplicação dos rótulos humanos e revisão das 216 que ainda têm só o rótulo da IA (`10j`) |
| 11. Exportar para o treino | `11_exportar_treino.py` | Cópia em `train/val/test` × `Fire/NoFire` com `split_manifest.csv` no formato do RD_Ignisalert |
| 12. Treino e avaliação | `12_treinar.py` | ResNet18, DenseNet121 ou EfficientNet-B0; limiar calibrado na validação; teste usado uma vez e quebrado por condição |
| 13. Teste de atalho | `13a`, `13b` | Imagens de floresta quadradas e pequenas da 2ª fonte, com e sem fogo, revisadas às cegas; mede se a rede usa o formato em vez da chama |
| 14. Negativos difíceis | `14a`, `14b` | Cenas sem fogo que parecem fogo ou fumaça (pôr do sol, neblina, nuvens, outono, luzes à noite, reflexos), da 2ª fonte e fora do dataset, revisadas às cegas; mede a taxa de falso alarme só nelas |
| 15. Robustez | `15a`–`15d` | Quase-duplicatas por conteúdo (CLIP/DINOv2) entre splits e fontes; linha de base só com cor; teste em tons de cinza; Grad-CAM (onde a rede olha) |

Achado principal (etapa 9): igualar a quantidade não igualou as condições. Imagens sem fogo são mais
quadradas e menores; imagens com fogo são mais escuras. Isso é risco de atalho para o modelo e está
documentado no site, com as medidas propostas para o treino.

O que ficou de fora de cada etapa não é apagado: vai para um CSV com o motivo (por exemplo
`relatorios/10_nova_fonte/.../fora.csv`).

Ficha técnica do dataset (origem, rótulos, usos indicados, vieses e limites): [`DATASHEET.md`](DATASHEET.md).

## Uso
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/01_origem.py
```
