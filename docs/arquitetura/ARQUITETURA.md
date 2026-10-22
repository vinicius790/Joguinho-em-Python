# Arquitetura

## Camadas

```text
cli.py, api/, web/        interfaces: terminal, REST e navegador
render/                   desenho no terminal e leitura de teclas
services/, persistence/   conquistas, fim de partida, sessões, SQLite, replays
simulation/               partidas automáticas e benchmark
engine/                   motor (regras de um turno) e tabelas de regras
levels/, ai/              geração de fases, busca de caminhos, inimigos e bot
domain/                   grade, entidades, enums, eventos e estado
```

As dependências apontam para baixo: `domain` não importa ninguém; `engine` usa `domain`,
`levels` e `ai`; as interfaces usam o motor e os serviços. O motor não sabe o que é
terminal, HTTP ou SQLite, e por isso a mesma partida roda igual na CLI, na API, no bot e
nos testes.

## Estado e terreno

- `Board` (`domain/board.py`) guarda só as paredes, que não mudam durante a fase. A lista
  de vizinhos livres de cada célula e as linhas de texto são calculadas uma vez.
- `GameState` (`domain/state.py`) guarda as entidades em coleções indexadas por posição:
  conjuntos de moedas e minas, dicionários de power-ups e fogo, lista de inimigos.
- A tela (`render_lines`) é montada só quando alguém pede, sobrepondo as entidades ao
  terreno.

Essa separação corrige o defeito da versão anterior, em que o tabuleiro era copiado e
redesenhado a cada passo (lento) sem redesenhar as paredes (que sumiam).

## O motor

`GameEngine.step(action)` executa um turno na ordem descrita em
[../jogo/GAMEPLAY.md](../jogo/GAMEPLAY.md). O motor mantém:

- `state`: o estado atual;
- `rng`: o gerador aleatório da partida, usado por vagantes e pelos itens que surgem;
- `history`: a lista de ações (e de avanços de fase), que é o replay;
- `events`: os últimos 2000 eventos (`level_start`, `collect`, `damage`, `explosion`...),
  cada um com um número de sequência, consumidos pela API.

Os status possíveis são `running`, `level_complete` (aguardando `next_level()`), `won` e
`lost`. Depois de `won` ou `lost`, `step` não faz mais nada.

## Determinismo

Mesma seed, modo, dificuldade e ações produzem o mesmo estado, em qualquer máquina:

- cada fase é gerada com um `Random` próprio, semeado com seed, modo, dificuldade e índice;
- os sorteios durante a partida usam apenas `engine.rng`, cujo estado entra no save;
- nenhuma regra depende da ordem de iteração de conjuntos.

`GameEngine.fingerprint()` devolve o SHA-256 do estado completo. Os testes usam essa
impressão para comparar partidas, saves e replays.

## Desempenho

O custo de um turno é dominado pela busca de caminhos dos inimigos. Para mantê-lo baixo:

- consultas por célula são O(1) (conjuntos e dicionários por posição);
- há um único mapa de distâncias por alvo e por turno, compartilhado pelos inimigos;
- a busca para ao alcançar o último inimigo interessado;
- vagantes e emboscadores longe do jogador nem consultam o mapa.

Os números medidos estão em
[../simulacao/SIMULACAO_E_BENCHMARK.md](../simulacao/SIMULACAO_E_BENCHMARK.md).

## Como estender

- **Novo inimigo**: adicione o tipo em `EnemyKind` e o símbolo em `ENEMY_SYMBOLS`
  (`domain/enums.py`) e trate-o em `choose_move` (`ai/strategies.py`).
- **Nova fase ou modo**: acrescente um `LevelSpec` em `levels/catalog.py`.
- **Novo gerador de mapa**: escreva a função em `levels/generators.py` e registre em
  `GENERATORS`; a borda e a conectividade são garantidas por `generate_walls`.
- **Novo power-up**: adicione em `PowerKind`, `POWER_SYMBOLS` e em `_take_powerup` no motor.
- **Nova interface**: use `GameEngine.snapshot()`, que devolve um dicionário pronto para
  JSON com as linhas da tela e os números do painel.
