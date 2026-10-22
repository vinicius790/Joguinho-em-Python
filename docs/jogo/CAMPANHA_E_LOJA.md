# Campanha, chefes, ouro e loja

## A campanha em três atos

A campanha tem 9 fases. Antes de cada uma o terminal mostra um capítulo da história
(`levels/story.py`); ao vencer a última, a tela final conta o desfecho.

| Ato | Fase | Título | O que muda |
| --- | --- | --- | --- |
| I - A Superfície | 1 | Caça às Moedas | só moedas e power-ups |
| | 2 | Minas Surpresa | minas |
| | 3 | Pega-Pega | **chefe: a Sentinela** (e a meta de 12 moedas) |
| II - As Ruínas | 4 | Corredor de Perigo | cavernas, saída trancada |
| | 5 | Labirinto Nebuloso | névoa e relógio |
| | 6 | Guardião das Ruínas | **chefe: o Guardião** |
| III - O Nexus | 7 | Fuga Final | relógio e os quatro inimigos |
| | 8 | Coração do Nexus | cavernas com névoa, 16 de 22 moedas e saída |
| | 9 | O Colosso | **chefe final: o Colosso** |

A história é só apresentação: não entra no histórico de ações, então não afeta replays.
A tela de história consome uma tecla (qualquer uma continua; `Q` sai).

## Chefes

Todo chefe (`B`) persegue o jogador ignorando minas, perde vida com o Pulso, com a Bomba,
com explosões de minas e com o toque de um jogador em Fúria, e muda de fase em 2/3 e 1/3
da vida. Os perfis ficam em `engine/rules.py` (`BOSSES`); a fase escolhe o seu com
`LevelSpec.boss`.

| Chefe | Fases | Velocidade | Aura de fogo | Padrão próprio |
| --- | --- | --- | --- | --- |
| Sentinela (`sentinel`) | patrulha, alarme, caçada | 2/3, 2/3, todo turno | cruz a cada 10 e 8 turnos; anel a cada 6 | não deixa rastro de fogo; **chama um perseguidor** a cada 25 turnos (alarme) e 15 (caçada) |
| Guardião (`guardian`) | vigilante, enfurecido, apocalipse | 1/2, 2/3, todo turno | cruz/8, anel/6, 12 células/5 | **rastro de fogo** a partir da segunda fase |
| Colosso (`colossus`) | desperto, sísmico, colapso | 1/3, 1/2, 2/3 | anel/6, 12 células/5, 12 células/4 | **larga minas** por onde passa; rastro de fogo a partir da segunda fase; chama perseguidores a cada 30 turnos no colapso |

Detalhes das habilidades:

- Reforços nascem em uma célula livre a pelo menos 3 passos do jogador e respeitam o
  limite de 12 inimigos por fase. Um chefe atordoado ou congelado não chama ninguém.
- A mina do Colosso só é colocada se as 8 células ao redor estiverem livres de paredes e
  de outras minas (sempre dá para contornar) e nunca ao lado do jogador, sobre moedas,
  power-ups ou a saída.
- Em uma fase de chefe com `meta`, é preciso derrotar o chefe **e** juntar as moedas.

## Ouro e loja

Cada moeda coletada rende 1 de **ouro** (além dos pontos). O ouro não muda a pontuação e
acompanha o jogador de uma fase para a outra.

Ao concluir uma fase (status `level_complete`) a loja abre. No terminal, as teclas `1` a
`5` compram e qualquer outra tecla segue para a próxima fase.

| Tecla | Item | Preço | Efeito |
| --- | --- | --- | --- |
| `1` | Coração | 12 | +1 de vida máxima (até 8) e cura 1 ponto |
| `2` | Escudo | 8 | +1 de escudo (máximo 3) |
| `3` | Botas | 15 | o dash recarrega em 4 turnos em vez de 6; só pode ser comprado uma vez |
| `4` | Poção | 6 | consumível: `H` cura 1 de vida (não é gasta com a vida cheia) |
| `5` | Bomba | 10 | consumível: `B` tira 1 de vida de todo inimigo a até 2 células (diagonais contam); não fere o jogador |

Usar Poção ou Bomba gasta o turno, como qualquer ação. Compras recusadas (ouro
insuficiente, item no máximo, loja fechada) não custam nada e explicam o motivo na
mensagem. Não há loja depois da última fase nem em modos de fase única.

## Persistência e determinismo

- Ouro, Botas e consumíveis ficam em `Player` (`gold`, `dash_bonus`, `items`) e por isso
  entram no save e na impressão digital da partida. Saves antigos, sem esses campos,
  continuam carregando (valem zero).
- Cada compra entra no histórico como um dígito (`1` a `5`) e cada uso de item como a
  tecla da ação (`h`, `b`). O replay refaz compras e usos na mesma ordem:
  `"actions": "ddss4>hdd"` é "andou, comprou uma Poção, avançou de fase, bebeu a Poção".
- Contadores novos em `stats`: `purchases` e `items_used`. Eventos novos: `purchase` e
  `item_used`.
- Na API: `POST /v1/games/{id}/shop/{item}` com `heart`, `shield`, `boots`, `potion` ou
  `bomb`; as ações `b` e `h` valem em `/actions`. O console web usa as mesmas teclas.
