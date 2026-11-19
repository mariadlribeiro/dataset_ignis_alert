# Campanha `rapida`

Teste de fumaça: 1 época e 40 imagens por conjunto, só para ver se tudo roda

Gerado em 2026-11-19T21:40:31+00:00 a partir de `benchmark/campanhas/rapida.toml`.

Ordenado pelo **F2 na validação** (o critério de escolha). As colunas de teste são só registro.

| Rodada | F2 val. | Recall val. | Espec. val. | F2 teste | Fogo perdido / alarme falso (teste) | Épocas (melhor) | min/época |
|---|---|---|---|---|---|---|---|
| `resnet18_torchvision_rapido` | **98,5%** | 100,0% | 85,7% | 96,2% | 1 / 0 | 1 (1) | 0,1 |

> Teste rápido: 1 época e 40 imagens por conjunto. Os números não têm valor.

Validação: 210 imagens. Teste: 207 imagens. Métricas com o limiar calibrado na validação.
Arquivos de cada rodada: `relatorios/12_treino/<rodada>/`.
