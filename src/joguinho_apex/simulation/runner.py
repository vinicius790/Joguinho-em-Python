"""Partidas automáticas com uma política (aleatória ou bot) e resumo estatístico."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from random import Random
from statistics import mean, median
from typing import Any

from ..ai.bot import BotPlayer
from ..domain.enums import Action, Difficulty, GameMode, GameStatus
from ..engine.engine import GameEngine

Policy = Callable[[GameEngine], Action]

POLICY_NAMES = ("random", "bot")


def make_policy(name: str, seed: int = 0) -> Policy:
    """Cria a política ``random`` (ação sorteada) ou ``bot`` (heurística)."""
    if name == "random":
        rng = Random(seed)
        actions = list(Action)
        return lambda engine: rng.choice(actions)
    if name == "bot":
        return BotPlayer().choose
    raise ValueError(f"Política desconhecida: {name!r}. Use uma de {POLICY_NAMES}.")


@dataclass(frozen=True, slots=True)
class EpisodeResult:
    """Resultado de uma partida simulada."""

    seed: int
    status: str
    score: int
    levels: int
    ticks: int
    coins: int
    damage: int
    enemies_defeated: int


def run_episode(
    seed: int,
    mode: GameMode | str = GameMode.CAMPAIGN,
    difficulty: Difficulty | str = Difficulty.NORMAL,
    policy: str = "bot",
    max_steps: int = 2000,
) -> EpisodeResult:
    """Joga uma partida até o fim ou até ``max_steps`` turnos.

    Uma partida interrompida pelo limite de turnos sai com status ``running``.
    Com a política ``bot``, a loja é usada entre as fases (``BotPlayer.shop``).
    """
    engine = GameEngine(seed, mode, difficulty)
    choose = make_policy(policy, seed)
    for _ in range(max_steps):
        status = engine.state.status
        if status is GameStatus.LEVEL_COMPLETE:
            if policy == "bot":
                BotPlayer.shop(engine)
            engine.next_level()
        elif status is not GameStatus.RUNNING:
            break
        engine.step(choose(engine))
    state = engine.state
    return EpisodeResult(
        seed=seed,
        status=state.status.value,
        score=state.score,
        levels=state.stats.levels_completed,
        ticks=state.stats.ticks,
        coins=state.stats.coins,
        damage=state.stats.damage_taken,
        enemies_defeated=state.stats.enemies_defeated,
    )


def run_episodes(
    episodes: int,
    seed: int = 0,
    mode: GameMode | str = GameMode.CAMPAIGN,
    difficulty: Difficulty | str = Difficulty.NORMAL,
    policy: str = "bot",
    max_steps: int = 2000,
) -> list[EpisodeResult]:
    """Joga ``episodes`` partidas com seeds consecutivas a partir de ``seed``."""
    return [
        run_episode(seed + offset, mode, difficulty, policy, max_steps)
        for offset in range(episodes)
    ]


def percentile(values: Sequence[float], fraction: float) -> float:
    """Percentil por interpolação linear; ``fraction`` vai de 0 a 1."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def summarize(results: Sequence[EpisodeResult]) -> dict[str, Any]:
    """Resumo de um lote: taxas de vitória e estatísticas de pontuação."""
    total = len(results)
    if not total:
        return {"episodes": 0}
    scores = [result.score for result in results]
    wins = sum(result.status == GameStatus.WON for result in results)
    losses = sum(result.status == GameStatus.LOST for result in results)
    return {
        "episodes": total,
        "wins": wins,
        "losses": losses,
        "unfinished": total - wins - losses,
        "win_rate": round(wins / total, 3),
        "score_mean": round(mean(scores), 1),
        "score_median": median(scores),
        "score_p90": round(percentile(scores, 0.9), 1),
        "score_min": min(scores),
        "score_max": max(scores),
        "levels_mean": round(mean(result.levels for result in results), 2),
        "ticks_mean": round(mean(result.ticks for result in results), 1),
        "damage_mean": round(mean(result.damage for result in results), 2),
    }


def results_as_dicts(results: Sequence[EpisodeResult]) -> list[dict[str, Any]]:
    """Converte os resultados em dicionários (para JSON)."""
    return [asdict(result) for result in results]
