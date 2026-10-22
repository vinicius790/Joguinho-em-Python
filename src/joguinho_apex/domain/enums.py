"""Enumerações e símbolos usados em todo o jogo."""

from __future__ import annotations

from enum import StrEnum


class Tile(StrEnum):
    """Caracteres desenhados na grade."""

    EMPTY = " "
    WALL = "#"
    PLAYER = "O"
    COIN = "$"
    MINE = "Q"
    FIRE = "*"
    EXIT_OPEN = "E"
    EXIT_LOCKED = "e"
    FOG = "~"


class Action(StrEnum):
    """Ação do jogador em um turno; o valor é a tecla correspondente."""

    UP = "w"
    LEFT = "a"
    DOWN = "s"
    RIGHT = "d"
    WAIT = "."
    DASH = "e"
    PULSE = "f"
    BOMB = "b"
    POTION = "h"

    @property
    def delta(self) -> tuple[int, int] | None:
        """Deslocamento ``(dx, dy)`` das ações de movimento; ``None`` nas demais."""
        return _DELTAS.get(self)

    @classmethod
    def parse(cls, value: str) -> Action:
        """Converte texto livre (tecla ou nome) em ação; levanta ``ValueError``."""
        key = value.strip().lower()
        key = _ALIASES.get(key, key)
        try:
            return cls(key)
        except ValueError:
            raise ValueError(
                "Ação inválida; use W/A/S/D, '.' (esperar), E (dash), F (pulso), "
                "B (bomba) ou H (poção)."
            ) from None


_DELTAS: dict[Action, tuple[int, int]] = {
    Action.UP: (0, -1),
    Action.LEFT: (-1, 0),
    Action.DOWN: (0, 1),
    Action.RIGHT: (1, 0),
}

_ALIASES: dict[str, str] = {
    "": ".",
    "up": "w",
    "left": "a",
    "down": "s",
    "right": "d",
    "wait": ".",
    "dash": "e",
    "pulse": "f",
    "bomb": "b",
    "potion": "h",
}


class GameStatus(StrEnum):
    """Situação da partida."""

    RUNNING = "running"
    LEVEL_COMPLETE = "level_complete"
    WON = "won"
    LOST = "lost"


class Difficulty(StrEnum):
    """Níveis de dificuldade, do mais brando ao mais severo."""

    STORY = "story"
    NORMAL = "normal"
    HARD = "hard"
    NIGHTMARE = "nightmare"
    APOCALYPSE = "apocalypse"


class GameMode(StrEnum):
    """Modos de jogo disponíveis."""

    CAMPAIGN = "campaign"
    CLASSIC = "classic"
    SURVIVAL = "survival"
    CHASE = "chase"
    GAUNTLET = "gauntlet"
    BOSS = "boss"
    ENDLESS = "endless"
    SANDBOX = "sandbox"


class MapKind(StrEnum):
    """Geradores de mapa."""

    OPEN = "open"
    SCATTER = "scatter"
    CAVES = "caves"
    MAZE = "maze"
    ROOMS = "rooms"
    HYBRID = "hybrid"


class EnemyKind(StrEnum):
    """Tipos de inimigo; cada um tem uma estratégia própria."""

    CHASER = "chaser"
    INTERCEPTOR = "interceptor"
    WANDERER = "wanderer"
    AMBUSHER = "ambusher"
    BOSS = "boss"


class PowerKind(StrEnum):
    """Power-ups coletáveis."""

    HEART = "heart"
    SHIELD = "shield"
    FREEZE = "freeze"
    MAGNET = "magnet"
    FURY = "fury"


ENEMY_SYMBOLS: dict[EnemyKind, str] = {
    EnemyKind.CHASER: "X",
    EnemyKind.INTERCEPTOR: "Y",
    EnemyKind.WANDERER: "W",
    EnemyKind.AMBUSHER: "A",
    EnemyKind.BOSS: "B",
}

POWER_SYMBOLS: dict[PowerKind, str] = {
    PowerKind.HEART: "+",
    PowerKind.SHIELD: "S",
    PowerKind.FREEZE: "F",
    PowerKind.MAGNET: "M",
    PowerKind.FURY: "!",
}

SLEEPING_AMBUSHER = "z"
