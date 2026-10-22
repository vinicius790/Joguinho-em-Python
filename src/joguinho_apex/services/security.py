"""Saneamento de entradas vindas de fora (nomes de jogador e de slot)."""

from __future__ import annotations

import re

MAX_NAME_LENGTH = 24
_FORBIDDEN = re.compile(r"[^\w \-]", flags=re.UNICODE)
_SPACES = re.compile(r"\s+")


def safe_name(value: str, default: str = "Jogador") -> str:
    """Devolve um nome só com letras, dígitos, espaço, ``_`` e ``-``.

    Pontos, barras e qualquer outro símbolo são removidos, então o resultado
    nunca contém ``..`` nem separadores de caminho. Um nome que fique vazio
    vira ``default``.
    """
    cleaned = _SPACES.sub(" ", _FORBIDDEN.sub("", value)).strip()[:MAX_NAME_LENGTH].strip()
    return cleaned or default


def is_safe_name(value: str) -> bool:
    """Indica se ``value`` já está na forma aceita por :func:`safe_name`."""
    return bool(value) and safe_name(value, default="") == value
