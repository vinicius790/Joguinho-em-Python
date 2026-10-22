"""Multiplayer local em turnos (versus) e desafio diário com ranking do dia.

Escrito com ``unittest`` para rodar tanto no pytest quanto em
``python -m unittest`` (sem dependências).
"""

import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from joguinho_apex.cli import TerminalGame, _versus_summary, main
from joguinho_apex.domain.enums import Action, GameMode, GameStatus
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.levels.catalog import daily_seed
from joguinho_apex.persistence.sqlite_store import DailyEntry, SQLiteStore
from joguinho_apex.render.terminal import versus_hud
from joguinho_apex.services.versus import VersusMatch

RACE = ["######", "#O $$#", "######"]
DAY = "2026-01-15"


def race():
    return GameEngine.from_rows(RACE, target=2)


def run_cli(*argv, stdin=""):
    out = io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin)):
        code = main(list(argv), out=out)
    return code, out.getvalue()


def finished(score, won=True):
    engine = GameEngine.from_rows(["#####", "#O$ #", "#####"], target=1, ranked=True)
    engine.step(Action.RIGHT)
    engine.state.score = score
    engine.state.status = GameStatus.WON if won else GameStatus.LOST
    return engine


class TempStore(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / "jogo.sqlite3"
        self.store = SQLiteStore(self.db)
        self.addCleanup(self.store.close)


class VersusMatchTest(unittest.TestCase):
    def test_players_alternate_one_action_each_on_identical_maps(self):
        match = VersusMatch(("Ana", "Bia"), race)
        first, second = match.engines
        self.assertIsNot(first, second)
        self.assertEqual(first.state.render_lines(), second.state.render_lines())
        match.step(Action.RIGHT)
        self.assertEqual((match.turn, first.state.tick, second.state.tick), (1, 1, 0))
        match.step(Action.WAIT)
        self.assertEqual((match.turn, first.state.tick, second.state.tick), (0, 1, 1))
        self.assertIs(match.current, first)
        self.assertIsNone(match.winner(), "sem vencedor enquanto alguém joga")

    def test_who_finishes_leaves_the_round_and_the_other_plays_alone(self):
        match = VersusMatch(("Ana", "Bia"), race)
        for action in (Action.RIGHT, Action.WAIT) * 3:
            match.step(action)
        self.assertIs(match.engines[0].state.status, GameStatus.WON)
        self.assertEqual(match.turn, 1)
        match.step(Action.RIGHT)
        self.assertEqual(match.turn, 1, "a vez não volta para quem já terminou")
        self.assertFalse(match.finished)
        match.step(Action.RIGHT)
        match.step(Action.RIGHT)
        self.assertTrue(match.finished)
        ticks = [engine.state.tick for engine in match.engines]
        self.assertEqual(ticks, [3, 6])
        match.step(Action.RIGHT)
        self.assertEqual([engine.state.tick for engine in match.engines], ticks)

    def test_winner_is_who_completed_then_the_highest_score(self):
        def decided(first, second):
            match = VersusMatch(("Ana", "Bia"), race)
            match.engines = (first, second)
            return match.winner()

        self.assertEqual(decided(finished(10), finished(900, won=False)), 0)
        self.assertEqual(decided(finished(10, won=False), finished(5)), 1)
        self.assertEqual(decided(finished(50), finished(80)), 1)
        self.assertEqual(decided(finished(70, won=False), finished(20, won=False)), 0)
        self.assertIsNone(decided(finished(50), finished(50)), "empate")

    def test_level_complete_advances_on_the_same_players_next_turn_and_shop_is_free(self):
        match = VersusMatch(("Ana", "Bia"), lambda: GameEngine(3, "chase", "story"))
        engine = match.engines[0]
        engine.state.status = GameStatus.LEVEL_COMPLETE
        engine.state.player.gold = 20
        self.assertTrue(match.buy("potion"))
        self.assertEqual(match.turn, 0, "comprar não gasta a vez")
        match.step(Action.WAIT)
        self.assertEqual((engine.state.level_index, engine.state.tick, match.turn), (1, 0, 1))
        self.assertEqual(engine.state.player.items, {"potion": 1})

    def test_hud_shows_both_players_and_whose_turn_it_is(self):
        match = VersusMatch(("Ana", "Bia"), race)
        match.step(Action.RIGHT)
        match.step(Action.RIGHT)
        match.step(Action.RIGHT)
        lines = versus_hud(match.names, match.engines, match.turn)
        self.assertEqual(lines[0], "VERSUS - vez de Bia (jogador 2)")
        self.assertTrue(lines[1].startswith("  1 Ana") and lines[2].startswith("> 2 Bia"))
        self.assertIn("10 pts", lines[1])
        self.assertIn("ouro   1", lines[1])
        self.assertIn("jogando", lines[2])


class VersusCliTest(TempStore):
    def test_summary_records_both_profiles_and_names_the_winner(self):
        match = VersusMatch(("Ana", "Bia"), race)
        match.engines = (finished(50), finished(80))
        text = _versus_summary(match, self.store)
        self.assertIn("VERSUS - Vitória de Bia!", text)
        self.assertIn("Ana: 50 pontos", text)
        self.assertEqual(self.store.profile("Ana").games, 1)
        self.assertEqual(self.store.profile("Bia").best_score, 80)
        match.engines = (finished(7), finished(7))
        self.assertIn("Empate!", _versus_summary(match, self.store))

    def test_versus_command_alternates_turns_from_stdin(self):
        self.store.close()
        args = ("--db", str(self.db), "--name", "Ana", "versus", "--name2", "Bia")
        code, output = run_cli(*args, "--mode", "sandbox", "--seed", "5", stdin="d\na\n.\nq\n")
        self.assertEqual(code, 0)
        turns = [line for line in output.splitlines() if line.startswith("VERSUS - vez de")]
        self.assertEqual([line.split()[4] for line in turns], ["Ana", "Bia", "Ana", "Bia"])
        self.assertIn("Laboratório - normal - seed 5", output)

        code, output = run_cli("--db", str(self.db), "--name", "Ana", "versus", "--name2", "Ana")
        self.assertEqual(code, 2)
        self.assertIn("nomes diferentes", output)


class DailyStoreTest(TempStore):
    def test_streak_counts_consecutive_calendar_days_once_across_modes(self):
        for day in ("2026-01-15", "2026-01-16", "2026-01-18"):
            self.store.record_daily(day, "Ana", finished(100))
        # Outra modalidade no mesmo dia não duplica a sequência.
        alternate = GameEngine.from_rows(
            ["#####", "#O$ #", "#####"], target=1, ranked=True
        )
        alternate.state.mode = GameMode.CHASE
        alternate.step(Action.RIGHT)
        alternate.state.status = GameStatus.WON
        self.store.record_daily("2026-01-16", "Ana", alternate)

        streak = self.store.daily_streak("Ana", date.fromisoformat("2026-01-18"))
        self.assertEqual((streak.current, streak.best, streak.played_today), (1, 2, True))

        self.store.record_daily("2026-01-17", "Ana", finished(100))
        streak = self.store.daily_streak("Ana", date.fromisoformat("2026-01-18"))
        self.assertEqual((streak.current, streak.best), (4, 4))

    def test_streak_grace_day_expiry_and_empty_history(self):
        today = date.fromisoformat("2026-01-20")
        self.assertEqual(self.store.daily_streak("Ana", today).current, 0)
        self.store.record_daily("2026-01-19", "Ana", finished(100))
        streak = self.store.daily_streak("Ana", today)
        self.assertEqual((streak.current, streak.best, streak.played_today), (1, 1, False))
        expired = self.store.daily_streak("Ana", date.fromisoformat("2026-01-21"))
        self.assertEqual((expired.current, expired.best), (0, 1))

    def test_streak_ignores_malformed_and_future_dates(self):
        self.store.record_daily("2026-01-20", "Ana", finished(100))
        self.store._execute(
            "INSERT INTO daily_scores(day, profile, score, mode, difficulty, levels, won)"
            " VALUES(?, ?, 0, 'sandbox', 'normal', 0, 0)",
            ("not-a-date", "Ana"),
        )
        self.store.record_daily("2026-01-22", "Ana", finished(100))
        streak = self.store.daily_streak("Ana", date.fromisoformat("2026-01-20"))
        self.assertEqual((streak.current, streak.best), (1, 1))

    def test_best_attempt_per_player_and_position(self):
        self.assertEqual(self.store.record_daily(DAY, "Ana", finished(100)), 1)
        self.assertEqual(self.store.record_daily(DAY, "Bia", finished(300, won=False)), 1)
        self.assertEqual(self.store.record_daily(DAY, "Ana", finished(40, won=False)), 2)
        self.assertEqual(self.store.record_daily(DAY, "Caio", finished(200)), 2)
        board = self.store.daily_leaderboard(DAY, "sandbox", "normal")
        self.assertEqual(
            board,
            [
                DailyEntry("Bia", 300, 1, False, 1),
                DailyEntry("Caio", 200, 1, True, 1),
                DailyEntry("Ana", 100, 1, True, 2),
            ],
        )
        self.assertEqual(self.store.record_daily(DAY, "Ana", finished(999, won=False)), 1)
        top = self.store.daily_leaderboard(DAY, "sandbox", "normal", 1)
        self.assertEqual(top, [DailyEntry("Ana", 999, 1, False, 3)])

    def test_rankings_are_separate_per_day_mode_and_difficulty(self):
        self.store.record_daily(DAY, "Ana", finished(100))
        self.assertEqual(self.store.daily_leaderboard("2026-01-16", "sandbox", "normal"), [])
        self.assertEqual(self.store.daily_leaderboard(DAY, "campaign", "normal"), [])
        self.assertEqual(self.store.daily_leaderboard(DAY, "sandbox", "hard"), [])
        self.assertEqual(self.store.leaderboard(), [], "o ranking geral é outra tabela")

    def test_terminal_game_records_the_daily_result_at_the_end(self):
        def new_engine():
            return GameEngine.from_rows(["#####", "#O$ #", "#####"], target=1, ranked=True)

        keys = iter(["d", "q"])
        out = io.StringIO()
        game = TerminalGame(
            self.store, "Ana", new_engine, lambda: next(keys), out, color=False, daily=DAY
        )
        game.run(new_engine())
        self.assertIn(f"Desafio diário de {DAY}: você está em 1º", out.getvalue())
        self.assertIn("1 tentativa(s)", out.getvalue())
        board = self.store.daily_leaderboard(DAY, "sandbox", "normal")
        self.assertEqual([(entry.profile, entry.won) for entry in board], [("Ana", True)])
        self.assertEqual(self.store.profile("Ana").games, 1, "também conta no perfil")


class DailyCliTest(TempStore):
    def test_seed_comes_from_the_date(self):
        self.assertEqual(daily_seed(date(2026, 1, 15)), daily_seed(date.fromisoformat(DAY)))
        self.assertNotEqual(daily_seed(date(2026, 1, 15)), daily_seed(date(2026, 1, 16)))

    def test_daily_command_plays_the_seed_of_the_day_and_shows_the_ranking(self):
        self.store.record_daily(DAY, "Bia", finished(120))
        self.store.close()
        base = ("--db", str(self.db), "--name", "Ana", "daily", "--date", DAY)
        seed = daily_seed(date.fromisoformat(DAY))

        code, output = run_cli(*base, "--mode", "sandbox", stdin="d\nq\n")
        self.assertEqual(code, 0)
        self.assertIn(f"Laboratório - normal - seed {seed}", output)

        code, output = run_cli(*base, "--mode", "sandbox", "--ranking")
        self.assertEqual(code, 0)
        self.assertIn(f"Desafio diário de {DAY} - Laboratório (normal), seed {seed}", output)
        self.assertIn("Bia", output)
        self.assertIn("120", output)

        code, output = run_cli(*base, "--ranking")
        self.assertIn("Ninguém jogou o desafio deste dia ainda.", output)

        code, output = run_cli("--db", str(self.db), "daily", "--date", "15/01/2026")
        self.assertEqual(code, 2)
        self.assertIn("Data inválida", output)

    def test_play_daily_counts_for_the_daily_ranking_too(self):
        self.store.close()
        today = date.today().isoformat()
        with mock.patch("joguinho_apex.cli.TerminalGame") as game:
            code, _ = run_cli(
                "--db", str(self.db), "--name", "Ana", "play", "--daily",
                "--mode", "sandbox", "--difficulty", "normal",
            )  # fmt: skip
        self.assertEqual(code, 0)
        self.assertEqual(game.call_args.kwargs["daily"], today)
        engine = game.return_value.run.call_args.args[0]
        self.assertEqual(engine.seed, daily_seed())

        with SQLiteStore(self.db) as store:
            store.save_game("Ana", "rapido", GameEngine(daily_seed(), "sandbox"))
            store.save_game("Bia", "rapido", GameEngine(5, "sandbox"))
        for name, expected in (("Ana", today), ("Bia", None)):
            with mock.patch("joguinho_apex.cli.TerminalGame") as game:
                run_cli("--db", str(self.db), "--name", name, "play", "--continue")
            self.assertEqual(game.call_args.kwargs["daily"], expected, name)

        with mock.patch("joguinho_apex.cli.TerminalGame") as game:
            run_cli("--db", str(self.db), "play", "--mode", "sandbox", "--difficulty", "normal")
        self.assertIsNone(game.call_args.kwargs["daily"])

    def test_daily_defaults_to_today(self):
        self.store.close()
        code, output = run_cli("--db", str(self.db), "daily", "--ranking")
        self.assertEqual(code, 0)
        self.assertIn(f"Desafio diário de {date.today().isoformat()}", output)
        self.assertIn(f"seed {daily_seed()}", output)


if __name__ == "__main__":
    unittest.main()
