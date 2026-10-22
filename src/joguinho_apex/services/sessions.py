"""Sessões de jogo em memória, com limite de quantidade e expiração."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..engine.engine import GameEngine


class SessionLimitError(RuntimeError):
    """O servidor já tem o máximo de partidas ativas."""


class ClientLimitError(SessionLimitError):
    """O cliente (endereço) já tem o máximo de partidas ativas que pode abrir."""


@dataclass(slots=True)
class GameSession:
    """Uma partida ativa na API.

    ``lock`` serializa as ações da mesma partida (as rotas rodam em threads);
    ``recorded`` evita gravar o resultado final mais de uma vez; ``saved``
    indica que o save do jogador é desta partida (salva ou carregada nela).
    """

    engine: GameEngine
    player: str | None
    last_seen: float
    client: str = ""
    recorded: bool = False
    saved: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def session_id(self) -> str:
        """Identificador da sessão (o mesmo do estado do jogo)."""
        return self.engine.state.session_id


class SessionManager:
    """Guarda as partidas ativas e descarta as ociosas.

    Sessões sem uso por mais de ``ttl`` segundos são removidas a cada criação.
    Com o limite atingido, novas partidas são recusadas em vez de derrubar as
    de outros jogadores. ``max_per_client`` impede que um único cliente ocupe
    todas as vagas.
    """

    def __init__(
        self,
        max_sessions: int = 200,
        ttl: float = 1800.0,
        clock: Callable[[], float] = time.monotonic,
        max_per_client: int = 20,
    ) -> None:
        """Configura limites e expiração; ``clock`` existe para os testes."""
        self.max_sessions = max_sessions
        self.max_per_client = max_per_client
        self.ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, GameSession] = {}

    def create(
        self, engine: GameEngine, player: str | None = None, client: str = ""
    ) -> GameSession:
        """Registra uma partida do ``client``.

        Levanta ``ClientLimitError`` se o cliente já tem ``max_per_client``
        partidas ativas e ``SessionLimitError`` se o servidor não tem vaga.
        """
        now = self._clock()
        with self._lock:
            self._purge(now)
            mine = sum(1 for session in self._sessions.values() if session.client == client)
            if mine >= self.max_per_client:
                raise ClientLimitError(
                    "Limite de partidas simultâneas por cliente atingido; encerre uma partida."
                )
            if len(self._sessions) >= self.max_sessions:
                raise SessionLimitError("Limite de partidas simultâneas atingido.")
            session = GameSession(engine, player, now, client)
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> GameSession | None:
        """Devolve a sessão (renovando seu prazo) ou ``None`` se não existe ou expirou."""
        now = self._clock()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if now - session.last_seen > self.ttl:
                del self._sessions[session_id]
                return None
            session.last_seen = now
            return session

    def remove(self, session_id: str) -> bool:
        """Encerra a sessão; devolve ``False`` se ela não existia."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def _purge(self, now: float) -> None:
        """Remove sessões ociosas há mais de ``ttl`` segundos."""
        expired = [
            sid for sid, session in self._sessions.items() if now - session.last_seen > self.ttl
        ]
        for sid in expired:
            del self._sessions[sid]

    def __len__(self) -> int:
        """Quantidade de sessões em memória."""
        with self._lock:
            return len(self._sessions)
