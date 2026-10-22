"""Catálogo de modos e fases."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from ..domain.entities import LevelSpec
from ..domain.enums import EnemyKind, GameMode, MapKind
from .editor import LEVEL_SUFFIX, LevelFile, load_level

CHASER = EnemyKind.CHASER
INTERCEPTOR = EnemyKind.INTERCEPTOR
WANDERER = EnemyKind.WANDERER
AMBUSHER = EnemyKind.AMBUSHER


@dataclass(frozen=True, slots=True)
class ModeInfo:
    """Nome e descrição de um modo, para menus e para a API."""

    title: str
    description: str


MODES: dict[GameMode, ModeInfo] = {
    GameMode.CAMPAIGN: ModeInfo("Campanha", "Nove fases em três atos, cada um com seu chefe."),
    GameMode.CLASSIC: ModeInfo("Clássico", "Campo aberto, como no jogo original."),
    GameMode.SURVIVAL: ModeInfo("Sobrevivência", "Ondas de inimigos até você cair."),
    GameMode.CHASE: ModeInfo("Pega-pega", "Três fases focadas em fugir de perseguidores."),
    GameMode.GAUNTLET: ModeInfo("Corredor", "Minas, inimigos e relógio correndo."),
    GameMode.BOSS: ModeInfo("Chefes", "Duas lutas seguidas contra o Guardião."),
    GameMode.ENDLESS: ModeInfo("Infinito", "Fases geradas sem fim, cada vez mais difíceis."),
    GameMode.SANDBOX: ModeInfo("Laboratório", "Uma fase tranquila para experimentar."),
}

_CAMPAIGN: tuple[LevelSpec, ...] = (
    LevelSpec(
        "campaign-1",
        "Caça às Moedas",
        MapKind.SCATTER,
        wall_density=0.04,
        coins=12,
        target=10,
        powerups=2,
    ),
    LevelSpec(
        "campaign-2",
        "Minas Surpresa",
        MapKind.SCATTER,
        wall_density=0.08,
        coins=14,
        target=12,
        mines=16,
        powerups=2,
    ),
    LevelSpec(
        "campaign-3",
        "Pega-Pega",
        MapKind.ROOMS,
        coins=16,
        target=12,
        enemies=(CHASER, WANDERER),
        powerups=3,
        boss_hp=3,
        boss="sentinel",
    ),
    LevelSpec(
        "campaign-4",
        "Corredor de Perigo",
        MapKind.CAVES,
        coins=18,
        target=14,
        enemies=(CHASER, INTERCEPTOR),
        mines=12,
        powerups=3,
        exit_required=True,
    ),
    LevelSpec(
        "campaign-5",
        "Labirinto Nebuloso",
        MapKind.MAZE,
        coins=16,
        target=12,
        enemies=(WANDERER, AMBUSHER, AMBUSHER),
        mines=6,
        powerups=3,
        exit_required=True,
        time_limit=600,
        fog_radius=7,
    ),
    LevelSpec(
        "campaign-6",
        "Guardião das Ruínas",
        MapKind.ROOMS,
        coins=10,
        enemies=(WANDERER,),
        mines=14,
        powerups=4,
        boss_hp=5,
    ),
    LevelSpec(
        "campaign-7",
        "Fuga Final",
        MapKind.HYBRID,
        coins=20,
        target=15,
        enemies=(CHASER, INTERCEPTOR, WANDERER, AMBUSHER),
        mines=14,
        powerups=4,
        exit_required=True,
        time_limit=500,
    ),
    LevelSpec(
        "campaign-8",
        "Coração do Nexus",
        MapKind.CAVES,
        coins=22,
        target=16,
        enemies=(CHASER, INTERCEPTOR, AMBUSHER),
        mines=16,
        powerups=4,
        exit_required=True,
        fog_radius=8,
    ),
    LevelSpec(
        "campaign-9",
        "O Colosso",
        MapKind.ROOMS,
        coins=12,
        enemies=(WANDERER, CHASER),
        mines=10,
        powerups=5,
        boss_hp=7,
        boss="colossus",
    ),
)

# A campanha da 21.0.0: sete fases e a fase 3 sem chefe. Fica guardada só para que
# replays daquela versão (``Replay.version == 1``) continuem conferindo.
_CAMPAIGN_V1: tuple[LevelSpec, ...] = (
    *_CAMPAIGN[:2],
    replace(_CAMPAIGN[2], boss_hp=0, boss="guardian"),
    *_CAMPAIGN[3:7],
)
CAMPAIGN_VERSION = 2
CAMPAIGNS: dict[int, tuple[LevelSpec, ...]] = {1: _CAMPAIGN_V1, CAMPAIGN_VERSION: _CAMPAIGN}

_CLASSIC: tuple[LevelSpec, ...] = (
    LevelSpec("classic-1", "Fase 0 - Moedas", MapKind.OPEN, coins=7, target=20, coin_respawn=True),
    LevelSpec(
        "classic-2",
        "Fase 1 - Minas Surpresa",
        MapKind.OPEN,
        coins=7,
        target=20,
        coin_respawn=True,
        mine_spawn_every=2,
    ),
    LevelSpec(
        "classic-3",
        "Fase 2 - Pega-Pega",
        MapKind.OPEN,
        coins=7,
        target=25,
        enemies=(CHASER,),
        coin_respawn=True,
    ),
)

_SURVIVAL: tuple[LevelSpec, ...] = (
    LevelSpec(
        "survival-1",
        "Última Trincheira",
        MapKind.CAVES,
        coins=10,
        enemies=(WANDERER, CHASER),
        mines=10,
        powerups=3,
        coin_respawn=True,
        enemy_spawn_every=60,
        powerup_spawn_every=45,
    ),
)

_CHASE: tuple[LevelSpec, ...] = (
    LevelSpec(
        "chase-1",
        "Pega-Pega I",
        MapKind.SCATTER,
        wall_density=0.06,
        coins=12,
        target=10,
        enemies=(CHASER,),
        powerups=1,
    ),
    LevelSpec(
        "chase-2",
        "Pega-Pega II",
        MapKind.ROOMS,
        coins=14,
        target=12,
        enemies=(CHASER, INTERCEPTOR),
        powerups=2,
    ),
    LevelSpec(
        "chase-3",
        "Pega-Pega III",
        MapKind.CAVES,
        coins=16,
        target=14,
        enemies=(CHASER, CHASER, INTERCEPTOR, AMBUSHER),
        powerups=3,
        exit_required=True,
    ),
)

_GAUNTLET: tuple[LevelSpec, ...] = (
    LevelSpec(
        "gauntlet-1",
        "Corredor I",
        MapKind.MAZE,
        coins=12,
        target=8,
        enemies=(WANDERER,),
        mines=10,
        powerups=1,
        exit_required=True,
        time_limit=450,
    ),
    LevelSpec(
        "gauntlet-2",
        "Corredor II",
        MapKind.CAVES,
        coins=14,
        target=10,
        enemies=(CHASER, WANDERER),
        mines=20,
        powerups=2,
        exit_required=True,
        time_limit=350,
    ),
    LevelSpec(
        "gauntlet-3",
        "Corredor III",
        MapKind.HYBRID,
        coins=16,
        target=12,
        enemies=(CHASER, INTERCEPTOR, AMBUSHER),
        mines=26,
        powerups=3,
        exit_required=True,
        time_limit=400,
    ),
)

_BOSS: tuple[LevelSpec, ...] = (
    LevelSpec(
        "boss-1", "Guardião das Ruínas", MapKind.ROOMS, coins=8, mines=14, powerups=4, boss_hp=5
    ),
    LevelSpec(
        "boss-2",
        "Guardião Desperto",
        MapKind.HYBRID,
        coins=8,
        enemies=(WANDERER, CHASER),
        mines=18,
        powerups=4,
        boss_hp=8,
    ),
)

_SANDBOX: tuple[LevelSpec, ...] = (
    LevelSpec(
        "sandbox-1",
        "Laboratório",
        MapKind.SCATTER,
        wall_density=0.05,
        coins=12,
        target=10,
        enemies=(WANDERER,),
        mines=4,
        powerups=5,
    ),
)

_FIXED: dict[GameMode, tuple[LevelSpec, ...]] = {
    GameMode.CAMPAIGN: _CAMPAIGN,
    GameMode.CLASSIC: _CLASSIC,
    GameMode.SURVIVAL: _SURVIVAL,
    GameMode.CHASE: _CHASE,
    GameMode.GAUNTLET: _GAUNTLET,
    GameMode.BOSS: _BOSS,
    GameMode.SANDBOX: _SANDBOX,
}

_ENDLESS_MAPS = (MapKind.SCATTER, MapKind.ROOMS, MapKind.CAVES, MapKind.MAZE, MapKind.HYBRID)
_ENDLESS_ROSTER = (WANDERER, CHASER, INTERCEPTOR, AMBUSHER)
ENDLESS_BOSS_EVERY = 5


def endless_level(index: int) -> LevelSpec:
    """Gera a fase ``index`` do modo infinito; a dificuldade cresce com o índice.

    A cada ``ENDLESS_BOSS_EVERY`` fases aparece um chefe com mais vida.
    """
    number = index + 1
    enemy_count = min(8, 1 + index // 2)
    roster = tuple(_ENDLESS_ROSTER[i % len(_ENDLESS_ROSTER)] for i in range(enemy_count))
    map_kind = _ENDLESS_MAPS[index % len(_ENDLESS_MAPS)]
    if number % ENDLESS_BOSS_EVERY == 0:
        return LevelSpec(
            f"endless-{number}",
            f"Fase {number} - Guardião",
            MapKind.ROOMS,
            coins=8,
            enemies=roster[:2],
            mines=min(30, 10 + index),
            powerups=4,
            boss_hp=4 + number // ENDLESS_BOSS_EVERY,
        )
    coins = min(24, 10 + 2 * index)
    return LevelSpec(
        f"endless-{number}",
        f"Fase {number}",
        map_kind,
        wall_density=0.08,
        coins=coins,
        target=coins - 2,
        enemies=roster,
        mines=min(40, 6 + 3 * index),
        powerups=3,
        exit_required=index >= 2,
    )


def _levels(mode: GameMode, campaign: int) -> tuple[LevelSpec, ...]:
    """Fases de um modo fixo; ``campaign`` escolhe a versão da campanha."""
    if mode is GameMode.CAMPAIGN:
        if campaign not in CAMPAIGNS:
            raise ValueError(f"Versão de campanha desconhecida: {campaign!r}.")
        return CAMPAIGNS[campaign]
    return _FIXED[mode]


def level_for(mode: GameMode, index: int, campaign: int = CAMPAIGN_VERSION) -> LevelSpec | None:
    """Devolve a fase ``index`` do modo, ou ``None`` depois da última."""
    if index < 0:
        return None
    if mode is GameMode.ENDLESS:
        return endless_level(index)
    levels = _levels(mode, campaign)
    return levels[index] if index < len(levels) else None


def level_count(mode: GameMode, campaign: int = CAMPAIGN_VERSION) -> int | None:
    """Quantidade de fases do modo; ``None`` para o modo infinito."""
    if mode is GameMode.ENDLESS:
        return None
    return len(_levels(mode, campaign))


def custom_level_names(directory: str | Path) -> list[str]:
    """Nomes (sem extensão) das fases ``.nivel`` da pasta de fases personalizadas."""
    folder = Path(directory)
    if not folder.is_dir():
        return []
    return sorted(path.stem for path in folder.glob(f"*{LEVEL_SUFFIX}"))


def custom_level(name: str, directory: str | Path) -> LevelFile:
    """Carrega uma fase personalizada por caminho ou pelo nome na pasta de fases.

    Levanta ``OSError`` se o arquivo não existe e ``LevelError`` se é inválido.
    """
    path = Path(name)
    if not path.is_file():
        file_name = name if name.endswith(LEVEL_SUFFIX) else name + LEVEL_SUFFIX
        path = Path(directory) / file_name
    return load_level(path)


def daily_seed(day: date | None = None) -> int:
    """Seed do desafio diário: a mesma para todos em um mesmo dia."""
    text = (day or date.today()).isoformat()
    return int(hashlib.sha256(text.encode()).hexdigest()[:12], 16)
