"""Modo Auto-Battler tático com perfis comportamentais e controle autônomo.

Permite simulações completas orientadas por inteligência artificial,
com suporte a alocação de árvore de habilidades, decisões de eventos,
compras automáticas na loja e geração contínua de telemetria.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..domain.enums import Action, EnemyKind, GameStatus
from ..domain.geometry import Position
from ..engine.engine import GameEngine
from .telemetry import TelemetryCollector, TelemetryReport, measure_engine_step


class TacticalProfile(StrEnum):
    """Perfis comportamentais do Auto-Battler."""

    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    SURVIVOR = "survivor"
    COLLECTOR = "collector"


@dataclass(frozen=True, slots=True)
class AutoBattlerDecision:
    """Decisão tomada pelo Auto-Battler em um turno."""

    action: Action
    profile: TacticalProfile
    reason: str


@dataclass(slots=True)
class AutoBattleResult:
    """Resultado da execução de uma partida ou sequência pelo Auto-Battler."""

    session_id: str
    status: str
    ticks: int
    score: int
    levels_completed: int
    hp: int
    skills_unlocked: list[str]
    telemetry: TelemetryReport


# Ordem prioritária de habilidades por perfil
SKILL_PRIORITIES: dict[TacticalProfile, list[str]] = {
    TacticalProfile.BALANCED: [
        "iron_skin",
        "fleet_foot",
        "golden_touch",
        "shield_master",
        "shockwave",
        "magnetic_aura",
        "long_stride",
        "phase_shift",
        "alchemical_mastery",
        "phoenix_heart",
        "momentum",
        "chrono_master",
    ],
    TacticalProfile.AGGRESSIVE: [
        "shockwave",
        "iron_skin",
        "fleet_foot",
        "shield_master",
        "long_stride",
        "phase_shift",
        "momentum",
        "phoenix_heart",
        "golden_touch",
        "alchemical_mastery",
        "magnetic_aura",
        "chrono_master",
    ],
    TacticalProfile.SURVIVOR: [
        "iron_skin",
        "shield_master",
        "fleet_foot",
        "phase_shift",
        "phoenix_heart",
        "golden_touch",
        "alchemical_mastery",
        "shockwave",
        "long_stride",
        "magnetic_aura",
        "momentum",
        "chrono_master",
    ],
    TacticalProfile.COLLECTOR: [
        "golden_touch",
        "magnetic_aura",
        "fleet_foot",
        "long_stride",
        "iron_skin",
        "alchemical_mastery",
        "shield_master",
        "chrono_master",
        "shockwave",
        "phase_shift",
        "momentum",
        "phoenix_heart",
    ],
}


def _bfs_step(
    board: Any, start: Position, goal: Position, blocked: set[Position]
) -> Position | None:
    """Encontra a próxima célula no caminho mais curto de start até goal."""
    if start == goal:
        return start
    queue = [start]
    parent: dict[Position, Position] = {start: start}
    while queue:
        curr = queue.pop(0)
        if curr == goal:
            step = goal
            while parent[step] != start:
                step = parent[step]
            return step
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nxt = Position(curr.x + dx, curr.y + dy)
            if not (0 <= nxt.x < board.width and 0 <= nxt.y < board.height):
                continue
            if board.blocked(nxt):
                continue
            if nxt in blocked and nxt != goal:
                continue
            if nxt not in parent:
                parent[nxt] = curr
                queue.append(nxt)
    return None


class AutoBattler:
    """Agente de combate tático autônomo."""

    def __init__(
        self,
        profile: TacticalProfile = TacticalProfile.BALANCED,
        auto_skills: bool = True,
        auto_shop: bool = True,
    ) -> None:
        """Inicializa o Auto-Battler com o perfil selecionado."""
        self.profile = profile
        self.auto_skills = auto_skills
        self.auto_shop = auto_shop

    def decide_action(self, engine: GameEngine) -> AutoBattlerDecision:
        """Determina a melhor ação no turno atual com base no estado e perfil."""
        state = engine.state
        player = state.player
        here = player.position

        # 1. Sobrevivência de emergência: se vida crítica, usar poção
        if player.hp <= 1 and player.items.get("potion", 0) > 0:
            return AutoBattlerDecision(Action.POTION, self.profile, "Vida crítica: usando poção")

        # 2. Defesa tática contra ameaças imediatas
        threats = [
            e for e in state.enemies if e.stunned == 0 and e.position.manhattan(here) <= 3
        ]

        # Se cercado e pulso pronto, desferir pulso
        if threats and player.pulse_cooldown == 0:
            return AutoBattlerDecision(Action.PULSE, self.profile, "Pulso tático contra inimigos")

        # Se inimigo adjacente perigoso e sem fúria, tentar bomba ou dash de fuga
        adjacent_enemies = [
            e for e in state.enemies if e.stunned == 0 and e.position.manhattan(here) == 1
        ]
        if adjacent_enemies and player.fury == 0:
            if player.items.get("bomb", 0) > 0:
                return AutoBattlerDecision(Action.BOMB, self.profile, "Inimigo colado: detonando bomba")
            if player.dash_cooldown == 0:
                return AutoBattlerDecision(Action.DASH, self.profile, "Fuga com dash defensivo")

        # 3. Alvos ofensivos com fúria ativa ou perfil agressivo
        if player.fury > 0 and state.enemies:
            nearest_enemy = min(state.enemies, key=lambda e: e.position.manhattan(here))
            blocked: set[Position] = set()
            step_pos = _bfs_step(state.board, here, nearest_enemy.position, blocked)
            if step_pos is not None:
                action = self._action_to_step(here, step_pos)
                if action:
                    return AutoBattlerDecision(action, self.profile, "Ataque com Fúria ativa")

        # 4. Alvos prioritários de mapa: moedas vs saída
        target: Position | None = None
        if state.exit_open and state.exit is not None:
            # Se a saída abriu e perfil é survivor ou balanced, priorizar saída
            if self.profile in (TacticalProfile.SURVIVOR, TacticalProfile.BALANCED) or not state.coins:
                target = state.exit

        if target is None and state.coins:
            target = min(state.coins, key=lambda c: c.manhattan(here))
        elif target is None and state.exit is not None:
            target = state.exit

        if target is not None:
            # Evita células ocupadas por inimigos caso não tenhamos fúria
            blocked = set()
            if player.fury == 0:
                for enemy in state.enemies:
                    if enemy.stunned == 0:
                        blocked.add(enemy.position)
            step_pos = _bfs_step(state.board, here, target, blocked)
            if step_pos is not None:
                action = self._action_to_step(here, step_pos)
                if action:
                    return AutoBattlerDecision(action, self.profile, f"Avançando até {target}")

        # 5. Movimento de escape/sobrevivência caso o caminho ideal esteja bloqueado
        for action in (Action.UP, Action.RIGHT, Action.DOWN, Action.LEFT):
            delta = action.delta
            if delta is None:
                continue
            cand = here.moved(*delta)
            if not state.board.blocked(cand) and not any(e.position == cand for e in state.enemies):
                return AutoBattlerDecision(action, self.profile, "Manobra evasiva segura")

        return AutoBattlerDecision(Action.WAIT, self.profile, "Aguardando abertura tática")

    def _action_to_step(self, from_pos: Position, to_pos: Position) -> Action | None:
        """Mapeia o passo de uma coordenada adjacente para uma ação de movimento."""
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        for action in (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT):
            if action.delta == (dx, dy):
                return action
        return None

    def allocate_skills(self, engine: GameEngine) -> list[str]:
        """Tenta desbloquear habilidades pendentes de acordo com as prioridades do perfil."""
        if not self.auto_skills:
            return []
        unlocked_now: list[str] = []
        priorities = SKILL_PRIORITIES.get(self.profile, SKILL_PRIORITIES[TacticalProfile.BALANCED])
        for skill_id in priorities:
            if engine.can_unlock_skill(skill_id)[0]:
                if engine.unlock_skill(skill_id):
                    unlocked_now.append(skill_id)
        return unlocked_now

    def handle_shop(self, engine: GameEngine) -> list[str]:
        """Realiza compras táticas na loja entre fases."""
        if not self.auto_shop or engine.state.status != GameStatus.LEVEL_COMPLETE:
            return []
        purchases: list[str] = []
        player = engine.state.player
        # Prioriza 1 poção se não tiver
        if player.items.get("potion", 0) == 0 and engine.can_buy("potion"):
            if engine.buy("potion"):
                purchases.append("potion")
        # Se perfil sobrevivente, compra escudo
        if self.profile == TacticalProfile.SURVIVOR and engine.can_buy("shield"):
            if engine.buy("shield"):
                purchases.append("shield")
        # Compra botas se tiver ouro sobrando
        if engine.can_buy("boots"):
            if engine.buy("boots"):
                purchases.append("boots")
        # Compra bomba se sobrar ouro
        if player.items.get("bomb", 0) < 2 and engine.can_buy("bomb"):
            if engine.buy("bomb"):
                purchases.append("bomb")
        return purchases

    def handle_event(self, engine: GameEngine) -> Any:
        """Resolve escolhas de eventos dinâmicos ativos automaticamente."""
        event = engine.active_event
        if event is None:
            return None
        # Seleciona a melhor escolha viável
        player = engine.state.player
        for choice in event.choices:
            if choice.cost_gold <= player.gold and choice.cost_hp < player.hp:
                if not choice.requires_item or player.items.get(choice.requires_item, 0) > 0:
                    return engine.resolve_event_choice(choice.choice_id)
        # Se nenhuma com custo der, pega a última (geralmente recusa/saída segura)
        return engine.resolve_event_choice(event.choices[-1].choice_id)

    def run_battle(
        self,
        engine: GameEngine,
        max_ticks: int = 2000,
        collector: TelemetryCollector | None = None,
    ) -> AutoBattleResult:
        """Executa a partida inteira em modo auto-battler gravando telemetria."""
        telemetry = collector or TelemetryCollector()

        # Alocação inicial de habilidades
        self.allocate_skills(engine)

        for _ in range(max_ticks):
            state = engine.state

            # Trata eventos dinâmicos se ativos
            if engine.active_event is not None:
                self.handle_event(engine)

            # Se a fase foi concluída, gerencia loja/habilidades e avança
            if state.status == GameStatus.LEVEL_COMPLETE:
                self.allocate_skills(engine)
                self.handle_shop(engine)
                engine.next_level()
                continue

            if state.status in (GameStatus.WON, GameStatus.LOST):
                break

            decision = self.decide_action(engine)
            measure_engine_step(engine, decision.action, telemetry)

        # Se venceu a partida, incrementa estatística
        if engine.state.status == GameStatus.WON:
            engine.state.stats.auto_battler_wins += 1

        report = telemetry.finish(engine)
        return AutoBattleResult(
            session_id=engine.state.session_id,
            status=engine.state.status.value,
            ticks=engine.state.tick,
            score=engine.state.score,
            levels_completed=engine.state.stats.levels_completed,
            hp=engine.state.player.hp,
            skills_unlocked=sorted(engine.state.player.skills),
            telemetry=report,
        )
