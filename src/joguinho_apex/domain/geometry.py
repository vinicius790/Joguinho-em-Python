"""Coordenadas inteiras da grade."""

from __future__ import annotations

from typing import NamedTuple


class Position(NamedTuple):
    """Célula da grade; ``x`` cresce para a direita e ``y`` para baixo."""

    x: int
    y: int

    def moved(self, dx: int, dy: int) -> Position:
        """Devolve a posição deslocada por ``(dx, dy)``."""
        return Position(self.x + dx, self.y + dy)

    def manhattan(self, other: Position) -> int:
        """Distância em passos ortogonais, ignorando paredes."""
        return abs(self.x - other.x) + abs(self.y - other.y)

    def chebyshev(self, other: Position) -> int:
        """Distância contando diagonais como um passo (raio de explosão)."""
        return max(abs(self.x - other.x), abs(self.y - other.y))

    def neighbors4(self) -> tuple[Position, ...]:
        """Devolve os quatro vizinhos ortogonais, sem checar limites."""
        return (
            Position(self.x, self.y - 1),
            Position(self.x - 1, self.y),
            Position(self.x, self.y + 1),
            Position(self.x + 1, self.y),
        )
