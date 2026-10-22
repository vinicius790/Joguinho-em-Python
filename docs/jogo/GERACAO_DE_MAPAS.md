# Geração de mapas

Cada fase é gerada de forma determinística a partir de `seed`, modo, dificuldade e número
da fase. A mesma combinação sempre produz o mesmo mapa.

## Geradores (`levels/generators.py`)

| Gerador | Como funciona | Onde aparece |
| --- | --- | --- |
| `open` | só a borda é parede, como no jogo original | modo clássico |
| `scatter` | cada célula vira parede com uma probabilidade pequena (pilares soltos) | fases iniciais, laboratório |
| `caves` | ruído aleatório suavizado por autômato celular (4 iterações da regra 4-5) | "Corredor de Perigo", sobrevivência |
| `maze` | labirinto por busca em profundidade; 15% das paredes entre dois corredores são abertas para criar laços | "Labirinto Nebuloso", "Corredor I" |
| `rooms` | até 10 salas retangulares ligadas por corredores em L, com um laço extra | "Pega-Pega", fases de chefe |
| `hybrid` | salas e corredores escavados dentro de cavernas | "Fuga Final" |

Depois de qualquer gerador, `generate_walls` fecha a borda e mantém apenas a maior região
livre (as outras viram parede). Se sobrar menos de 15% da grade, o mapa é trocado por um
campo aberto.

## Montagem da fase (`levels/builder.py`)

Sobre o terreno, `build_layout` posiciona, nesta ordem:

1. o **jogador**, na célula livre mais próxima do centro;
2. a **saída** (se a fase exige), na célula mais distante do jogador pelo caminho;
3. os **inimigos**, a pelo menos 12 passos de caminho do jogador (ou metade da maior
   distância, em mapas pequenos); a quantidade é multiplicada pelo fator da dificuldade;
4. as **moedas** e os **power-ups**, em células livres sorteadas;
5. as **minas**, uma a uma.

Uma mina só é aceita se, com ela, todas as outras células livres continuarem alcançáveis
a partir do jogador sem pisar em minas. Assim nenhuma moeda, power-up ou saída fica presa
atrás de uma mina, e nunca é obrigatório levar dano para concluir a fase. Minas também não
nascem a 2 passos ou menos do jogador.

Minas que surgem durante a fase (modo clássico) seguem uma regra local equivalente: só
nascem em células cujas 8 vizinhas estão livres, então sempre dá para contorná-las.

## Fases feitas à mão

`GameEngine.from_rows` aceita um mapa em texto com os mesmos símbolos da tela:

```python
from joguinho_apex.engine.engine import GameEngine

engine = GameEngine.from_rows(
    [
        "##########",
        "#O$$ Q  E#",
        "#  X     #",
        "##########",
    ],
    target=2,
)
```

Os testes das regras usam esse recurso, e `examples/fase_personalizada.py` mostra um caso
completo. Partidas assim podem ser salvas e têm replay (o replay guarda o mapa inicial), mas
por padrão não valem para ranking nem conquistas (`ranked=False`).
