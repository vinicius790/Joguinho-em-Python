"""Testes para o Auto-Battler tático e sistema de telemetria."""

from joguinho_apex.domain.enums import Action, GameMode, GameStatus
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.simulation.auto_battler import (
    AutoBattler,
    TacticalProfile,
)
from joguinho_apex.simulation.telemetry import (
    TelemetryCollector,
    TelemetryReport,
    measure_engine_step,
)


def test_telemetry_collector_lifecycle():
    engine = GameEngine.from_rows(["####", "#O$#", "####"], target=5)
    collector = TelemetryCollector()

    duration_ms = measure_engine_step(engine, Action.RIGHT, collector)
    assert duration_ms >= 0.0
    assert len(collector.metrics) == 1
    assert collector.metrics[0].action == "d"

    report = collector.finish(engine)
    assert isinstance(report, TelemetryReport)
    assert report.total_ticks == 1
    assert report.coins_collected == 1
    assert report.visited_cells_count >= 1

    summary_text = report.render_ascii_summary()
    assert "RELATÓRIO DE TELEMETRIA TÁTICA" in summary_text
    assert "Média por passo" in summary_text

    data = report.to_dict()
    assert "session_id" in data
    assert data["coins_collected"] == 1


def test_auto_battler_execution_profiles():
    for profile in (
        TacticalProfile.BALANCED,
        TacticalProfile.AGGRESSIVE,
        TacticalProfile.SURVIVOR,
        TacticalProfile.COLLECTOR,
    ):
        engine = GameEngine.from_rows(["######", "#O  $#", "######"], target=1)
        battler = AutoBattler(profile=profile)
        result = battler.run_battle(engine, max_ticks=20)
        assert result.status in (GameStatus.WON.value, GameStatus.RUNNING.value)
        assert result.ticks > 0
        assert result.telemetry is not None


def test_auto_battler_skill_allocation():
    engine = GameEngine(10, "sandbox")
    engine.state.player.skill_points = 5
    battler = AutoBattler(profile=TacticalProfile.AGGRESSIVE, auto_skills=True)

    allocated = battler.allocate_skills(engine)
    assert len(allocated) > 0
    assert any(s in engine.state.player.skills for s in allocated)
