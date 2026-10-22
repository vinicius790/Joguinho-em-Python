"""Bot que joga sozinho: usado pela simulação e pelo benchmark."""

from __future__ import annotations

from ..domain.enums import Action, EnemyKind
from ..domain.geometry import Position
from ..domain.state import GameState
from ..engine.engine import GameEngine
from ..engine.rules import BOMB_RADIUS, PULSE_RADIUS
from .pathfinding import as_cells, nearest_path

DANGER_RADIUS = 2
FLEE_RADIUS = 3
BOMB_CROWD = 2

# O que o bot compra na loja, em ordem de prioridade (um de cada por visita).
SHOPPING_LIST: tuple[str, ...] = ("potion", "shield", "bomb", "heart", "boots")

_ACTION_BY_DELTA: dict[tuple[int, int], Action] = {
    (0, -1): Action.UP,
    (-1, 0): Action.LEFT,
    (0, 1): Action.DOWN,
    (1, 0): Action.RIGHT,
}


class BotPlayer:
    """Política heurística: busca o objetivo mais próximo evitando perigo.

    A cada turno o bot, nesta ordem: usa o Pulso se o chefe está ao alcance ou
    se há inimigo colado; segue o caminho mais curto até um objetivo sem passar
    por minas, fogo ou perto de inimigos; foge se está acuado; aceita um
    caminho arriscado se não há outro; e espera se nada disso é possível.
    Antes de tudo, bebe uma Poção com 1 de vida e solta uma Bomba quando o chefe
    ou dois inimigos estão a até 2 células. Na loja, :meth:`shop` compra pela
    ``SHOPPING_LIST``.

    O bot enxerga o estado inteiro (ignora a névoa) e não usa o dash.
    """

    @staticmethod
    def shop(engine: GameEngine) -> list[str]:
        """Compra o que puder da ``SHOPPING_LIST`` (só entre fases); devolve as compras."""
        return [item for item in SHOPPING_LIST if engine.buy(item)]

    def choose(self, engine: GameEngine) -> Action:
        """Escolhe a ação do turno para a partida ``engine``."""
        state = engine.state
        player = state.player
        board = state.board
        here = player.position

        active = self._active_enemies(state)
        if player.items.get("potion") and player.hp == 1 < player.max_hp:
            return Action.POTION
        if player.items.get("bomb"):
            near = [e for e in state.enemies if e.position.chebyshev(here) <= BOMB_RADIUS]
            if len(near) >= BOMB_CROWD or any(e.kind is EnemyKind.BOSS for e in near):
                return Action.BOMB
        if player.pulse_cooldown == 0:
            boss = state.boss
            if boss is not None and boss.position.manhattan(here) <= PULSE_RADIUS:
                return Action.PULSE
            if any(enemy.manhattan(here) <= DANGER_RADIUS for enemy in active):
                return Action.PULSE

        hazards = as_cells(board, state.mines)
        hazards |= as_cells(board, state.fires)
        hazards |= as_cells(board, (enemy.position for enemy in state.enemies))
        danger = {
            board.index(cell)
            for enemy in active
            for dx in range(-DANGER_RADIUS, DANGER_RADIUS + 1)
            for dy in range(abs(dx) - DANGER_RADIUS, DANGER_RADIUS - abs(dx) + 1)
            if board.inside(cell := enemy.moved(dx, dy))
        }
        goals = self._goals(state)

        step = self._step(state, nearest_path(board, here, goals, hazards | danger))
        if step is not None:
            return step
        if any(enemy.manhattan(here) <= FLEE_RADIUS for enemy in active):
            flee = self._flee(state, active, hazards)
            if flee is not None:
                return flee
        step = self._step(state, nearest_path(board, here, goals, hazards))
        return step if step is not None else Action.WAIT

    @staticmethod
    def _active_enemies(state: GameState) -> list[Position]:
        """Posições dos inimigos que representam ameaça neste turno."""
        if state.freeze or state.player.fury:
            return []
        return [
            enemy.position
            for enemy in state.enemies
            if enemy.stunned == 0 and (enemy.kind is not EnemyKind.AMBUSHER or enemy.enraged)
        ]

    @staticmethod
    def _goals(state: GameState) -> set[int]:
        """Objetivos do momento: saída aberta, chefe (com Pulso pronto) ou itens."""
        board = state.board
        if state.level.exit_required and state.exit_open and state.exit is not None:
            return {board.index(state.exit)}
        goals = as_cells(board, state.coins) | as_cells(board, state.powerups)
        boss = state.boss
        if boss is not None and state.player.pulse_cooldown == 0:
            goals |= set(board.neighbors[board.index(boss.position)])
        return goals

    @staticmethod
    def _step(state: GameState, path: list[Position]) -> Action | None:
        """Ação que leva ao segundo ponto do caminho (o primeiro é o jogador)."""
        if len(path) < 2:
            return None
        here = state.player.position
        return _ACTION_BY_DELTA[(path[1].x - here.x, path[1].y - here.y)]

    @staticmethod
    def _flee(state: GameState, active: list[Position], hazards: set[int]) -> Action | None:
        """Passo para o vizinho seguro mais distante dos inimigos, se melhora."""
        board = state.board
        here = state.player.position

        def safety(cell: Position) -> int:
            return min(cell.manhattan(enemy) for enemy in active)

        best: Position | None = None
        best_safety = safety(here)
        for index in board.neighbors[board.index(here)]:
            if index in hazards:
                continue
            cell = board.position(index)
            if safety(cell) > best_safety:
                best, best_safety = cell, safety(cell)
        if best is None:
            return None
        return _ACTION_BY_DELTA[(best.x - here.x, best.y - here.y)]
