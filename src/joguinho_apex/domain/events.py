"""Eventos emitidos pelo motor a cada mudança relevante."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    """Registro de algo que aconteceu; ``seq`` é crescente dentro da partida."""

    seq: int
    kind: str
    tick: int
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Converte o evento em dicionário serializável."""
        return {"seq": self.seq, "kind": self.kind, "tick": self.tick, "payload": self.payload}


class EventKind:
    """Nomes dos eventos emitidos pelo motor."""

    LEVEL_START = "level_start"
    COLLECT = "collect"
    POWERUP = "powerup"
    DAMAGE = "damage"
    SHIELD = "shield"
    EXPLOSION = "explosion"
    ENEMY_DEFEATED = "enemy_defeated"
    BOSS_HIT = "boss_hit"
    BOSS_FIRE = "boss_fire"
    DASH = "dash"
    PULSE = "pulse"
    EXIT_OPEN = "exit_open"
    SPAWN = "spawn"
    PURCHASE = "purchase"
    ITEM_USED = "item_used"
    LEVEL_COMPLETE = "level_complete"
    WIN = "win"
    LOSS = "loss"
    SKILL_UNLOCKED = "skill_unlocked"
    DYNAMIC_EVENT = "dynamic_event"
    DYNAMIC_CHOICE = "dynamic_choice"
    CHEAT_DEATH = "cheat_death"
