"""Replays: a seed e a lista de ações bastam para refazer a partida."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..domain.entities import LevelSpec
from ..domain.enums import Action, GameMode
from ..engine.engine import NEXT_LEVEL_TOKEN, GameEngine
from ..engine.shop import BY_TOKEN
from ..levels.builder import layout_from_rows
from ..levels.catalog import CAMPAIGN_VERSION

REPLAY_VERSION = 2
LEGACY_VERSION = 1  # replays da 21.0.0: campanha de sete fases e impressão sem ouro e itens


@dataclass(frozen=True, slots=True)
class Replay:
    """Registro compacto de uma partida.

    ``actions`` tem um caractere por turno (a tecla da ação), ``>`` a cada
    avanço de fase e um dígito por compra na loja. ``fingerprint`` é a impressão
    do estado final, usada para conferir se a reprodução chegou exatamente ao
    mesmo lugar. ``campaign`` é a versão da campanha jogada e ``level`` guarda a
    fase personalizada (receita e mapa inicial), quando a partida não veio do
    catálogo. Replays da versão 1 (21.0.0) não têm esses campos e são refeitos
    com a campanha antiga.
    """

    seed: int
    mode: str
    difficulty: str
    actions: str
    fingerprint: str
    score: int
    version: int = REPLAY_VERSION
    campaign: int = CAMPAIGN_VERSION
    level: dict[str, Any] | None = None
    levels: list[dict[str, Any]] | None = None

    @classmethod
    def from_engine(cls, engine: GameEngine) -> Replay:
        """Captura o replay da partida até o turno atual."""
        rows = engine.custom_rows
        pack = engine.to_dict().get("custom_pack")
        level = None
        if rows is not None and pack is None:
            # Passa por JSON para ficar igual ao que ``load`` lê (tuplas viram listas).
            level = json.loads(json.dumps({"spec": engine.state.level.to_dict(), "rows": rows}))
        return cls(
            seed=engine.seed,
            mode=engine.mode.value,
            difficulty=engine.difficulty.value,
            actions="".join(engine.history),
            fingerprint=engine.fingerprint(),
            score=engine.state.score,
            campaign=engine.campaign,
            level=level,
            levels=pack,
        )

    @property
    def legacy(self) -> bool:
        """Indica um replay da 21.0.0 (formato da versão 1)."""
        return self.version == LEGACY_VERSION

    def new_engine(self) -> GameEngine:
        """Partida nova, no ponto de partida do replay."""
        if self.version not in (LEGACY_VERSION, REPLAY_VERSION):
            raise ValueError(f"Versão de replay não suportada: {self.version!r}.")
        if self.level is not None:
            spec = LevelSpec.from_dict(self.level["spec"])
            layout = layout_from_rows(self.level["rows"])
            return GameEngine(self.seed, GameMode.SANDBOX, self.difficulty, custom=(spec, layout))
        if self.levels is not None:
            custom = tuple(
                (LevelSpec.from_dict(item["spec"]), layout_from_rows(item["rows"]))
                for item in self.levels
            )
            return GameEngine(self.seed, GameMode.SANDBOX, self.difficulty, custom=custom)
        campaign = 1 if self.legacy else self.campaign
        return GameEngine(self.seed, self.mode, self.difficulty, campaign=campaign)

    def play(self) -> GameEngine:
        """Refaz a partida do zero e devolve o motor no estado final."""
        engine = self.new_engine()
        for token in self.actions:
            if token == NEXT_LEVEL_TOKEN:
                engine.next_level()
            elif token in BY_TOKEN:
                engine.buy(BY_TOKEN[token])
            else:
                engine.step(Action(token))
        return engine

    def matches(self, engine: GameEngine) -> bool:
        """Confere se ``engine`` chegou ao estado final gravado."""
        return engine.fingerprint(legacy=self.legacy) == self.fingerprint

    def verify(self) -> bool:
        """Confere se a reprodução chega ao mesmo estado final gravado."""
        try:
            return self.matches(self.play())
        except (ValueError, TypeError, KeyError):
            return False

    def save(self, path: str | Path) -> None:
        """Grava o replay em JSON."""
        Path(path).write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: str | Path) -> Replay:
        """Lê um replay em JSON (versão 1 ou 2)."""
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))
