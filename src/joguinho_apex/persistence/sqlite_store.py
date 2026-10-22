"""Banco SQLite com saves, perfis, conquistas, ranking e desafio diário."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any

from ..domain.enums import GameStatus
from ..engine.engine import GameEngine

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles(
    name TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    games INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    total_score INTEGER NOT NULL DEFAULT 0,
    best_score INTEGER NOT NULL DEFAULT 0,
    coins INTEGER NOT NULL DEFAULT 0,
    enemies_defeated INTEGER NOT NULL DEFAULT 0,
    ticks INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS achievements(
    profile TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile, achievement_id)
);
CREATE TABLE IF NOT EXISTS scores(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile TEXT NOT NULL,
    score INTEGER NOT NULL,
    mode TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    seed INTEGER NOT NULL,
    levels INTEGER NOT NULL,
    won INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS scores_by_mode ON scores(mode, score DESC);
CREATE TABLE IF NOT EXISTS saves(
    profile TEXT NOT NULL,
    slot TEXT NOT NULL,
    mode TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    level INTEGER NOT NULL,
    score INTEGER NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile, slot)
);
CREATE TABLE IF NOT EXISTS daily_scores(
    day TEXT NOT NULL,
    profile TEXT NOT NULL,
    score INTEGER NOT NULL,
    mode TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    levels INTEGER NOT NULL,
    won INTEGER NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (day, mode, difficulty, profile)
);
"""


class IntegrityError(ValueError):
    """Erro de integridade criptográfica (SHA-256 inválido ou payload adulterado)."""


@dataclass(frozen=True, slots=True)
class Profile:
    """Totais acumulados de um jogador."""

    name: str
    created_at: str
    games: int
    wins: int
    losses: int
    total_score: int
    best_score: int
    coins: int
    enemies_defeated: int
    ticks: int


@dataclass(frozen=True, slots=True)
class ScoreEntry:
    """Uma linha do ranking."""

    profile: str
    score: int
    mode: str
    difficulty: str
    seed: int
    levels: int
    won: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class DailyEntry:
    """Uma linha do ranking do desafio diário: a melhor tentativa do jogador no dia."""

    profile: str
    score: int
    levels: int
    won: bool
    attempts: int


@dataclass(frozen=True, slots=True)
class DailyStreak:
    """Sequência diária atual e recorde pessoal de participação."""

    current: int
    best: int
    played_today: bool


@dataclass(frozen=True, slots=True)
class SaveInfo:
    """Resumo de uma partida salva."""

    slot: str
    mode: str
    difficulty: str
    level: int
    score: int
    updated_at: str


class SQLiteStore:
    """Acesso ao banco do jogo.

    A conexão é compartilhada entre threads (a API atende requisições em um
    pool de threads), por isso toda operação passa por um ``Lock``.
    """

    def __init__(self, path: str | Path) -> None:
        """Abre (ou cria) o banco em ``path``; ``":memory:"`` cria um banco volátil."""
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        """Fecha a conexão."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SQLiteStore:
        """Permite usar o banco em um bloco ``with``."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Fecha a conexão ao sair do bloco ``with``."""
        self.close()

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self._lock, self._conn:
            return self._conn.execute(sql, params).rowcount

    # ---------------------------------------------------------------- saves

    def save_game(self, profile: str, slot: str, engine: GameEngine) -> str:
        """Grava a partida no slot do perfil com envelope e checksum SHA-256."""
        state = engine.state
        raw_payload = json.dumps(engine.to_dict(), ensure_ascii=False, separators=(",", ":"))
        checksum = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        envelope = {
            "format": "apex_save_v2",
            "checksum": checksum,
            "payload": raw_payload,
        }
        envelope_json = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
        self._execute(
            "INSERT OR REPLACE INTO saves(profile, slot, mode, difficulty, level, score, payload)"
            " VALUES(?, ?, ?, ?, ?, ?, ?)",
            (
                profile,
                slot,
                state.mode.value,
                state.difficulty.value,
                state.level_index + 1,
                state.score,
                envelope_json,
            ),
        )
        return checksum

    def load_game(
        self, profile: str, slot: str, verify_checksum: bool = True
    ) -> GameEngine | None:
        """Restaura a partida do slot com verificação de integridade SHA-256.

        Um save com checksum violado levanta ``IntegrityError``.
        Um save corrompido ou de outra versão levanta ``ValueError``.
        """
        rows = self._query(
            "SELECT payload FROM saves WHERE profile = ? AND slot = ?", (profile, slot)
        )
        if not rows:
            return None
        raw = rows[0]["payload"]
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("format") == "apex_save_v2":
                expected_hash = parsed.get("checksum", "")
                payload_str = parsed.get("payload", "")
                if verify_checksum:
                    actual_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
                    if actual_hash != expected_hash:
                        raise IntegrityError(
                            f"Falha de integridade SHA-256 no save de {profile} ({slot}): "
                            f"esperado {expected_hash}, obtido {actual_hash}."
                        )
                data = json.loads(payload_str)
            else:
                data = parsed
            return GameEngine.from_dict(data)
        except IntegrityError:
            raise
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError(
                f"O save de {profile} está corrompido ou é de outra versão."
            ) from error

    def list_saves(self, profile: str) -> list[SaveInfo]:
        """Lista os saves do perfil, do mais recente ao mais antigo."""
        rows = self._query(
            "SELECT slot, mode, difficulty, level, score, updated_at FROM saves"
            " WHERE profile = ? ORDER BY updated_at DESC, slot",
            (profile,),
        )
        return [SaveInfo(**dict(row)) for row in rows]

    def delete_save(self, profile: str, slot: str) -> bool:
        """Apaga o save; devolve ``False`` se ele não existia."""
        deleted = self._execute("DELETE FROM saves WHERE profile = ? AND slot = ?", (profile, slot))
        return deleted > 0

    # --------------------------------------------------------------- perfis

    def profile(self, name: str) -> Profile | None:
        """Devolve o perfil, ou ``None`` se o jogador nunca terminou uma partida."""
        rows = self._query("SELECT * FROM profiles WHERE name = ?", (name,))
        return Profile(**dict(rows[0])) if rows else None

    def record_game(self, name: str, engine: GameEngine, ranked: bool = True) -> Profile:
        """Soma uma partida encerrada aos totais do perfil e ao ranking.

        Com ``ranked=False`` (fases personalizadas) a partida conta no perfil
        (partidas, vitórias, moedas, turnos), mas a pontuação não entra no total,
        no recorde nem no ranking: um mapa feito à mão pode ser trivial.
        """
        state = engine.state
        won = state.status is GameStatus.WON
        score = state.score if ranked else 0
        with self._lock, self._conn:
            self._conn.execute("INSERT OR IGNORE INTO profiles(name) VALUES(?)", (name,))
            self._conn.execute(
                "UPDATE profiles SET games = games + 1, wins = wins + ?, losses = losses + ?,"
                " total_score = total_score + ?, best_score = MAX(best_score, ?),"
                " coins = coins + ?, enemies_defeated = enemies_defeated + ?, ticks = ticks + ?"
                " WHERE name = ?",
                (
                    int(won),
                    int(not won),
                    score,
                    score,
                    state.stats.coins,
                    state.stats.enemies_defeated,
                    state.stats.ticks,
                    name,
                ),
            )
            if ranked:
                self._conn.execute(
                    "INSERT INTO scores(profile, score, mode, difficulty, seed, levels, won)"
                    " VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (
                        name,
                        state.score,
                        state.mode.value,
                        state.difficulty.value,
                        state.seed,
                        state.stats.levels_completed,
                        int(won),
                    ),
                )
        profile = self.profile(name)
        assert profile is not None  # acabou de ser inserido
        return profile

    # ----------------------------------------------------------- conquistas

    def unlock(self, name: str, achievement_ids: set[str]) -> list[str]:
        """Registra conquistas e devolve só as que são novas para o perfil."""
        new = []
        with self._lock, self._conn:
            for achievement_id in sorted(achievement_ids):
                cursor = self._conn.execute(
                    "INSERT OR IGNORE INTO achievements(profile, achievement_id) VALUES(?, ?)",
                    (name, achievement_id),
                )
                if cursor.rowcount:
                    new.append(achievement_id)
        return new

    def achievements(self, name: str) -> list[str]:
        """Identificadores das conquistas do perfil, na ordem em que saíram."""
        rows = self._query(
            "SELECT achievement_id FROM achievements WHERE profile = ?"
            " ORDER BY unlocked_at, achievement_id",
            (name,),
        )
        return [row["achievement_id"] for row in rows]

    # -------------------------------------------------------------- ranking

    def leaderboard(self, mode: str | None = None, limit: int = 10) -> list[ScoreEntry]:
        """Maiores pontuações, de um modo ou de todos."""
        sql = "SELECT profile, score, mode, difficulty, seed, levels, won, created_at FROM scores"
        params: tuple[Any, ...] = ()
        if mode is not None:
            sql += " WHERE mode = ?"
            params = (mode,)
        sql += " ORDER BY score DESC, id ASC LIMIT ?"
        rows = self._query(sql, (*params, limit))
        return [ScoreEntry(**{**dict(row), "won": bool(row["won"])}) for row in rows]

    # ------------------------------------------------------ desafio diário

    def record_daily(self, day: str, name: str, engine: GameEngine) -> int:
        """Registra uma tentativa do desafio de ``day`` (``AAAA-MM-DD``).

        Cada jogador tem uma linha por dia, modo e dificuldade: fica a maior
        pontuação e ``attempts`` conta as tentativas. Devolve a posição do
        jogador no ranking do dia.
        """
        state = engine.state
        mode, difficulty = state.mode.value, state.difficulty.value
        won = int(state.status is GameStatus.WON)
        self._execute(
            "INSERT INTO daily_scores(day, profile, score, mode, difficulty, levels, won)"
            " VALUES(?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(day, mode, difficulty, profile) DO UPDATE SET"
            " attempts = attempts + 1,"
            " levels = CASE WHEN excluded.score > score THEN excluded.levels ELSE levels END,"
            " won = CASE WHEN excluded.score > score THEN excluded.won ELSE won END,"
            " score = MAX(score, excluded.score)",
            (day, name, state.score, mode, difficulty, state.stats.levels_completed, won),
        )
        names = [entry.profile for entry in self.daily_leaderboard(day, mode, difficulty, -1)]
        return names.index(name) + 1

    def daily_leaderboard(
        self, day: str, mode: str, difficulty: str, limit: int = 10
    ) -> list[DailyEntry]:
        """Ranking do desafio de ``day``; ``limit`` negativo devolve todos."""
        rows = self._query(
            "SELECT profile, score, levels, won, attempts FROM daily_scores"
            " WHERE day = ? AND mode = ? AND difficulty = ?"
            " ORDER BY score DESC, created_at ASC, profile ASC LIMIT ?",
            (day, mode, difficulty, limit),
        )
        return [DailyEntry(**{**dict(row), "won": bool(row["won"])}) for row in rows]

    def daily_streak(self, name: str, today: date | None = None) -> DailyStreak:
        """Calcula dias consecutivos com ao menos uma tentativa em qualquer modo.

        A sequência atual continua válida durante o dia seguinte ao último
        registro: se ainda não houve tentativa hoje, a contagem ancora ontem.
        Linhas inválidas e datas futuras são ignoradas.
        """
        reference = today or date.today()
        rows = self._query("SELECT DISTINCT day FROM daily_scores WHERE profile = ?", (name,))
        days: set[date] = set()
        for row in rows:
            value = row["day"]
            try:
                parsed = date.fromisoformat(value)
            except (TypeError, ValueError):
                continue
            if parsed.isoformat() == value and parsed <= reference:
                days.add(parsed)

        played_today = reference in days
        anchor = reference if played_today else reference - timedelta(days=1)
        current = 0
        while anchor - timedelta(days=current) in days:
            current += 1

        best = run = 0
        previous: date | None = None
        for day in sorted(days):
            run = run + 1 if previous is not None and day == previous + timedelta(days=1) else 1
            best = max(best, run)
            previous = day
        return DailyStreak(current, best, played_today)

    def rank_of(self, score: int, mode: str) -> int:
        """Posição (a partir de 1) que ``score`` ocupa no ranking do modo."""
        rows = self._query(
            "SELECT COUNT(*) AS better FROM scores WHERE mode = ? AND score > ?", (mode, score)
        )
        return int(rows[0]["better"]) + 1
