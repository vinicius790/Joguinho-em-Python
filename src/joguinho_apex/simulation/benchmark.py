"""Benchmark do motor: turnos por segundo."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from ..ai.bot import BotPlayer
from ..domain.enums import Difficulty, GameMode, GameStatus
from ..engine.engine import GameEngine
from .runner import make_policy


def benchmark(
    steps: int = 10_000,
    seed: int = 0,
    mode: GameMode | str = GameMode.CAMPAIGN,
    difficulty: Difficulty | str = Difficulty.NORMAL,
    policy: str = "bot",
) -> dict[str, Any]:
    """Mede quantos turnos por segundo o motor processa.

    Só o tempo de ``GameEngine.step`` entra em ``engine_steps_per_second``;
    ``total_steps_per_second`` inclui a política que escolhe as ações e a
    geração das fases. Quando a partida termina, outra começa com a seed
    seguinte, até completar ``steps`` turnos.
    """
    if steps < 1:
        raise ValueError("steps deve ser >= 1.")
    engine = GameEngine(seed, mode, difficulty)
    choose = make_policy(policy, seed)
    games = 1
    engine_seconds = 0.0
    started = perf_counter()
    done = 0
    while done < steps:
        status = engine.state.status
        if status is GameStatus.LEVEL_COMPLETE:
            if policy == "bot":
                BotPlayer.shop(engine)
            engine.next_level()
            continue
        if status is not GameStatus.RUNNING:
            games += 1
            engine = GameEngine(seed + games, mode, difficulty)
            continue
        action = choose(engine)
        before = perf_counter()
        engine.step(action)
        engine_seconds += perf_counter() - before
        done += 1
    total_seconds = perf_counter() - started
    return {
        "mode": GameMode(mode).value,
        "difficulty": Difficulty(difficulty).value,
        "policy": policy,
        "steps": steps,
        "games": games,
        "engine_seconds": round(engine_seconds, 4),
        "total_seconds": round(total_seconds, 4),
        "engine_steps_per_second": round(steps / engine_seconds) if engine_seconds else 0,
        "total_steps_per_second": round(steps / total_seconds) if total_seconds else 0,
    }
