"""História da campanha: três atos, um texto antes de cada fase e o final."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chapter:
    """Texto mostrado antes de uma fase da campanha."""

    act: str
    text: str


ACT_1 = "Ato I - A Superfície"
ACT_2 = "Ato II - As Ruínas"
ACT_3 = "Ato III - O Nexus"

CHAPTERS: dict[str, Chapter] = {
    "campaign-1": Chapter(
        ACT_1,
        "O Nexus, a máquina que mantinha a cidade acesa, parou. Você desce com uma lanterna "
        "e os bolsos vazios: cada moeda antiga ainda guarda um pouco de energia.",
    ),
    "campaign-2": Chapter(
        ACT_1,
        "Os antigos donos não queriam visitas. O chão está semeado de minas (Q): "
        "olhe onde pisa, e lembre que explosões também ferem quem persegue você.",
    ),
    "campaign-3": Chapter(
        ACT_1,
        "Um alarme soa. A Sentinela, vigia da entrada, acordou e chama reforços quando é "
        "ferida. Junte as moedas e derrube-a com o Pulso (F) para abrir o caminho.",
    ),
    "campaign-4": Chapter(
        ACT_2,
        "Abaixo da entrada, as cavernas. Há uma saída (E) do outro lado, mas ela só abre "
        "com a meta de moedas, e os vigias ficam furiosos quando ela abre.",
    ),
    "campaign-5": Chapter(
        ACT_2,
        "A névoa do labirinto engole a luz da lanterna e o ar está acabando: há um relógio. "
        "Emboscadores dormem (z) nos corredores. Não os acorde à toa.",
    ),
    "campaign-6": Chapter(
        ACT_2,
        "As Ruínas têm dono. O Guardião deixa fogo por onde passa e fica mais rápido a cada "
        "golpe. Atraia-o para as minas ou use o Pulso de perto.",
    ),
    "campaign-7": Chapter(
        ACT_3,
        "Com o Guardião caído, tudo desaba. Corra: os quatro tipos de vigia estão atrás de "
        "você e o tempo é curto.",
    ),
    "campaign-8": Chapter(
        ACT_3,
        "O coração do Nexus pulsa no escuro. As últimas moedas estão aqui, entre minas e "
        "névoa. Gaste seu ouro na loja antes da última porta.",
    ),
    "campaign-9": Chapter(
        ACT_3,
        "O Colosso é o próprio Nexus de pé: lento, mas a cada passo larga minas e sua aura "
        "de fogo é enorme. Derrube-o e a cidade volta a acender.",
    ),
}

ENDING = (
    "O Colosso tomba e, no silêncio, o Nexus volta a zumbir. Lá em cima, janela por janela, "
    "a cidade acende. Você sobe com os bolsos cheios e uma história que ninguém vai acreditar."
)


def chapter_for(level_id: str) -> Chapter | None:
    """Capítulo da fase, ou ``None`` para fases fora da campanha."""
    return CHAPTERS.get(level_id)
