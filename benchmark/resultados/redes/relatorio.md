# Campanha `redes`

ResNet18 x DenseNet121 x EfficientNet-B0, mesmo protocolo (Etapa 12)

Gerado em 2026-11-19T21:45:43+00:00 a partir de `benchmark/campanhas/redes.toml`.

Ordenado pelo **F2 na validação** (o critério de escolha). As colunas de teste são só registro.

| Rodada | F2 val. | Recall val. | Espec. val. | F2 teste | Fogo perdido / alarme falso (teste) | Épocas (melhor) | min/época |
|---|---|---|---|---|---|---|---|
| `resnet18_torchvision` | **99,8%** | 100,0% | 99,0% | 97,9% | 3 / 0 | 13 (6) | 2,7 |
| `efficientnet_b0_torchvision` | **99,7%** | 100,0% | 97,9% | 99,1% | 1 / 1 | 10 (3) | 2,6 |
| `densenet121_torchvision` | **99,5%** | 100,0% | 96,9% | 99,1% | 1 / 1 | 11 (4) | 6,4 |

Variação entre as rodadas: F2 na validação de 99,5% a 99,8%; no teste, de 97,9% a 99,1%.

Validação: 210 imagens. Teste: 207 imagens. Métricas com o limiar calibrado na validação.
Arquivos de cada rodada: `relatorios/12_treino/<rodada>/`.
