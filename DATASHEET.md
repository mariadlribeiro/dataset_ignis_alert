# Datasheet: dataset Ignis Alert (combinado, 1.388 imagens)

Modelo "Datasheets for Datasets" (Gebru et al., 2021), resumido. Os números saem dos relatórios do repositório.
Última atualização: 25/11/2026, depois da Etapa 10i (rótulos humanos da 2ª fonte).

## 1. Motivação
- **Para quê:** treinar e avaliar um classificador "tem fogo / não tem fogo" para o protótipo Ignis Alert. A IA faz
  a triagem e uma pessoa confirma o alerta.
- **Quem fez:** Maria de Lurdes e Maria Heduarda, na disciplina LIAA/LEAS 2026.2 da Unipampa.
- **Por que não usar um dataset pronto:** na 1ª apresentação, as redes deram 95–98% de acurácia em um dataset do
  Kaggle. Ao misturar três fontes, a acurácia caiu para 87,5%. Havia rótulos errados, cópias e imagens fora de
  contexto. Por isso o dataset foi refeito imagem por imagem, a partir de 16/10/2026.

## 2. Composição
| | com fogo | sem fogo | total |
|---|---:|---:|---:|
| treino | 525 | 446 | 971 |
| validação | 114 | 96 | 210 |
| teste | 112 | 95 | 207 |
| **total** | **751** | **637** | **1.388** |

- **Fontes:**
  - `phylake1337/fire-dataset` v1 (Kaggle, CC0): 988 imagens incluídas de 999 arquivos;
  - `cristiancristancho/forest-fire-image-dataset` v2 (Kaggle): 400 imagens, escolhidas por diversidade entre 11.034
    arquivos (Etapa 10c). A licença desta fonte ainda precisa ser conferida na página do Kaggle, porque o download
    não trouxe arquivo de licença.
- **Ambiente** (com fogo / sem fogo):
  - floresta 511/578;
  - prédios 83/5;
  - cidade 61/27;
  - casa 55/5;
  - outros 41/21.
- **Definição de fogo:** chama visível. Fumaça sem chama conta como **sem fogo**. A fumaça tem um rótulo separado
  (sim, não ou incerto).
- **Ficaram de fora:** 11 arquivos que não são fotografia (9 imagens sintéticas, 1 visualização de sensor e 1 GIF
  animado), listados em `fora.csv`.
- **Cópias:**
  - as cópias exatas (SHA-256) e as quase cópias (dHash) foram agrupadas na Etapa 3;
  - cada grupo fica inteiro em um único split (`group_key` no manifesto; o treino recusa grupos divididos);
  - a Etapa 15a procura também a mesma cena com outro recorte, usando a semelhança de conteúdo pelo CLIP.
- **Dados pessoais:** não há rótulos de pessoas. As fotos são públicas. Algumas mostram casas e ruas, mas nenhuma
  identifica alguém pelo nome.

## 3. Coleta e rotulagem
- **Origem de cada arquivo:** registrada com SHA-256, caminho original e versão do Kaggle (Etapas 1 e 10a).
- **Quem rotulou cada imagem** (coluna `fonte_fogo` do inventário):

  | fonte do rótulo de fogo | imagens | o que significa |
  |---|---:|---|
  | revisão humana | 577 | uma pessoa olhou a imagem |
  | sugestão automática | 591 | fonte 1: concorda com a pasta de origem, sem revisão individual |
  | revisão por IA | 216 | fonte 2: rotulada por IA, ainda sem revisão humana (Etapa 10j) |
  | cópia exata / decisão humana | 4 | herdou o rótulo da cópia, ou foi decidida no desempate |

- **Como foi a revisão humana** (critérios completos em `GUIA_ROTULAGEM.md`):
  - foi às cegas: a página não mostra o rótulo da IA nas imagens de auditoria;
  - a ordem foi embaralhada com semente fixa;
  - houve uma revisora só, por divisão de tarefas da dupla;
  - os casos de dúvida foram para uma rodada de desempate (Etapa 10g).
- **Concordância entre a IA e a revisão humana** (2ª fonte):
  - fogo: 183 de 184 imagens;
  - ambiente: errado em 81 das 184. Quase sempre era "outros" no lugar de floresta, e foi corrigido na Etapa 10i.
- **Limite conhecido:** só uma pessoa revisou, então não dá para medir a concordância entre pessoas (kappa entre
  revisoras).

## 4. Pré-processamento
- Os arquivos são copiados sem recodificar e conferidos por SHA-256 (Etapa 11).
- O formato real é detectado pelo conteúdo. Por exemplo, um `.png` que na verdade é JPEG fica registrado como JPEG.
- Redimensionamento e normalização acontecem só no carregamento do treino (Etapa 12). O dataset guarda os
  originais.

## 5. Usos
- **Usos indicados:**
  - pesquisa e ensino;
  - comparar redes com o mesmo protocolo;
  - triagem com confirmação humana.
- **Não usar como:**
  - detector único de incêndio, sem uma pessoa confirmando;
  - medida de desempenho em câmera fixa, drone ou satélite. A maioria das imagens é foto terrestre, de celular ou
    da web.
- **Resultados que já mostram o limite:**
  - no teste principal, a EfficientNet-B0 errou 2 de 207 imagens;
  - nos negativos difíceis (Etapa 14b), o falso alarme sobe de cerca de 1% para cerca de 10%;
  - no pôr do sol, o falso alarme é de 22% (6 de 27; IC 95% de 10,6 a 40,8%).
- **Vieses conhecidos:**
  - a floresta domina o dataset (1.089 de 1.388 imagens);
  - há pouca cena sem fogo em prédios e casas;
  - o formato da imagem já esteve ligado à classe, e isso foi verificado na Etapa 13 (teste de atalho);
  - a Etapa 15 mede quanto a cor sozinha explica os acertos.

## 6. Privacidade
- **Cópia pública:** a Etapa 16 monta a cópia para distribuir.
  - Remove EXIF (GPS, aparelho, data), XMP, IPTC e textos embutidos sem recodificar: os pixels continuam idênticos
    aos do treino.
  - Borra rostos reconhecíveis e placas legíveis. O CLIP aponta as candidatas, e uma pessoa marca cada retângulo.
- **Fotos tiradas pela equipe** (Etapa 14c) são só para avaliação: não entram no dataset nem no git.

## 7. Versões
| versão | data | o que é |
|---|---|---|
| v1.0 | 26/11/2026 | 1.388 imagens, rótulos e divisão depois da Etapa 10i. Manifesto do treino: SHA-256 `2be202c4…0873`. Tag `v1.0` no git |

- **Regra das versões:** mudou um rótulo ou um split, nova versão menor (v1.1). Entrou ou saiu uma fonte, nova
  versão maior (v2.0).
- **Próxima versão:** a v1.1 incorpora a revisão das 216 imagens (10j) e os pares de quase-duplicatas confirmados
  (15a).

## 8. Distribuição e manutenção
- **Onde fica:**
  - os scripts, inventários e relatórios ficam no GitHub (`mariadlribeiro/dataset_ignis_alert`);
  - as imagens não estão no git: são baixadas do Kaggle e reorganizadas pelos scripts.
- **Como reproduzir:**
  - rode as etapas 01 a 11 em ordem (veja o README);
  - `split_manifest.csv` congela a divisão, e `inventario.csv` congela os rótulos.
- **Como corrigir um rótulo:**
  - registre a decisão em `relatorios/10_nova_fonte/rotulos_humanos_A/decisoes_pendencias.csv`, ou na revisão da
    Etapa 10j;
  - rode `10i_aplicar_rotulos_humanos.py --mover` e depois a Etapa 11. A divisão treino/validação/teste não muda.
- **Pendências:**
  - revisar as 216 imagens que ainda têm só o rótulo da IA (10j);
  - conferir a licença da 2ª fonte;
  - conferir os pares de quase-duplicatas da Etapa 15a;
  - gerar a cópia pública v1.0 (Etapa 16) depois da marcação de rostos e placas.
