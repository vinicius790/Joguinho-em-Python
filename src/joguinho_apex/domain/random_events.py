"""Eventos dinâmicos aleatórios (encontros, mercadores e santuários).

Define eventos que ocorrem proceduralmente durante a exploração ou entre fases,
oferecendo escolhas táticas com recompensas, custos e riscos para o jogador.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    """Categoria do evento dinâmico."""

    SHRINE = "shrine"
    MERCHANT = "merchant"
    ENCOUNTER = "encounter"


@dataclass(frozen=True, slots=True)
class EventChoice:
    """Opção disponível para o jogador em um evento."""

    choice_id: str
    text: str
    cost_gold: int = 0
    cost_hp: int = 0
    requires_item: str | None = None
    outcome_description: str = ""


@dataclass(frozen=True, slots=True)
class EventOutcome:
    """Resultado da aplicação de uma escolha do evento."""

    success: bool
    message: str
    hp_change: int = 0
    gold_change: int = 0
    sp_change: int = 0
    shield_change: int = 0
    max_hp_change: int = 0
    items_change: dict[str, int] = field(default_factory=dict)
    fury_turns: int = 0
    freeze_turns: int = 0
    reset_cooldowns: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serializa o resultado do evento."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DynamicEvent:
    """Definição de um evento procedural dinâmico."""

    event_id: str
    title: str
    event_type: EventType
    narrative: str
    choices: tuple[EventChoice, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serializa o evento dinâmico."""
        return {
            "id": self.event_id,
            "title": self.title,
            "type": self.event_type.value,
            "narrative": self.narrative,
            "choices": [
                {
                    "id": c.choice_id,
                    "text": c.text,
                    "cost_gold": c.cost_gold,
                    "cost_hp": c.cost_hp,
                    "requires_item": c.requires_item,
                    "outcome": c.outcome_description,
                }
                for c in self.choices
            ],
        }


# Catálogo dos eventos disponíveis
EVENT_CATALOG: tuple[DynamicEvent, ...] = (
    # --- Santuários Místicos ---
    DynamicEvent(
        event_id="shrine_vitality",
        title="Santuário da Vitalidade Antiga",
        event_type=EventType.SHRINE,
        narrative="Um obelisco de cristal emana um brilho esmeralda suave, aquecendo suas feridas.",
        choices=(
            EventChoice(
                choice_id="pray_heal",
                text="Rezar humildemente pela cura das feridas (Restaura até 2 HP).",
                outcome_description="Restaura 2 pontos de vida.",
            ),
            EventChoice(
                choice_id="bathe_essence",
                text="Imergir no núcleo cristalino (Custa 20 ouro: +1 Max HP e restaura vida).",
                cost_gold=20,
                outcome_description="+1 Max HP e vida totalmente restaurada.",
            ),
            EventChoice(
                choice_id="leave_shrine",
                text="Deixar o santuário intacto e seguir em frente.",
                outcome_description="Nenhum efeito.",
            ),
        ),
    ),
    DynamicEvent(
        event_id="shrine_shadow",
        title="Altar do Sacrifício Sombrio",
        event_type=EventType.SHRINE,
        narrative="Runas vermelhas pulsam sobre uma laje de obsidiana. O poder cobra seu preço em sangue.",
        choices=(
            EventChoice(
                choice_id="sacrifice_blood",
                text="Derramar uma gota de sangue (-1 HP: ganha 35 ouro e +1 Ponto de Habilidade).",
                cost_hp=1,
                outcome_description="Perde 1 HP, ganha 35 de ouro e 1 SP.",
            ),
            EventChoice(
                choice_id="purify_altar",
                text="Consagrar o altar com ouro (Custa 25 ouro: ganha +2 de escudo protetor).",
                cost_gold=25,
                outcome_description="Ganha 2 camadas de escudo.",
            ),
            EventChoice(
                choice_id="refuse_shadow",
                text="Rejeitar a comunhão sombria e recuar.",
                outcome_description="Nenhum efeito.",
            ),
        ),
    ),
    DynamicEvent(
        event_id="shrine_storm",
        title="Monólito da Tempestade",
        event_type=EventType.SHRINE,
        narrative="Relâmpagos estáticos crepitam ao redor do monólito de ferro estelar.",
        choices=(
            EventChoice(
                choice_id="channel_lightning",
                text="Absorver a energia cinética (Ativa Fúria por 15 turnos e congela ameaças por 8).",
                outcome_description="Concede Fúria tempestuosa e Congelamento temporal.",
            ),
            EventChoice(
                choice_id="discharge_static",
                text="Descarregar a eletricidade estática (Reseta instantaneamente recargas de Dash e Pulso).",
                outcome_description="Recarrega todas as habilidades ativas.",
            ),
            EventChoice(
                choice_id="ignore_storm",
                text="Ignorar a tempestade e manter o passo.",
                outcome_description="Nenhum efeito.",
            ),
        ),
    ),
    # --- Mercadores Errantes ---
    DynamicEvent(
        event_id="merchant_wanderer",
        title="Caravana do Mercador Nômade",
        event_type=EventType.MERCHANT,
        narrative="Um comerciante encapuzado abre baús repletos de frascos e relíquias raras de expedições.",
        choices=(
            EventChoice(
                choice_id="buy_potion",
                text="Comprar Frasco de Vida Revigorante (Custa 15 ouro: +1 Poção no inventário).",
                cost_gold=15,
                outcome_description="+1 Poção de cura adicionada ao inventário.",
            ),
            EventChoice(
                choice_id="buy_bombs",
                text="Comprar Pacote de Detonadores (Custa 25 ouro: +2 Bombas no inventário).",
                cost_gold=25,
                outcome_description="+2 Bombas de demolição adicionadas.",
            ),
            EventChoice(
                choice_id="buy_tome",
                text="Adquirir Tomo Arcano Antigo (Custa 40 ouro: +1 Ponto de Habilidade permanente).",
                cost_gold=40,
                outcome_description="+1 Ponto de Habilidade concedido.",
            ),
            EventChoice(
                choice_id="decline_trade",
                text="Agradecer educadamente e guardar suas moedas.",
                outcome_description="Nenhum efeito.",
            ),
        ),
    ),
    DynamicEvent(
        event_id="merchant_smuggler",
        title="Covil do Contrabandista Misterioso",
        event_type=EventType.MERCHANT,
        narrative="Um contrabandista sussurra de trás de uma pilha de escombros, exibindo itens lacrados.",
        choices=(
            EventChoice(
                choice_id="mystery_box",
                text="Comprar Baú Lacrado da Sorte (Custa 20 ouro: conteúdo desconhecido).",
                cost_gold=20,
                outcome_description="Surpresa: ouro abundante, poção ou relíquia.",
            ),
            EventChoice(
                choice_id="smuggler_shield",
                text="Comprar Escudo Reforçado de Sucata (Custa 18 ouro: +2 Escudos).",
                cost_gold=18,
                outcome_description="+2 Escudos de defesa imediata.",
            ),
            EventChoice(
                choice_id="ignore_smuggler",
                text="Afastar-se do contrabandista suspeito.",
                outcome_description="Nenhum efeito.",
            ),
        ),
    ),
    # --- Encontros Dinâmicos ---
    DynamicEvent(
        event_id="encounter_goblin",
        title="Emboscada do Goblin Coletor",
        event_type=EventType.ENCOUNTER,
        narrative="Um goblin ágil surge de uma fenda lateral carregando um saco tinindo moedas de ouro!",
        choices=(
            EventChoice(
                choice_id="fight_goblin",
                text="Saltar sobre o goblin e desarmá-lo (Requer perícia rápida: rende 35 ouro).",
                outcome_description="Derrota o goblin e recupera 35 moedas de ouro.",
            ),
            EventChoice(
                choice_id="bomb_goblin",
                text="Lançar uma Bomba no caminho de fuga (Consome 1 Bomba: rende 55 ouro).",
                requires_item="bomb",
                outcome_description="Gasta 1 Bomba e captura 55 moedas de ouro.",
            ),
            EventChoice(
                choice_id="let_escape",
                text="Ignorar o goblin e não se arriscar.",
                outcome_description="O goblin escapa com o tesouro.",
            ),
        ),
    ),
    DynamicEvent(
        event_id="encounter_lost_traveler",
        title="O Explorador Perdido nas Minas",
        event_type=EventType.ENCOUNTER,
        narrative="Você encontra um jovem aventureiro encurralado entre células minadas, pedindo socorro.",
        choices=(
            EventChoice(
                choice_id="rescue_traveler",
                text="Guiar o explorador em segurança (+1 Ponto de Habilidade e 20 ouro em gratidão).",
                outcome_description="Resgate bem-sucedido: +1 SP e +20 ouro.",
            ),
            EventChoice(
                choice_id="give_potion",
                text="Doar uma Poção de Cura para ele se recuperar (Consome 1 Poção: +40 ouro e +1 SP).",
                requires_item="potion",
                outcome_description="Gasta 1 Poção, recebe recompensa generosa de +40 ouro e +1 SP.",
            ),
            EventChoice(
                choice_id="leave_traveler",
                text="Não se desviar da sua missão prioritária.",
                outcome_description="O explorador encontra seu próprio rumo.",
            ),
        ),
    ),
    DynamicEvent(
        event_id="encounter_time_rift",
        title="Anomalia da Fenda Temporal",
        event_type=EventType.ENCOUNTER,
        narrative="O espaço ao redor vacila em ondas crono-quânticas. O tempo parece fluir em câmera lenta.",
        choices=(
            EventChoice(
                choice_id="step_into_rift",
                text="Tocar o centro da fenda (Recarrega Dash/Pulso e congela tudo ao redor por 10 turnos).",
                outcome_description="Recarga total imediata e congelamento de 10 turnos.",
            ),
            EventChoice(
                choice_id="harvest_chronos",
                text="Coletar resíduo de éter temporal (+25 ouro e +1 Ponto de Habilidade).",
                outcome_description="Ganha 25 de ouro e 1 Ponto de Habilidade.",
            ),
            EventChoice(
                choice_id="bypass_rift",
                text="Desviar da distorção temporal.",
                outcome_description="Nenhum efeito.",
            ),
        ),
    ),
)

EVENTS_BY_ID: dict[str, DynamicEvent] = {event.event_id: event for event in EVENT_CATALOG}
DEFAULT_EVENTS = EVENT_CATALOG


def create_random_event(rng: Any, event_type: EventType | None = None) -> DynamicEvent:
    """Seleciona proceduralmente um evento do catálogo."""
    candidates = EVENT_CATALOG
    if event_type is not None:
        candidates = tuple(e for e in candidates if e.event_type == event_type)
    return rng.choice(candidates)
