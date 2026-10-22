"""Conquistas: catálogo e regras de desbloqueio."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import Difficulty, GameMode, GameStatus
from ..domain.state import GameState

COLLECTOR_COINS = 100
HUNTER_KILLS = 5
MARATHON_LEVELS = 10
VETERAN_GAMES = 10


@dataclass(frozen=True, slots=True)
class Achievement:
    """Uma conquista do catálogo."""

    achievement_id: str
    title: str
    description: str


ACHIEVEMENTS: tuple[Achievement, ...] = (
    Achievement("first_coin", "Primeira Moeda", "Colete sua primeira moeda."),
    Achievement("combo_5", "Combo x5", "Colete 5 moedas seguidas sem deixar o combo cair."),
    Achievement("combo_10", "Combo x10", "Colete 10 moedas seguidas sem deixar o combo cair."),
    Achievement("collector", "Magnata", "Colete 100 moedas em uma única partida."),
    Achievement("survivor", "Sobrevivente", "Vença uma partida sem perder vida."),
    Achievement(
        "speedrunner", "Velocista", "Conclua uma fase cronometrada em até metade do tempo."
    ),
    Achievement("hunter", "Caçador", "Derrote 5 inimigos em uma única partida."),
    Achievement("demolition", "Demolidor", "Derrote um inimigo com a explosão de uma mina."),
    Achievement("boss_slayer", "Matador de Guardiões", "Derrote um chefe."),
    Achievement("champion", "Campeão", "Conclua a campanha."),
    Achievement("nightmare", "Pesadelo", "Vença uma partida em nightmare ou apocalypse."),
    Achievement("marathon", "Maratonista", "Conclua 10 fases em uma única partida."),
    Achievement("veteran", "Veterano", "Termine 10 partidas com o mesmo perfil."),
    Achievement("first_skill", "Despertar do Poder", "Desbloqueie sua primeira habilidade na árvore."),
    Achievement("master_tree", "Mestre dos Talentos", "Desbloqueie pelo menos 5 habilidades em uma partida."),
    Achievement("shrine_pilgrim", "Peregrino dos Santuários", "Ative um santuário misterioso."),
    Achievement("merchant_customer", "Negociador", "Realize uma negociação com um mercador errante."),
    Achievement("event_explorer", "Aventureiro Errante", "Vivencie 3 eventos dinâmicos pelo caminho."),
    Achievement("auto_battler_champ", "Mente Tática", "Vença uma partida usando o modo Auto-Battler."),
)

BY_ID: dict[str, Achievement] = {item.achievement_id: item for item in ACHIEVEMENTS}


def evaluate(state: GameState, games_played: int = 0) -> set[str]:
    """Identificadores das conquistas que o estado atual já garante.

    ``games_played`` é o total de partidas encerradas do perfil (já contando a
    atual), usado pela conquista de veterano.
    """
    stats = state.stats
    won = state.status is GameStatus.WON
    checks = {
        "first_coin": stats.coins >= 1,
        "combo_5": stats.best_combo >= 5,
        "combo_10": stats.best_combo >= 10,
        "collector": stats.coins >= COLLECTOR_COINS,
        "survivor": won and stats.damage_taken == 0,
        "speedrunner": stats.fast_clears >= 1,
        "hunter": stats.enemies_defeated >= HUNTER_KILLS,
        "demolition": stats.mine_kills >= 1,
        "boss_slayer": stats.bosses_defeated >= 1,
        "champion": won and state.mode is GameMode.CAMPAIGN,
        "nightmare": won and state.difficulty in (Difficulty.NIGHTMARE, Difficulty.APOCALYPSE),
        "marathon": stats.levels_completed >= MARATHON_LEVELS,
        "veteran": games_played >= VETERAN_GAMES,
        "first_skill": stats.skills_unlocked >= 1 or len(state.player.skills) >= 1,
        "master_tree": stats.skills_unlocked >= 5 or len(state.player.skills) >= 5,
        "shrine_pilgrim": stats.shrines_used >= 1,
        "merchant_customer": stats.merchant_trades >= 1,
        "event_explorer": stats.events_encountered >= 3,
        "auto_battler_champ": won and stats.auto_battler_wins >= 1,
    }
    return {achievement_id for achievement_id, unlocked in checks.items() if unlocked}
