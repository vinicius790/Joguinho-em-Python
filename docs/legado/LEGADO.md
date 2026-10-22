# O jogo original

`legacy/ORIGINAL_APP.py` é o primeiro "Joguinho em Python": um script único de cerca de 430
linhas, mantido como registro histórico. Ele não é importado pelo pacote.

## Como ele funciona

- O tabuleiro de 60x30 é uma lista linear de 1.800 células. Cada posição é calculada à mão
  (`linha * 60 + coluna`), e as bordas são protegidas por longas cadeias de comparações de
  índices.
- O jogador (`O`) anda com `w`, `a`, `s`, `d` seguido de Enter; Enter vazio repete o último
  movimento.
- Há sempre 7 moedas (`$`) no campo; cada uma vale um ponto.
- Dos 20 aos 40 pontos ("FASE UM - minas surpresa") surge uma bomba (`Q`) por turno. Pisar
  em uma dispara uma animação de explosão que espalha fumaça (`#`) e encerra a partida.
  Ao chegar a 40 pontos as bombas restantes são removidas.
- A partir dos 50 pontos ("FASE 2 - pega pega") aparece um perseguidor (`X`) que anda em
  direção ao jogador; encostar nele encerra a partida.

## O que foi alterado no arquivo

Só a codificação. O arquivo tinha os acentos corrompidos (texto UTF-8 lido como Latin-1 e
gravado de novo), e um identificador com `ç` quebrava a sintaxe na linha 377. A conversão
inversa restaurou o texto original em 10 linhas; o código não foi reescrito. Um teste
confere que o arquivo compila.

Para rodá-lo: `python legacy/ORIGINAL_APP.py`. Ele ainda contém a linha de depuração
`pontos = 49`, que faz a partida começar perto da fase do perseguidor.

## O que a versão atual manteve

| No original | Na versão atual |
| --- | --- |
| grade 60x30 e os símbolos `O`, `$`, `Q`, `X`, `#` | iguais; `#` passou a ser parede |
| fases por pontuação: moedas, minas, pega-pega | modo `classic`, com as três fases em campo aberto |
| 7 moedas sempre no campo | `coin_respawn` nas fases do modo clássico |
| uma bomba nova por turno | uma mina a cada 2 turnos, sempre contornável |
| perseguidor que anda em linha reta | perseguidor com busca de caminho |
| Enter para repetir ou esperar | teclas sem Enter; Enter espera um turno |

O `README_ORIGINAL.md` que acompanhava o script foi removido por ser uma cópia do código.
