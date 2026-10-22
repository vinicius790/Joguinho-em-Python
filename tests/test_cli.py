"""Linha de comando: partida no terminal, simulação, benchmark, perfil e replay."""

import io
import json

import pytest

from joguinho_apex.cli import QUICK_SLOT, TerminalGame, main
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.persistence.replay import Replay
from joguinho_apex.persistence.sqlite_store import SQLiteStore
from joguinho_apex.services.achievements import ACHIEVEMENTS

WIN_MAP = ["#####", "#O$ #", "#####"]
LOSE_MAP = ["#####", "#OQ #", "#####"]


def keys(*sequence):
    queue = list(sequence)
    return lambda: queue.pop(0) if queue else "eof"


def run_cli(*argv, stdin="", monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    out = io.StringIO()
    code = main(list(argv), out=out)
    return code, out.getvalue()


@pytest.fixture
def store(tmp_path):
    with SQLiteStore(tmp_path / "jogo.sqlite3") as database:
        yield database


def play(store, rows, *sequence, target=1, hp=None):
    def new_engine():
        # ranked=True: estes mapas de teste valem para perfil, ranking e conquistas.
        engine = GameEngine.from_rows(rows, target=target, ranked=True)
        if hp is not None:
            engine.state.player.hp = hp
        return engine

    out = io.StringIO()
    TerminalGame(store, "Ana", new_engine, keys(*sequence), out, color=False).run(new_engine())
    return out.getvalue()


def test_winning_shows_victory_screen_and_records_everything(store):
    output = play(store, WIN_MAP, "d", "q")
    assert "VITÓRIA!" in output and "Pontuação final: 170" in output
    assert "Nova conquista: Primeira Moeda" in output
    assert "Posição no ranking de Laboratório: 1º" in output
    profile = store.profile("Ana")
    assert profile.games == 1 and profile.wins == 1 and profile.best_score == 170
    assert [entry.score for entry in store.leaderboard("sandbox")] == [170]
    assert "first_coin" in store.achievements("Ana")


def test_losing_shows_game_over_and_counts_a_loss(store):
    output = play(store, LOSE_MAP, "d", "q", hp=1)
    assert "FIM DE JOGO" in output and "Você foi derrotado." in output
    profile = store.profile("Ana")
    assert profile.losses == 1 and profile.wins == 0


def test_play_again_starts_a_fresh_game(store):
    output = play(store, WIN_MAP, "d", "r", "d", "q")
    assert output.count("VITÓRIA!") == 2
    assert store.profile("Ana").games == 2


def test_save_key_writes_a_save_and_finishing_removes_it(store):
    play(store, WIN_MAP, "g", "q")
    assert [save.slot for save in store.list_saves("Ana")] == [QUICK_SLOT]
    assert store.profile("Ana") is None, "sair no meio não conta como partida"
    play(store, WIN_MAP, "g", "d", "q")
    assert store.list_saves("Ana") == []


def test_unknown_key_and_arrows(store):
    output = play(store, ["######", "#O  $#", "######"], "x", "right", "right", "right", "q")
    assert "Tecla sem função: 'x'." in output and "VITÓRIA!" in output


def test_play_command_reads_keys_from_stdin_and_continues(tmp_path, monkeypatch):
    db = str(tmp_path / "cli.sqlite3")
    base = ("--db", db, "--name", "Ana ../x")
    args = (*base, "play", "--mode", "sandbox", "--difficulty", "story", "--seed", "5")
    code, output = run_cli(*args, stdin="d\ng\nq\n", monkeypatch=monkeypatch)
    assert code == 0 and "Laboratório - story - seed 5" in output and "Jogo salvo." in output

    code, output = run_cli(*base, "saves", monkeypatch=monkeypatch)
    assert code == 0 and output.startswith("rapido: sandbox/story, fase 1")

    code, output = run_cli(*base, "play", "--continue", stdin="q\n", monkeypatch=monkeypatch)
    assert code == 0 and "Partida carregada." in output and "Turno 1" in output

    code, output = run_cli(
        "--db", db, "--name", "Bia", "play", "--continue", monkeypatch=monkeypatch
    )
    assert code == 1 and "Não há partida salva para Bia." in output


def test_profile_and_ranking_commands(tmp_path, monkeypatch):
    db = tmp_path / "cli.sqlite3"
    with SQLiteStore(db) as database:
        play(database, WIN_MAP, "d", "q")
    code, output = run_cli("--db", str(db), "--name", "Ana", "profile", monkeypatch=monkeypatch)
    assert code == 0 and "Ana - Novato" in output and "[x] Primeira Moeda" in output
    assert "[ ] Magnata" in output and f"Conquistas: 2/{len(ACHIEVEMENTS)}" in output
    code, output = run_cli("--db", str(db), "ranking", monkeypatch=monkeypatch)
    assert code == 0 and "Ana" in output and "170" in output
    code, output = run_cli("--db", str(db), "--name", "Zé", "profile", monkeypatch=monkeypatch)
    assert "ainda não terminou nenhuma partida" in output
    code, output = run_cli("--db", str(db), "ranking", "--mode", "boss", monkeypatch=monkeypatch)
    assert "Ainda não há partidas registradas." in output


def test_simulate_command_prints_json_summary(monkeypatch):
    code, output = run_cli(
        "simulate", "--episodes", "2", "--mode", "sandbox", "--details", monkeypatch=monkeypatch
    )
    report = json.loads(output)
    assert code == 0 and report["summary"]["episodes"] == 2 and len(report["episodes"]) == 2
    assert report["policy"] == "bot" and report["summary"]["wins"] == 2


def test_benchmark_command_prints_a_table(monkeypatch):
    code, output = run_cli(
        "benchmark",
        "--steps",
        "200",
        "--mode",
        "sandbox",
        "--policy",
        "random",
        monkeypatch=monkeypatch,
    )
    lines = output.strip().splitlines()
    assert code == 0 and len(lines) == 2 and lines[1].split()[0] == "sandbox"
    assert int(lines[1].split()[2]) > 0


def test_replay_command_verifies_file(tmp_path, monkeypatch):
    engine = GameEngine(4, "sandbox")
    path = tmp_path / "r.json"
    Replay.from_engine(engine).save(path)
    code, output = run_cli("replay", str(path), monkeypatch=monkeypatch)
    assert code == 0 and "Replay íntegro" in output
    data = json.loads(path.read_text(encoding="utf-8"))
    data["fingerprint"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output = run_cli("replay", str(path), monkeypatch=monkeypatch)
    assert code == 1 and "NÃO confere" in output
    code, output = run_cli("replay", str(tmp_path / "nada.json"), monkeypatch=monkeypatch)
    assert code == 1 and "Não foi possível ler o replay" in output


def test_no_command_without_terminal_prints_help(monkeypatch):
    code, output = run_cli(monkeypatch=monkeypatch)
    assert code == 0 and "usage: joguinho" in output
    for command in ("play", "simulate", "benchmark", "profile", "ranking", "saves", "replay"):
        assert command in output


def test_invalid_mode_is_rejected_by_the_parser(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run_cli("play", "--mode", "inexistente", monkeypatch=monkeypatch)
    assert "invalid choice" in capsys.readouterr().err


def test_restart_keeps_the_save_of_the_abandoned_game_regression(store):
    """Bug antigo: salvar, reiniciar e terminar a nova partida apagava o save."""
    play(store, ["######", "#O $ #", "######"], "d", "g", "r", "d", "d", "q")
    assert store.profile("Ana").games == 1
    assert [save.slot for save in store.list_saves("Ana")] == [QUICK_SLOT]


@pytest.mark.parametrize(
    "argv",
    [
        ("benchmark", "--steps", "0"),
        ("simulate", "--episodes", "-1"),
        ("simulate", "--max-steps", "0"),
        ("ranking", "--limit", "-5"),
    ],
)
def test_counts_must_be_positive_regression(argv, monkeypatch, capsys):
    """Bug antigo: ``benchmark --steps 0`` terminava com um traceback."""
    with pytest.raises(SystemExit):
        run_cli(*argv, monkeypatch=monkeypatch)
    assert "maior que zero" in capsys.readouterr().err


def test_unreadable_database_and_save_give_clear_messages_regression(tmp_path, monkeypatch):
    """Bug antigo: banco ou save corrompido terminava com um traceback."""
    bad = tmp_path / "ruim.sqlite3"
    bad.write_text("isto não é um banco SQLite", encoding="utf-8")
    code, output = run_cli("--db", str(bad), "profile", monkeypatch=monkeypatch)
    assert code == 2 and "Não foi possível abrir o banco" in output

    db = tmp_path / "ok.sqlite3"
    with SQLiteStore(db) as database:
        database.save_game("Ana", QUICK_SLOT, GameEngine(1, "sandbox"))
        database._execute("UPDATE saves SET payload = ?", ("{",))
    code, output = run_cli(
        "--db", str(db), "--name", "Ana", "play", "--continue", monkeypatch=monkeypatch
    )
    assert code == 1 and "corrompido" in output


def test_cli_skills_command(monkeypatch):
    code, output = run_cli("skills", monkeypatch=monkeypatch)
    assert code == 0
    assert "ÁRVORE DE HABILIDADES" in output
    assert "Pele de Ferro" in output
    assert "Passo Ligeiro" in output

    code, output = run_cli("skills", "--branch", "combat", monkeypatch=monkeypatch)
    assert code == 0
    assert "[COMBAT]" in output
    assert "[AGILITY]" not in output


def test_cli_autobattle_command(monkeypatch):
    code, output = run_cli(
        "autobattle",
        "--profile", "aggressive",
        "--seed", "42",
        "--mode", "sandbox",
        "--max-steps", "50",
        monkeypatch=monkeypatch,
    )
    assert code == 0
    assert "SIMULAÇÃO AUTO-BATTLER" in output
    assert "Perfil Tático: aggressive" in output

    code, output = run_cli(
        "autobattle",
        "--profile", "balanced",
        "--seed", "42",
        "--mode", "sandbox",
        "--max-steps", "50",
        "--json",
        monkeypatch=monkeypatch,
    )
    assert code == 0
    data = json.loads(output)
    assert "telemetry" in data
    assert data["profile"] == "balanced"


def test_cli_export_and_import_save(tmp_path, monkeypatch):
    db = tmp_path / "cli.sqlite3"
    save_file = tmp_path / "partida.save.json"
    with SQLiteStore(db) as database:
        database.save_game("Ana", QUICK_SLOT, GameEngine(42, "sandbox"))

    code, output = run_cli(
        "--db", str(db), "--name", "Ana",
        "export-save", str(save_file),
        monkeypatch=monkeypatch,
    )
    assert code == 0 and "exportada com sucesso" in output
    assert save_file.exists()

    # Import into another slot
    code, output = run_cli(
        "--db", str(db), "--name", "Ana",
        "import-save", str(save_file),
        "--slot", "slot2",
        monkeypatch=monkeypatch,
    )
    assert code == 0 and "importada com sucesso" in output

    with SQLiteStore(db) as database:
        loaded = database.load_game("Ana", "slot2")
        assert loaded.seed == 42

