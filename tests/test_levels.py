"""Geradores de mapa, montagem de fases e catálogo."""

from datetime import date
from random import Random

import pytest

from joguinho_apex.ai.pathfinding import as_cells, distance_map, nearest_path, shortest_path
from joguinho_apex.domain.board import Board
from joguinho_apex.domain.enums import Difficulty, EnemyKind, GameMode, MapKind
from joguinho_apex.domain.geometry import Position
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.engine.rules import TUNINGS
from joguinho_apex.levels.builder import build_layout, layout_from_rows, scaled_roster
from joguinho_apex.levels.catalog import daily_seed, endless_level, level_count, level_for
from joguinho_apex.levels.generators import generate_walls

NORMAL = TUNINGS[Difficulty.NORMAL]


def open_region_is_connected(board, start, blocked=()):
    reach = distance_map(board, start, blocked)
    reachable = len(reach) - reach.count(-1)
    return reachable == len(board.open_cells()) - len(blocked)


@pytest.mark.parametrize("kind", list(MapKind))
@pytest.mark.parametrize("size", [(60, 30), (31, 17), (20, 11)])
def test_generators_seal_border_and_connect_everything(kind, size):
    """Inclui tamanhos ímpares: o gerador híbrido antigo indexava com a largura errada."""
    width, height = size
    walls = generate_walls(kind, width, height, Random(5), 0.08)
    assert len(walls) == width * height
    board = Board(width, height, walls)
    for x in range(width):
        assert board.blocked(Position(x, 0)) and board.blocked(Position(x, height - 1))
    for y in range(height):
        assert board.blocked(Position(0, y)) and board.blocked(Position(width - 1, y))
    cells = board.open_cells()
    assert len(cells) >= 0.15 * width * height
    assert open_region_is_connected(board, cells[0])


@pytest.mark.parametrize("kind", list(MapKind))
def test_generators_are_deterministic(kind):
    first = generate_walls(kind, 60, 30, Random(11), 0.08)
    assert first == generate_walls(kind, 60, 30, Random(11), 0.08)
    if kind is not MapKind.OPEN:
        assert first != generate_walls(kind, 60, 30, Random(12), 0.08)


def test_generators_produce_different_terrain():
    counts = {kind: sum(generate_walls(kind, 60, 30, Random(3), 0.08)) for kind in MapKind}
    assert counts[MapKind.OPEN] == 2 * 60 + 2 * 28
    assert counts[MapKind.MAZE] > counts[MapKind.SCATTER] > counts[MapKind.OPEN]


def test_tiny_map_is_rejected():
    with pytest.raises(ValueError):
        generate_walls(MapKind.OPEN, 4, 4, Random(1))


@pytest.mark.parametrize("mode", list(GameMode))
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_every_mode_builds_a_solvable_first_level(mode, seed):
    spec = level_for(mode, 0)
    layout = build_layout(spec, Random(seed), NORMAL)
    board = layout.board
    everything = [layout.player, *layout.coins, *layout.mines, *layout.powerups]
    everything += [pos for _, pos in layout.enemies]
    if layout.exit is not None:
        everything.append(layout.exit)
    assert len(everything) == len(set(everything)), "duas entidades na mesma célula"
    assert not any(board.blocked(pos) for pos in everything)
    assert len(layout.coins) == spec.coins
    assert spec.coin_respawn or spec.coins >= spec.target, "a meta precisa ser alcançável"
    assert (layout.exit is not None) == spec.exit_required
    # Minas nunca isolam parte do mapa: tudo é alcançável sem pisar nelas.
    assert open_region_is_connected(board, layout.player, as_cells(board, layout.mines))


def test_campaign_levels_use_all_generators_and_enemy_kinds():
    total = level_count(GameMode.CAMPAIGN)
    specs = [level_for(GameMode.CAMPAIGN, index) for index in range(total)]
    maps = {spec.map_kind for spec in specs}
    assert maps >= {MapKind.SCATTER, MapKind.ROOMS, MapKind.CAVES, MapKind.MAZE, MapKind.HYBRID}
    kinds = {kind for spec in specs for kind in spec.enemies}
    assert kinds == set(EnemyKind) - {EnemyKind.BOSS}
    assert any(spec.boss_hp for spec in specs) and any(spec.time_limit for spec in specs)
    assert sum(spec.coins for spec in specs) >= 100, "a conquista Magnata precisa ser possível"
    assert level_for(GameMode.CAMPAIGN, total) is None


def test_enemies_start_far_and_exit_is_the_farthest_cell():
    spec = level_for(GameMode.CAMPAIGN, 3)
    layout = build_layout(spec, Random(8), NORMAL)
    dist = distance_map(layout.board, layout.player)
    for _, pos in layout.enemies:
        assert dist[layout.board.index(pos)] >= 12
    assert dist[layout.board.index(layout.exit)] == max(dist)


def test_engine_puts_the_boss_in_boss_levels():
    engine = GameEngine(1, "boss")
    assert engine.state.boss is not None and engine.state.boss.hp == 5
    assert engine.state.level.objective.startswith("Derrote")


def test_endless_mode_never_ends_and_gets_harder():
    assert level_count(GameMode.ENDLESS) is None
    first, later = endless_level(0), endless_level(8)
    assert len(later.enemies) > len(first.enemies) and later.mines > first.mines
    assert endless_level(4).boss_hp > 0 and endless_level(9).boss_hp > endless_level(4).boss_hp
    assert level_for(GameMode.ENDLESS, 500) is not None


def test_scaled_roster_and_daily_seed():
    kinds = (EnemyKind.CHASER, EnemyKind.WANDERER)
    assert scaled_roster(kinds, 2.0) == [*kinds, *kinds]
    assert scaled_roster(kinds, 0.1) == [EnemyKind.CHASER]
    assert scaled_roster((), 2.0) == []
    assert daily_seed(date(2026, 1, 1)) == daily_seed(date(2026, 1, 1))
    assert daily_seed(date(2026, 1, 1)) != daily_seed(date(2026, 1, 2))


def test_layout_from_rows_reads_every_symbol():
    layout = layout_from_rows(["#########", "#O$Q*E+!#", "#XYWAzB #", "#########"])
    assert layout.player == Position(1, 1)
    assert layout.coins == {Position(2, 1)} and layout.mines == {Position(3, 1)}
    assert layout.exit == Position(5, 1) and len(layout.powerups) == 2
    assert [kind for kind, _ in layout.enemies].count(EnemyKind.AMBUSHER) == 2
    with pytest.raises(ValueError):
        layout_from_rows(["###", "#?#", "###"])
    with pytest.raises(ValueError):
        layout_from_rows(["###", "# #", "###"])


def test_pathfinding_finds_shortest_routes():
    board = Board.from_rows(["#######", "#  #  #", "#  #  #", "#     #", "#######"])
    path = shortest_path(board, Position(1, 1), Position(5, 1))
    assert path[0] == Position(1, 1) and path[-1] == Position(5, 1)
    assert len(path) == 9
    blocked = {board.index(Position(3, 3))}
    assert shortest_path(board, Position(1, 1), Position(5, 1), blocked) == []
    goals = {board.index(Position(5, 1)), board.index(Position(2, 3))}
    assert nearest_path(board, Position(1, 1), goals)[-1] == Position(2, 3)
    assert nearest_path(board, Position(1, 1), set()) == []


def test_distance_map_calls_do_not_share_state():
    """Bug antigo: ``blocked_extra=set()`` como argumento padrão mutável."""
    board = Board(5, 5)
    first = distance_map(board, Position(0, 0))
    assert first == distance_map(board, Position(0, 0))
    assert first[board.index(Position(4, 4))] == 8
