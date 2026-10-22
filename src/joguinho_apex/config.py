"""Configuração lida de variáveis de ambiente ``JOGUINHO_*``."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


def default_db_path() -> str:
    """Devolve o caminho padrão do banco: ``~/.joguinho-apex/joguinho.sqlite3``."""
    return str(Path.home() / ".joguinho-apex" / "joguinho.sqlite3")


def default_levels_dir() -> str:
    """Devolve a pasta padrão das fases personalizadas: ``~/.joguinho-apex/fases``."""
    return str(Path.home() / ".joguinho-apex" / "fases")


def _int(env: Mapping[str, str], key: str, default: int, minimum: int) -> int:
    """Lê um inteiro do ambiente, com valor padrão e limite inferior."""
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{key} deve ser um número inteiro, recebido: {raw!r}") from None
    if value < minimum:
        raise ValueError(f"{key} deve ser >= {minimum}, recebido: {value}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Parâmetros de execução do jogo, da persistência e da API."""

    seed: int | None = None
    db_path: str = field(default_factory=default_db_path)
    player: str = "Jogador"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    max_sessions: int = 200
    max_sessions_per_client: int = 20
    session_ttl: int = 1800
    rate_limit: int = 600
    levels_dir: str = field(default_factory=default_levels_dir)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Monta as configurações a partir do ambiente (ou de um mapa de teste)."""
        source = os.environ if env is None else env
        raw_seed = source.get("JOGUINHO_SEED", "").strip()
        return cls(
            seed=_int(source, "JOGUINHO_SEED", 0, 0) if raw_seed else None,
            db_path=source.get("JOGUINHO_DB", "").strip() or default_db_path(),
            player=source.get("JOGUINHO_PLAYER", "").strip() or "Jogador",
            api_host=source.get("JOGUINHO_API_HOST", "").strip() or "127.0.0.1",
            api_port=_int(source, "JOGUINHO_API_PORT", 8000, 1),
            max_sessions=_int(source, "JOGUINHO_MAX_SESSIONS", 200, 1),
            max_sessions_per_client=_int(source, "JOGUINHO_MAX_SESSIONS_PER_CLIENT", 20, 1),
            session_ttl=_int(source, "JOGUINHO_SESSION_TTL", 1800, 1),
            rate_limit=_int(source, "JOGUINHO_RATE_LIMIT", 600, 1),
            levels_dir=source.get("JOGUINHO_LEVELS", "").strip() or default_levels_dir(),
        )
