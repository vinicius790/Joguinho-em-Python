"""Constantes de regras: pontuação, habilidades, dificuldades e fases do chefe."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import Difficulty, PowerKind

# Pontuação base (multiplicada pelo fator da dificuldade).
SCORE_COIN = 10
SCORE_POWERUP = 5
SCORE_ENEMY = 50
SCORE_BOSS = 500
SCORE_LEVEL = 100
SCORE_PER_HP = 20

# Combo: moedas coletadas com menos de COMBO_WINDOW turnos de intervalo.
COMBO_WINDOW = 12
COMBO_CAP = 10
COMBO_SHIELD_EVERY = 5
MAX_SHIELD = 3

# Habilidades do jogador.
DASH_RANGE = 3
DASH_COOLDOWN = 6
PULSE_RADIUS = 3
PULSE_COOLDOWN = 20
PULSE_STUN = 4
PULSE_BOSS_STUN = 2

# Itens da loja.
BOMB_RADIUS = 2
BOOTS_BONUS = 2
MAX_HP_CAP = 8

# Dano e perigos.
INVULNERABLE_TICKS = 2
FIRE_TTL = 3
MAGNET_RADIUS = 3

# Duração (em turnos) dos power-ups temporários.
POWER_DURATION: dict[PowerKind, int] = {
    PowerKind.FREEZE: 8,
    PowerKind.MAGNET: 25,
    PowerKind.FURY: 12,
}

# Limites de itens criados durante a fase.
MAX_SPAWNED_ENEMIES = 12
MAX_SPAWNED_MINES = 60
SPAWN_ENEMY_DISTANCE = 12
SPAWN_MINE_DISTANCE = 3

# Um nível com limite de tempo concluído em até metade do tempo conta como "rápido".
FAST_CLEAR_FRACTION = 0.5


@dataclass(frozen=True, slots=True)
class DifficultyTuning:
    """Ajustes aplicados por dificuldade.

    ``enemy_speed`` é uma fração ``(passos, turnos)``: ``(2, 3)`` significa que
    os inimigos andam em dois de cada três turnos do jogador.
    """

    player_hp: int
    enemy_speed: tuple[int, int]
    enemy_factor: float
    mine_factor: float
    damage: int
    score_factor: float
    time_factor: float
    powerup_factor: float


TUNINGS: dict[Difficulty, DifficultyTuning] = {
    Difficulty.STORY: DifficultyTuning(5, (1, 2), 0.5, 0.5, 1, 0.5, 1.5, 1.5),
    Difficulty.NORMAL: DifficultyTuning(3, (2, 3), 1.0, 1.0, 1, 1.0, 1.0, 1.0),
    Difficulty.HARD: DifficultyTuning(3, (3, 4), 1.25, 1.3, 1, 1.5, 0.9, 0.8),
    Difficulty.NIGHTMARE: DifficultyTuning(3, (1, 1), 1.5, 1.7, 2, 2.0, 0.8, 0.6),
    Difficulty.APOCALYPSE: DifficultyTuning(3, (1, 1), 2.0, 2.2, 3, 3.0, 0.7, 0.5),
}


_CROSS = ((0, -1), (-1, 0), (0, 1), (1, 0))
_RING = (*_CROSS, (-1, -1), (1, -1), (-1, 1), (1, 1))
_NOVA = (*_RING, (0, -2), (-2, 0), (0, 2), (2, 0))


@dataclass(frozen=True, slots=True)
class BossPhase:
    """Comportamento do chefe em uma faixa de vida.

    ``aura`` são os deslocamentos, a partir do chefe, das células incendiadas
    a cada ``fire_period`` turnos; ``trail`` deixa fogo por onde ele passa.
    ``summon_every`` invoca um perseguidor a cada N turnos e ``mine_trail``
    faz o chefe largar minas por onde passa.
    """

    name: str
    speed: tuple[int, int]
    fire_period: int
    aura: tuple[tuple[int, int], ...]
    trail: bool
    summon_every: int = 0
    mine_trail: bool = False


BOSS_PHASES: tuple[BossPhase, BossPhase, BossPhase] = (
    BossPhase("vigilante", (1, 2), 8, _CROSS, trail=False),
    BossPhase("enfurecido", (2, 3), 6, _RING, trail=True),
    BossPhase("apocalipse", (1, 1), 5, _NOVA, trail=True),
)


@dataclass(frozen=True, slots=True)
class BossProfile:
    """Um chefe: nome com artigo (para mensagens), rótulo do HUD e três fases."""

    title: str
    label: str
    phases: tuple[BossPhase, BossPhase, BossPhase]


BOSSES: dict[str, BossProfile] = {
    "guardian": BossProfile("o Guardião", "Guardião", BOSS_PHASES),
    # Ato I: rápida e sem rastro de fogo, mas chama perseguidores.
    "sentinel": BossProfile(
        "a Sentinela",
        "Sentinela",
        (
            BossPhase("patrulha", (2, 3), 10, _CROSS, trail=False),
            BossPhase("alarme", (2, 3), 8, _CROSS, trail=False, summon_every=25),
            BossPhase("caçada", (1, 1), 6, _RING, trail=False, summon_every=15),
        ),
    ),
    # Ato III: lento, com aura grande, e semeia minas pelo caminho.
    "colossus": BossProfile(
        "o Colosso",
        "Colosso",
        (
            BossPhase("desperto", (1, 3), 6, _RING, trail=False, mine_trail=True),
            BossPhase("sísmico", (1, 2), 5, _NOVA, trail=True, mine_trail=True),
            BossPhase("colapso", (2, 3), 4, _NOVA, trail=True, mine_trail=True, summon_every=30),
        ),
    ),
}


def boss_phase(hp: int, max_hp: int, boss: str = "guardian") -> BossPhase:
    """Escolhe a fase do chefe: acima de 2/3 da vida, acima de 1/3 ou abaixo."""
    phases = BOSSES[boss].phases
    if hp * 3 > max_hp * 2:
        return phases[0]
    if hp * 3 > max_hp:
        return phases[1]
    return phases[2]
