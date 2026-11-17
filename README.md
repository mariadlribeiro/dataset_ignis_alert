

**Site do projeto:** https://mariadlribeiro.github.io/dataset_ignis_alert/

O site fica na pasta `docs/` (página, vídeo da retrospectiva e imagem de capa) e é publicado pelo GitHub Pages a partir dela.
﻿# dataset_ignis_alert â€“ preparaÃ§Ã£o do dataset `phylake1337/fire-dataset` (Ignis Alert)

Pipeline reprodutÃ­vel, um dataset por vez. Originais nunca sÃ£o modificados; imagens ficam fora do git
(`data/` no `.gitignore`) e a rastreabilidade vem dos manifestos SHA-256 e dos CSVs em `relatorios/`.

| Etapa | Script | SaÃ­da |
|---|---|---|
| 1. Origem | `scripts/01_origem.py` | `relatorios/01_origem/` |
| 2. ValidaÃ§Ã£o | `scripts/02_validacao.py` | `relatorios/02_validacao/` |
| 3. Duplicatas | `scripts/03_duplicatas.py` | `relatorios/03_duplicatas/` |
| 4. DivisÃ£o (por grupo) | `scripts/04_divisao.py` | `relatorios/04_divisao/` |
| 5. OrganizaÃ§Ã£o | `scripts/05_organizacao.py` | `dataset_organizado/` (cÃ³pia) |

## Uso
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/01_origem.py
```
