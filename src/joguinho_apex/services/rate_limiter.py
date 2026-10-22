"""Limite de requisições por cliente, com janela fixa."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Permite até ``limit`` chamadas por ``window`` segundos para cada chave.

    Guarda um contador por chave e descarta os contadores vencidos a cada
    janela, então a memória fica limitada pelos clientes ativos no período.
    """

    def __init__(
        self, limit: int = 60, window: float = 60.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Configura o limite; ``clock`` existe para os testes controlarem o tempo."""
        self.limit = limit
        self.window = window
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[str, tuple[float, int]] = {}
        self._last_sweep = clock()

    def allow(self, key: str) -> bool:
        """Conta uma chamada da chave e diz se ela está dentro do limite."""
        now = self._clock()
        with self._lock:
            if now - self._last_sweep >= self.window:
                self._sweep(now)
            start, count = self._hits.get(key, (now, 0))
            if now - start >= self.window:
                start, count = now, 0
            if count >= self.limit:
                return False
            self._hits[key] = (start, count + 1)
            return True

    def _sweep(self, now: float) -> None:
        """Remove contadores cuja janela já terminou."""
        self._hits = {
            key: (start, count)
            for key, (start, count) in self._hits.items()
            if now - start < self.window
        }
        self._last_sweep = now

    def __len__(self) -> int:
        """Quantidade de chaves com contador em memória."""
        with self._lock:
            return len(self._hits)
