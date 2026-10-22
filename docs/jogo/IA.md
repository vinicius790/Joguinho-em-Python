# Inteligência dos inimigos e do bot

## Busca de caminhos

`ai/pathfinding.py` usa busca em largura. Como todo passo custa o mesmo, ela já devolve o
caminho mínimo. A cada turno o motor calcula **um** mapa de distâncias a partir do jogador
e todos os inimigos o consultam: cada um anda para a célula vizinha com a menor distância.
A busca para assim que alcança o último inimigo que precisa dela.

Minas contam como parede para os inimigos comuns. Duas regras valem para todos: dois
inimigos nunca ocupam a mesma célula, e nenhum entra na célula do jogador (o ataque
acontece a partir da célula vizinha).

## Tipos de inimigo (`ai/strategies.py`)

| Tipo | Símbolo | Comportamento |
| --- | --- | --- |
| Perseguidor | `X` | segue o caminho mínimo até o jogador |
| Interceptador | `Y` | mira a célula 4 passos à frente do jogador, na direção em que ele olha, para cortar a rota; a 3 passos ou menos, persegue direto |
| Vagante | `W` | anda ao acaso (parado em 20% dos turnos); persegue quando o jogador chega a 6 passos de caminho |
| Emboscador | `A` / `z` | dorme (`z`) até o jogador chegar a 5 passos de caminho; então acorda enfurecido e persegue |

Um inimigo **enfurecido** anda todo turno, qualquer que seja a dificuldade. Isso acontece
com o emboscador ao acordar e com todos os inimigos comuns quando a saída abre.

Com a **Fúria** ativa no jogador, os inimigos comuns fogem para a célula vizinha mais
distante. Com o **Gelo**, ninguém se move. Um inimigo atordoado pelo Pulso perde os turnos
em que estiver atordoado.

A velocidade vem da dificuldade como fração de turnos (por exemplo, 2 passos a cada 3
turnos no `normal`). Cada inimigo acumula essa fração em `energy` e anda quando ela completa
um passo inteiro.

## O Guardião

O chefe persegue o jogador ignorando minas: ao pisar em uma, ela explode e ele perde 1 de
vida. Ele também perde vida com o Pulso e com o toque de um jogador em Fúria. A cada tantos
turnos solta uma aura de fogo ao redor de si (nunca na célula do jogador).

| Vida restante | Fase | Velocidade | Aura | Rastro de fogo |
| --- | --- | --- | --- | --- |
| acima de 2/3 | vigilante | 1 a cada 2 turnos | 4 células em cruz, a cada 8 turnos | não |
| acima de 1/3 | enfurecido | 2 a cada 3 turnos | 8 células ao redor, a cada 6 turnos | sim |
| até 1/3 | apocalipse | todo turno | 12 células, a cada 5 turnos | sim |

A vida do Guardião é a da fase multiplicada pelo fator de inimigos da dificuldade.

O Guardião é um de três perfis de chefe. A Sentinela (ato I) chama perseguidores e o
Colosso (ato III) larga minas por onde passa; as tabelas dos três estão em
[CAMPANHA_E_LOJA.md](CAMPANHA_E_LOJA.md). O bot trata todos do mesmo jeito.

## O bot (`ai/bot.py`)

O bot joga sozinho e alimenta `joguinho simulate` e `joguinho benchmark`. Entre as fases,
`BotPlayer.shop` compra pela lista `SHOPPING_LIST` (Poção, Escudo, Bomba, Coração, Botas; um
de cada por visita, o que o ouro permitir). A cada turno ele:

1. bebe uma Poção se está com 1 de vida (e a vida máxima é maior);
2. solta uma Bomba se o chefe, ou pelo menos dois inimigos, estão a até 2 células;
3. usa o Pulso se o Guardião está ao alcance ou se há inimigo a 2 passos;
4. segue o caminho mais curto até o objetivo (moeda, power-up, saída aberta ou o Guardião
   quando o Pulso está pronto), sem passar por minas, fogo ou a menos de 2 passos de inimigos;
5. se não há caminho seguro e há inimigo a 3 passos, foge para o vizinho mais seguro;
6. se nada disso serve, aceita um caminho que passa perto de inimigos;
7. em último caso, espera.

É uma heurística, não um jogador ótimo: não usa o dash, não planeja além do próximo
objetivo e enxerga através da névoa. As taxas de vitória medidas estão em
[../simulacao/SIMULACAO_E_BENCHMARK.md](../simulacao/SIMULACAO_E_BENCHMARK.md).
