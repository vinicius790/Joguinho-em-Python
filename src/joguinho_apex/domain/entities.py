"""Entidades do jogo e descrição de fases."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .enums import EnemyKind, MapKind
from .geometry import Position


@dataclass(slots=True)
class Player:
    """Jogador: vida, escudo, combo, habilidades, efeitos temporários, ouro e itens.

    ``gold`` é a moeda da loja (1 por moeda coletada), ``items`` guarda os
    consumíveis comprados e ``dash_bonus`` é o desconto das Botas na recarga.
    """

    position: Position
    hp: int = 3
    max_hp: int = 3
    shield: int = 0
    combo: int = 0
    combo_timer: int = 0
    invulnerable: int = 0
    facing: tuple[int, int] = (1, 0)
    dash_cooldown: int = 0
    pulse_cooldown: int = 0
    magnet: int = 0
    fury: int = 0
    gold: int = 0
    dash_bonus: int = 0
    items: dict[str, int] = field(default_factory=dict)
    skill_points: int = 0
    skills: set[str] = field(default_factory=set)
    cheat_death_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serializa o jogador para o formato de save."""
        data = asdict(self)
        data["skills"] = sorted(self.skills)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Player:
        """Reconstrói o jogador a partir de um save."""
        fields = dict(data)
        fields["position"] = Position(*fields["position"])
        dx, dy = fields["facing"]
        fields["facing"] = (int(dx), int(dy))
        if "skills" in fields:
            fields["skills"] = set(fields["skills"])
        return cls(**fields)


@dataclass(slots=True)
class Enemy:
    """Inimigo; ``energy`` acumula a velocidade fracionária entre turnos."""

    enemy_id: str
    kind: EnemyKind
    position: Position
    hp: int = 1
    max_hp: int = 1
    energy: int = 0
    stunned: int = 0
    enraged: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serializa o inimigo para o formato de save."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Enemy:
        """Reconstrói o inimigo a partir de um save."""
        fields = dict(data)
        fields["kind"] = EnemyKind(fields["kind"])
        fields["position"] = Position(*fields["position"])
        return cls(**fields)


@dataclass(frozen=True, slots=True)
class LevelSpec:
    """Receita de uma fase: mapa, quantidades e regras de objetivo.

    ``coins`` é o total colocado no mapa e ``target`` quantas são exigidas.
    Os campos ``*_spawn_every`` criam novos itens a cada N turnos durante a
    fase; ``coin_respawn`` mantém sempre ``coins`` moedas no mapa. ``boss`` escolhe
    o perfil do chefe em ``engine.rules.BOSSES``.
    """

    level_id: str
    title: str
    map_kind: MapKind = MapKind.SCATTER
    width: int = 60
    height: int = 30
    wall_density: float = 0.08
    coins: int = 10
    target: int = 0
    enemies: tuple[EnemyKind, ...] = ()
    mines: int = 0
    powerups: int = 0
    boss_hp: int = 0
    exit_required: bool = False
    time_limit: int | None = None
    fog_radius: int = 0
    coin_respawn: bool = False
    mine_spawn_every: int = 0
    enemy_spawn_every: int = 0
    powerup_spawn_every: int = 0
    boss: str = "guardian"

    @property
    def objective(self) -> str:
        """Texto curto do objetivo, mostrado no HUD."""
        if self.boss_hp > 0:
            from ..engine.rules import BOSSES  # import tardio: rules importa este pacote

            extra = f" e colete {self.target} moedas" if self.target else ""
            return f"Derrote {BOSSES[self.boss].title}{extra} (Pulso ou minas)"
        if self.target and self.exit_required:
            return f"Colete {self.target} moedas e alcance a saída (E)"
        if self.target:
            return f"Colete {self.target} moedas"
        if self.exit_required:
            return "Alcance a saída (E)"
        return "Sobreviva o máximo possível"

    def to_dict(self) -> dict[str, Any]:
        """Serializa a receita para o formato de save."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LevelSpec:
        """Reconstrói a receita a partir de um save."""
        fields = dict(data)
        fields["map_kind"] = MapKind(fields["map_kind"])
        fields["enemies"] = tuple(EnemyKind(kind) for kind in fields["enemies"])
        return cls(**fields)


@dataclass(slots=True)
class Statistics:
    """Contadores da partida inteira; não são zerados entre fases."""

    ticks: int = 0
    moves: int = 0
    coins: int = 0
    damage_taken: int = 0
    enemies_defeated: int = 0
    mine_kills: int = 0
    bosses_defeated: int = 0
    mines_triggered: int = 0
    powerups: int = 0
    best_combo: int = 0
    levels_completed: int = 0
    fast_clears: int = 0
    dashes: int = 0
    pulses: int = 0
    purchases: int = 0
    items_used: int = 0
    skills_unlocked: int = 0
    shrines_used: int = 0
    merchant_trades: int = 0
    events_encountered: int = 0
    auto_battler_wins: int = 0
    telemetry_steps: int = 0

    def to_dict(self) -> dict[str, int]:
        """Serializa os contadores."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Statistics:
        """Reconstrói os contadores preservando compatibilidade com saves legados."""
        fields = {
            k: int(v)
            for k, v in data.items()
            if k
            in {
                "ticks",
                "moves",
                "coins",
                "damage_taken",
                "enemies_defeated",
                "mine_kills",
                "bosses_defeated",
                "mines_triggered",
                "powerups",
                "best_combo",
                "levels_completed",
                "fast_clears",
                "dashes",
                "pulses",
                "purchases",
                "items_used",
                "skills_unlocked",
                "shrines_used",
                "merchant_trades",
                "events_encountered",
                "auto_battler_wins",
                "telemetry_steps",
            }
        }
        return cls(**fields)
