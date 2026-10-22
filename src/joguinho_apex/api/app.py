"""API REST do jogo e console web em ``/console``.

Requer os extras ``api`` (``pip install -e ".[api]"``).
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from fastapi import FastAPI, HTTPException, Query, Request, Response
    from fastapi.responses import JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:
    FastAPI = Any  # type: ignore[misc,assignment]
    HTTPException = Any  # type: ignore[misc,assignment]
    Query = Any  # type: ignore[misc,assignment]
    Request = Any  # type: ignore[misc,assignment]
    Response = Any  # type: ignore[misc,assignment]
    JSONResponse = Any  # type: ignore[misc,assignment]
    RedirectResponse = Any  # type: ignore[misc,assignment]
    StaticFiles = Any  # type: ignore[misc,assignment]

from .. import CODENAME, __version__
from ..config import Settings
from ..domain.enums import Difficulty, GameMode, GameStatus
from ..engine.engine import GameEngine
from ..engine.shop import BY_ID as SHOP_ITEMS
from ..levels.catalog import MODES, level_count, level_for
from ..persistence.sqlite_store import SQLiteStore
from ..services.achievements import ACHIEVEMENTS
from ..services.progress import rank_title, record_result
from ..services.rate_limiter import RateLimiter
from ..services.security import is_safe_name
from ..services.sessions import ClientLimitError, GameSession, SessionLimitError, SessionManager
from .schemas import ActionRequest, CreateGameRequest, GameResponse, LoadGameRequest

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
WEB_SLOT = "web"
RANDOM_SEED_LIMIT = 2**31
CONSOLE_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação; ``settings`` permite configurar banco e limites nos testes."""
    from fastapi import FastAPI, HTTPException, Query, Request, Response
    from fastapi.responses import JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles

    config = settings or Settings.from_env()
    store = SQLiteStore(config.db_path)
    sessions = SessionManager(
        config.max_sessions, config.session_ttl, max_per_client=config.max_sessions_per_client
    )
    limiter = RateLimiter(config.rate_limit, 60.0)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        store.close()

    app = FastAPI(title=f"{CODENAME} API", version=__version__, lifespan=lifespan)
    app.state.sessions = sessions
    app.state.store = store

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Aplica o limite de requisições em ``/v1`` e os cabeçalhos de segurança."""
        path = request.url.path
        if path.startswith("/v1") and not limiter.allow(client_of(request)):
            return JSONResponse(
                {"detail": "Limite de requisições excedido."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if path.startswith("/console"):
            response.headers["Content-Security-Policy"] = CONSOLE_CSP
            response.headers["X-Frame-Options"] = "DENY"
        return response

    def find(session_id: str) -> GameSession:
        session = sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "Sessão não encontrada ou expirada.")
        return session

    def client_of(request: Request) -> str:
        return request.client.host if request.client else "desconhecido"

    def open_session(engine: GameEngine, player: str | None, client: str) -> GameSession:
        try:
            return sessions.create(engine, player, client)
        except ClientLimitError as error:
            raise HTTPException(429, str(error), headers={"Retry-After": "60"}) from error
        except SessionLimitError as error:
            raise HTTPException(503, str(error)) from error

    def respond(session: GameSession, result: dict[str, Any] | None = None) -> GameResponse:
        state = session.engine.state
        return GameResponse(
            session_id=session.session_id,
            status=state.status.value,
            score=state.score,
            snapshot=session.engine.snapshot(),
            result=result,
        )

    def finish(session: GameSession) -> dict[str, Any] | None:
        """Grava perfil, ranking e conquistas uma única vez ao fim da partida."""
        ended = session.engine.state.status in (GameStatus.WON, GameStatus.LOST)
        if not ended or session.recorded or session.player is None:
            return None
        session.recorded = True
        outcome = record_result(store, session.player, session.engine)
        # Só apaga o save que pertence a esta partida (salva ou carregada aqui);
        # o save de outra partida do mesmo jogador continua no banco.
        if session.saved:
            store.delete_save(session.player, WEB_SLOT)
        return {
            "position": outcome.position,
            "title": outcome.title,
            "new_achievements": [asdict(item) for item in outcome.new_achievements],
        }

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/console/")

    @app.get("/health")
    def health() -> dict[str, Any]:
        """Situação do serviço e quantidade de partidas ativas."""
        return {"status": "ok", "version": __version__, "sessions": len(sessions)}

    @app.get("/v1/catalog")
    def catalog() -> dict[str, Any]:
        """Modos (com suas fases), dificuldades e conquistas disponíveis."""
        modes = {}
        for mode, info in MODES.items():
            count = level_count(mode)
            titles = [spec.title for i in range(count or 0) if (spec := level_for(mode, i))]
            modes[mode.value] = {
                "title": info.title,
                "description": info.description,
                "levels": titles,
                "endless": count is None,
            }
        return {
            "modes": modes,
            "difficulties": [level.value for level in Difficulty],
            "achievements": [asdict(item) for item in ACHIEVEMENTS],
        }

    @app.post("/v1/games", status_code=201)
    def create_game(request: CreateGameRequest, http: Request) -> GameResponse:
        """Cria uma partida; sem ``seed``, usa ``JOGUINHO_SEED`` ou sorteia uma."""
        seed = request.seed
        if seed is None:
            seed = config.seed if config.seed is not None else secrets.randbelow(RANDOM_SEED_LIMIT)
        engine = GameEngine(seed, request.mode, request.difficulty)
        return respond(open_session(engine, request.name, client_of(http)))

    @app.post("/v1/games/load", status_code=201)
    def load_game(request: LoadGameRequest, http: Request) -> GameResponse:
        """Retoma, em uma nova sessão, a partida salva pelo jogador no console."""
        try:
            engine = store.load_game(request.name, WEB_SLOT)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        if engine is None:
            raise HTTPException(404, "Não há partida salva para esse jogador.")
        # O save guarda o identificador antigo; reutilizá-lo sobrescreveria a
        # sessão original se ela ainda estivesse ativa.
        engine.state.session_id = str(uuid.uuid4())
        session = open_session(engine, request.name, client_of(http))
        session.saved = True
        return respond(session)

    @app.get("/v1/games/{session_id}")
    def get_game(session_id: str) -> GameResponse:
        """Estado atual da partida."""
        session = find(session_id)
        with session.lock:
            return respond(session)

    @app.post("/v1/games/{session_id}/actions")
    def act(session_id: str, request: ActionRequest) -> GameResponse:
        """Executa um turno com a ação enviada."""
        session = find(session_id)
        with session.lock:
            session.engine.step(request.action)
            return respond(session, finish(session))

    @app.post("/v1/games/{session_id}/next-level")
    def next_level(session_id: str) -> GameResponse:
        """Avança de fase; só vale quando o status é ``level_complete``."""
        session = find(session_id)
        with session.lock:
            if not session.engine.next_level():
                raise HTTPException(409, "A fase atual ainda não foi concluída.")
            return respond(session)

    @app.post("/v1/games/{session_id}/shop/{item_id}")
    def buy(session_id: str, item_id: str) -> GameResponse:
        """Compra um item da loja; só vale entre fases (status ``level_complete``)."""
        session = find(session_id)
        with session.lock:
            engine = session.engine
            if engine.state.status is not GameStatus.LEVEL_COMPLETE:
                raise HTTPException(409, "A loja só abre entre fases.")
            if item_id not in SHOP_ITEMS:
                raise HTTPException(404, "Item desconhecido.")
            if not engine.buy(item_id):
                raise HTTPException(409, engine.state.message)
            return respond(session)

    @app.post("/v1/games/{session_id}/save")
    def save_game(session_id: str) -> dict[str, bool]:
        """Salva a partida no perfil do jogador (exige nome na criação)."""
        session = find(session_id)
        if session.player is None:
            raise HTTPException(409, "Só partidas criadas com nome de jogador podem ser salvas.")
        with session.lock:
            if session.engine.state.status in (GameStatus.WON, GameStatus.LOST):
                raise HTTPException(409, "A partida já terminou.")
            store.save_game(session.player, WEB_SLOT, session.engine)
            session.saved = True
        return {"saved": True}

    @app.get("/v1/games/{session_id}/events")
    def events(session_id: str, since: int = Query(default=0, ge=0)) -> dict[str, Any]:
        """Eventos da partida com sequência maior que ``since``."""
        session = find(session_id)
        with session.lock:
            return {
                "events": session.engine.transcript(since),
                "last": session.engine.event_seq,
            }

    @app.delete("/v1/games/{session_id}")
    def delete_game(session_id: str) -> dict[str, bool]:
        """Encerra a sessão."""
        if not sessions.remove(session_id):
            raise HTTPException(404, "Sessão não encontrada ou expirada.")
        return {"deleted": True}

    @app.get("/v1/leaderboard")
    def leaderboard(
        mode: GameMode | None = None, limit: int = Query(default=10, ge=1, le=50)
    ) -> dict[str, Any]:
        """Maiores pontuações, de um modo ou de todos."""
        entries = store.leaderboard(None if mode is None else mode.value, limit)
        return {"entries": [asdict(entry) for entry in entries]}

    @app.get("/v1/profiles/{name}")
    def profile(name: str) -> dict[str, Any]:
        """Totais, título e conquistas de um jogador."""
        found = store.profile(name) if is_safe_name(name) else None
        if found is None:
            raise HTTPException(404, "Perfil não encontrado.")
        return {
            "profile": asdict(found),
            "title": rank_title(found.total_score),
            "achievements": store.achievements(name),
        }

    app.mount("/console", StaticFiles(directory=str(WEB_DIR), html=True), name="console")
    return app


def run() -> None:
    """Ponto de entrada do comando ``joguinho-api``."""
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host=settings.api_host, port=settings.api_port)
