"""Leitura de teclas sem Enter (Windows e POSIX), com alternativa por linhas.

Todas as variantes devolvem o mesmo vocabulário: letras minúsculas, ``" "``,
``"up"``, ``"down"``, ``"left"``, ``"right"``, ``"enter"``, ``"esc"`` e
``"eof"`` quando a entrada acabou.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TextIO

KeyReader = Callable[[], str]

_WINDOWS_ARROWS = {"H": "up", "P": "down", "K": "left", "M": "right"}
_ANSI_ARROWS = {"A": "up", "B": "down", "D": "left", "C": "right"}


def _normalize(char: str) -> str:
    """Traduz caracteres de controle para nomes e letras para minúsculas."""
    if char in ("\r", "\n"):
        return "enter"
    if char == "\x1b":
        return "esc"
    if char == "\x03":
        raise KeyboardInterrupt
    if char in ("\x04", "\x1a", ""):
        return "eof"
    return char.lower()


def line_reader(stream: TextIO) -> KeyReader:
    """Leitor para entrada que não é terminal: cada linha vale uma tecla.

    Uma linha vazia vale ``enter``; o fim da entrada vale ``eof``.
    """

    def read() -> str:
        line = stream.readline()
        if not line:
            return "eof"
        text = line.strip()
        if not text:
            return "enter"
        return text.lower() if len(text) > 1 else _normalize(text)

    return read


if sys.platform == "win32":
    import msvcrt

    def _read_terminal_key() -> str:
        """Lê uma tecla do console do Windows; setas chegam em dois caracteres."""
        char = msvcrt.getwch()
        if char in ("\x00", "\xe0"):
            return _WINDOWS_ARROWS.get(msvcrt.getwch(), "")
        return _normalize(char)

else:
    import select
    import termios
    import tty

    def _read_terminal_key() -> str:
        """Lê uma tecla do terminal POSIX em modo cbreak; setas são ``ESC [ X``."""
        descriptor = sys.stdin.fileno()
        saved = termios.tcgetattr(descriptor)
        try:
            tty.setcbreak(descriptor)
            char = sys.stdin.read(1)
            if char == "\x1b" and select.select([sys.stdin], [], [], 0.05)[0]:
                sequence = sys.stdin.read(2)
                return _ANSI_ARROWS.get(sequence[-1:], "esc")
            return _normalize(char)
        finally:
            termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)


def make_key_reader(stream: TextIO | None = None) -> KeyReader:
    """Escolhe o leitor: tecla a tecla em terminal, linha a linha fora dele."""
    source = sys.stdin if stream is None else stream
    if stream is None and source.isatty():
        return _read_terminal_key
    return line_reader(source)
