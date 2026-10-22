"""Regras do motor, testadas em fases desenhadas à mão."""

import random

import pytest

from joguinho_apex.domain.enums import Action, EnemyKind, GameStatus, PowerKind
from joguinho_apex.domain.geometry import Position
from joguinho_apex.engine import rules
from joguinho_apex.engine.engine import GameEngine


def make(rows, **options):
    return GameEngine.from_rows(rows, **options)


def steps(engine, *actions):
    for action in actions:
        engine.step(action)
    return engine.state


# ------------------------------------------------------------------ movimento


def test_move_updates_position_and_tick():
    engine = make(["#####", "#O  #", "#####"])
    state = steps(engine, Action.RIGHT)
    assert state.player.position == Position(2, 1)
    assert state.tick == 1 and state.stats.moves == 1


def test_wall_blocks_but_turn_passes():
    engine = make(["####", "#O #", "####"])
    state = steps(engine, Action.LEFT)
    assert state.player.position == Position(1, 1)
    assert state.message == "Movimento bloqueado."
    assert state.tick == 1 and state.stats.moves == 0


def test_walls_survive_every_step_regression():
    """Bug antigo: o tabuleiro era zerado a cada passo e as paredes sumiam."""
    engine = GameEngine(42, "campaign")
    before = engine.state.board.wall_count()
    drawn = sum(row.count("#") for row in engine.state.render_lines())
    rng = random.Random(1)
    for _ in range(60):
        engine.step(rng.choice(list(Action)))
    assert before > 100
    assert engine.state.board.wall_count() == before
    assert sum(row.count("#") for row in engine.state.render_lines()) == drawn == before


def test_invalid_mode_and_difficulty_are_rejected():
    with pytest.raises(ValueError):
        GameEngine(1, "nao-existe")
    with pytest.raises(ValueError):
        GameEngine(1, "campaign", "impossivel")


# --------------------------------------------------------------- moedas/combo


def test_coins_build_combo_and_grant_shield():
    engine = make(["#########", "#O$$$$$ #", "#########"])
    state = steps(engine, *[Action.RIGHT] * 5)
    assert state.stats.coins == 5 and state.level_coins == 5
    assert state.score == 10 + 20 + 30 + 40 + 50
    assert state.stats.best_combo == 5
    assert state.player.shield == 1


def test_combo_expires_after_window():
    engine = make(["####", "#O$#", "####"])
    state = steps(engine, Action.RIGHT, *[Action.WAIT] * (rules.COMBO_WINDOW - 1))
    assert state.player.combo == 1
    assert steps(engine, Action.WAIT).player.combo == 0


# --------------------------------------------------------------- minas e dano


def test_mine_explodes_once_and_hurts():
    engine = make(["######", "#OQ  #", "######"])
    state = steps(engine, Action.RIGHT)
    assert state.player.hp == 2
    assert not state.mines and state.stats.mines_triggered == 1
    assert state.stats.damage_taken == 1


def test_shield_absorbs_hit():
    engine = make(["######", "#OQ  #", "######"])
    engine.state.player.shield = 1
    state = steps(engine, Action.RIGHT)
    assert state.player.hp == 3 and state.player.shield == 0


def test_mine_chain_reaction_hurts_only_once():
    engine = make(["#######", "#OQQ  #", "#######"])
    state = steps(engine, Action.RIGHT)
    assert state.stats.mines_triggered == 2 and not state.mines
    assert state.player.hp == 2


def test_mine_explosion_defeats_adjacent_enemy():
    engine = make(["#######", "#OQX  #", "#######"])
    state = steps(engine, Action.RIGHT)
    assert state.enemies == []
    assert state.stats.mine_kills == 1 and state.stats.enemies_defeated == 1
    assert state.score == rules.SCORE_ENEMY


def test_enemy_attack_respects_invulnerability():
    engine = make(["#####", "#OX #", "#####"])
    enemy = engine.state.enemies[0]
    enemy.enraged = True
    assert steps(engine, Action.WAIT).player.hp == 2
    assert enemy.position == Position(2, 1), "o inimigo ataca sem entrar na célula"
    assert steps(engine, Action.WAIT).player.hp == 2
    assert steps(engine, Action.WAIT).player.hp == 1


def test_walking_into_enemy_hurts_and_does_not_move():
    engine = make(["#####", "#OX #", "#####"])
    state = steps(engine, Action.RIGHT)
    assert state.player.position == Position(1, 1)
    assert state.player.hp == 2


def test_fire_with_one_turn_left_still_burns_regression():
    """Bug antigo: o fogo perdia duração antes da colisão e nunca queimava."""
    engine = make(["#####", "#O* #", "#####"])
    fire = Position(2, 1)
    engine.state.fires[fire] = 1
    state = steps(engine, Action.RIGHT)
    assert state.player.hp == 2
    assert fire not in state.fires


def test_fire_lasts_its_full_duration():
    engine = make(["######", "#O  *#", "######"])
    fire = Position(4, 1)
    for _ in range(rules.FIRE_TTL - 1):
        assert fire in steps(engine, Action.WAIT).fires
    assert fire not in steps(engine, Action.WAIT).fires


# ---------------------------------------------------------------- habilidades


def test_dash_jumps_mine_collects_and_recharges():
    engine = make(["########", "#O Q$  #", "########"])
    state = steps(engine, Action.DASH)
    assert state.player.position == Position(4, 1)
    assert state.player.hp == 3 and Position(3, 1) in state.mines
    assert state.stats.coins == 1 and state.stats.dashes == 1
    state = steps(engine, Action.DASH)
    assert state.player.position == Position(4, 1)
    assert "recarregando" in state.message


def test_dash_is_ready_again_after_cooldown():
    engine = make(["#" * 14, "#O" + " " * 11 + "#", "#" * 14])
    steps(engine, Action.DASH, *[Action.WAIT] * (rules.DASH_COOLDOWN - 1))
    state = steps(engine, Action.DASH)
    assert state.player.position == Position(1 + 2 * rules.DASH_RANGE, 1)


def test_dash_stops_before_wall_and_enemy():
    engine = make(["####", "#O #", "####"])
    assert steps(engine, Action.DASH).player.position == Position(2, 1)
    engine = make(["######", "#O X #", "######"])
    assert steps(engine, Action.DASH).player.position == Position(2, 1)


def test_pulse_stuns_enemies_in_range():
    engine = make(["#######", "#O X  #", "#######"])
    enemy = engine.state.enemies[0]
    enemy.enraged = True
    state = steps(engine, Action.PULSE)
    assert enemy.stunned == rules.PULSE_STUN - 1
    assert enemy.position == Position(3, 1)
    assert state.player.pulse_cooldown == rules.PULSE_COOLDOWN
    steps(engine, Action.PULSE)
    assert "recarregando" in engine.state.message


# ------------------------------------------------------------------ power-ups


def test_heart_and_shield_powerups():
    engine = make(["######", "#O+S #", "######"])
    engine.state.player.hp = 1
    state = steps(engine, Action.RIGHT)
    assert state.player.hp == 2
    state = steps(engine, Action.RIGHT)
    assert state.player.shield == 2 and state.stats.powerups == 2


def test_magnet_pulls_nearby_coins():
    engine = make(["########", "#OM  $ #", "########"])
    state = steps(engine, Action.RIGHT)
    assert state.player.magnet == rules.POWER_DURATION[PowerKind.MAGNET]
    assert not state.coins and state.stats.coins == 1


def test_freeze_stops_enemies():
    engine = make(["#######", "#OF  X#", "#######"])
    enemy = engine.state.enemies[0]
    enemy.enraged = True
    state = steps(engine, Action.RIGHT, Action.WAIT, Action.WAIT)
    assert state.freeze > 0
    assert enemy.position == Position(5, 1)


def test_fury_defeats_enemy_on_contact():
    engine = make(["#######", "#O!X  #", "#######"])
    state = steps(engine, Action.RIGHT, Action.RIGHT)
    assert state.enemies == []
    assert state.player.position == Position(3, 1)
    assert state.score == rules.SCORE_POWERUP + rules.SCORE_ENEMY


# ----------------------------------------------------------- vitória/derrota


def test_collecting_target_wins_single_level():
    engine = make(["####", "#O$#", "####"], target=1)
    state = steps(engine, Action.RIGHT)
    assert state.status is GameStatus.WON
    bonus = rules.SCORE_LEVEL + rules.SCORE_PER_HP * 3
    assert state.score == rules.SCORE_COIN + bonus
    assert state.stats.levels_completed == 1


def test_exit_stays_locked_until_target():
    engine = make(["#######", "#O E$ #", "#######"], target=1)
    state = steps(engine, Action.RIGHT, Action.RIGHT)
    assert state.player.position == state.exit
    assert not state.exit_open and state.status is GameStatus.RUNNING
    state = steps(engine, Action.RIGHT)
    assert state.exit_open and state.status is GameStatus.RUNNING
    assert steps(engine, Action.LEFT).status is GameStatus.WON


def test_opening_exit_enrages_enemies():
    engine = make(["########", "#O$ E W#", "########"], target=1)
    assert not engine.state.enemies[0].enraged
    steps(engine, Action.RIGHT)
    assert engine.state.enemies[0].enraged


def test_time_limit_loses_the_game():
    engine = make(["######", "#O  $#", "######"], target=1, time_limit=3)
    state = steps(engine, Action.WAIT, Action.WAIT)
    assert state.status is GameStatus.RUNNING and state.time_left == 1
    state = steps(engine, Action.WAIT)
    assert state.status is GameStatus.LOST and state.message == "Tempo esgotado."


def test_death_ends_game_and_further_steps_do_nothing():
    engine = make(["######", "#OQ  #", "######"])
    engine.state.player.hp = 1
    state = steps(engine, Action.RIGHT)
    assert state.status is GameStatus.LOST and state.player.hp == 0
    tick = state.tick
    assert steps(engine, Action.LEFT).tick == tick
    assert engine.next_level() is False


# ----------------------------------------------------------------------- chefe


def test_pulse_hurts_boss_and_killing_it_wins():
    engine = make(["#######", "#O B  #", "#######"], boss_hp=2)
    state = steps(engine, Action.PULSE)
    assert state.boss is not None and state.boss.hp == 1
    assert state.status is GameStatus.RUNNING
    engine.state.player.pulse_cooldown = 0
    state = steps(engine, Action.PULSE)
    assert state.boss is None and state.status is GameStatus.WON
    assert state.stats.bosses_defeated == 1


def test_boss_detonates_mines_and_takes_damage():
    engine = make(["#########", "#O   QB #", "#########"], boss_hp=3)
    engine.state.player.invulnerable = 99
    for _ in range(4):
        engine.step(Action.WAIT)
    assert not engine.state.mines
    assert engine.state.boss is not None and engine.state.boss.hp == 2


def test_boss_aura_burns_around_it_but_never_on_the_player():
    engine = make(["#########", "#O #B   #", "#########"], boss_hp=3)
    period = rules.BOSS_PHASES[0].fire_period
    state = steps(engine, *[Action.WAIT] * period)
    assert Position(5, 1) in state.fires
    assert state.player.position not in state.fires
    state = steps(engine, *[Action.WAIT] * rules.FIRE_TTL)
    assert Position(5, 1) not in state.fires


def test_boss_phases_follow_health():
    names = [rules.boss_phase(hp, 6).name for hp in (6, 5, 4, 3, 2, 1)]
    assert names == [
        "vigilante",
        "vigilante",
        "enfurecido",
        "enfurecido",
        "apocalipse",
        "apocalipse",
    ]


# ------------------------------------------------------------------- inimigos


def test_chaser_follows_and_respects_difficulty_speed():
    corridor = ["#" * 26, "#O" + " " * 22 + "X#", "#" * 26]
    moved = {}
    for difficulty in ("story", "normal", "nightmare"):
        engine = make(corridor, difficulty=difficulty)
        steps(engine, *[Action.WAIT] * 6)
        moved[difficulty] = 24 - engine.state.enemies[0].position.x
    assert moved == {"story": 3, "normal": 4, "nightmare": 6}


def test_enemies_never_cross_mines():
    engine = make(["########", "#O Q  X#", "########"])
    enemy = engine.state.enemies[0]
    enemy.enraged = True
    steps(engine, *[Action.WAIT] * 8)
    assert enemy.position.x > 3 and engine.state.player.hp == 3


def test_ambusher_sleeps_until_player_is_close():
    engine = make(["#" * 14, "#O" + " " * 10 + "A#", "#" * 14])
    ambusher = engine.state.enemies[0]
    steps(engine, *[Action.WAIT] * 5)
    assert not ambusher.enraged and ambusher.position == Position(12, 1)
    assert "z" in engine.state.render_lines()[1]
    steps(engine, *[Action.RIGHT] * 6)
    assert ambusher.enraged and ambusher.position.x < 12


def test_wanderer_ignores_distant_player():
    engine = make(["#" * 24, "#O" + " " * 20 + "W#", "#" * 24])
    steps(engine, *[Action.WAIT] * 12)
    assert engine.state.enemies[0].position.x > 10 and engine.state.player.hp == 3


def test_interceptor_aims_ahead_of_the_player():
    rows = ["#" * 16] + ["#" + " " * 14 + "#"] * 8 + ["#" * 16]
    rows[5] = "#    O         #"
    rows[1] = "#        Y     #"
    interceptor = make(rows)
    rows[1] = "#        X     #"
    chaser = make(rows)
    for engine in (interceptor, chaser):
        engine.state.enemies[0].enraged = True
        engine.step(Action.WAIT)
    assert interceptor.state.enemies[0].position == Position(9, 2)
    assert chaser.state.enemies[0].position == Position(8, 1)
    assert interceptor.state.enemies[0].kind is EnemyKind.INTERCEPTOR


# -------------------------------------------------------- partidas com fases


def test_difficulty_changes_hp_enemies_and_mines():
    assert GameEngine(1, "campaign", "story").state.player.hp == 5
    assert GameEngine(1, "campaign", "normal").state.player.hp == 3
    assert len(GameEngine(3, "chase", "normal").state.enemies) == 1
    assert len(GameEngine(3, "chase", "apocalypse").state.enemies) == 2
    easy = GameEngine(3, "campaign", "story")
    hard = GameEngine(3, "campaign", "apocalypse")
    for engine in (easy, hard):
        engine._start_level(1, engine.state)
    assert len(easy.state.mines) < len(hard.state.mines)


def test_statistics_survive_level_changes_regression():
    """Bug antigo: as estatísticas eram recriadas a cada fase."""
    from joguinho_apex.ai.bot import BotPlayer

    engine = GameEngine(4, "classic")
    bot = BotPlayer()
    while engine.state.status is GameStatus.RUNNING:
        engine.step(bot.choose(engine))
    assert engine.state.status is GameStatus.LEVEL_COMPLETE
    stats, score, coins = engine.state.stats, engine.state.score, engine.state.stats.coins
    assert coins >= 20
    assert engine.next_level() is True
    assert engine.state.stats is stats and engine.state.stats.coins == coins
    assert engine.state.score == score and engine.state.level_index == 1
    assert engine.state.level_coins == 0 and engine.state.status is GameStatus.RUNNING


def test_classic_mode_spawns_mines_and_keeps_coins():
    engine = GameEngine(2, "classic")
    engine._start_level(1, engine.state)
    assert not engine.state.mines
    steps(engine, *[Action.WAIT] * 40)
    assert len(engine.state.mines) >= 10
    assert len(engine.state.coins) == engine.state.level.coins


def test_survival_mode_spawns_enemies_over_time():
    engine = GameEngine(2, "survival")
    start = len(engine.state.enemies)
    engine.state.player.invulnerable = 10_000
    steps(engine, *[Action.WAIT] * 130)
    assert len(engine.state.enemies) > start
    assert engine.state.status is GameStatus.RUNNING


def test_same_seed_and_actions_give_same_state():
    rng = random.Random(9)
    actions = [rng.choice(list(Action)) for _ in range(150)]
    first, second = GameEngine(7, "gauntlet", "hard"), GameEngine(7, "gauntlet", "hard")
    for action in actions:
        first.step(action)
        second.step(action)
    assert first.fingerprint() == second.fingerprint()
    assert (
        GameEngine(8, "gauntlet", "hard").fingerprint()
        != GameEngine(7, "gauntlet", "hard").fingerprint()
    )


def test_fog_hides_distant_cells():
    engine = make(["#" * 40, "#O" + " " * 36 + "$#", "#" * 40], fog_radius=3)
    row = engine.state.render_lines()[1]
    assert row[1] == "O" and row[-2] == "~"
    assert engine.state.render_lines(fog=False)[1][-2] == "$"


def test_enraged_enemy_moves_one_cell_per_turn_regression():
    """Bug antigo: a energia acumulada virava 3 passos no turno em que a saída abria."""
    rows = ["#" * 14, "#O$" + " " * 9 + "X#", "#E" + " " * 11 + "#", "#" * 14]
    engine = make(rows, target=1)
    enemy = engine.state.enemies[0]
    steps(engine, Action.WAIT)
    assert enemy.position.x == 12 and enemy.energy == 2
    steps(engine, Action.RIGHT)
    assert enemy.enraged and enemy.position.x == 11
    steps(engine, Action.WAIT)
    assert enemy.position.x == 10


def test_boss_phase_change_does_not_give_extra_steps_regression():
    engine = make(["#" * 20, "#O" + " " * 16 + "B#", "#" * 20], boss_hp=3)
    boss = engine.state.boss
    boss.hp, boss.energy = 1, 2  # fase "apocalipse" (1 passo por turno) com energia de sobra
    engine.state.player.invulnerable = 99
    steps(engine, Action.WAIT)
    assert boss.position.x == 17


def test_map_with_two_players_is_rejected():
    with pytest.raises(ValueError):
        make(["#####", "#OO #", "#####"])
