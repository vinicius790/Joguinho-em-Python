# Regras do jogo

O jogo é por turnos: cada ação do jogador vale um turno, e só então o resto do mundo se
move. As constantes citadas aqui ficam em `src/joguinho_apex/engine/rules.py`.

## Símbolos

| Símbolo | O que é |
| --- | --- |
| `O` | você |
| `#` | parede |
| `$` | moeda |
| `Q` | mina |
| `*` | fogo |
| `e` / `E` | saída trancada / aberta |
| `X` | perseguidor |
| `Y` | interceptador |
| `W` | vagante |
| `A` / `z` | emboscador acordado / dormindo |
| `B` | chefe (Sentinela, Guardião ou Colosso) |
| `+` `S` `F` `M` `!` | power-ups: vida, escudo, gelo, ímã, fúria |
| `~` | névoa (célula fora do campo de visão) |

## Ordem de um turno

1. Recargas e efeitos temporários perdem um turno.
2. O jogador age: mover, dash, pulso, bomba, poção ou esperar. Bater em parede gasta o turno.
3. A célula do jogador é resolvida: moeda, power-up, ímã, mina e fogo.
4. O fogo perde um turno de duração (depois de queimar, nunca antes).
5. Os inimigos se movem e atacam; o chefe solta sua aura de fogo (e, conforme o perfil,
   chama reforços ou larga minas).
6. Nascem os itens previstos pela fase (moedas, minas, inimigos, power-ups).
7. O jogo decide: derrota, fase concluída ou vitória.

## Vida, dano e escudo

- Cada golpe tira o dano da dificuldade (1, 2 ou 3). Um escudo absorve um golpe inteiro.
- Depois de qualquer golpe (mesmo absorvido) o jogador fica um turno completo sem poder
  ser atingido de novo.
- Inimigos atacam a partir da célula vizinha; nunca ocupam a célula do jogador. Andar
  contra um inimigo também fere.
- Ao passar de fase o jogador recupera 1 de vida e mantém o escudo.

## Moedas, combo e pontuação

- A fase é concluída ao coletar a **meta** de moedas (e alcançar a saída, se houver).
- Coletar outra moeda em até 11 turnos aumenta o combo. A moeda vale `10 x combo`
  (até x10). A cada 5 de combo o jogador ganha 1 de escudo (máximo 3). Levar dano zera o combo.
- Power-up: 5 pontos. Inimigo derrotado: 50. Chefe: 500.
- Fase concluída: `100 + turnos restantes no relógio + 20 x vida`.
- Cada moeda também rende 1 de **ouro**, gasto na loja entre as fases (não muda a
  pontuação). Ver [CAMPANHA_E_LOJA.md](CAMPANHA_E_LOJA.md).
- Toda pontuação é multiplicada pelo fator da dificuldade.

## Minas, fogo e saída

- Pisar em uma mina a detona. A explosão atinge as 8 células ao redor: fere o jogador,
  derrota inimigos comuns, tira 1 de vida do chefe e detona minas vizinhas em cadeia.
- Inimigos comuns nunca pisam em minas; o chefe pisa e as detona.
- Fogo queima quem entra ou fica na célula e dura 3 turnos.
- A saída (`e`) abre (`E`) quando a meta de moedas é atingida. Nesse momento todos os
  inimigos comuns ficam enfurecidos e passam a andar todo turno.
- Fases com limite de tempo terminam em derrota quando o relógio zera.

## Habilidades

| Habilidade | Tecla | Efeito | Recarga |
| --- | --- | --- | --- |
| Dash | `E` | avança até 3 células na direção atual; salta minas e fogo no caminho, recolhe itens e para antes de paredes e inimigos | 6 turnos |
| Pulso | `F` | atordoa por 4 turnos os inimigos a até 3 passos; tira 1 de vida do chefe e o atordoa por 2 | 20 turnos |

A célula em que o dash termina é resolvida normalmente: cair em cima de uma mina a detona.
Com as Botas da loja, o dash recarrega em 4 turnos.

Itens consumíveis comprados na loja também são ações de um turno:

| Item | Tecla | Efeito |
| --- | --- | --- |
| Poção | `H` | cura 1 de vida; não é gasta com a vida cheia |
| Bomba | `B` | tira 1 de vida de cada inimigo a até 2 células; não fere o jogador |

## Power-ups

| Símbolo | Nome | Efeito |
| --- | --- | --- |
| `+` | Vida | recupera 1 de vida |
| `S` | Escudo | +2 de escudo (máximo 3) |
| `F` | Gelo | inimigos não se movem por 8 turnos |
| `M` | Ímã | por 25 turnos, coleta moedas a até 3 passos |
| `!` | Fúria | por 12 turnos, os inimigos fogem e tocar neles os derrota (o chefe perde 1 de vida) |

## Modos

| Modo | Fases | Resumo |
| --- | --- | --- |
| `campaign` | 9 | três atos com história e um chefe por ato (fases 3, 6 e 9); fase 5 com névoa e relógio, fase 7 com relógio e os quatro inimigos; ver [CAMPANHA_E_LOJA.md](CAMPANHA_E_LOJA.md) |
| `classic` | 3 | campo aberto como no original: moedas que reaparecem, depois minas que surgem a cada 2 turnos, depois um perseguidor |
| `survival` | 1 | sem meta: inimigos e power-ups novos surgem com o tempo; termina na derrota |
| `chase` | 3 | perseguidores e interceptadores em número crescente; a última fase tem um emboscador e saída |
| `gauntlet` | 3 | minas, inimigos, saída e relógio |
| `boss` | 2 | duas lutas contra o Guardião, a segunda com 8 de vida e capangas |
| `endless` | infinito | fases geradas com mais moedas, minas e inimigos; um Guardião a cada 5 fases |
| `sandbox` | 1 | fase tranquila para experimentar |

`joguinho play --daily` usa uma seed derivada da data, igual para todos no mesmo dia;
`joguinho daily` faz o mesmo e mantém um ranking do dia. `joguinho versus` põe dois
jogadores em turnos alternados. Ver [VERSUS_E_DAILY.md](VERSUS_E_DAILY.md). Fases feitas
à mão: [EDITOR_DE_FASES.md](EDITOR_DE_FASES.md).

## Dificuldades

| Dificuldade | Vida | Inimigos andam | Inimigos | Minas | Dano | Pontos | Tempo | Power-ups |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `story` | 5 | 1 a cada 2 turnos | x0,5 | x0,5 | 1 | x0,5 | x1,5 | x1,5 |
| `normal` | 3 | 2 a cada 3 turnos | x1 | x1 | 1 | x1 | x1 | x1 |
| `hard` | 3 | 3 a cada 4 turnos | x1,25 | x1,3 | 1 | x1,5 | x0,9 | x0,8 |
| `nightmare` | 3 | todo turno | x1,5 | x1,7 | 2 | x2 | x0,8 | x0,6 |
| `apocalypse` | 3 | todo turno | x2 | x2,2 | 3 | x3 | x0,7 | x0,5 |

## Conquistas

| Conquista | Como desbloquear |
| --- | --- |
| Primeira Moeda | coletar uma moeda |
| Combo x5 / Combo x10 | chegar a combo 5 / 10 |
| Magnata | 100 moedas em uma única partida |
| Sobrevivente | vencer sem perder vida |
| Velocista | concluir uma fase cronometrada em até metade do tempo |
| Caçador | derrotar 5 inimigos em uma partida |
| Demolidor | derrotar um inimigo com a explosão de uma mina |
| Matador de Guardiões | derrotar um chefe |
| Campeão | concluir a campanha |
| Pesadelo | vencer em `nightmare` ou `apocalypse` |
| Maratonista | concluir 10 fases em uma partida |
| Veterano | terminar 10 partidas com o mesmo perfil |

As estatísticas valem para a partida inteira (não são zeradas entre fases). As conquistas
são gravadas no perfil quando a partida termina, e o título do jogador (de Novato a Nexus)
depende da pontuação acumulada. Fases personalizadas (`play --level`) contam como partida,
mas não dão pontos ao perfil, não entram no ranking nem desbloqueiam conquistas.
