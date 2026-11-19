# Campanha `custo`

Tempo por imagem, parâmetros e tamanho das 3 redes, por lote e resolução

Medido em 2026-11-19T21:41:13+00:00, CPU, 8 threads, torch 2.15.0+cpu. Mediana de 20 medições.

| Rede | Lote | Resolução | ms por imagem | Imagens/s | Parâmetros (milhões) | Arquivo (MB) |
|---|---|---|---|---|---|---|
| resnet18 | 1 | 224 | 34.04 | 29.4 | 11.18 | 42.7 |
| resnet18 | 8 | 224 | 36.29 | 27.6 | 11.18 | 42.7 |
| densenet121 | 1 | 224 | 96.81 | 10.3 | 6.96 | 27.1 |
| densenet121 | 8 | 224 | 91.7 | 10.9 | 6.96 | 27.1 |
| efficientnet_b0 | 1 | 224 | 35.0 | 28.6 | 4.01 | 15.6 |
| efficientnet_b0 | 8 | 224 | 30.44 | 32.9 | 4.01 | 15.6 |

O tempo depende da máquina: compare as redes entre si, na mesma máquina, não com outros computadores.
