"""Busca em largura sobre a grade.

A grade tem custo uniforme, então a busca em largura já devolve caminhos
mínimos. Um único mapa de distâncias a partir do jogador serve a todos os
inimigos do turno.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

from ..domain.board import Board
from ..domain.geometry import Position

UNREACHABLE = -1


def as_cells(board: Board, positions: Iterable[Position]) -> set[int]:
    """Converte posições em um conjunto de índices lineares."""
    width = board.width
    return {pos.y * width + pos.x for pos in positions}


def distance_map(
    board: Board,
    source: Position,
    blocked: Collection[int] = (),
    until: Collection[int] = (),
) -> list[int]:
    """Distância em passos de ``source`` a cada célula; ``-1`` se inalcançável.

    ``blocked`` contém índices lineares de células intransponíveis além das
    paredes (por exemplo, minas). A origem nunca é considerada bloqueada.

    Com ``until``, a busca para assim que todas essas células forem
    alcançadas e as células mais distantes ficam com ``-1``. Isso basta para
    os inimigos, que só precisam das distâncias entre eles e o alvo.
    """
    neighbors = board.neighbors
    dist = [UNREACHABLE] * len(neighbors)
    start = board.index(source)
    dist[start] = 0
    queue = [start]
    pending = len(until)
    for cell in queue:  # a fila cresce durante a iteração
        if pending and cell in until:
            pending -= 1
            if pending == 0:
                break
        step = dist[cell] + 1
        for nxt in neighbors[cell]:
            if dist[nxt] < 0 and nxt not in blocked:
                dist[nxt] = step
                queue.append(nxt)
    return dist


def path_to(board: Board, dist: list[int], goal: Position) -> list[Position]:
    """Reconstrói o caminho da origem do mapa ``dist`` até ``goal``.

    Devolve a lista de posições incluindo origem e destino, ou lista vazia se
    ``goal`` é inalcançável.
    """
    cell = board.index(goal)
    if dist[cell] < 0:
        return []
    path = [cell]
    neighbors = board.neighbors
    while dist[cell] > 0:
        wanted = dist[cell] - 1
        cell = next(nxt for nxt in neighbors[cell] if dist[nxt] == wanted)
        path.append(cell)
    path.reverse()
    return [board.position(index) for index in path]


def shortest_path(
    board: Board, start: Position, goal: Position, blocked: Collection[int] = ()
) -> list[Position]:
    """Caminho mínimo de ``start`` a ``goal`` (lista vazia se não existe)."""
    if board.blocked(start) or board.blocked(goal):
        return []
    return path_to(board, distance_map(board, start, blocked), goal)


def nearest_path(
    board: Board, source: Position, goals: Collection[int], blocked: Collection[int] = ()
) -> list[Position]:
    """Caminho mínimo de ``source`` até a célula de ``goals`` mais próxima.

    A busca para no primeiro objetivo encontrado. Devolve lista vazia se
    nenhum objetivo é alcançável; a origem não conta como objetivo.
    """
    neighbors = board.neighbors
    start = board.index(source)
    parent = {start: start}
    queue = [start]
    for cell in queue:  # a fila cresce durante a iteração
        if cell in goals and cell != start:
            path = [cell]
            while cell != start:
                cell = parent[cell]
                path.append(cell)
            path.reverse()
            return [board.position(index) for index in path]
        for nxt in neighbors[cell]:
            if nxt not in parent and nxt not in blocked:
                parent[nxt] = cell
                queue.append(nxt)
    return []
