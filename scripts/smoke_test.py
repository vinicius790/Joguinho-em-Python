"""Teste de fumaça: o bot joga o modo Laboratório e o replay precisa conferir.

Uso: ``python scripts/smoke_test.py`` (com o pacote instalado ou ``PYTHONPATH=src``).
"""

import sys

from joguinho_apex.domain.enums import GameStatus
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.persistence.replay import Replay
from joguinho_apex.simulation.runner import make_policy


def main() -> int:
    """Joga uma partida curta e valida que o replay reproduz o estado final."""
    engine = GameEngine(42, "sandbox", "normal")
    walls = engine.state.board.wall_count()
    choose = make_policy("bot")
    for _ in range(1000):
        if engine.state.status is not GameStatus.RUNNING:
            break
        engine.step(choose(engine))
    state = engine.state
    print(f"status={state.status.value} pontos={state.score} turnos={state.tick} paredes={walls}")
    if state.board.wall_count() != walls:
        print("ERRO: as paredes mudaram durante a partida.")
        return 1
    if not Replay.from_engine(engine).verify():
        print("ERRO: o replay não reproduziu o estado final.")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
