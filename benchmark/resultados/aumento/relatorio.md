# Campanha `aumento`

EfficientNet-B0 com e sem aumento de dados

Gerado em 2026-11-19T23:19:58+00:00 a partir de `benchmark/campanhas/aumento.toml`.

Ordenado pelo **F2 na validação** (o critério de escolha). As colunas de teste são só registro.

| Rodada | F2 val. | Recall val. | Espec. val. | F2 teste | Fogo perdido / alarme falso (teste) | Épocas (melhor) | min/época |
|---|---|---|---|---|---|---|---|
| `efficientnet_b0_torchvision` | **99,7%** | 100,0% | 97,9% | 99,1% | 1 / 1 | 10 (3) | 2,6 |
| `efficientnet_b0_nenhum` | **99,7%** | 100,0% | 97,9% | 99,3% | 1 / 0 | 9 (2) | 3,2 |

Variação entre as rodadas: F2 na validação de 99,7% a 99,7%; no teste, de 99,1% a 99,3%.

Validação: 210 imagens. Teste: 207 imagens. Métricas com o limiar calibrado na validação.
Arquivos de cada rodada: `relatorios/12_treino/<rodada>/`.
