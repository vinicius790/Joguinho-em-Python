"""Save/load em SQLite, perfis, ranking, conquistas e replays."""

import json
import random
from dataclasses import asdict
from pathlib import Path

import pytest

from joguinho_apex.ai.bot import BotPlayer
from joguinho_apex.domain.enums import Action, GameStatus
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.persistence.replay import Replay
from joguinho_apex.persistence.sqlite_store import SQLiteStore
from joguinho_apex.services.achievements import ACHIEVEMENTS, evaluate
from joguinho_apex.services.progress import rank_title, record_result

DATA = Path(__file__).resolve().parent / "data"


def play_out(engine, limit=3000):
    bot = BotPlayer()
    for _ in range(limit):
        status = engine.state.status
        if status is GameStatus.LEVEL_COMPLETE:
            engine.next_level()
        elif status is not GameStatus.RUNNING:
            break
        engine.step(bot.choose(engine))
    return engine


def random_actions(count, seed=3):
    rng = random.Random(seed)
    return [rng.choice(list(Action)) for _ in range(count)]


@pytest.fixture
def store(tmp_path):
    with SQLiteStore(tmp_path / "jogo.sqlite3") as database:
        yield database


def test_save_and_load_restore_the_exact_state(store):
    engine = GameEngine(21, "survival", "hard")
    for action in random_actions(40):
        engine.step(action)
    store.save_game("Ana", "rapido", engine)
    loaded = store.load_game("Ana", "rapido")
    assert loaded is not None and loaded is not engine
    assert loaded.fingerprint() == engine.fingerprint()
    assert loaded.state.session_id == engine.state.session_id
    # Continuar as duas partidas dá o mesmo resultado, inclusive nos sorteios.
    for action in random_actions(60, seed=4):
        engine.step(action)
        loaded.step(action)
    assert loaded.fingerprint() == engine.fingerprint()


def test_saves_are_listed_replaced_and_deleted(store):
    engine = GameEngine(1, "sandbox")
    store.save_game("Ana", "rapido", engine)
    engine.step(Action.WAIT)
    store.save_game("Ana", "rapido", engine)
    saves = store.list_saves("Ana")
    assert [(save.slot, save.mode, save.level) for save in saves] == [("rapido", "sandbox", 1)]
    assert store.load_game("Ana", "rapido").state.tick == 1
    assert store.load_game("Bia", "rapido") is None
    assert store.delete_save("Ana", "rapido") is True
    assert store.delete_save("Ana", "rapido") is False and store.list_saves("Ana") == []


def test_custom_level_can_be_saved_and_loaded(store):
    engine = GameEngine.from_rows(["######", "#O$ X#", "######"], target=1)
    store.save_game("Ana", "x", engine)
    loaded = store.load_game("Ana", "x")
    assert loaded.is_custom and loaded.fingerprint() == engine.fingerprint()
    loaded.step(Action.RIGHT)
    assert loaded.state.status is GameStatus.WON


def test_unsupported_save_version_is_rejected():
    data = GameEngine(1, "sandbox").to_dict()
    data["version"] = 999
    with pytest.raises(ValueError):
        GameEngine.from_dict(data)


def test_save_payload_is_plain_json():
    plain = json.loads(json.dumps(GameEngine(1, "boss").to_dict()))
    assert json.loads(json.dumps(GameEngine.from_dict(plain).to_dict())) == plain


def test_finished_game_updates_profile_ranking_and_achievements(store):
    engine = play_out(GameEngine(5, "sandbox"))
    assert engine.state.status is GameStatus.WON
    result = record_result(store, "Ana", engine)
    assert result.profile.games == 1 and result.profile.wins == 1
    assert result.profile.best_score == engine.state.score == result.profile.total_score
    assert result.position == 1
    assert "first_coin" in {item.achievement_id for item in result.new_achievements}
    assert "first_coin" in store.achievements("Ana")

    again = record_result(store, "Ana", play_out(GameEngine(6, "sandbox")))
    assert again.profile.games == 2
    assert "first_coin" not in {item.achievement_id for item in again.new_achievements}
    board = store.leaderboard("sandbox")
    assert len(board) == 2 and board[0].score >= board[1].score
    assert store.leaderboard("campaign") == [] and len(store.leaderboard()) == 2
    assert store.profile("Ninguem") is None


def test_running_game_cannot_enter_the_ranking(store):
    with pytest.raises(ValueError):
        record_result(store, "Ana", GameEngine(1, "sandbox"))
    assert store.leaderboard() == []


def test_achievement_rules():
    engine = GameEngine.from_rows(["####", "#O$#", "####"], target=1, difficulty="nightmare")
    assert evaluate(engine.state) == set()
    engine.step(Action.RIGHT)
    assert evaluate(engine.state) == {"first_coin", "survivor", "nightmare"}
    stats = engine.state.stats
    stats.coins, stats.best_combo, stats.enemies_defeated = 100, 10, 5
    stats.mine_kills = stats.bosses_defeated = stats.fast_clears = 1
    stats.levels_completed = 10
    stats.skills_unlocked = 5
    stats.shrines_used = 1
    stats.merchant_trades = 1
    stats.events_encountered = 3
    stats.auto_battler_wins = 1
    unlocked = evaluate(engine.state, games_played=10)
    assert unlocked == {item.achievement_id for item in ACHIEVEMENTS} - {"champion"}


def test_coins_accumulate_across_levels_so_magnata_is_reachable():
    """Bug antigo: com estatísticas zeradas por fase, 100 moedas era impossível."""
    engine = play_out(GameEngine(3, "classic"), limit=6000)
    assert engine.state.stats.levels_completed >= 2
    assert engine.state.stats.coins >= 40 > engine.state.level.target


def test_fast_clear_counts_for_speedrunner():
    engine = GameEngine.from_rows(["####", "#O$#", "####"], target=1, time_limit=10)
    engine.step(Action.RIGHT)
    assert engine.state.stats.fast_clears == 1 and "speedrunner" in evaluate(engine.state)


def test_rank_titles():
    assert rank_title(0) == "Novato" and rank_title(499) == "Novato"
    assert rank_title(500) == "Explorador" and rank_title(10**6) == "Nexus"


def test_replay_reproduces_the_final_state(tmp_path):
    engine = play_out(GameEngine(12, "chase"))
    replay = Replay.from_engine(engine)
    again = replay.play()
    assert again.fingerprint() == engine.fingerprint()
    assert again.state.score == engine.state.score == replay.score
    assert again.state.level_index == engine.state.level_index
    path = tmp_path / "partida.json"
    replay.save(path)
    assert Replay.load(path) == replay and Replay.load(path).verify()


def test_tampered_replay_fails_verification():
    engine = GameEngine(2, "sandbox")
    for action in random_actions(30):
        engine.step(action)
    replay = Replay.from_engine(engine)
    assert replay.verify()
    data = {
        "seed": replay.seed,
        "mode": replay.mode,
        "difficulty": replay.difficulty,
        "fingerprint": replay.fingerprint,
        "score": replay.score,
    }
    assert not Replay(actions=replay.actions + "d", **data).verify()
    assert not Replay(actions=replay.actions[:-1] + "?", **data).verify()
    assert not Replay(actions=replay.actions, version=99, **data).verify()


def test_custom_level_replay_carries_the_map_and_verifies(tmp_path):
    rows = ["#######", "#O $ X#", "#  B  #", "#######"]
    engine = GameEngine.from_rows(rows, target=1, boss="sentinel", title="Duelo")
    for action in (Action.RIGHT, Action.RIGHT, Action.PULSE, Action.WAIT, Action.DOWN):
        engine.step(action)
    replay = Replay.from_engine(engine)
    assert replay.level is not None and replay.level["rows"] == rows
    assert replay.level["spec"]["boss"] == "sentinel" and replay.level["spec"]["title"] == "Duelo"
    path = tmp_path / "fase.json"
    replay.save(path)
    loaded = Replay.load(path)
    assert loaded == replay and loaded.verify()
    assert loaded.play().state.level.title == "Duelo"
    tampered = {**replay.level, "rows": ["#######", "#O   X#", "#  B  #", "#######"]}
    assert not Replay(**{**asdict(replay), "level": tampered}).verify()
    assert not Replay(**{**asdict(replay), "level": {"rows": rows}}).verify()


def test_replays_of_version_21_0_0_still_verify():
    """Gravados pela 21.0.0 (campanha de 7 fases, sem ouro nem itens) e guardados em tests/data."""
    for name, mode, levels in (("campaign", "campaign", 7), ("boss", "boss", 2)):
        replay = Replay.load(DATA / f"legado-21.0.0-{name}.json")
        assert replay.version == 1 and replay.mode == mode
        engine = replay.play()
        assert engine.state.status is GameStatus.WON and engine.level_total == levels
        assert replay.verify(), name
        assert engine.fingerprint() != replay.fingerprint, "o formato novo tem ouro e itens"
    old = Replay.load(DATA / "legado-21.0.0-campaign.json")
    as_new = Replay(**{**asdict(old), "version": 2, "campaign": 2})
    assert not as_new.verify(), "na campanha nova a fase 3 tem chefe e o mapa diverge"


def test_new_replays_record_the_campaign_version(tmp_path):
    engine = GameEngine(4, "campaign")
    for action in random_actions(20):
        engine.step(action)
    replay = Replay.from_engine(engine)
    assert (replay.version, replay.campaign, replay.level) == (2, 2, None)
    assert replay.verify()
    with pytest.raises(ValueError):
        GameEngine(1, "campaign", campaign=99)


def test_saves_from_21_0_0_continue_in_the_old_campaign():
    data = GameEngine(1, "campaign").to_dict()
    for key in ("campaign", "ranked"):
        del data[key]
    for key in ("gold", "items", "dash_bonus"):
        del data["state"]["player"][key]
    old = GameEngine.from_dict(data)
    assert (old.campaign, old.level_total, old.ranked) == (1, 7, True)
    assert GameEngine.from_dict(GameEngine(1, "campaign").to_dict()).level_total == 9


def test_custom_levels_count_in_the_profile_without_ranking_or_achievements(store):
    engine = GameEngine.from_rows(["####", "#O$#", "####"], target=1, difficulty="nightmare")
    engine.step(Action.RIGHT)
    assert engine.state.status is GameStatus.WON and not engine.ranked
    result = record_result(store, "Ana", engine)
    assert result.position is None and result.new_achievements == ()
    assert (result.profile.games, result.profile.wins, result.profile.coins) == (1, 1, 1)
    assert result.profile.total_score == result.profile.best_score == 0
    assert store.leaderboard() == [] and store.achievements("Ana") == []
    store.save_game("Ana", "x", GameEngine.from_rows(["####", "#O$#", "####"], target=1))
    loaded = store.load_game("Ana", "x")
    assert not loaded.ranked and not loaded.restart().ranked
