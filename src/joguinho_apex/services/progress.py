"""Fim de partida: atualiza perfil, ranking e conquistas de uma vez."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import GameStatus
from ..engine.engine import GameEngine
from ..persistence.sqlite_store import Profile, SQLiteStore
from .achievements import BY_ID, Achievement, evaluate

RANKS: tuple[tuple[int, str], ...] = (
    (0, "Novato"),
    (500, "Explorador"),
    (1500, "Sobrevivente"),
    (3000, "Caçador"),
    (6000, "Veterano"),
    (10000, "Mestre"),
    (20000, "Lenda"),
    (40000, "Nexus"),
)


def rank_title(total_score: int) -> str:
    """Título do jogador conforme a pontuação acumulada em todas as partidas."""
    title = RANKS[0][1]
    for threshold, name in RANKS:
        if total_score >= threshold:
            title = name
    return title


@dataclass(frozen=True, slots=True)
class GameResult:
    """O que mudou no perfil ao fim de uma partida.

    ``position`` é ``None`` para fases personalizadas, que não entram no ranking.
    """

    profile: Profile
    position: int | None
    new_achievements: tuple[Achievement, ...]

    @property
    def title(self) -> str:
        """Título do jogador depois desta partida."""
        return rank_title(self.profile.total_score)


def record_result(store: SQLiteStore, name: str, engine: GameEngine) -> GameResult:
    """Grava uma partida encerrada: perfil, ranking e conquistas novas.

    Levanta ``ValueError`` se a partida ainda não terminou, para que uma
    partida em andamento nunca entre no ranking. Partidas não ranqueadas
    (``engine.ranked`` falso, como as fases personalizadas) contam só como
    partida no perfil: sem pontuação, ranking nem conquistas, porque um mapa
    feito à mão pode tornar qualquer conquista trivial.
    """
    if engine.state.status not in (GameStatus.WON, GameStatus.LOST):
        raise ValueError("Só partidas encerradas entram no perfil e no ranking.")
    if not engine.ranked:
        return GameResult(store.record_game(name, engine, ranked=False), None, ())
    profile = store.record_game(name, engine)
    unlocked = store.unlock(name, evaluate(engine.state, profile.games))
    position = store.rank_of(engine.state.score, engine.state.mode.value)
    return GameResult(profile, position, tuple(BY_ID[item] for item in unlocked))
