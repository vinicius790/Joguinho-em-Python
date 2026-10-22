"""Sistema de telemetria para coleta de métricas em tempo real e diagnósticos de partida.

Mede desempenho de execução, trajetória de vida, dispersão espacial (heatmap),
índice de risco e eficiência de recursos durante partidas interativas ou automáticas.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from ..domain.enums import EnemyKind, GameStatus
from ..engine.engine import GameEngine


@dataclass(slots=True)
class StepMetric:
    """Métrica individual capturada em um turno."""

    tick: int
    level_index: int
    action: str
    hp: int
    max_hp: int
    shield: int
    gold: int
    score: int
    enemies_alive: int
    nearest_enemy_dist: int
    position: tuple[int, int]
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Serializa a métrica do passo."""
        return asdict(self)


@dataclass(slots=True)
class TelemetryReport:
    """Relatório consolidado de telemetria da partida."""

    session_id: str
    mode: str
    difficulty: str
    status: str
    total_ticks: int
    final_score: int
    final_hp: int
    total_damage_taken: int
    enemies_defeated: int
    coins_collected: int
    skills_unlocked: int
    avg_step_ms: float
    max_step_ms: float
    min_step_ms: float
    visited_cells_count: int
    most_visited_cell: tuple[int, int] | None
    danger_ticks: int
    timeline: list[StepMetric] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converte o relatório para dicionário serializável."""
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "difficulty": self.difficulty,
            "status": self.status,
            "total_ticks": self.total_ticks,
            "final_score": self.final_score,
            "final_hp": self.final_hp,
            "total_damage_taken": self.total_damage_taken,
            "enemies_defeated": self.enemies_defeated,
            "coins_collected": self.coins_collected,
            "skills_unlocked": self.skills_unlocked,
            "avg_step_ms": round(self.avg_step_ms, 3),
            "max_step_ms": round(self.max_step_ms, 3),
            "min_step_ms": round(self.min_step_ms, 3),
            "visited_cells_count": self.visited_cells_count,
            "most_visited_cell": list(self.most_visited_cell) if self.most_visited_cell else None,
            "danger_ticks": self.danger_ticks,
            "timeline_length": len(self.timeline),
        }

    def render_ascii_summary(self) -> str:
        """Renderiza um painel textual detalhado com métricas da telemetria."""
        status_sym = "✓ VITÓRIA" if self.status == GameStatus.WON else "✗ DERROTA"
        lines = [
            "==================================================",
            "        RELATÓRIO DE TELEMETRIA TÁTICA           ",
            "==================================================",
            f" Sessão:    {self.session_id[:8]}... | Status: {status_sym}",
            f" Modo:      {self.mode.upper()} | Dificuldade: {self.difficulty.upper()}",
            f" Turnos:    {self.total_ticks} | Pontuação: {self.final_score}",
            f" Vida Final:{self.final_hp} | Dano Sofrido: {self.total_damage_taken}",
            f" Inimigos:  {self.enemies_defeated} derrotados | Moedas: {self.coins_collected}",
            f" Perícias:  {self.skills_unlocked} desbloqueadas",
            "--------------------------------------------------",
            " DESEMPENHO E LATÊNCIA DO MOTOR:",
            f" Média por passo: {self.avg_step_ms:.3f} ms",
            f" Mínimo / Máximo: {self.min_step_ms:.3f} ms / {self.max_step_ms:.3f} ms",
            "--------------------------------------------------",
            " ANÁLISE ESPACIAL E RISCO:",
            f" Células únicas exploradas: {self.visited_cells_count}",
            f" Célula mais frequentada:   {self.most_visited_cell or 'N/A'}",
            f" Turnos em perigo crítico:  {self.danger_ticks} ({self.danger_ticks / max(1, self.total_ticks) * 100:.1f}%)",
            "==================================================",
        ]
        return "\n".join(lines)

    ascii_dashboard = render_ascii_summary


class TelemetryCollector:
    """Coletor ativo de telemetria acoplado aos passos do motor."""

    def __init__(self, record_timeline: bool = True) -> None:
        """Inicializa o coletor de telemetria."""
        self.record_timeline = record_timeline
        self.metrics: list[StepMetric] = []
        self.cell_visits: Counter[tuple[int, int]] = Counter()
        self._danger_ticks = 0

    def record_step(
        self, engine: GameEngine, action_name: str, duration_ms: float
    ) -> StepMetric:
        """Registra o estado após a execução de uma ação."""
        state = engine.state
        player = state.player
        pos = (player.position.x, player.position.y)
        self.cell_visits[pos] += 1

        nearest_dist = 999
        for enemy in state.enemies:
            dist = enemy.position.manhattan(player.position)
            if dist < nearest_dist:
                nearest_dist = dist

        is_danger = nearest_dist <= 2 or player.hp == 1
        if is_danger:
            self._danger_ticks += 1

        metric = StepMetric(
            tick=state.tick,
            level_index=state.level_index,
            action=action_name,
            hp=player.hp,
            max_hp=player.max_hp,
            shield=player.shield,
            gold=player.gold,
            score=state.score,
            enemies_alive=sum(1 for e in state.enemies if e.kind is not EnemyKind.BOSS),
            nearest_enemy_dist=nearest_dist if nearest_dist != 999 else 0,
            position=pos,
            duration_ms=duration_ms,
        )

        if self.record_timeline:
            self.metrics.append(metric)

        state.stats.telemetry_steps += 1
        return metric

    def finish(self, engine: GameEngine) -> TelemetryReport:
        """Gera o relatório final consolidado."""
        state = engine.state
        total_ticks = len(self.metrics) or state.tick
        durations = [m.duration_ms for m in self.metrics] if self.metrics else [0.0]

        avg_ms = sum(durations) / len(durations) if durations else 0.0
        max_ms = max(durations) if durations else 0.0
        min_ms = min(durations) if durations else 0.0

        most_visited = self.cell_visits.most_common(1)
        most_visited_cell = most_visited[0][0] if most_visited else None

        return TelemetryReport(
            session_id=state.session_id,
            mode=state.mode.value,
            difficulty=state.difficulty.value,
            status=state.status.value,
            total_ticks=total_ticks,
            final_score=state.score,
            final_hp=state.player.hp,
            total_damage_taken=state.stats.damage_taken,
            enemies_defeated=state.stats.enemies_defeated,
            coins_collected=state.stats.coins,
            skills_unlocked=len(state.player.skills),
            avg_step_ms=avg_ms,
            max_step_ms=max_ms,
            min_step_ms=min_ms,
            visited_cells_count=len(self.cell_visits),
            most_visited_cell=most_visited_cell,
            danger_ticks=self._danger_ticks,
            timeline=list(self.metrics),
        )


def measure_engine_step(
    engine: GameEngine, action_val: Any, collector: TelemetryCollector | None = None
) -> float:
    """Executa um passo no motor registrando a medição de tempo e telemetria."""
    t0 = time.perf_counter()
    engine.step(action_val)
    t1 = time.perf_counter()
    duration_ms = (t1 - t0) * 1000.0

    if collector is not None:
        action_str = getattr(action_val, "value", str(action_val))
        collector.record_step(engine, action_str, duration_ms)

    return duration_ms
