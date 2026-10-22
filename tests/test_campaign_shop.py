"""Campanha com história, chefes por ato, ouro, loja e itens.

Escrito com ``unittest`` para rodar tanto no pytest quanto em
``python -m unittest`` (sem dependências).
"""

import io
import json
import tempfile
import unittest
from pathlib import Path

from joguinho_apex.ai.bot import BotPlayer
from joguinho_apex.cli import TerminalGame
from joguinho_apex.domain.enums import Action, EnemyKind, GameMode, GameStatus
from joguinho_apex.domain.geometry import Position
from joguinho_apex.engine import rules
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.engine.shop import BY_ID, SHOP, TOKENS
from joguinho_apex.levels.catalog import level_count, level_for
from joguinho_apex.levels.story import CHAPTERS, ENDING, chapter_for
from joguinho_apex.persistence.replay import Replay
from joguinho_apex.persistence.sqlite_store import SQLiteStore
from joguinho_apex.render.terminal import panel_lines, render_shop, render_summary

TWO_COINS = ["######", "#O$$ #", "######"]


def shop_engine(gold=100):
    """Partida da campanha parada na loja (fase 1 concluída pelo bot), com ``gold`` de ouro."""
    engine = GameEngine(3, "campaign", "story")
    bot = BotPlayer()
    for _ in range(1500):
        if engine.state.status is not GameStatus.RUNNING:
            break
        engine.step(bot.choose(engine))
    assert engine.state.status is GameStatus.LEVEL_COMPLETE
    engine.state.player.gold = gold
    return engine


class StoryTest(unittest.TestCase):
    def test_campaign_has_three_acts_each_with_its_own_boss(self):
        total = level_count(GameMode.CAMPAIGN)
        specs = [level_for(GameMode.CAMPAIGN, index) for index in range(total)]
        self.assertEqual(total, 9)
        bosses = [(index + 1, spec.boss) for index, spec in enumerate(specs) if spec.boss_hp]
        self.assertEqual(bosses, [(3, "sentinel"), (6, "guardian"), (9, "colossus")])
        acts = [chapter_for(spec.level_id).act for spec in specs]
        self.assertEqual([acts.count(act) for act in dict.fromkeys(acts)], [3, 3, 3])

    def test_every_campaign_level_has_a_chapter_and_other_modes_have_none(self):
        self.assertEqual(set(CHAPTERS), {f"campaign-{number}" for number in range(1, 10)})
        self.assertTrue(all(len(chapter.text) > 60 for chapter in CHAPTERS.values()))
        self.assertIsNone(chapter_for("boss-1"))
        self.assertIsNone(chapter_for("custom"))
        self.assertGreater(len(ENDING), 60)

    def test_terminal_shows_story_then_shop_then_next_chapter(self):
        keys = iter(["enter", "4", "9", "x", "enter", "q"])
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as folder, SQLiteStore(Path(folder) / "j.db") as store:
            game = TerminalGame(store, "Ana", shop_engine, lambda: next(keys), out, color=False)
            game.run(shop_engine())
        text = out.getvalue()
        self.assertIn("Ato I - A Superfície", text)
        self.assertIn("LOJA - fase concluída: Caça às Moedas", text)
        self.assertIn("Comprado: Poção. Ouro restante: 94.", text)
        self.assertIn("Itens: Poção x1", text)
        self.assertIn("Fase 2: Minas Surpresa", text)
        self.assertIn("Fase 2/9: Minas Surpresa", text)
        self.assertLess(text.index("LOJA"), text.index("Fase 2: Minas Surpresa"))

    def test_summary_tells_the_ending_only_for_a_campaign_victory(self):
        engine = GameEngine(1, "campaign")
        engine.state.status = GameStatus.WON
        self.assertIn("a cidade acende", " ".join(render_summary(engine, None, []).split()))
        engine.state.status = GameStatus.LOST
        self.assertNotIn("Colosso tomba", render_summary(engine, None, []))
        other = GameEngine(1, "sandbox")
        other.state.status = GameStatus.WON
        self.assertNotIn("Colosso tomba", render_summary(other, None, []))


class BossTest(unittest.TestCase):
    def test_profiles_have_different_patterns(self):
        self.assertEqual(set(rules.BOSSES), {"guardian", "sentinel", "colossus"})
        self.assertIs(rules.BOSSES["guardian"].phases, rules.BOSS_PHASES)
        patterns = {
            name: [
                (p.speed, p.fire_period, p.trail, p.summon_every, p.mine_trail) for p in boss.phases
            ]
            for name, boss in rules.BOSSES.items()
        }
        self.assertEqual(len({str(value) for value in patterns.values()}), 3)
        self.assertEqual(rules.boss_phase(1, 6, "sentinel").name, "caçada")
        self.assertEqual(rules.boss_phase(6, 6, "colossus").name, "desperto")
        self.assertEqual(rules.boss_phase(6, 6).name, "vigilante")

    def test_sentinel_summons_chasers_only_after_being_hurt(self):
        rows = ["#" * 22, "#O" + " " * 18 + "B#", "#" + " " * 20 + "#", "#" * 22]
        engine = GameEngine.from_rows(rows, boss="sentinel", boss_hp=6)
        boss = engine.state.boss
        boss.stunned = 10_000
        for _ in range(60):
            engine.step(Action.WAIT)
        self.assertEqual(len(engine.state.enemies), 1, "a fase 'patrulha' não invoca")
        boss.hp = 3
        boss.stunned = 0
        engine.state.player.invulnerable = 10_000
        for _ in range(rules.boss_phase(3, 6, "sentinel").summon_every):
            engine.step(Action.WAIT)
        kinds = [enemy.kind for enemy in engine.state.enemies]
        self.assertIn(EnemyKind.CHASER, kinds)
        self.assertIn("Sentinela", engine.state.level.objective)

    def test_colossus_leaves_mines_behind(self):
        rows = ["#" * 30, *["#" + " " * 28 + "#"] * 7, "#" * 30]
        rows[1] = "#O" + " " * 27 + "#"
        rows[4] = "#" + " " * 19 + "B" + " " * 8 + "#"
        engine = GameEngine.from_rows(rows, boss="colossus", boss_hp=9)
        self.assertFalse(engine.state.mines)
        engine.state.player.invulnerable = 10_000
        for _ in range(40):
            engine.step(Action.WAIT)
            engine.state.player.invulnerable = 10_000
        self.assertTrue(engine.state.mines, "o Colosso semeia minas por onde passa")
        self.assertNotIn(engine.state.boss.position, engine.state.mines)

    def test_other_enemies_avoid_the_colossus_mine_in_the_same_turn_regression(self):
        """Bug da revisão: a mina nova não valia para quem andava depois do Colosso."""
        rows = ["##########", "#        #", "#O     BX#", "#        #", "##########"]
        engine = GameEngine.from_rows(rows, boss="colossus", boss_hp=9)
        boss = engine.state.boss
        chaser = next(e for e in engine.state.enemies if e.kind is EnemyKind.CHASER)
        boss.energy, chaser.energy = 2, 1  # os dois andam neste turno, o Colosso primeiro
        engine.step(Action.WAIT)
        self.assertEqual(boss.position, Position(6, 2))
        self.assertIn(Position(7, 2), engine.state.mines)
        self.assertNotIn(chaser.position, engine.state.mines)

    def test_guardian_never_summons_or_lays_mines(self):
        rows = ["#" * 30, *["#" + " " * 28 + "#"] * 7, "#" * 30]
        rows[1] = "#O" + " " * 27 + "#"
        rows[4] = "#" + " " * 19 + "B" + " " * 8 + "#"
        engine = GameEngine.from_rows(rows, boss_hp=9)
        for _ in range(40):
            engine.step(Action.WAIT)
            engine.state.player.invulnerable = 10_000
        self.assertFalse(engine.state.mines)
        self.assertEqual(len(engine.state.enemies), 1)

    def test_boss_level_with_target_needs_the_coins_too(self):
        engine = GameEngine.from_rows(["######", "#O$B #", "######"], target=1, boss_hp=1)
        engine.state.boss.stunned = 99
        engine.step(Action.PULSE)
        self.assertIsNone(engine.state.boss)
        self.assertIs(engine.state.status, GameStatus.RUNNING)
        engine.step(Action.RIGHT)
        self.assertIs(engine.state.status, GameStatus.WON)

    def test_unknown_boss_is_rejected(self):
        with self.assertRaises(ValueError):
            GameEngine.from_rows(["####", "#OB#", "####"], boss="dragao")


class ShopTest(unittest.TestCase):
    def test_each_coin_gives_one_gold(self):
        engine = GameEngine.from_rows(TWO_COINS, target=2)
        engine.step(Action.RIGHT)
        self.assertEqual(engine.state.player.gold, 1)
        self.assertEqual(engine.snapshot()["player"]["gold"], 1)
        self.assertIn("Ouro 1", "\n".join(panel_lines(engine)))

    def test_shop_is_closed_during_a_level(self):
        engine = GameEngine.from_rows(TWO_COINS, target=2)
        engine.state.player.gold = 99
        self.assertFalse(engine.buy("potion"))
        self.assertEqual(engine.state.player.gold, 99)
        self.assertEqual(engine.history, [])

    def test_buying_applies_real_effects_and_spends_gold(self):
        engine = shop_engine()
        player = engine.state.player
        hp, max_hp, shield = player.hp, player.max_hp, player.shield
        for item in ("heart", "shield", "boots", "potion", "bomb", "bomb"):
            self.assertTrue(engine.buy(item), item)
        self.assertEqual((player.hp, player.max_hp), (hp + 1, max_hp + 1))
        self.assertEqual(player.shield, shield + 1)
        self.assertEqual(player.dash_bonus, rules.BOOTS_BONUS)
        self.assertEqual(player.items, {"potion": 1, "bomb": 2})
        spent = sum(BY_ID[item].price for item in ("heart", "shield", "boots", "potion", "bomb"))
        self.assertEqual(player.gold, 100 - spent - BY_ID["bomb"].price)
        self.assertEqual(engine.state.stats.purchases, 6)
        self.assertEqual("".join(engine.history[-6:]), "123455")
        self.assertIn("Botas calçadas", render_shop(engine))

    def test_refusals_cost_nothing(self):
        engine = shop_engine(gold=5)
        self.assertFalse(engine.buy("potion"))
        self.assertIn("Ouro insuficiente", engine.state.message)
        self.assertFalse(engine.buy("espada"))
        engine.state.player.gold = 100
        engine.state.player.shield = rules.MAX_SHIELD
        self.assertFalse(engine.buy("shield"))
        self.assertTrue(engine.buy("boots"))
        self.assertFalse(engine.buy("boots"), "as Botas só podem ser compradas uma vez")
        engine.state.player.max_hp = rules.MAX_HP_CAP
        self.assertFalse(engine.buy("heart"))
        self.assertEqual(engine.state.player.gold, 100 - BY_ID["boots"].price)
        self.assertEqual(engine.state.stats.purchases, 1)

    def test_inventory_follows_the_player_to_the_next_level_and_into_the_save(self):
        engine = shop_engine()
        for item in ("boots", "potion", "bomb"):
            engine.buy(item)
        gold = engine.state.player.gold
        self.assertTrue(engine.next_level())
        player = engine.state.player
        self.assertEqual((player.gold, player.dash_bonus), (gold, rules.BOOTS_BONUS))
        self.assertEqual(player.items, {"potion": 1, "bomb": 1})
        restored = GameEngine.from_dict(json.loads(json.dumps(engine.to_dict())))
        self.assertEqual(restored.state.player.items, {"potion": 1, "bomb": 1})
        self.assertEqual(restored.state.player.gold, gold)
        self.assertEqual(restored.fingerprint(), engine.fingerprint())

    def test_old_saves_without_gold_or_items_still_load(self):
        data = GameEngine(1, "sandbox").to_dict()
        for key in ("gold", "items", "dash_bonus"):
            del data["state"]["player"][key]
        del data["state"]["level"]["boss"]
        for key in ("purchases", "items_used"):
            del data["state"]["stats"][key]
        player = GameEngine.from_dict(data).state.player
        self.assertEqual((player.gold, player.items, player.dash_bonus), (0, {}, 0))

    def test_boots_shorten_the_dash_cooldown(self):
        engine = GameEngine.from_rows(["########", "#O     #", "########"], target=0)
        engine.state.player.dash_bonus = rules.BOOTS_BONUS
        engine.step(Action.DASH)
        self.assertEqual(engine.state.player.dash_cooldown, rules.DASH_COOLDOWN - rules.BOOTS_BONUS)

    def test_potion_heals_and_is_kept_when_health_is_full(self):
        engine = GameEngine.from_rows(TWO_COINS, target=2)
        player = engine.state.player
        player.items = {"potion": 1}
        engine.step(Action.POTION)
        self.assertEqual(player.items, {"potion": 1})
        self.assertIn("Vida cheia", engine.state.message)
        player.hp -= 1
        engine.step(Action.POTION)
        self.assertEqual((player.hp, player.items), (player.max_hp, {}))
        engine.step(Action.POTION)
        self.assertEqual(engine.state.message, "Você não tem Poção.")
        self.assertEqual(engine.state.stats.items_used, 1)

    def test_bomb_hits_enemies_in_range_and_spares_the_player(self):
        engine = GameEngine.from_rows(
            ["#########", "#O X   W#", "# B     #", "#########"], boss_hp=4
        )
        player = engine.state.player
        player.items = {"bomb": 1}
        for enemy in engine.state.enemies:
            enemy.stunned = 99
        engine.step(Action.BOMB)
        kinds = sorted(enemy.kind.value for enemy in engine.state.enemies)
        self.assertEqual(kinds, ["boss", "wanderer"], "o perseguidor a 2 células foi derrotado")
        self.assertEqual(engine.state.boss.hp, 3)
        self.assertEqual((player.hp, player.items), (player.max_hp, {}))
        self.assertEqual(player.position, Position(1, 1))
        engine.step(Action.BOMB)
        self.assertEqual(engine.state.message, "Você não tem Bomba.")

    def test_replay_repeats_purchases_and_item_use(self):
        engine = shop_engine(gold=30)
        engine.buy("potion")
        engine.buy("bomb")
        engine.next_level()
        for action in (Action.BOMB, Action.LEFT, Action.POTION, Action.DASH, Action.WAIT):
            engine.step(action)
        replay = Replay.from_engine(engine)
        self.assertIn(TOKENS["potion"] + TOKENS["bomb"] + ">", replay.actions)
        # O ouro foi ajustado à mão em shop_engine, então refazemos a partir de um motor igual.
        again = shop_engine(gold=30)
        for token in replay.actions[len("".join(again.history)) :]:
            if token == ">":
                again.next_level()
            elif token.isdigit():
                again.buy(SHOP[int(token) - 1].item_id)
            else:
                again.step(Action(token))
        self.assertEqual(again.fingerprint(), engine.fingerprint())

    def test_replay_verifies_a_real_game_with_a_purchase(self):
        engine = GameEngine(3, "campaign", "story")
        bot = BotPlayer()
        while engine.state.status is GameStatus.RUNNING:
            engine.step(bot.choose(engine))
        self.assertGreaterEqual(engine.state.player.gold, BY_ID["potion"].price)
        self.assertTrue(engine.buy("potion"))
        engine.next_level()
        for _ in range(30):
            engine.step(bot.choose(engine))
        replay = Replay.from_engine(engine)
        self.assertIn(TOKENS["potion"], replay.actions)
        self.assertTrue(replay.verify())
        self.assertEqual(replay.play().state.player.items, engine.state.player.items)


class BotItemsTest(unittest.TestCase):
    def test_bot_shops_by_its_list_and_only_between_levels(self):
        engine = shop_engine(gold=30)
        self.assertEqual(BotPlayer.shop(engine), ["potion", "shield", "bomb"])
        self.assertEqual(engine.state.player.gold, 30 - 6 - 8 - 10)
        running = GameEngine.from_rows(TWO_COINS, target=2)
        running.state.player.gold = 99
        self.assertEqual(BotPlayer.shop(running), [])

    def test_bot_drinks_a_potion_at_one_hp_and_bombs_crowds_and_bosses(self):
        bot = BotPlayer()
        engine = GameEngine.from_rows(["#########", "#O     $#", "#########"], target=1)
        player = engine.state.player
        player.items = {"potion": 1}
        self.assertIsNot(bot.choose(engine), Action.POTION)
        player.hp = 1
        self.assertIs(bot.choose(engine), Action.POTION)
        boss = GameEngine.from_rows(["#########", "#O B   $#", "#########"], target=1, boss_hp=3)
        boss.state.player.items = {"bomb": 1}
        self.assertIs(bot.choose(boss), Action.BOMB)
        crowd = GameEngine.from_rows(["#########", "#O X   $#", "# W     #", "#########"], target=1)
        crowd.state.player.items = {"bomb": 1}
        self.assertIs(bot.choose(crowd), Action.BOMB)

    def test_simulated_campaign_buys_and_uses_items(self):
        engine = GameEngine(7, "campaign", "story")
        bot = BotPlayer()
        for _ in range(4000):
            status = engine.state.status
            if status is GameStatus.LEVEL_COMPLETE:
                BotPlayer.shop(engine)
                engine.next_level()
            elif status is GameStatus.RUNNING:
                engine.step(bot.choose(engine))
            else:
                break
        stats = engine.state.stats
        self.assertGreater(stats.purchases, 0)
        self.assertGreater(stats.items_used, 0)
        self.assertTrue(Replay.from_engine(engine).verify())


if __name__ == "__main__":
    unittest.main()
