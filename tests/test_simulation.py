"""Simulação, bot, benchmark e renderização."""

import io

import pytest

from joguinho_apex.ai.bot import BotPlayer
from joguinho_apex.domain.enums import Action, GameStatus
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.render.keys import line_reader
from joguinho_apex.render.terminal import colorize, render_frame
from joguinho_apex.simulation.benchmark import benchmark
from joguinho_apex.simulation.runner import make_policy, percentile, run_episodes, summarize


def test_simulation_is_reproducible():
    first = run_episodes(3, seed=10, mode="chase", policy="bot", max_steps=400)
    assert first == run_episodes(3, seed=10, mode="chase", policy="bot", max_steps=400)
    assert [result.seed for result in first] == [10, 11, 12]
    assert first != run_episodes(3, seed=20, mode="chase", policy="bot", max_steps=400)


def test_bot_beats_the_sandbox_and_outscores_random_play():
    bot = summarize(run_episodes(6, seed=0, mode="sandbox", policy="bot"))
    rand = summarize(run_episodes(6, seed=0, mode="sandbox", policy="random", max_steps=300))
    assert bot["wins"] == 6 and bot["win_rate"] == 1.0
    assert bot["score_mean"] > rand["score_mean"]
    assert bot["episodes"] == bot["wins"] + bot["losses"] + bot["unfinished"]


def test_bot_avoids_mines_and_uses_pulse():
    engine = GameEngine.from_rows(["#######", "#OQ$  #", "#     #", "#######"], target=1)
    bot = BotPlayer()
    while engine.state.status is GameStatus.RUNNING:
        engine.step(bot.choose(engine))
    assert engine.state.status is GameStatus.WON
    assert engine.state.player.hp == 3 and engine.state.stats.mines_triggered == 0
    cornered = GameEngine.from_rows(["#####", "#OX$#", "#####"], target=1)
    assert bot.choose(cornered) is Action.PULSE


def test_summary_and_percentile():
    assert summarize([]) == {"episodes": 0}
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert percentile([10, 20], 0.9) == pytest.approx(19)
    assert percentile([], 0.5) == 0.0
    with pytest.raises(ValueError):
        make_policy("genio")


def test_benchmark_reports_thousands_of_steps_per_second_regression():
    """Bug antigo: ~50 turnos/s por redesenhar o tabuleiro inteiro a cada passo."""
    report = benchmark(steps=1500, seed=1, mode="campaign", policy="random")
    assert report["steps"] == 1500 and report["games"] >= 1
    assert report["engine_steps_per_second"] > 1000
    with pytest.raises(ValueError):
        benchmark(steps=0)


def test_render_frame_shows_hud_legend_and_keys():
    engine = GameEngine(3, "campaign")
    expected = (
        "APEX NEXUS",
        "Fase 1/9: Caça às Moedas",
        "Objetivo: Colete 10 moedas",
        "Vida    3/3 [###]",
        "Dash [E] pronto",
        "Aviso de teste",
        "$ moeda",
        "Q sair",
    )
    for wide in (True, False):
        frame = render_frame(engine, notice="Aviso de teste", wide=wide)
        for text in expected:
            assert text in frame
    lines = render_frame(engine, wide=True).split("\n")
    assert len(lines) == 30 and all(len(line) <= 100 for line in lines)
    colored = colorize("#O $")
    assert "\x1b[" in colored and colored.endswith("\x1b[0m")
    assert colorize("   ") == "   "


def test_line_reader_translates_lines_into_keys():
    read = line_reader(io.StringIO("D\n\nup\n.\n"))
    assert [read(), read(), read(), read(), read()] == ["d", "enter", "up", ".", "eof"]
