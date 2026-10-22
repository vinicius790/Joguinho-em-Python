"""Estado completo de uma partida."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .board import Board
from .entities import Enemy, LevelSpec, Player, Statistics
from .enums import (
    ENEMY_SYMBOLS,
    POWER_SYMBOLS,
    SLEEPING_AMBUSHER,
    Difficulty,
    EnemyKind,
    GameMode,
    GameStatus,
    PowerKind,
    Tile,
)
from .geometry import Position


@dataclass(slots=True)
class GameState:
    """Tudo o que descreve a partida em um dado turno.

    O terreno fica em ``board``; as entidades ficam em coleções indexadas por
    posição, de modo que cada regra consulta uma célula em tempo constante.
    """

    session_id: str
    seed: int
    mode: GameMode
    difficulty: Difficulty
    level_index: int
    level: LevelSpec
    board: Board
    player: Player
    enemies: list[Enemy] = field(default_factory=list)
    coins: set[Position] = field(default_factory=set)
    mines: set[Position] = field(default_factory=set)
    powerups: dict[Position, PowerKind] = field(default_factory=dict)
    fires: dict[Position, int] = field(default_factory=dict)
    exit: Position | None = None
    status: GameStatus = GameStatus.RUNNING
    stats: Statistics = field(default_factory=Statistics)
    tick: int = 0
    level_tick: int = 0
    level_coins: int = 0
    score: int = 0
    freeze: int = 0
    time_limit: int | None = None
    message: str = ""

    @property
    def exit_open(self) -> bool:
        """A saída existe e a meta de moedas já foi atingida."""
        return self.exit is not None and self.level_coins >= self.level.target

    @property
    def time_left(self) -> int | None:
        """Turnos restantes na fase, ou ``None`` se não há limite."""
        if self.time_limit is None:
            return None
        return max(0, self.time_limit - self.level_tick)

    @property
    def boss(self) -> Enemy | None:
        """O chefe da fase, se estiver vivo."""
        for enemy in self.enemies:
            if enemy.kind is EnemyKind.BOSS:
                return enemy
        return None

    def visible(self, pos: Position) -> bool:
        """Indica se a célula está dentro do raio de visão em fases com névoa."""
        radius = self.level.fog_radius
        if radius <= 0:
            return True
        dx = pos.x - self.player.position.x
        dy = pos.y - self.player.position.y
        # Células de terminal são ~2x mais altas que largas: achata o eixo x.
        return dx * dx + 4 * dy * dy <= 4 * radius * radius

    def render_lines(self, fog: bool = True) -> list[str]:
        """Desenha a grade com as entidades por cima do terreno."""
        grid = [list(row) for row in self.board.rows()]
        if self.exit is not None:
            symbol = Tile.EXIT_OPEN if self.exit_open else Tile.EXIT_LOCKED
            grid[self.exit.y][self.exit.x] = symbol.value
        for pos in self.fires:
            grid[pos.y][pos.x] = Tile.FIRE.value
        for pos in self.mines:
            grid[pos.y][pos.x] = Tile.MINE.value
        for pos in self.coins:
            grid[pos.y][pos.x] = Tile.COIN.value
        for pos, kind in self.powerups.items():
            grid[pos.y][pos.x] = POWER_SYMBOLS[kind]
        for enemy in self.enemies:
            asleep = enemy.kind is EnemyKind.AMBUSHER and not enemy.enraged
            symbol_text = SLEEPING_AMBUSHER if asleep else ENEMY_SYMBOLS[enemy.kind]
            grid[enemy.position.y][enemy.position.x] = symbol_text
        player = self.player.position
        grid[player.y][player.x] = Tile.PLAYER.value
        if fog and self.level.fog_radius > 0:
            for y, row in enumerate(grid):
                for x in range(len(row)):
                    if not self.visible(Position(x, y)):
                        row[x] = Tile.FOG.value
        return ["".join(row) for row in grid]

    def snapshot(self) -> dict[str, Any]:
        """Visão da partida para clientes (terminal, API e console web)."""
        player = self.player
        boss = self.boss
        return {
            "session_id": self.session_id,
            "seed": self.seed,
            "mode": self.mode.value,
            "difficulty": self.difficulty.value,
            "status": self.status.value,
            "message": self.message,
            "score": self.score,
            "tick": self.tick,
            "level": {
                "index": self.level_index,
                "id": self.level.level_id,
                "title": self.level.title,
                "objective": self.level.objective,
                "target": self.level.target,
                "fog_radius": self.level.fog_radius,
                "boss": self.level.boss if self.level.boss_hp else None,
            },
            "size": {"width": self.board.width, "height": self.board.height},
            "rows": self.render_lines(),
            "player": {
                "x": player.position.x,
                "y": player.position.y,
                "hp": player.hp,
                "max_hp": player.max_hp,
                "shield": player.shield,
                "combo": player.combo,
                "dash_cooldown": player.dash_cooldown,
                "pulse_cooldown": player.pulse_cooldown,
                "magnet": player.magnet,
                "fury": player.fury,
                "gold": player.gold,
                "items": dict(player.items),
                "skill_points": player.skill_points,
                "skills": sorted(player.skills),
            },
            "boss": None if boss is None else {"hp": boss.hp, "max_hp": boss.max_hp},
            "enemies": sum(1 for enemy in self.enemies if enemy.kind is not EnemyKind.BOSS),
            "coins_collected": self.level_coins,
            "coins_left": len(self.coins),
            "exit_open": self.exit_open,
            "time_left": self.time_left,
            "freeze": self.freeze,
            "stats": self.stats.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serializa o estado inteiro (formato de save, sem perdas)."""
        return {
            "session_id": self.session_id,
            "seed": self.seed,
            "mode": self.mode.value,
            "difficulty": self.difficulty.value,
            "level_index": self.level_index,
            "level": self.level.to_dict(),
            "walls": self.board.rows(),
            "player": self.player.to_dict(),
            "enemies": [enemy.to_dict() for enemy in self.enemies],
            "coins": sorted(self.coins),
            "mines": sorted(self.mines),
            "powerups": sorted((pos.x, pos.y, kind.value) for pos, kind in self.powerups.items()),
            "fires": sorted((pos.x, pos.y, ttl) for pos, ttl in self.fires.items()),
            "exit": self.exit,
            "status": self.status.value,
            "stats": self.stats.to_dict(),
            "tick": self.tick,
            "level_tick": self.level_tick,
            "level_coins": self.level_coins,
            "score": self.score,
            "freeze": self.freeze,
            "time_limit": self.time_limit,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameState:
        """Reconstrói o estado a partir de :meth:`to_dict`."""
        return cls(
            session_id=data["session_id"],
            seed=data["seed"],
            mode=GameMode(data["mode"]),
            difficulty=Difficulty(data["difficulty"]),
            level_index=data["level_index"],
            level=LevelSpec.from_dict(data["level"]),
            board=Board.from_rows(data["walls"]),
            player=Player.from_dict(data["player"]),
            enemies=[Enemy.from_dict(item) for item in data["enemies"]],
            coins={Position(x, y) for x, y in data["coins"]},
            mines={Position(x, y) for x, y in data["mines"]},
            powerups={Position(x, y): PowerKind(kind) for x, y, kind in data["powerups"]},
            fires={Position(x, y): ttl for x, y, ttl in data["fires"]},
            exit=None if data["exit"] is None else Position(*data["exit"]),
            status=GameStatus(data["status"]),
            stats=Statistics.from_dict(data["stats"]),
            tick=data["tick"],
            level_tick=data["level_tick"],
            level_coins=data["level_coins"],
            score=data["score"],
            freeze=data["freeze"],
            time_limit=data["time_limit"],
            message=data["message"],
        )
