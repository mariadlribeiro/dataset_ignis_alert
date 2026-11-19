# Campanha `sementes`

EfficientNet-B0 com 3 sementes: quanto o resultado varia por acaso

Gerado em 2026-11-19T23:27:04+00:00 a partir de `benchmark/campanhas/sementes.toml`.

Ordenado pelo **F2 na validação** (o critério de escolha). As colunas de teste são só registro.

| Rodada | F2 val. | Recall val. | Espec. val. | F2 teste | Fogo perdido / alarme falso (teste) | Épocas (melhor) | min/época |
|---|---|---|---|---|---|---|---|
| `efficientnet_b0_torchvision` | **99,7%** | 100,0% | 97,9% | 99,1% | 1 / 1 | 10 (3) | 2,6 |
| `efficientnet_b0_torchvision_s2026` | **99,7%** | 100,0% | 97,9% | 99,1% | 0 / 5 | 11 (4) | 3,3 |
| `efficientnet_b0_torchvision_s7` | **99,5%** | 100,0% | 96,9% | 99,1% | 1 / 1 | 8 (1) | 3,0 |

Variação entre as rodadas: F2 na validação de 99,5% a 99,7%; no teste, de 99,1% a 99,1%.
Só a semente muda: média do F2 no teste 99,1%, desvio-padrão 0.01 pontos. Diferenças entre redes menores que isso não indicam que uma é melhor.

Validação: 210 imagens. Teste: 207 imagens. Métricas com o limiar calibrado na validação.
Arquivos de cada rodada: `relatorios/12_treino/<rodada>/`.
