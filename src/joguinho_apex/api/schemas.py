"""Contratos de entrada e saída da API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.enums import Action, Difficulty, GameMode
from ..services.security import MAX_NAME_LENGTH, is_safe_name

MAX_SEED = 2**63 - 1


def _check_name(value: str | None) -> str | None:
    """Recusa nomes com caracteres fora do conjunto permitido."""
    if value is not None and not is_safe_name(value):
        raise ValueError("use só letras, dígitos, espaço, '_' e '-' (até 24 caracteres)")
    return value


class CreateGameRequest(BaseModel):
    """Pedido de nova partida; modo e dificuldade precisam existir."""

    model_config = ConfigDict(extra="forbid")

    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)
    mode: GameMode = GameMode.CAMPAIGN
    difficulty: Difficulty = Difficulty.NORMAL
    name: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)

    _name = field_validator("name")(_check_name)


class ActionRequest(BaseModel):
    """Ação de um turno: ``w a s d``, ``.`` (esperar), ``e``, ``f``, ``b`` (bomba) ou ``h``."""

    model_config = ConfigDict(extra="forbid")

    action: Action

    @field_validator("action", mode="before")
    @classmethod
    def _parse(cls, value: Any) -> Any:
        """Aceita também os nomes por extenso (``up``, ``wait``, ``dash``...)."""
        return Action.parse(value) if isinstance(value, str) and len(value) <= 8 else value


class LoadGameRequest(BaseModel):
    """Pedido para retomar a partida salva de um jogador."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=MAX_NAME_LENGTH)

    _name = field_validator("name")(_check_name)


class GameResponse(BaseModel):
    """Estado da partida depois de uma operação."""

    session_id: str
    status: str
    score: int
    snapshot: dict[str, Any]
    result: dict[str, Any] | None = None
