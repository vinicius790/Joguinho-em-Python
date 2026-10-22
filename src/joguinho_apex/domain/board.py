"""Terreno estático da fase: só paredes, sem entidades."""

from __future__ import annotations

from collections.abc import Sequence

from .enums import Tile
from .geometry import Position


class Board:
    """Grade retangular de paredes.

    O terreno nunca muda durante uma fase, então a lista de vizinhos livres de
    cada célula e as linhas de texto são calculadas uma única vez. Moedas,
    minas e inimigos ficam no ``GameState``, indexados por posição.
    """

    __slots__ = ("_neighbors", "_rows", "height", "walls", "width")

    def __init__(self, width: int, height: int, walls: Sequence[bool] | None = None) -> None:
        """Cria a grade; ``walls`` é uma lista linear (linha a linha) de paredes."""
        if width < 1 or height < 1:
            raise ValueError("A grade precisa ter largura e altura positivas.")
        cells = [False] * (width * height) if walls is None else list(walls)
        if len(cells) != width * height:
            raise ValueError("Quantidade de células diferente de largura x altura.")
        self.width = width
        self.height = height
        self.walls = cells
        self._neighbors: list[tuple[int, ...]] | None = None
        self._rows: list[str] | None = None

    @classmethod
    def from_rows(cls, rows: Sequence[str]) -> Board:
        """Cria a grade a partir de linhas de texto em que ``#`` é parede."""
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("As linhas do mapa precisam ter o mesmo comprimento.")
        walls = [char == Tile.WALL for row in rows for char in row]
        return cls(len(rows[0]), len(rows), walls)

    def index(self, pos: Position) -> int:
        """Converte posição em índice linear."""
        return pos.y * self.width + pos.x

    def position(self, index: int) -> Position:
        """Converte índice linear em posição."""
        y, x = divmod(index, self.width)
        return Position(x, y)

    def inside(self, pos: Position) -> bool:
        """Indica se a posição está dentro da grade."""
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def blocked(self, pos: Position) -> bool:
        """Indica se a posição é parede ou está fora da grade."""
        if not (0 <= pos.x < self.width and 0 <= pos.y < self.height):
            return True
        return self.walls[pos.y * self.width + pos.x]

    @property
    def neighbors(self) -> list[tuple[int, ...]]:
        """Índices dos vizinhos livres de cada célula (vazio para paredes)."""
        if self._neighbors is None:
            self._neighbors = self._build_neighbors()
        return self._neighbors

    def _build_neighbors(self) -> list[tuple[int, ...]]:
        width, height, walls = self.width, self.height, self.walls
        table: list[tuple[int, ...]] = []
        for index, wall in enumerate(walls):
            if wall:
                table.append(())
                continue
            y, x = divmod(index, width)
            around = []
            if y > 0 and not walls[index - width]:
                around.append(index - width)
            if x > 0 and not walls[index - 1]:
                around.append(index - 1)
            if y < height - 1 and not walls[index + width]:
                around.append(index + width)
            if x < width - 1 and not walls[index + 1]:
                around.append(index + 1)
            table.append(tuple(around))
        return table

    def open_cells(self) -> list[Position]:
        """Lista todas as células que não são parede."""
        return [self.position(i) for i, wall in enumerate(self.walls) if not wall]

    def wall_count(self) -> int:
        """Quantidade de paredes."""
        return sum(self.walls)

    def rows(self) -> list[str]:
        """Linhas de texto do terreno, sem entidades."""
        if self._rows is None:
            width = self.width
            self._rows = [
                "".join(
                    Tile.WALL.value if wall else Tile.EMPTY.value
                    for wall in self.walls[start : start + width]
                )
                for start in range(0, len(self.walls), width)
            ]
        return self._rows
