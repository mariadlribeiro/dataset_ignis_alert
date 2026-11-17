# dataset_ignis_alert – preparação do dataset `phylake1337/fire-dataset` (Ignis Alert)

**Site do projeto:** https://mariadlribeiro.github.io/dataset_ignis_alert/

O site fica na pasta `docs/` (página, vídeo da retrospectiva e imagem de capa) e é publicado pelo GitHub Pages a partir dela.

Pipeline reprodutível, um dataset por vez. Originais nunca são modificados; imagens ficam fora do git
(`data/` no `.gitignore`) e a rastreabilidade vem dos manifestos SHA-256 e dos CSVs em `relatorios/`.

| Etapa | Script | Saída |
|---|---|---|
| 1. Origem | `scripts/01_origem.py` | `relatorios/01_origem/` |
| 2. Validação | `scripts/02_validacao.py` | `relatorios/02_validacao/` |
| 3. Duplicatas | `scripts/03_duplicatas.py` | `relatorios/03_duplicatas/` |
| 4. Divisão (por grupo) | `scripts/04_divisao.py` | `relatorios/04_divisao/` |
| 5. Organização | `scripts/05_organizacao.py` | `dataset_organizado/` (cópia) |

## Uso
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/01_origem.py
```
