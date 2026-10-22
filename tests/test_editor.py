"""Editor de fases: formato .nivel, validação, catálogo e comandos da CLI.

Escrito com ``unittest`` para rodar tanto no pytest quanto em
``python -m unittest`` (sem dependências).
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from joguinho_apex.cli import main
from joguinho_apex.domain.enums import Action, GameStatus
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.levels.catalog import custom_level, custom_level_names
from joguinho_apex.levels.editor import (
    LevelError,
    LevelFile,
    blank_level,
    check,
    format_level,
    load_level,
    paint,
    parse_level,
    save_level,
    validate,
)
from joguinho_apex.render.editor import LevelEditor

GOOD = """; comentário
titulo: Cofre
meta: 2
tempo: 120

#########
#O $ $ E#
#########
"""


def run_cli(*argv, stdin=""):
    out = io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin)):
        code = main(list(argv), out=out)
    return code, out.getvalue()


def problems_of(*rows, **options):
    return validate(LevelFile(tuple(rows), **options))


class FormatTest(unittest.TestCase):
    def test_parse_reads_header_and_map(self):
        level, problems = parse_level(GOOD)
        self.assertEqual(problems, [])
        self.assertEqual(level.title, "Cofre")
        self.assertEqual((level.target, level.time_limit, level.boss_hp), (2, 120, 0))
        self.assertEqual(level.rows, ("#########", "#O $ $ E#", "#########"))

    def test_format_is_the_inverse_of_parse(self):
        level = LevelFile(("#####", "#O$B#", "#####"), "Duelo", 1, 4, 0, 6, "sentinel")
        text = format_level(level)
        self.assertIn("chefe: sentinel", text)
        self.assertNotIn("tempo", text, "valores padrão não são gravados")
        self.assertEqual(parse_level(text), (level, []))

    def test_header_problems_are_reported_with_line_numbers(self):
        _, problems = parse_level("meta: muitas\ncor: azul\nsolto\n###\n#O#\n###\n")
        self.assertEqual(len(problems), 3)
        self.assertIn("Linha 1: 'meta' precisa ser um número", problems[0])
        self.assertIn("Linha 2: chave desconhecida 'cor'", problems[1])
        self.assertIn("Linha 3", problems[2])

    def test_odd_numbers_and_unsafe_titles_are_problems_not_crashes_regression(self):
        """Bug da revisão: '²' e números enormes derrubavam a leitura com ValueError."""
        text = "meta: ²\ntempo: " + "9" * 5000 + "\ntitulo: \x1b[2Jlimpa\n###\n#O#\n###\n"
        level, problems = parse_level(text)
        self.assertEqual(len(problems), 3, problems)
        self.assertIn("Linha 1: 'meta' precisa ser um número", problems[0])
        self.assertIn("Linha 2: 'tempo'", problems[1])
        self.assertIn("Linha 3: 'titulo'", problems[2])
        self.assertEqual(level.title, "Fase personalizada")
        self.assertEqual(parse_level("tempo: 999999\n###\n#O#\n###\n")[1], [])

    def test_map_keeps_trailing_spaces_and_drops_trailing_blank_lines(self):
        level, _ = parse_level("####\n#O $\n####\n\n\n")
        self.assertEqual(level.rows, ("####", "#O $", "####"))


class ValidationTest(unittest.TestCase):
    def test_good_level_has_no_problems(self):
        level, problems = check(GOOD)
        self.assertEqual(problems, [])
        self.assertEqual(validate(blank_level(10, 6)), [])

    def test_each_rule_is_checked(self):
        cases = {
            "não tem mapa": problems_of(),
            "comprimentos diferentes": problems_of("####", "#O$#", "###", target=1),
            "exatamente um jogador (O); tem 0": problems_of("####", "# $#", "####", target=1),
            "exatamente um jogador (O); tem 2": problems_of("####", "#OO#", "####", target=1),
            "Símbolo desconhecido '?' em (2, 1)": problems_of("####", "#O?#", "####"),
            "Chefe desconhecido 'dragao'": problems_of("####", "#OB#", "####", boss="dragao"),
            "maior que as moedas do mapa (1)": problems_of("####", "#O$#", "####", target=3),
            "não tem objetivo": problems_of("####", "#O$#", "####"),
            "não tem chefe (B)": problems_of("####", "#O$#", "####", target=1, boss_hp=4),
            "Só pode haver uma saída": problems_of("#####", "#OEE#", "#####"),
            "Só pode haver um chefe": problems_of("#####", "#OBB#", "#####"),
            "fora do permitido": problems_of("##", "#O", target=0),
            "'vida_chefe' vai de 0 a 30": problems_of("####", "#OB#", "####", boss_hp=999),
        }
        for expected, problems in cases.items():
            with self.subTest(expected=expected):
                self.assertTrue(any(expected in text for text in problems), problems)

    def test_items_behind_walls_or_mines_are_unreachable(self):
        problems = problems_of("#######", "#O#$ E#", "#######", target=1)
        self.assertEqual(
            problems, ["Moeda inalcançável em (3, 1).", "Saída inalcançável em (5, 1)."]
        )
        self.assertEqual(
            problems_of("######", "#OQ$X#", "######", target=1),
            ["Moeda inalcançável em (3, 1).", "Inimigo inalcançável em (4, 1)."],
        )
        self.assertEqual(problems_of("######", "#O Q$#", "#   +#", "######", target=1), [])


class FilesAndCatalogTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def test_save_load_and_play_a_level_until_victory(self):
        path = self.folder / "sub" / "cofre.nivel"
        save_level(path, parse_level(GOOD)[0])
        self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        level = load_level(path)
        engine = GameEngine.from_rows(level.rows, **level.options())
        self.assertEqual(engine.state.level.title, "Cofre")
        self.assertEqual(engine.state.time_limit, 120)
        for _ in range(6):
            engine.step(Action.RIGHT)
        self.assertIs(engine.state.status, GameStatus.WON)

    def test_load_rejects_invalid_files_listing_every_problem(self):
        path = self.folder / "ruim.nivel"
        path.write_text("meta: 5\n####\n#O$#\n####\n", encoding="utf-8")
        with self.assertRaises(LevelError) as caught:
            load_level(path)
        self.assertEqual(len(caught.exception.problems), 1)
        self.assertIn("maior que as moedas", str(caught.exception))

    def test_catalog_finds_levels_by_name_or_path(self):
        save_level(self.folder / "cofre.nivel", parse_level(GOOD)[0])
        save_level(self.folder / "arena.nivel", blank_level(8, 5))
        self.assertEqual(custom_level_names(self.folder), ["arena", "cofre"])
        self.assertEqual(custom_level_names(self.folder / "nada"), [])
        self.assertEqual(custom_level("cofre", self.folder).title, "Cofre")
        self.assertEqual(custom_level("cofre.nivel", self.folder).title, "Cofre")
        by_path = custom_level(str(self.folder / "arena.nivel"), self.folder / "outra")
        self.assertEqual(by_path.title, "Nova fase")
        with self.assertRaises(OSError):
            custom_level("sumiu", self.folder)


class EditorTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def test_paint_keeps_a_single_player(self):
        level = paint(blank_level(6, 4), 3, 2, "O")
        self.assertEqual(level.rows, ("######", "#    #", "#  OE#", "######"))

    def test_editor_moves_paints_changes_target_and_saves(self):
        path = self.folder / "nova.nivel"
        keys = iter(["right", "$", "l", "q", "down", "x", "=", "?", "g", "esc"])
        out = io.StringIO()
        editor = LevelEditor(path, blank_level(8, 5), lambda: next(keys), out, color=False)
        editor.run()
        level = load_level(path)
        self.assertEqual(level.rows[1], "#O$Q   #")
        self.assertEqual(level.rows[2], "#  X   #")
        self.assertEqual(level.target, 1)
        text = out.getvalue()
        self.assertIn("Tecla sem função: '?'.", text)
        self.assertIn("Gravado em", text)
        self.assertIn("Fase válida.", text)

    def test_editor_shows_problems_live_and_stays_inside_the_map(self):
        editor = LevelEditor(
            self.folder / "x.nivel", blank_level(5, 5), lambda: "esc", io.StringIO(), False
        )
        for key in ("up", "up", "left", "left", "."):
            editor.press(key)
        self.assertEqual((editor.x, editor.y), (0, 0))
        self.assertTrue(editor.dirty)
        editor.press("down")
        editor.press("right")
        editor.press(".")
        self.assertIn("exatamente um jogador (O); tem 0", editor.frame())
        self.assertFalse(editor.press("esc"))

    def test_editor_opens_a_one_row_map_regression(self):
        """Bug da revisão: o cursor começava em (1, 1) e saía de mapas mínimos."""
        path = self.folder / "fina.nivel"
        path.write_text("#O$E\n", encoding="utf-8")
        code, output = run_cli("editar", str(path), "--no-color", stdin="esc\n")
        self.assertEqual(code, 0)
        self.assertIn("Cursor: (1, 0) 'O'", output)

    def test_resumed_custom_level_restarts_the_same_level_regression(self):
        """Bug da revisão: R depois de --continue abria o Laboratório do catálogo."""
        path = self.folder / "cofre.nivel"
        save_level(path, parse_level(GOOD)[0])
        db = str(self.folder / "jogo.sqlite3")
        base = ("--db", db, "--name", "Ana", "play")
        code, _ = run_cli(*base, "--level", str(path), stdin="d\ng\nq\n")
        self.assertEqual(code, 0)
        code, output = run_cli(*base, "--continue", stdin="r\nq\n")
        self.assertEqual(code, 0)
        self.assertIn("Partida carregada.", output)
        self.assertIn("Turno 1", output)
        self.assertNotIn("Fase 1/1: Laboratório", output)
        restarted = output[output.rindex("Fase 1/1: Cofre") :]
        self.assertIn("Partida reiniciada.", restarted)
        self.assertIn("Turno 0", restarted)

    def test_custom_level_is_unranked_and_its_replay_verifies(self):
        save_level(self.folder / "cofre.nivel", parse_level(GOOD)[0])
        db = str(self.folder / "jogo.sqlite3")
        with contextlib.chdir(self.folder):
            code, output = run_cli(
                "--db", db, "--name", "Ana", "play", "--level", "cofre.nivel",
                stdin="d\n" * 6 + "p\nq\n",
            )  # fmt: skip
            self.assertEqual(code, 0)
            self.assertIn("VITÓRIA!", output)
            self.assertIn("sem ranking nem conquistas", output)
            self.assertNotIn("Nova conquista", output)
            self.assertIn("Replay salvo em replay-fase-0.json", output)
            code, output = run_cli("replay", "replay-fase-0.json")
        self.assertEqual(code, 0)
        self.assertIn("Replay íntegro", output)
        code, output = run_cli("--db", db, "ranking")
        self.assertIn("Ainda não há partidas registradas.", output)
        code, output = run_cli("--db", db, "--name", "Ana", "profile")
        self.assertIn("Partidas: 1  Vitórias: 1", output)
        self.assertIn("Conquistas: 0/", output)

    def test_cli_validar_editar_and_play_level(self):
        path = self.folder / "cofre.nivel"
        code, output = run_cli("editar", str(self.folder / "cofre"), stdin="right\n$\n=\ng\nesc\n")
        self.assertEqual(code, 0)
        self.assertTrue(path.is_file(), "a extensão .nivel é acrescentada")

        code, output = run_cli("validar", str(path))
        self.assertEqual(code, 0)
        self.assertIn("fase válida - Nova fase (30x12)", output)

        db = str(self.folder / "jogo.sqlite3")
        code, output = run_cli("--db", db, "play", "--level", str(path), stdin="d\nq\n")
        self.assertEqual(code, 0)
        self.assertIn("Fase 1/1: Nova fase", output)
        self.assertIn("Moedas  1/1", output)

        path.write_text("meta: 9\n####\n#O$#\n####\n", encoding="utf-8")
        code, output = run_cli("validar", str(path))
        self.assertEqual(code, 1)
        self.assertIn("1 problema(s)", output)
        code, output = run_cli("--db", db, "play", "--level", str(path))
        self.assertEqual(code, 1)
        self.assertIn("Não foi possível carregar a fase", output)
        code, output = run_cli("validar", str(self.folder / "nada.nivel"))
        self.assertEqual(code, 1)
        self.assertIn("Não foi possível ler", output)

    def test_cli_play_level_by_name_uses_the_levels_folder(self):
        save_level(self.folder / "cofre.nivel", parse_level(GOOD)[0])
        db = str(self.folder / "jogo.sqlite3")
        with mock.patch.dict("os.environ", {"JOGUINHO_LEVELS": str(self.folder)}):
            code, output = run_cli(
                "--db", db, "--name", "Ana", "play", "--level", "cofre", stdin="d\n" * 6 + "q\n"
            )
            self.assertEqual(code, 0)
            self.assertIn("VITÓRIA!", output)
            code, output = run_cli("--db", db, "play", "--level", "outra")
            self.assertEqual(code, 1)
            self.assertIn("Fases em", output)
            self.assertIn("cofre", output)


if __name__ == "__main__":
    unittest.main()
