"""Testes de pacotes comunitários, progressão, save, replay e CLI."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from joguinho_apex.cli import main
from joguinho_apex.domain.enums import Action, GameStatus
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.levels.adventure import AdventureError, list_adventures, load_adventure
from joguinho_apex.persistence.replay import Replay


LEVEL_ONE = "titulo: Ponte\nmeta: 1\n\n############\n#O$$$$$$E  #\n############\n"
LEVEL_TWO = "titulo: Torre\nmeta: 1\n\n########\n#O$E   #\n########\n"


class AdventurePackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "ponte.nivel").write_text(LEVEL_ONE, encoding="utf-8")
        (self.root / "torre.nivel").write_text(LEVEL_TWO, encoding="utf-8")
        self.manifest = self.root / "ruinas.aventura.json"
        self.write_manifest()

    def write_manifest(self, **updates: object) -> None:
        data: dict[str, object] = {
            "version": 1,
            "id": "ruinas-do-nexus",
            "title": "As Ruinas do Nexus",
            "description": "Duas provas encadeadas.",
            "author": "Equipe APEX",
            "stages": [
                {"id": "ponte", "file": "ponte.nivel"},
                {"id": "torre", "file": "torre.nivel"},
            ],
        }
        data.update(updates)
        self.manifest.write_text(json.dumps(data), encoding="utf-8")

    def test_loads_manifest_and_preserves_stage_order(self) -> None:
        pack = load_adventure(self.manifest)
        self.assertEqual(pack.pack_id, "ruinas-do-nexus")
        self.assertEqual([stage.stage_id for stage in pack.stages], ["ponte", "torre"])
        self.assertEqual([stage.level.title for stage in pack.stages], ["Ponte", "Torre"])

    def test_rejects_traversal_absolute_and_non_level_paths(self) -> None:
        for unsafe in ("../outside.nivel", str(self.root / "ponte.nivel"), "ponte.txt"):
            with self.subTest(path=unsafe):
                self.write_manifest(stages=[{"id": "ponte", "file": unsafe}, {"id": "torre", "file": "torre.nivel"}])
                with self.assertRaises(AdventureError):
                    load_adventure(self.manifest)

    def test_rejects_duplicate_ids_files_and_json_keys(self) -> None:
        self.write_manifest(stages=[{"id": "igual", "file": "ponte.nivel"}, {"id": "igual", "file": "torre.nivel"}])
        with self.assertRaisesRegex(AdventureError, "id inválido ou repetido"):
            load_adventure(self.manifest)
        self.write_manifest(stages=[{"id": "uma", "file": "ponte.nivel"}, {"id": "duas", "file": "ponte.nivel"}])
        with self.assertRaisesRegex(AdventureError, "Fase repetida"):
            load_adventure(self.manifest)
        self.manifest.write_text('{"version":1,"version":1}', encoding="utf-8")
        with self.assertRaisesRegex(AdventureError, "duplicada"):
            load_adventure(self.manifest)

    def test_rejects_unknown_fields_short_packs_and_invalid_levels(self) -> None:
        self.write_manifest(extra="no")
        with self.assertRaisesRegex(AdventureError, "desconhecidos"):
            load_adventure(self.manifest)
        self.write_manifest(stages=[{"id": "unica", "file": "ponte.nivel"}])
        with self.assertRaisesRegex(AdventureError, "de 2 a 20"):
            load_adventure(self.manifest)
        self.write_manifest()
        (self.root / "torre.nivel").write_text("mapa invalido", encoding="utf-8")
        with self.assertRaisesRegex(AdventureError, "inválida"):
            load_adventure(self.manifest)

    def test_lists_manifest_files_deterministically(self) -> None:
        (self.root / "z.aventura.json").write_text("{}", encoding="utf-8")
        (self.root / "A.aventura.json").write_text("{}", encoding="utf-8")
        self.assertEqual([path.name for path in list_adventures(self.root)], ["A.aventura.json", "ruinas.aventura.json", "z.aventura.json"])

    def test_engine_carries_progress_and_completes_each_stage(self) -> None:
        pack = load_adventure(self.manifest)
        engine = GameEngine.from_levels([(stage.stage_id, stage.level) for stage in pack.stages], seed=12)
        self.assertFalse(engine.ranked)
        self.assertEqual(engine.level_total, 2)
        for _ in range(6):
            engine.step(Action.RIGHT)
        engine.step(Action.RIGHT)
        self.assertIs(engine.state.status, GameStatus.LEVEL_COMPLETE)
        self.assertEqual(engine.state.player.gold, 6)
        self.assertTrue(engine.buy("potion"))
        self.assertTrue(engine.next_level())
        self.assertEqual(engine.state.level_index, 1)
        self.assertEqual(engine.state.player.gold, 0)
        self.assertEqual(engine.state.player.items, {"potion": 1})
        engine.step(Action.RIGHT)
        engine.step(Action.RIGHT)
        self.assertIs(engine.state.status, GameStatus.WON)

    def test_save_restart_and_replay_keep_the_whole_pack(self) -> None:
        pack = load_adventure(self.manifest)
        levels = [(stage.stage_id, stage.level) for stage in pack.stages]
        engine = GameEngine.from_levels(levels, seed=21)
        for _ in range(7):
            engine.step(Action.RIGHT)
        self.assertTrue(engine.buy("potion"))
        engine.next_level()
        for action in (Action.RIGHT,):
            engine.step(action)
        restored = GameEngine.from_dict(json.loads(json.dumps(engine.to_dict())))
        self.assertEqual(restored.fingerprint(), engine.fingerprint())
        self.assertEqual(restored.level_total, 2)
        self.assertEqual(restored.state.level_index, 1)
        replay = Replay.from_engine(engine)
        self.assertTrue(replay.verify())
        restarted = restored.restart()
        self.assertEqual(restarted.state.level_index, 0)
        self.assertEqual(restarted.state.score, 0)

    def test_cli_validates_and_lists_campaigns(self) -> None:
        output = io.StringIO()
        self.assertEqual(main(["aventura", "validar", str(self.manifest)], output), 0)
        self.assertIn("2 fases", output.getvalue())
        output = io.StringIO()
        self.assertEqual(main(["aventura", "listar", str(self.root)], output), 0)
        self.assertIn("ruinas-do-nexus", output.getvalue())

    def test_cli_plays_all_stages_and_records_the_unranked_result(self) -> None:
        database = self.root / "player.sqlite3"
        output = io.StringIO()
        keys = io.StringIO("d\nd\nd\nd\nd\nd\nd\nd\nd\nd\nq\n")
        with patch("sys.stdin", keys):
            result = main(
                ["--db", str(database), "--name", "Aventureiro", "aventura", "jogar", str(self.manifest), "--seed", "7", "--no-color"],
                output,
            )
        self.assertEqual(result, 0)
        self.assertIn("Aventura:", output.getvalue())
        self.assertIn("Vitória", output.getvalue())


if __name__ == "__main__":
    unittest.main()
