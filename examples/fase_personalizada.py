"""Exemplo: desenha uma fase à mão, joga algumas ações e mostra o resultado.

Uso: ``python examples/fase_personalizada.py`` (com o pacote instalado).
"""

from joguinho_apex.domain.enums import Action
from joguinho_apex.engine.engine import GameEngine

MAPA = [
    "##########",
    "#O$$ Q  E#",
    "#   ##   #",
    "#  X     #",
    "##########",
]

engine = GameEngine.from_rows(MAPA, target=2)
for action in (Action.RIGHT, Action.RIGHT, Action.DASH, Action.RIGHT, Action.RIGHT):
    engine.step(action)
    print(f"{action.name:<6} -> {engine.state.status.value}: {engine.state.message}")
print("\n".join(engine.state.render_lines()))
print("pontos:", engine.state.score)
