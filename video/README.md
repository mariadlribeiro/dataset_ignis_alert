# Retrospectiva v2

Ajustes na retrospectiva (`docs/retrospectiva.mp4`) depois da avaliação de 24/11:

- `cartelas.py gancho gancho.mp4`: abertura de 6,5 s com a foto `non_fire.133` (incêndio guardado como "sem fogo").
- `zoom.py original.mp4 meio.mp4`: amplia as telas de inventário (0:21–0:33) e de detalhamento (1:28–1:41), mantendo a legenda no lugar.
- `cartelas.py resultado resultado.mp4`: fecho de 7 s com a EfficientNet-B0 em duas fotos reais do teste
  (`fire.676`: 99,8% de fogo; `fire.320`: 3,1%), valores de `relatorios/12_treino/efficientnet_b0_torchvision/predicoes_teste.csv`.

Montagem: gancho + meio até 110,8 s + resultado + resto do meio (ffmpeg `concat`).
