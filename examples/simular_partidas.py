"""Exemplo: simula partidas com o bot e imprime o resumo estatístico.

Uso: ``python examples/simular_partidas.py`` (com o pacote instalado).
"""

from joguinho_apex.simulation.runner import run_episodes, summarize

results = run_episodes(episodes=10, seed=2026, mode="chase", difficulty="normal", policy="bot")
for key, value in summarize(results).items():
    print(f"{key:>14}: {value}")
