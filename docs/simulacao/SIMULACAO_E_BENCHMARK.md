# Simulação e benchmark

## Partidas automáticas

```bash
joguinho simulate --episodes 50 --mode chase --difficulty normal --policy bot
```

Opções: `--episodes`, `--seed` (seed da primeira partida; as seguintes usam seeds
consecutivas), `--mode`, `--difficulty`, `--policy` (`bot` ou `random`), `--max-steps`
(turnos por partida, padrão 2000) e `--details` (inclui cada partida no JSON).

A saída é um JSON com o resumo do lote: vitórias, derrotas, partidas interrompidas pelo
limite de turnos (`unfinished`), taxa de vitória, média, mediana, percentil 90, mínimo e
máximo da pontuação e médias de fases, turnos e dano. Como biblioteca:

```python
from joguinho_apex.simulation.runner import run_episodes, summarize

print(summarize(run_episodes(episodes=10, seed=2026, mode="chase")))
```

As simulações são reproduzíveis: mesma seed, mesmo resultado.

### Resultado do bot (20 partidas por modo, dificuldade normal, até 4000 turnos)

| Modo | Vitórias | Derrotas | Interrompidas | Pontuação média | Fases concluídas (média) |
| --- | --- | --- | --- | --- | --- |
| campaign | 1 | 18 | 1 | 2521,1 | 4 |
| classic | 18 | 0 | 2 | 1781 | 2,9 |
| chase | 8 | 11 | 1 | 1070,5 | 2,35 |
| gauntlet | 10 | 10 | 0 | 1174,5 | 2,05 |
| boss | 7 | 13 | 0 | 1119 | 1,3 |
| sandbox | 20 | 0 | 0 | 354,2 | 1 |

Medido na 21.1.0 (campanha de nove fases, com o bot comprando na loja e usando Poção e
Bomba). Comando usado: `joguinho simulate --episodes 20 --mode <modo> --max-steps 4000`. O bot é
uma heurística simples (veja [../jogo/IA.md](../jogo/IA.md)); os números servem para
comparar mudanças de regras, não como medida da dificuldade para uma pessoa.

## Benchmark

```bash
joguinho benchmark --steps 10000                  # todos os modos, com o bot
joguinho benchmark --steps 10000 --mode campaign --policy random
```

São duas medidas, em turnos por segundo:

- **motor**: só o tempo dentro de `GameEngine.step`;
- **total**: inclui a política que escolhe as ações e a geração das fases.

### Números medidos

Medidos em 2026-10-02, Windows 11, CPython 3.13.5, 5000 turnos por modo
(`joguinho benchmark --steps 5000`). Os valores mudam de máquina para máquina; use-os
como ordem de grandeza.

| Modo | Motor, com bot | Total, com bot | Motor, ações aleatórias | Total, ações aleatórias |
| --- | --- | --- | --- | --- |
| campaign | 5964 | 1948 | 74145 | 63452 |
| classic | 4519 | 1459 | 65035 | 56159 |
| survival | 1766 | 851 | 2484 | 972 |
| chase | 1631 | 854 | 3322 | 1653 |
| gauntlet | 2632 | 948 | 34209 | 11388 |
| boss | 2521 | 835 | 7476 | 2505 |
| endless | 8751 | 2214 | 33177 | 19863 |
| sandbox | 6761 | 1454 | 29931 | 21187 |

Com ações aleatórias a partida fica nas primeiras fases, que têm poucos inimigos, e por
isso o motor passa de dezenas de milhares de turnos por segundo. Os modos com perseguidores
ativos o tempo todo (`chase`, `survival`) são os mais lentos, porque cada turno faz uma
busca em largura no mapa.

Para comparação, a versão 20.0.0 fazia cerca de 51 turnos por segundo no mesmo computador
(`benchmark(1000)` no modo `sandbox`), porque copiava e redesenhava o tabuleiro inteiro a
cada passo.

O teste `test_benchmark_reports_thousands_of_steps_per_second_regression` falha se o motor
cair abaixo de 1000 turnos por segundo na campanha com ações aleatórias.
