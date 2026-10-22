"""Estratégias de movimento dos inimigos.

Cada tipo decide para qual célula vizinha quer ir no turno:

- ``chaser`` (X): segue o caminho mínimo até o jogador;
- ``interceptor`` (Y): mira a célula à frente do jogador para cortar a rota;
- ``wanderer`` (W): vaga ao acaso e só persegue quando o jogador chega perto;
- ``ambusher`` (A): dorme até o jogador se aproximar e então persegue enfurecido;
- ``boss`` (B): persegue ignorando minas (e as detona ao pisar).

Com Fúria ativa no jogador, todos os inimigos comuns fogem.
"""

from __future__ import annotations

from random import Random

from ..domain.entities import Enemy
from ..domain.enums import EnemyKind
from ..domain.geometry import Position
from ..domain.state import GameState
from .pathfinding import as_cells, distance_map

WANDER_SIGHT = 6
WANDER_REST_CHANCE = 0.2
AMBUSH_RANGE = 5
INTERCEPT_LEAD = 4
INTERCEPT_CLOSE = 3


class AIContext:
    """Dados compartilhados pelos inimigos em um turno.

    Os mapas de distância são calculados sob demanda e reaproveitados por
    todos os inimigos que miram o mesmo alvo.
    """

    __slots__ = ("_maps", "_starts", "board", "mine_cells", "occupied", "rng", "state")

    def __init__(self, state: GameState, rng: Random) -> None:
        """Captura minas e posições ocupadas no início da fase dos inimigos."""
        self.state = state
        self.board = state.board
        self.rng = rng
        self.mine_cells = frozenset(as_cells(state.board, state.mines))
        self.occupied = as_cells(state.board, (enemy.position for enemy in state.enemies))
        self._starts = frozenset(
            state.board.index(enemy.position)
            for enemy in state.enemies
            if not _idle(enemy, state.player.position)
        )
        self._maps: dict[tuple[Position, bool, bool], list[int]] = {}

    def distances(
        self, target: Position, avoid_mines: bool = True, full: bool = False
    ) -> list[int]:
        """Mapa de distâncias até ``target``, tratando minas como paredes ou não.

        Por padrão a busca para ao alcançar todos os inimigos; ``full`` pede o
        mapa inteiro (necessário para fugir, que olha células mais distantes).
        """
        key = (target, avoid_mines, full)
        found = self._maps.get(key)
        if found is None:
            blocked = self.mine_cells if avoid_mines else ()
            until = () if full else self._starts
            found = distance_map(self.board, target, blocked, until)
            self._maps[key] = found
        return found


def choose_move(ctx: AIContext, enemy: Enemy) -> Position:
    """Devolve a célula para onde ``enemy`` quer ir (pode ser a do jogador)."""
    state = ctx.state
    player = state.player
    if enemy.kind is EnemyKind.BOSS:
        return _toward(ctx, enemy, ctx.distances(player.position, avoid_mines=False), False)

    if player.fury > 0:
        return _away(ctx, enemy, ctx.distances(player.position, full=True))
    if _idle(enemy, player.position):
        return _rest(ctx, enemy)

    to_player = ctx.distances(player.position)
    here = to_player[ctx.board.index(enemy.position)]
    if enemy.kind is EnemyKind.AMBUSHER and not enemy.enraged:
        if not 0 <= here <= AMBUSH_RANGE:
            return enemy.position
        enemy.enraged = True
    if enemy.kind is EnemyKind.WANDERER and not enemy.enraged and not 0 <= here <= WANDER_SIGHT:
        return _wander(ctx, enemy)
    if (
        enemy.kind is EnemyKind.INTERCEPTOR
        and enemy.position.manhattan(player.position) > INTERCEPT_CLOSE
    ):
        return _toward(ctx, enemy, ctx.distances(lead_target(state)), True)
    return _toward(ctx, enemy, to_player, True)


def _idle(enemy: Enemy, player: Position) -> bool:
    """Vagante ou emboscador longe demais para notar o jogador.

    A distância em linha reta nunca é maior que a do caminho, então quem está
    fora do alcance por ela dispensa a busca de caminho neste turno.
    """
    if enemy.enraged:
        return False
    if enemy.kind is EnemyKind.WANDERER:
        return enemy.position.manhattan(player) > WANDER_SIGHT
    if enemy.kind is EnemyKind.AMBUSHER:
        return enemy.position.manhattan(player) > AMBUSH_RANGE
    return False


def _rest(ctx: AIContext, enemy: Enemy) -> Position:
    """Comportamento de quem não notou o jogador: vagar ou continuar dormindo."""
    if enemy.kind is EnemyKind.WANDERER:
        return _wander(ctx, enemy)
    return enemy.position


def lead_target(state: GameState) -> Position:
    """Célula alguns passos à frente do jogador, na direção em que ele olha."""
    pos = state.player.position
    dx, dy = state.player.facing
    for _ in range(INTERCEPT_LEAD):
        nxt = pos.moved(dx, dy)
        if state.board.blocked(nxt) or nxt in state.mines:
            break
        pos = nxt
    return pos


def _toward(ctx: AIContext, enemy: Enemy, dist: list[int], avoid_mines: bool) -> Position:
    """Escolhe o vizinho livre mais próximo do alvo do mapa ``dist``."""
    board = ctx.board
    here = board.index(enemy.position)
    best = here
    best_dist = dist[here] if dist[here] >= 0 else len(dist)
    for cell in board.neighbors[here]:
        candidate = dist[cell]
        if candidate < 0 or candidate >= best_dist or cell in ctx.occupied:
            continue
        if avoid_mines and cell in ctx.mine_cells:
            continue
        best, best_dist = cell, candidate
    return board.position(best)


def _away(ctx: AIContext, enemy: Enemy, dist: list[int]) -> Position:
    """Escolhe o vizinho livre mais distante do jogador (fuga durante a Fúria)."""
    board = ctx.board
    here = board.index(enemy.position)
    best, best_dist = here, dist[here]
    for cell in board.neighbors[here]:
        if cell in ctx.occupied or cell in ctx.mine_cells:
            continue
        if dist[cell] > best_dist:
            best, best_dist = cell, dist[cell]
    return board.position(best)


def _wander(ctx: AIContext, enemy: Enemy) -> Position:
    """Passo aleatório para um vizinho livre; às vezes fica parado."""
    board = ctx.board
    options = [
        cell
        for cell in board.neighbors[board.index(enemy.position)]
        if cell not in ctx.occupied and cell not in ctx.mine_cells
    ]
    if not options or ctx.rng.random() < WANDER_REST_CHANCE:
        return enemy.position
    return board.position(ctx.rng.choice(options))
