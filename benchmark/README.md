# Benchmark parametrizável do Ignis Alert

Artefato da disciplina **LEAS 2026/2** (UNIPAMPA Alegrete). Ele transforma os experimentos do projeto em
**campanhas**: cada campanha é um arquivo de parâmetros, e quem usa escolhe qual rodar. O runner monta as
rodadas, reaproveita o que já foi treinado e gera tabela, relatório e gráfico.

Dados: o dataset de 1.388 imagens deste repositório (Etapas 1 a 11). Fogo = chama visível; fumaça sozinha
não é fogo. Treino 971 · validação 210 · teste 207, divididos por grupo de duplicatas.

## Como rodar

Na raiz do repositório, com o ambiente do projeto (Python 3.12, `torch`, `torchvision`, `matplotlib`):

```powershell
# 1. uma vez: gerar a pasta de treino a partir do dataset organizado (Etapa 11)
.\.venv\Scripts\python.exe scripts\11_exportar_treino.py

# 2. ver as campanhas e o que já foi feito
.\.venv\Scripts\python.exe benchmark\rodar.py --listar

# 3. ver o plano e o tempo estimado de uma campanha, sem rodar nada
.\.venv\Scripts\python.exe benchmark\rodar.py --campanha sementes --so-plano

# 4. rodar
.\.venv\Scripts\python.exe benchmark\rodar.py --campanha sementes
```

`--refazer` roda de novo rodadas que já existem. Em Linux ou macOS, troque `.\.venv\Scripts\python.exe` por `python`.

## Campanhas

| Campanha | Tipo | O que responde | Tempo (CPU) |
|---|---|---|---|
| `rapida` | treino | O ambiente está pronto? 1 época, 40 imagens por conjunto; números sem valor | ~1 min |
| `redes` | treino | Qual arquitetura? ResNet18 × DenseNet121 × EfficientNet-B0, mesmo protocolo | já feita |
| `aumento` | treino | O aumento de dados ajuda? EfficientNet-B0 com e sem | ~30–50 min |
| `sementes` | treino | Quanto o resultado muda por acaso? EfficientNet-B0 com 3 sementes | ~1–2 h |
| `atalho` | avaliação | A rede olha a chama ou o formato? Redes treinadas em 297 fotos quadradas e pequenas | ~3 min |
| `custo` | avaliação | Quanto custa rodar? Tempo por imagem, parâmetros e tamanho de cada rede | ~5 min |

### Criar uma campanha

Copie um arquivo de `campanhas/` e mude os parâmetros. Em `[base]` ficam os valores fixos; em `[grade]`,
listas de valores: o runner roda **todas as combinações**.

```toml
nome = "lote"
descricao = "EfficientNet-B0 com lote 8 e 16"
tipo = "treino"

[base]
aumento = "torchvision"
epocas = 20

[grade]
rede = ["efficientnet_b0"]
lote = [8, 16]
```

Parâmetros de treino aceitos (com o padrão): `rede` (resnet18, densenet121, efficientnet_b0), `aumento`
(torchvision ou nenhum), `epocas` (20), `lote` (8), `lr` (0.0001), `paciencia` (7), `tamanho` (224),
`semente` (42), `teste_rapido` (false).

Cada rodada recebe um nome que descreve só o que difere do padrão (por exemplo,
`efficientnet_b0_torchvision_s7` é a semente 7). Uma rodada com os mesmos parâmetros nunca é treinada duas vezes.

## O que sai

```
benchmark/resultados/<campanha>/
  tabela.csv      uma linha por rodada (ou por rede, lote e resolução, na campanha custo)
  relatorio.md    a tabela comentada
  grafico.png     F2 na validação e no teste, por rodada (campanhas de treino)
  logs/           a saída de cada rodada
relatorios/12_treino/<rodada>/   métricas, predições, histórico, condições e config de cada treino
data/modelos/<rodada>/modelo.pth pesos (fora do git)
```

## Regras de método

1. **Escolher pela validação, nunca pelo teste.** A tabela é ordenada pelo F2 na validação. O teste aparece só
   como registro: se fosse usado para escolher, viraria mais uma validação e deixaria de medir o mundo real.
2. **Mesmo protocolo em todas as rodadas:** pré-treino ImageNet, aumento só no treino, perda com peso por
   classe, melhor época por F2 na validação, limiar calibrado na validação. Detalhes em `scripts/12_treinar.py`.
3. **F2 como métrica principal.** Num alerta, perder um incêndio custa mais que um alarme falso.
4. **Diferença menor que a variação entre sementes não é diferença.** Use a campanha `sementes` antes de dizer que
   uma configuração é melhor que outra.

### Um achado do próprio benchmark

Na campanha `redes`, o F2 na validação ficou entre 99,5% e 99,8% nas três redes: a validação de 210 imagens
**saturou** e não separa as arquiteturas (a ResNet18 aparece em primeiro por menos de uma imagem). A escolha da
EfficientNet-B0 para o aplicativo foi feita pelo empate de desempenho somado ao custo (treino 2 a 3 vezes mais
rápido que a DenseNet121), e não por uma vantagem no teste. Para separar as redes de verdade, o próximo passo é
uma validação maior ou com casos difíceis.

### O que as campanhas mostraram (19 nov. 2026)

| Campanha | Resultado |
|---|---|
| `redes` | F2 no teste de 97,8% (ResNet18) a 99,1% (DenseNet121 e EfficientNet-B0); na validação, 99,5% a 99,8% |
| `sementes` | Mesma EfficientNet-B0, só a semente muda: F2 no teste 99,1% nas três, mas **alarme falso de 1 a 5** e fogo perdido de 0 a 1 |
| `aumento` | Com aumento: 1 fogo perdido / 1 alarme falso; sem: 1 / 0. Diferença menor que a variação entre sementes |
| `atalho` | Recall nas 297 fotos quadradas e pequenas: 95,3% (ResNet18), 96,6% (EfficientNet-B0), 100% (DenseNet121) |
| `custo` | Por imagem, na CPU das autoras: ResNet18 ~34 ms, EfficientNet-B0 ~30–35 ms, DenseNet121 ~92–97 ms |

Conclusão: as diferenças de desempenho entre as redes (1 a 2 imagens) ficam dentro do que muda por acaso, e o
F2 sozinho esconde a variação de alarmes falsos. A EfficientNet-B0 foi escolhida pelo custo: cerca de 3 vezes
mais rápida por imagem que a DenseNet121, com o mesmo F2. Cada campanha tem seu `relatorio.md` em `resultados/`.

## Como foi gerado com IA

Este benchmark foi construído com apoio do **Claude (Anthropic)**, em conversa com as autoras, em novembro de 2026.

| Parte | Quem fez |
|---|---|
| Ideia de transformar os experimentos em benchmark de campanhas | sugestão do professor (LEAS) |
| Escolha das campanhas, do local (pasta `benchmark/`) e da rede do aplicativo | as autoras |
| Código: `rodar.py`, arquivos de campanha, `scripts/11` a `13b`, este README | gerado pelo Claude; executado e conferido pelas autoras |
| Rótulos do dataset | revisão humana e por IA, registrada por imagem no inventário |
| Rótulos do teste de atalho | revisão cega pelo Claude, conferida pelas autoras por amostra |
| Treinos e medições | executados pelas autoras, na CPU do próprio computador |

O que foi conferido: as seis campanhas foram executadas pelas autoras no próprio computador em 19/11/2026. Os números nos relatórios vêm dos arquivos gerados pelos
scripts, não foram digitados à mão.

## Autoras

Maria de Lurdes e Maria Heduarda, LIAA e LEAS 2026/2, UNIPAMPA Alegrete.
Site do projeto: https://mariadlribeiro.github.io/dataset_ignis_alert/
