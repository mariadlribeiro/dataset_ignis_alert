# Guia de rotulagem do Ignis Alert

Critérios que valem para toda revisão humana do projeto: as Etapas 5, 10e, 10g, 10h, 10j, 13a, 14a e 14c. As
páginas de revisão mostram uma versão curta deles ao lado de cada campo. Este guia é a versão completa: quando a
página e o guia parecerem discordar, vale o guia. Quando o guia mudar, registre a data e o motivo no fim.

## Regra de ouro

**Rotule o que está na imagem, não o que provavelmente aconteceu.** Um céu laranja pode vir de um incêndio
atrás do morro, mas se não há chama na foto, o fogo é "não". A legenda, o nome do arquivo, a pasta de origem e a
sugestão da IA não entram na decisão. Por isso a revisão é cega.

## 1. Fogo

| Rótulo | Quando |
|---|---|
| **sim** | Há **chama visível**, mesmo pequena, mesmo parcialmente coberta por fumaça. |
| **não** | Nenhuma chama. Brilho, céu laranja, brasa sem chama, só fumaça, reflexo, luz artificial ou cena apagada. |
| **incerto** | Você olhou com atenção, ampliou a imagem e **não dá para afirmar** se há chama. |

**Chama controlada** (lareira, vela, fogão, churrasco, fogueira cercada) é **fogo = sim**, porque o rótulo mede
"há chama". Isso não é incêndio, e a diferença fica no campo **cena** da Etapa 14c. A rede acha chama; quem decide
se é um incêndio é a pessoa que confirma o alerta no aplicativo.

**Como reconhecer uma chama:** é uma língua irregular, mais clara no centro (branco ou amarelo) e laranja ou
vermelha nas bordas. Está presa a um combustível (tronco, mato, telhado). Costuma ter fumaça acima e ilumina o
que está perto.

### Fogo × pôr do sol, céu laranja e luzes

| Indício | Fogo | Pôr do sol / luz |
|---|---|---|
| De onde vem a luz | De um ponto no chão ou na vegetação | Do céu, no horizonte, ou de uma lâmpada |
| Forma | Línguas irregulares, recortadas | Disco do sol, gradiente suave, ponto redondo |
| Sombras | Curtas, tremidas, em várias direções | Longas e paralelas (sol) ou cônicas (farol) |
| Fumaça | Quase sempre presente | Ausente; só nuvens |
| Cor do céu | Laranja de baixo para cima, com fumaça | Gradiente laranja, rosa, azul, uniforme |

- **Silhueta de árvore contra laranja** (como o `fire.135`): é fogo **sim** se dá para ver chama por trás dos
  galhos. Se for só céu, é **não**.
- **Faróis, lanternas e postes:** fogo **não**, mesmo com halo laranja.
- **Brasa vermelha sem chama** (rescaldo): fogo **não**. Anote "brasa" na observação.

## 2. Fumaça

| Rótulo | Quando |
|---|---|
| **sim** | Fumaça de queima visível, com ou sem chama na foto. |
| **não** | Ar limpo, ou só neblina, nuvem, vapor ou poeira. |
| **incerto** | Pode ser fumaça, neblina ou nuvem, e os indícios abaixo não resolvem. |

### Fumaça × neblina × nuvem

| Indício | Fumaça | Neblina / névoa | Nuvem |
|---|---|---|---|
| Origem | Sai de **um ponto** (coluna ou pluma) | Espalhada, preenche vales e o chão | No céu, sem ligação com o chão |
| Forma | Volutas, se alarga ao subir, inclina com o vento | Camada uniforme, horizontal | Base plana, topo em couve-flor |
| Cor | Cinza, marrom, amarelada ou preta; às vezes azulada | Branca ou cinza-clara, uniforme | Branca ou cinza, com sombra embaixo |
| Luz | Deixa o sol laranja ou avermelhado | Deixa a luz branca e difusa | Sombras nítidas no chão |
| Contexto | Pode haver chama, brasa, área queimada | Manhã cedo, vale úmido, perto de água | Céu aberto, horizonte |

- A neblina entre pinheiros num vale (como o `non_fire.51`) é fumaça **não**. Era o caso típico de alarme falso.
- Uma coluna escura saindo de trás de um morro é fumaça **sim**, mesmo sem chama visível. O fogo continua **não**.
- Fumaça sozinha nunca vira fogo **sim**: no projeto, "fogo" é chama.

## 3. Cena (só nos negativos difíceis, Etapas 14a e 14c)

Marque **o que mais pode ser confundido com fogo ou fumaça** na foto: pôr ou nascer do sol, neblina, nuvens,
folhagem de outono, luzes à noite, reflexo ou brilho de sol, chama controlada (lareira, vela, fogão, churrasco),
faróis ou lanternas. Se nada se parece com fogo, marque **nenhuma** ou **outra cena**.

## 4. Ambiente

**Onde a cena acontece, não o que está queimando.** Um carro pegando fogo numa rua é **cidade**.

| Rótulo | Quando |
|---|---|
| floresta | Mata, bosque, vegetação densa, ou paisagem florestal vista de longe. |
| cidade | Rua, bairro, espaço público urbano. |
| casa | Residência por fora ou por dentro, ou quintal. |
| prédios | Prédio comercial ou industrial, fábrica, arranha-céu. |
| outros | Campo aberto, montanha, lago, veículo, objeto ou pessoa em destaque. |
| incerto | Não dá para dizer onde é: close no fogo, imagem escura, recorte. |

- **Campo com algumas árvores:** é floresta se as árvores dominam a cena; senão, é outros.
- **Casa no meio do mato:** é casa se a casa é o assunto da foto; se ela aparece pequena na paisagem, é floresta.
- Foi aqui que a IA mais errou: 81 de 184 imagens tinham ambiente errado, quase sempre "outros" no lugar de floresta.

## 5. Quando usar "incerto"

- **Use** quando, depois de ampliar a imagem e conferir os indícios das tabelas, as duas respostas continuam
  defensáveis. Exemplo: um ponto laranja minúsculo e borrado, que pode ser chama ou farol.
- **Não use** para ganhar tempo, nem quando a dúvida é sobre o que aconteceu fora da foto.
- **O que acontece com o incerto:**
  - não entra em nenhuma métrica;
  - vai para `pendencias.csv` e passa por uma decisão humana (desempate) antes de entrar no dataset;
  - fica registrado com o motivo em `decisoes_pendencias.csv`. Exemplo: `FIRE (357)` foi para "outros", sem fogo.
- **Escreva na observação** o porquê, em poucas palavras: "chama ou reflexo?", "fumaça ou neblina?".

## 6. Tipo de imagem e o que fica de fora

| Tipo | Destino |
|---|---|
| Fotografia | Entra. |
| Sintética (jogo, CGI, ilustração, montagem) | Fica de fora do dataset, com motivo. |
| Visualização de sensor (LiDAR, mapa de calor) | Fica de fora do dataset, com motivo. |

## 7. Como revisar

1. Faça a revisão **cega**: a página não mostra a sugestão da IA nem a pasta. Não procure o arquivo fora dela.
2. Olhe a foto inteira e depois amplie as regiões laranja, brancas e cinzas.
3. Decida o **fogo** antes da fumaça e do ambiente.
4. Na dúvida entre "não" e "incerto", releia a seção 5.
5. Exporte o CSV ao terminar cada sessão. A página guarda o progresso no navegador, mas o CSV é o registro oficial.

## Histórico

- **26/11/2026:** primeira versão escrita. Junta os critérios das páginas de revisão e acrescenta os casos de pôr
  do sol, neblina, chama controlada e faróis, a pedido da avaliação de 24/11.
