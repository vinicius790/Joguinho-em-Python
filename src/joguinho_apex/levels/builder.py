"""Montagem de fases: terreno + posições iniciais de todas as entidades."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from random import Random

from ..ai.pathfinding import distance_map
from ..domain.board import Board
from ..domain.entities import LevelSpec
from ..domain.enums import (
    ENEMY_SYMBOLS,
    POWER_SYMBOLS,
    SLEEPING_AMBUSHER,
    EnemyKind,
    PowerKind,
    Tile,
)
from ..domain.geometry import Position
from ..engine.rules import FIRE_TTL, DifficultyTuning
from .generators import generate_walls

SAFE_START_DISTANCE = 12
MINE_CLEARANCE = 2
MINE_ATTEMPT_FACTOR = 4

_ENEMY_BY_SYMBOL: dict[str, EnemyKind] = {symbol: kind for kind, symbol in ENEMY_SYMBOLS.items()}
_ENEMY_BY_SYMBOL[SLEEPING_AMBUSHER] = EnemyKind.AMBUSHER
_POWER_BY_SYMBOL: dict[str, PowerKind] = {symbol: kind for kind, symbol in POWER_SYMBOLS.items()}


@dataclass(slots=True)
class LevelLayout:
    """Fase pronta para o motor: terreno e posições iniciais."""

    board: Board
    player: Position
    coins: set[Position] = field(default_factory=set)
    mines: set[Position] = field(default_factory=set)
    powerups: dict[Position, PowerKind] = field(default_factory=dict)
    enemies: list[tuple[EnemyKind, Position]] = field(default_factory=list)
    fires: dict[Position, int] = field(default_factory=dict)
    exit: Position | None = None


def scaled_roster(kinds: Sequence[EnemyKind], factor: float) -> list[EnemyKind]:
    """Ajusta a lista de inimigos pela dificuldade, repetindo os tipos em ciclo."""
    if not kinds:
        return []
    count = max(1, round(len(kinds) * factor))
    return [kinds[i % len(kinds)] for i in range(count)]


def build_layout(spec: LevelSpec, rng: Random, tuning: DifficultyTuning) -> LevelLayout:
    """Gera a fase descrita por ``spec`` de forma determinística para ``rng``.

    Garantias: o jogador nasce perto do centro; a saída fica na célula mais
    distante; inimigos nascem longe; e as minas nunca desconectam a área
    livre, então toda moeda e a saída são alcançáveis sem pisar em mina.
    """
    walls = generate_walls(spec.map_kind, spec.width, spec.height, rng, spec.wall_density)
    board = Board(spec.width, spec.height, walls)
    cells = board.open_cells()
    center = Position(spec.width // 2, spec.height // 2)
    player = min(cells, key=lambda pos: (pos.manhattan(center), pos))
    dist = distance_map(board, player)
    layout = LevelLayout(board, player)

    free = [pos for pos in cells if pos != player]
    rng.shuffle(free)
    taken = {player}

    if spec.exit_required:
        layout.exit = max(free, key=lambda pos: (dist[board.index(pos)], pos))
        taken.add(layout.exit)

    roster = scaled_roster(spec.enemies, tuning.enemy_factor)
    if spec.boss_hp > 0:
        roster.append(EnemyKind.BOSS)
    far_limit = min(SAFE_START_DISTANCE, max(dist) // 2)
    far = [pos for pos in free if pos not in taken and dist[board.index(pos)] >= far_limit]
    for kind in roster:
        if not far:
            break
        pos = far.pop()
        taken.add(pos)
        layout.enemies.append((kind, pos))

    remaining = (pos for pos in free if pos not in taken)
    for _ in range(spec.coins):
        coin = next(remaining, None)
        if coin is None:
            break
        layout.coins.add(coin)
    taken |= layout.coins

    kinds = list(PowerKind)
    remaining = (pos for pos in free if pos not in taken)
    for _ in range(round(spec.powerups * tuning.powerup_factor)):
        spot = next(remaining, None)
        if spot is None:
            break
        layout.powerups[spot] = rng.choice(kinds)
    taken |= layout.powerups.keys()

    _place_mines(layout, round(spec.mines * tuning.mine_factor), free, taken, len(cells))
    return layout


def _place_mines(
    layout: LevelLayout,
    count: int,
    candidates: Sequence[Position],
    taken: set[Position],
    open_total: int,
) -> None:
    """Coloca minas sem desconectar a área livre.

    Cada mina candidata só é aceita se todas as demais células livres
    continuarem alcançáveis a partir do jogador sem pisar em minas.
    """
    board = layout.board
    blocked: set[int] = set()
    attempts = count * MINE_ATTEMPT_FACTOR
    for pos in candidates:
        if len(layout.mines) >= count or attempts <= 0:
            break
        if pos in taken or pos.manhattan(layout.player) <= MINE_CLEARANCE:
            continue
        attempts -= 1
        cell = board.index(pos)
        blocked.add(cell)
        reach = distance_map(board, layout.player, blocked)
        if len(reach) - reach.count(-1) == open_total - len(blocked):
            layout.mines.add(pos)
        else:
            blocked.discard(cell)


def layout_to_rows(layout: LevelLayout) -> list[str]:
    """Desenha a fase em texto (o inverso de :func:`layout_from_rows`)."""
    grid = [list(row) for row in layout.board.rows()]
    cells: list[tuple[Position, str]] = [(pos, Tile.COIN.value) for pos in layout.coins]
    cells += [(pos, Tile.MINE.value) for pos in layout.mines]
    cells += [(pos, Tile.FIRE.value) for pos in layout.fires]
    cells += [(pos, POWER_SYMBOLS[kind]) for pos, kind in layout.powerups.items()]
    cells += [(pos, ENEMY_SYMBOLS[kind]) for kind, pos in layout.enemies]
    if layout.exit is not None:
        cells.append((layout.exit, Tile.EXIT_OPEN.value))
    cells.append((layout.player, Tile.PLAYER.value))
    for pos, symbol in cells:
        grid[pos.y][pos.x] = symbol
    return ["".join(row) for row in grid]


def layout_from_rows(rows: Sequence[str]) -> LevelLayout:
    """Lê uma fase desenhada em texto, com os mesmos símbolos da tela.

    Útil para testes e fases feitas à mão. Aceita ``#`` parede, ``O`` jogador,
    ``$`` moeda, ``Q`` mina, ``*`` fogo, ``E`` saída, inimigos ``X Y W A B``
    (``z`` é emboscador dormindo) e power-ups ``+ S F M !``.
    """
    board = Board.from_rows(rows)
    player: Position | None = None
    layout = LevelLayout(board, Position(0, 0))
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            pos = Position(x, y)
            if char == Tile.PLAYER:
                if player is not None:
                    raise ValueError("O mapa precisa ter exatamente um jogador (O).")
                player = pos
            elif char == Tile.COIN:
                layout.coins.add(pos)
            elif char == Tile.MINE:
                layout.mines.add(pos)
            elif char == Tile.FIRE:
                layout.fires[pos] = FIRE_TTL
            elif char in (Tile.EXIT_OPEN, Tile.EXIT_LOCKED):
                layout.exit = pos
            elif char in _ENEMY_BY_SYMBOL:
                layout.enemies.append((_ENEMY_BY_SYMBOL[char], pos))
            elif char in _POWER_BY_SYMBOL:
                layout.powerups[pos] = _POWER_BY_SYMBOL[char]
            elif char not in (Tile.EMPTY, Tile.WALL):
                raise ValueError(f"Símbolo desconhecido no mapa: {char!r} em ({x}, {y}).")
    if player is None:
        raise ValueError("O mapa precisa ter exatamente um jogador (O).")
    layout.player = player
    return layout
