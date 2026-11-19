# Campanha `sementes`

EfficientNet-B0 com 3 sementes: quanto o resultado varia por acaso

Gerado em 2026-11-19T23:29:06+00:00 a partir de `benchmark/campanhas/sementes.toml`.

Ordenado pelo **F2 na validação** (o critério de escolha). As colunas de teste são só registro.

| Rodada | F2 val. | Recall val. | Espec. val. | F2 teste | Fogo perdido / alarme falso (teste) | Épocas (melhor) | min/época |
|---|---|---|---|---|---|---|---|
| `efficientnet_b0_torchvision` | **99,7%** | 100,0% | 97,9% | 99,1% | 1 / 1 | 10 (3) | 2,6 |
| `efficientnet_b0_torchvision_s2026` | **99,7%** | 100,0% | 97,9% | 99,1% | 0 / 5 | 11 (4) | 3,3 |
| `efficientnet_b0_torchvision_s7` | **99,5%** | 100,0% | 96,9% | 99,1% | 1 / 1 | 8 (1) | 3,0 |

Variação entre as rodadas: F2 na validação de 99,5% a 99,7%; no teste, de 99,1% a 99,1%.

**Só a semente muda.** O que varia por acaso, no teste:
- F2: média 99,1%, desvio-padrão 0,0 ponto(s);
- recall de fogo: de 99,1% a 100,0% (fogo perdido: de 0 a 1);
- especificidade: de 94,7% a 99,0% (alarme falso: de 1 a 5).

O F2 pesa mais o fogo perdido e por isso quase não muda quando só os alarmes falsos mudam. Diferenças entre configurações menores que essas faixas não indicam que uma é melhor.

Validação: 210 imagens. Teste: 207 imagens. Métricas com o limiar calibrado na validação.
Arquivos de cada rodada: `relatorios/12_treino/<rodada>/`.
