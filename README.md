# dataset_ignis_alert – preparação do dataset (Ignis Alert)

**Site do projeto:** https://mariadlribeiro.github.io/dataset_ignis_alert/

O site fica na pasta `docs/` (página, vídeo da retrospectiva e imagem de capa) e é publicado pelo GitHub Pages a partir dela.

Pipeline reprodutível, um dataset por vez. Originais nunca são modificados; imagens ficam fora do git
(`data/` no `.gitignore`) e a rastreabilidade vem dos manifestos SHA-256 e dos CSVs em `relatorios/`.

Hoje o dataset tem **1.388 imagens**: as da fonte 1 (`fire-dataset`, 999 arquivos) mais **400 imagens de floresta**
escolhidas entre os 11.034 arquivos da fonte 2 (`forest-fire-image-dataset`). Fogo = chamas visíveis; fumaça sozinha não conta como fogo.
Cada grupo de duplicatas fica inteiro em uma só parte (treino, validação ou teste).

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
| 10. Segunda fonte | `10a`–`10d` | Inventário, sugestões, seleção por diversidade e integração |
| 11. Exportar para o treino | `11_exportar_treino.py` | Cópia em `train/val/test` × `Fire/NoFire` com `split_manifest.csv` no formato do RD_Ignisalert |

Achado principal (etapa 9): igualar a quantidade não igualou as condições. Imagens sem fogo são mais
quadradas e menores; imagens com fogo são mais escuras. Isso é risco de atalho para o modelo e está
documentado no site, com as medidas propostas para o treino.

O que ficou de fora de cada etapa não é apagado: vai para um CSV com o motivo (por exemplo
`relatorios/10_nova_fonte/.../fora.csv`).

## Uso
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/01_origem.py
```
