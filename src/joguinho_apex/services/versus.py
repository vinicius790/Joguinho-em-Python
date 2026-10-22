"""Multiplayer local em turnos: dois jogadores alternam ações no mesmo teclado.

Cada jogador tem a própria partida, criada com a mesma seed, modo e
dificuldade (mapas idênticos). As partidas não interferem uma na outra, então
cada uma continua determinística e tem replay próprio.
"""

from __future__ import annotations

from collections.abc import Callable

from ..domain.enums import Action, GameStatus
from ..engine.engine import GameEngine

_OPEN = (GameStatus.RUNNING, GameStatus.LEVEL_COMPLETE)


class VersusMatch:
    """Disputa entre dois jogadores em turnos alternados.

    Regras: cada ação vale um turno e passa a vez; quem termina (vitória ou
    derrota) sai da roda e o outro joga sozinho até terminar. Ganha quem
    concluiu o modo; se os dois concluíram (ou os dois caíram), ganha a maior
    pontuação; pontuações iguais dão empate.
    """

    def __init__(self, names: tuple[str, str], new_engine: Callable[[], GameEngine]) -> None:
        """Cria as duas partidas com ``new_engine`` (uma chamada por jogador)."""
        self.names = names
        self.engines = (new_engine(), new_engine())
        self.turn = 0

    @property
    def finished(self) -> bool:
        """Indica se os dois jogadores já terminaram."""
        return all(engine.state.status not in _OPEN for engine in self.engines)

    @property
    def current(self) -> GameEngine:
        """Partida do jogador da vez."""
        return self.engines[self.turn]

    def step(self, action: Action) -> None:
        """Aplica a ação do jogador da vez e passa a vez (se o outro ainda joga).

        Uma fase concluída avança sozinha no turno seguinte do mesmo jogador;
        use :meth:`buy` antes disso para comprar na loja.
        """
        if self.finished:
            return
        engine = self.current
        if not engine.next_level():
            engine.step(action)
        other = 1 - self.turn
        if self.engines[other].state.status in _OPEN:
            self.turn = other

    def buy(self, item_id: str) -> bool:
        """Compra na loja do jogador da vez, sem gastar o turno."""
        return self.current.buy(item_id)

    def winner(self) -> int | None:
        """Índice (0 ou 1) do vencedor; ``None`` em empate ou disputa em andamento."""
        if not self.finished:
            return None
        ranks = [
            (engine.state.status is GameStatus.WON, engine.state.score) for engine in self.engines
        ]
        if ranks[0] == ranks[1]:
            return None
        return 0 if ranks[0] > ranks[1] else 1
