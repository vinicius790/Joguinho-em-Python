"""Geradores procedurais de terreno.

Todos devolvem uma lista linear de booleanos (``True`` = parede) e são
determinísticos para um mesmo ``Random``. :func:`generate_walls` aplica as
garantias comuns: borda fechada e uma única região livre conectada.
"""

from __future__ import annotations

from collections.abc import Callable
from random import Random

from ..domain.enums import MapKind

Walls = list[bool]

MIN_SIZE = 5
MIN_OPEN_FRACTION = 0.15
CAVE_FILL = 0.40
CAVE_ITERATIONS = 4
MAZE_BRAID = 0.15
ROOM_ATTEMPTS = 80
ROOM_LIMIT = 10


def open_field(width: int, height: int, rng: Random, density: float) -> Walls:
    """Campo aberto, como no jogo original: só a borda é parede."""
    return [False] * (width * height)


def scatter(width: int, height: int, rng: Random, density: float) -> Walls:
    """Pilares espalhados: cada célula vira parede com probabilidade ``density``."""
    return [rng.random() < density for _ in range(width * height)]


def caves(width: int, height: int, rng: Random, density: float) -> Walls:
    """Cavernas por autômato celular (regra 4-5) sobre ruído inicial."""
    fill = CAVE_FILL + density / 2
    walls = [rng.random() < fill for _ in range(width * height)]
    for _ in range(CAVE_ITERATIONS):
        smoothed = walls.copy()
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                i = y * width + x
                around = (
                    walls[i - width - 1]
                    + walls[i - width]
                    + walls[i - width + 1]
                    + walls[i - 1]
                    + walls[i + 1]
                    + walls[i + width - 1]
                    + walls[i + width]
                    + walls[i + width + 1]
                )
                smoothed[i] = around >= 5 or (walls[i] and around >= 4)
        walls = smoothed
    return walls


def maze(width: int, height: int, rng: Random, density: float) -> Walls:
    """Labirinto por busca em profundidade, com parte das paredes aberta.

    O labirinto perfeito só teria becos sem saída; abrir ``MAZE_BRAID`` das
    paredes entre dois corredores cria laços para fugir dos inimigos.
    """
    walls = [True] * (width * height)
    walls[width + 1] = False
    stack = [(1, 1)]
    while stack:
        x, y = stack[-1]
        options = [
            (x + dx, y + dy)
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
            if 0 < x + dx < width - 1
            and 0 < y + dy < height - 1
            and walls[(y + dy) * width + x + dx]
        ]
        if not options:
            stack.pop()
            continue
        nx, ny = rng.choice(options)
        walls[((y + ny) // 2) * width + (x + nx) // 2] = False
        walls[ny * width + nx] = False
        stack.append((nx, ny))
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            i = y * width + x
            if not walls[i]:
                continue
            horizontal = not walls[i - 1] and not walls[i + 1]
            vertical = not walls[i - width] and not walls[i + width]
            if horizontal != vertical and rng.random() < MAZE_BRAID:
                walls[i] = False
    return walls


def rooms(width: int, height: int, rng: Random, density: float) -> Walls:
    """Salas retangulares ligadas por corredores em L."""
    walls = [True] * (width * height)
    placed: list[tuple[int, int, int, int]] = []
    for _ in range(ROOM_ATTEMPTS):
        if len(placed) >= ROOM_LIMIT:
            break
        w = rng.randint(6, 14)
        h = rng.randint(4, 8)
        if w > width - 3 or h > height - 3:
            continue
        x = rng.randint(1, width - w - 1)
        y = rng.randint(1, height - h - 1)
        if any(
            x <= ox + ow and ox <= x + w and y <= oy + oh and oy <= y + h
            for ox, oy, ow, oh in placed
        ):
            continue
        placed.append((x, y, w, h))
        for row in range(y, y + h):
            start = row * width + x
            walls[start : start + w] = [False] * w
    centers = sorted((x + w // 2, y + h // 2) for x, y, w, h in placed)
    for a, b in zip(centers, centers[1:], strict=False):
        _corridor(walls, width, a, b, rng)
    if len(centers) > 2:
        _corridor(walls, width, centers[0], centers[-1], rng)
    return walls


def _corridor(
    walls: Walls, width: int, a: tuple[int, int], b: tuple[int, int], rng: Random
) -> None:
    """Abre um corredor em L entre dois pontos."""
    (ax, ay), (bx, by) = a, b
    corner_x, corner_y = (bx, ay) if rng.random() < 0.5 else (ax, by)
    for x in range(min(ax, corner_x), max(ax, corner_x) + 1):
        walls[ay * width + x] = False
    for y in range(min(ay, corner_y), max(ay, corner_y) + 1):
        walls[y * width + ax] = False
    for x in range(min(bx, corner_x), max(bx, corner_x) + 1):
        walls[by * width + x] = False
    for y in range(min(by, corner_y), max(by, corner_y) + 1):
        walls[y * width + bx] = False


def hybrid(width: int, height: int, rng: Random, density: float) -> Walls:
    """Salas e corredores escavados dentro de cavernas."""
    carved = rooms(width, height, rng, density)
    cave = caves(width, height, rng, density)
    return [a and b for a, b in zip(carved, cave, strict=True)]


GENERATORS: dict[MapKind, Callable[[int, int, Random, float], Walls]] = {
    MapKind.OPEN: open_field,
    MapKind.SCATTER: scatter,
    MapKind.CAVES: caves,
    MapKind.MAZE: maze,
    MapKind.ROOMS: rooms,
    MapKind.HYBRID: hybrid,
}


def generate_walls(
    kind: MapKind, width: int, height: int, rng: Random, density: float = 0.08
) -> Walls:
    """Gera o terreno de uma fase com borda fechada e área livre conectada.

    Se o gerador produzir área livre demais pequena (menos de
    ``MIN_OPEN_FRACTION`` da grade), o resultado é trocado por um campo aberto.
    """
    if width < MIN_SIZE or height < MIN_SIZE:
        raise ValueError(f"O mapa precisa ter pelo menos {MIN_SIZE}x{MIN_SIZE} células.")
    walls = GENERATORS[kind](width, height, rng, density)
    _seal_border(walls, width, height)
    if _keep_largest_region(walls, width) < MIN_OPEN_FRACTION * width * height:
        walls = open_field(width, height, rng, density)
        _seal_border(walls, width, height)
    return walls


def _seal_border(walls: Walls, width: int, height: int) -> None:
    """Transforma toda a borda em parede."""
    for x in range(width):
        walls[x] = True
        walls[(height - 1) * width + x] = True
    for y in range(height):
        walls[y * width] = True
        walls[y * width + width - 1] = True


def _keep_largest_region(walls: Walls, width: int) -> int:
    """Fecha todas as regiões livres menores e devolve o tamanho da maior.

    Pressupõe borda fechada, o que dispensa checar limites dos vizinhos.
    """
    seen = [False] * len(walls)
    best: list[int] = []
    for start, wall in enumerate(walls):
        if wall or seen[start]:
            continue
        region = [start]
        seen[start] = True
        for cell in region:  # a lista cresce durante a iteração
            for nxt in (cell - width, cell - 1, cell + 1, cell + width):
                if not walls[nxt] and not seen[nxt]:
                    seen[nxt] = True
                    region.append(nxt)
        if len(region) > len(best):
            best = region
    keep = set(best)
    for cell in range(len(walls)):
        if cell not in keep:
            walls[cell] = True
    return len(best)
