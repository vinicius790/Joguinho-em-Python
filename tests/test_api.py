"""API REST: fluxo de jogo, validação, limites e console web."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from joguinho_apex.ai.bot import BotPlayer  # noqa: E402
from joguinho_apex.api.app import create_app  # noqa: E402
from joguinho_apex.config import Settings  # noqa: E402
from joguinho_apex.services.achievements import ACHIEVEMENTS  # noqa: E402


def make_client(tmp_path, **overrides):
    settings = Settings(db_path=str(tmp_path / "api.sqlite3"), **overrides)
    return TestClient(create_app(settings))


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)


def new_game(client, **body):
    response = client.post("/v1/games", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_security_headers(client):
    from joguinho_apex import __version__

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "sessions": 0}
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_game_flow_moves_the_player(client):
    game = new_game(client, seed=9, mode="sandbox", difficulty="normal")
    sid, before = game["session_id"], game["snapshot"]["player"]
    assert game["status"] == "running" and game["snapshot"]["seed"] == 9
    assert len(game["snapshot"]["rows"]) == 30 and len(game["snapshot"]["rows"][0]) == 60
    moved = None
    for action in ("d", "a", "s", "w"):
        response = client.post(f"/v1/games/{sid}/actions", json={"action": action})
        assert response.status_code == 200
        after = response.json()["snapshot"]["player"]
        if (after["x"], after["y"]) != (before["x"], before["y"]):
            moved = action
            break
    assert moved is not None
    assert client.get(f"/v1/games/{sid}").json()["snapshot"]["tick"] >= 1
    events = client.get(f"/v1/games/{sid}/events").json()
    assert events["events"][0]["kind"] == "level_start" and events["last"] >= 1
    assert client.get(f"/v1/games/{sid}/events?since={events['last']}").json()["events"] == []
    assert client.post(f"/v1/games/{sid}/next-level").status_code == 409


def test_shop_opens_only_between_levels(client):
    game = new_game(client, seed=3, mode="campaign", difficulty="story")
    sid = game["session_id"]
    assert game["snapshot"]["player"]["gold"] == 0 and game["snapshot"]["player"]["items"] == {}
    assert client.post(f"/v1/games/{sid}/shop/potion").status_code == 409
    engine = client.app.state.sessions.get(sid).engine
    bot = BotPlayer()
    while engine.state.status.value == "running":
        engine.step(bot.choose(engine))
    assert engine.state.status.value == "level_complete"
    engine.state.player.gold = 7
    assert client.post(f"/v1/games/{sid}/shop/espada").status_code == 404
    bought = client.post(f"/v1/games/{sid}/shop/potion")
    assert bought.status_code == 200
    player = bought.json()["snapshot"]["player"]
    assert player["gold"] == 1 and player["items"] == {"potion": 1}
    refused = client.post(f"/v1/games/{sid}/shop/bomb")
    assert refused.status_code == 409 and "Ouro insuficiente" in refused.json()["detail"]


def test_seed_zero_is_respected_regression(client):
    """Bug antigo: ``seed or 0`` tratava a seed 0 como ausente."""
    first = new_game(client, seed=0, mode="sandbox")["snapshot"]
    second = new_game(client, seed=0, mode="sandbox")["snapshot"]
    other = new_game(client, seed=1, mode="sandbox")["snapshot"]
    assert first["seed"] == 0 and first["rows"] == second["rows"] != other["rows"]


def test_env_seed_is_used_when_request_has_none(tmp_path):
    client = make_client(tmp_path, seed=0)
    assert new_game(client, mode="sandbox")["snapshot"]["seed"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {"mode": "inexistente"},
        {"difficulty": "impossivel"},
        {"seed": -1},
        {"seed": 2**63},
        {"seed": "abc"},
        {"name": "../../etc"},
        {"name": "x" * 25},
        {"mode": "sandbox", "extra": 1},
    ],
)
def test_invalid_game_requests_are_rejected_regression(client, body):
    """Bug antigo: modo e dificuldade inválidos eram aceitos em silêncio."""
    assert client.post("/v1/games", json=body).status_code == 422
    assert client.get("/health").json()["sessions"] == 0


def test_invalid_actions_and_unknown_sessions(client):
    sid = new_game(client, mode="sandbox")["session_id"]
    for body in ({"action": "voar"}, {"action": 7}, {}, {"action": "x" * 500}):
        assert client.post(f"/v1/games/{sid}/actions", json=body).status_code == 422
    assert client.post(f"/v1/games/{sid}/actions", json={"action": "wait"}).status_code == 200
    for path in ("/v1/games/nao-existe", "/v1/games/nao-existe/events"):
        assert client.get(path).status_code == 404
    assert client.post("/v1/games/nao-existe/actions", json={"action": "w"}).status_code == 404
    assert client.delete(f"/v1/games/{sid}").json() == {"deleted": True}
    assert client.delete(f"/v1/games/{sid}").status_code == 404


def test_session_limit_returns_503_regression(tmp_path):
    """Bug antigo: o dicionário global de partidas crescia sem limite."""
    client = make_client(tmp_path, max_sessions=2)
    first = new_game(client, mode="sandbox")["session_id"]
    new_game(client, mode="sandbox")
    assert client.post("/v1/games", json={"mode": "sandbox"}).status_code == 503
    client.delete(f"/v1/games/{first}")
    new_game(client, mode="sandbox")


def test_one_client_cannot_take_every_session(tmp_path):
    client = make_client(tmp_path, max_sessions=10, max_sessions_per_client=2)
    first = new_game(client, mode="sandbox")["session_id"]
    new_game(client, mode="sandbox")
    refused = client.post("/v1/games", json={"mode": "sandbox"})
    assert refused.status_code == 429 and "por cliente" in refused.json()["detail"]
    assert refused.headers["Retry-After"] == "60"
    other = TestClient(client.app, client=("203.0.113.9", 50000))
    assert other.post("/v1/games", json={"mode": "sandbox"}).status_code == 201
    client.delete(f"/v1/games/{first}")
    new_game(client, mode="sandbox")


def test_rate_limit_returns_429_only_on_api_routes(tmp_path):
    client = make_client(tmp_path, rate_limit=3)
    codes = [client.get("/v1/catalog").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert client.get("/health").status_code == 200
    assert client.get("/console/").status_code == 200


def test_catalog_lists_modes_difficulties_and_achievements(client):
    data = client.get("/v1/catalog").json()
    assert set(data["modes"]) == {
        "campaign", "classic", "survival", "chase", "gauntlet", "boss", "endless", "sandbox"
    }  # fmt: skip
    assert len(data["modes"]["campaign"]["levels"]) == 9
    assert data["modes"]["endless"]["endless"] is True
    assert data["difficulties"] == ["story", "normal", "hard", "nightmare", "apocalypse"]
    assert len(data["achievements"]) == len(ACHIEVEMENTS)


def test_finished_named_game_enters_profile_and_leaderboard_once(client):
    game = new_game(client, seed=5, mode="sandbox", name="Ana")
    sid = game["session_id"]
    engine = client.app.state.sessions.get(sid).engine
    bot = BotPlayer()
    result = None
    for _ in range(2000):
        data = client.post(f"/v1/games/{sid}/actions", json={"action": bot.choose(engine)}).json()
        if data["status"] != "running":
            result = data
            break
    assert result is not None and result["status"] == "won"
    assert result["result"]["position"] == 1
    assert "first_coin" in [item["achievement_id"] for item in result["result"]["new_achievements"]]
    again = client.post(f"/v1/games/{sid}/actions", json={"action": "w"}).json()
    assert again["result"] is None, "o resultado só é gravado uma vez"

    board = client.get("/v1/leaderboard?mode=sandbox").json()["entries"]
    assert len(board) == 1 and board[0]["profile"] == "Ana" and board[0]["won"] is True
    profile = client.get("/v1/profiles/Ana").json()
    assert profile["profile"]["games"] == 1 and profile["title"] == "Novato"
    assert client.get("/v1/profiles/Ninguem").status_code == 404
    assert client.get("/v1/leaderboard?mode=errado").status_code == 422
    assert client.get("/v1/leaderboard?limit=0").status_code == 422


def test_save_and_load_through_the_api(client):
    sid = new_game(client, seed=3, mode="sandbox", name="Ana")["session_id"]
    client.post(f"/v1/games/{sid}/actions", json={"action": "."})
    assert client.post(f"/v1/games/{sid}/save").json() == {"saved": True}
    loaded = client.post("/v1/games/load", json={"name": "Ana"})
    assert loaded.status_code == 201
    assert loaded.json()["snapshot"]["tick"] == 1
    # A partida carregada ganha sessão própria e não derruba a original.
    assert loaded.json()["session_id"] != sid
    assert client.get("/health").json()["sessions"] == 2
    assert client.get(f"/v1/games/{sid}/events").json()["events"][0]["kind"] == "level_start"
    assert client.post("/v1/games/load", json={"name": "Bia"}).status_code == 404
    assert client.post("/v1/games/load", json={"name": "../x"}).status_code == 422
    anonymous = new_game(client, mode="sandbox")["session_id"]
    assert client.post(f"/v1/games/{anonymous}/save").status_code == 409


def test_console_is_served_with_csp_and_accessible_markup(client):
    root = client.get("/", follow_redirects=False)
    assert root.status_code in (302, 307) and root.headers["location"] == "/console/"
    page = client.get("/console/")
    assert (
        page.status_code == 200 and "script-src 'self'" in page.headers["Content-Security-Policy"]
    )
    html = page.text
    assert '<html lang="pt-BR">' in html and "<canvas" in html and 'name="viewport"' in html
    assert "onclick" not in html and "aria-live" in html
    script = client.get("/console/app.js").text
    assert "innerHTML" not in script and "keydown" in script and "getContext" in script
    manifest = client.get("/console/manifest.json").json()
    assert manifest["icons"] and manifest["icons"][0]["src"] == "icon.svg"
    assert client.get("/console/icon.svg").status_code == 200
    assert "CACHE_VERSION" in client.get("/console/sw.js").text


def test_finishing_another_game_keeps_the_players_save_regression(client):
    """Bug antigo: o fim de qualquer partida do jogador apagava o save de outra partida."""
    saved = new_game(client, seed=1, mode="sandbox", name="Ana")["session_id"]
    assert client.post(f"/v1/games/{saved}/save").json() == {"saved": True}
    other = new_game(client, seed=5, mode="sandbox", name="Ana")["session_id"]
    engine = client.app.state.sessions.get(other).engine
    bot = BotPlayer()
    for _ in range(2000):
        data = client.post(f"/v1/games/{other}/actions", json={"action": bot.choose(engine)})
        if data.json()["status"] != "running":
            break
    assert data.json()["result"] is not None
    loaded = client.post("/v1/games/load", json={"name": "Ana"})
    assert loaded.status_code == 201 and loaded.json()["snapshot"]["seed"] == 1


def test_corrupted_save_returns_409_regression(client):
    """Bug antigo: um save ilegível derrubava a rota com erro 500."""
    sid = new_game(client, mode="sandbox", name="Ana")["session_id"]
    client.post(f"/v1/games/{sid}/save")
    store = client.app.state.store
    store._execute("UPDATE saves SET payload = ?", ('{"version": 1}',))
    response = client.post("/v1/games/load", json={"name": "Ana"})
    assert response.status_code == 409 and "corrompido" in response.json()["detail"]
