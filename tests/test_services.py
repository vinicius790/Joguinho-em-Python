"""Saneamento de nomes, limite de requisições, sessões e configuração."""

import pytest

from joguinho_apex.config import Settings
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.services.rate_limiter import RateLimiter
from joguinho_apex.services.security import is_safe_name, safe_name
from joguinho_apex.services.sessions import ClientLimitError, SessionLimitError, SessionManager


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_safe_name_removes_path_tricks_regression():
    """Bug antigo: ``safe_name('../Alice!!')`` devolvia ``'..Alice'``."""
    assert safe_name("../Alice!!") == "Alice"
    assert ".." not in safe_name("..\\..//etc/passwd")
    assert safe_name("  João   da_Silva-2  ") == "João da_Silva-2"
    assert safe_name("<script>") == "script"
    assert safe_name("...") == "Jogador"
    assert len(safe_name("x" * 100)) == 24


def test_is_safe_name():
    assert is_safe_name("Ana Maria") and is_safe_name("jogador_1")
    assert not is_safe_name("") and not is_safe_name("../x") and not is_safe_name(" Ana")
    assert not is_safe_name("x" * 25)


def test_rate_limiter_blocks_then_recovers():
    clock = Clock()
    limiter = RateLimiter(limit=2, window=10, clock=clock)
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b"), "cada cliente tem o próprio contador"
    clock.now = 10
    assert limiter.allow("a")


def test_rate_limiter_forgets_idle_clients_regression():
    """Bug antigo: o dicionário de clientes crescia para sempre."""
    clock = Clock()
    limiter = RateLimiter(limit=5, window=10, clock=clock)
    for index in range(500):
        limiter.allow(f"cliente-{index}")
    assert len(limiter) == 500
    clock.now = 11
    limiter.allow("novo")
    assert len(limiter) == 1


def test_session_manager_enforces_limit_and_ttl():
    clock = Clock()
    manager = SessionManager(max_sessions=2, ttl=100, clock=clock)
    first = manager.create(GameEngine(1, "sandbox"), "Ana")
    manager.create(GameEngine(2, "sandbox"))
    with pytest.raises(SessionLimitError):
        manager.create(GameEngine(3, "sandbox"))
    assert manager.get(first.session_id) is first and first.player == "Ana"

    clock.now = 90
    assert manager.get(first.session_id) is first, "o uso renova o prazo"
    clock.now = 150
    third = manager.create(GameEngine(3, "sandbox"))
    assert len(manager) == 2, "a sessão ociosa foi descartada para abrir vaga"
    assert manager.get(first.session_id) is first and manager.get(third.session_id) is third

    clock.now = 400
    assert manager.get(first.session_id) is None
    assert manager.remove(third.session_id) is True and manager.remove(third.session_id) is False
    assert manager.get("inexistente") is None


def test_session_manager_limits_each_client():
    manager = SessionManager(max_sessions=10, max_per_client=2)
    manager.create(GameEngine(1, "sandbox"), client="1.1.1.1")
    second = manager.create(GameEngine(2, "sandbox"), client="1.1.1.1")
    with pytest.raises(ClientLimitError):
        manager.create(GameEngine(3, "sandbox"), client="1.1.1.1")
    manager.create(GameEngine(4, "sandbox"), client="2.2.2.2")
    manager.remove(second.session_id)
    manager.create(GameEngine(5, "sandbox"), client="1.1.1.1")
    assert len(manager) == 3 and issubclass(ClientLimitError, SessionLimitError)


def test_settings_from_env():
    settings = Settings.from_env({})
    assert settings.seed is None and settings.api_port == 8000
    assert settings.db_path.endswith("joguinho.sqlite3")
    env = {"JOGUINHO_SEED": "0", "JOGUINHO_DB": "x.db", "JOGUINHO_API_PORT": "9"}
    custom = Settings.from_env(env)
    assert custom.seed == 0 and custom.db_path == "x.db" and custom.api_port == 9
    assert settings.max_sessions_per_client == 20
    assert Settings.from_env({"JOGUINHO_MAX_SESSIONS_PER_CLIENT": "3"}).max_sessions_per_client == 3
    bad_values = (
        {"JOGUINHO_API_PORT": "abc"},
        {"JOGUINHO_MAX_SESSIONS": "0"},
        {"JOGUINHO_MAX_SESSIONS_PER_CLIENT": "0"},
        {"JOGUINHO_SEED": "-1"},
    )
    for bad in bad_values:
        with pytest.raises(ValueError):
            Settings.from_env(bad)
