"""Loja entre fases: catálogo de itens comprados com o ouro da partida."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShopItem:
    """Um item da loja; ``consumable`` vai para o inventário em vez de agir na hora."""

    item_id: str
    title: str
    price: int
    description: str
    consumable: bool = False


# A posição na tupla (a partir de 1) é a tecla de compra e o símbolo gravado no replay.
SHOP: tuple[ShopItem, ...] = (
    ShopItem("heart", "Coração", 12, "+1 de vida máxima e cura 1 ponto"),
    ShopItem("shield", "Escudo", 8, "+1 escudo (máximo 3)"),
    ShopItem("boots", "Botas", 15, "dash recarrega 2 turnos mais rápido (uma vez)"),
    ShopItem("potion", "Poção", 6, "consumível [H]: cura 1 de vida", consumable=True),
    ShopItem("bomb", "Bomba", 10, "consumível [B]: fere inimigos a até 2 células", consumable=True),
)

BY_ID: dict[str, ShopItem] = {item.item_id: item for item in SHOP}
TOKENS: dict[str, str] = {item.item_id: str(number) for number, item in enumerate(SHOP, start=1)}
BY_TOKEN: dict[str, str] = {token: item_id for item_id, token in TOKENS.items()}
