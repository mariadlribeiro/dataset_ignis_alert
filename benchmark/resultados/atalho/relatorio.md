# Campanha `atalho`

Redes já treinadas no teste de atalho (297 fotos quadradas e pequenas)

| Rede | Recall teste → atalho | Especificidade teste → atalho | Fogo perdido / alarme falso (atalho) |
|---|---|---|---|
| resnet18 | 97,3% → **95,3%** | 100,0% → 100,0% | 7 / 0 |
| efficientnet_b0 | 99,1% → **96,6%** | 99,0% → 99,3% | 5 / 1 |
| densenet121 | 99,1% → **100,0%** | 99,0% → 100,0% | 0 / 0 |

Uma queda grande no recall indicaria que a rede usa o formato da imagem em vez da chama.
Detalhes: `relatorios/13_atalho/resultado/`.
