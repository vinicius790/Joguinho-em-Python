"""Editor de fases no terminal: um cursor, uma tecla por símbolo e validação ao vivo."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TextIO

from ..levels.editor import LevelFile, paint, save_level, validate
from .keys import KeyReader
from .terminal import RESET, Screen, colorize

REVERSE = "\x1b[7m"
MAX_PROBLEMS = 6

MOVES: dict[str, tuple[int, int]] = {
    "up": (0, -1),
    "i": (0, -1),
    "down": (0, 1),
    "k": (0, 1),
    "left": (-1, 0),
    "j": (-1, 0),
    "right": (1, 0),
    "l": (1, 0),
}

# Tecla -> símbolo gravado no mapa (as letras são as mesmas da tela do jogo).
PAINT: dict[str, str] = {
    " ": " ",
    ".": " ",
    "#": "#",
    "o": "O",
    "$": "$",
    "q": "Q",
    "*": "*",
    "e": "E",
    "x": "X",
    "y": "Y",
    "w": "W",
    "a": "A",
    "z": "z",
    "b": "B",
    "+": "+",
    "s": "S",
    "f": "F",
    "m": "M",
    "!": "!",
}

HELP: tuple[str, ...] = (
    "Setas ou I/J/K/L movem o cursor. Uma tecla pinta a célula:",
    "# parede  . vazio  O você  $ moeda  Q mina  * fogo  E saída",
    "X Y W A inimigos  Z dormindo  B chefe  + S F M ! power-ups",
    "- e = mudam a meta de moedas   G grava   Esc sai",
)


class LevelEditor:
    """Edita uma fase em memória e grava no formato ``.nivel``."""

    def __init__(
        self, path: Path, level: LevelFile, read_key: KeyReader, out: TextIO, color: bool
    ) -> None:
        """Guarda a fase aberta; o cursor começa na célula (1, 1), ou (0, 0) em mapas mínimos."""
        self.path = path
        self.level = level
        self.read_key = read_key
        self.screen = Screen(out, color)
        self.color = color
        self.x = min(1, len(level.rows[0]) - 1)
        self.y = min(1, len(level.rows) - 1)
        self.dirty = False
        self.notice = ""

    def frame(self) -> str:
        """Tela do editor: mapa com o cursor, dados da fase, problemas e ajuda."""
        level = self.level
        rows = []
        for y, row in enumerate(level.rows):
            if y != self.y or not self.screen.interactive:
                rows.append(colorize(row) if self.color else row)
                continue
            left, cell, right = row[: self.x], row[self.x], row[self.x + 1 :]
            if self.color:
                left, right = colorize(left), colorize(right)
            rows.append(f"{left}{REVERSE}{cell}{RESET}{right}")
        problems = validate(level)
        state = "com alterações não gravadas" if self.dirty else "gravada"
        cell = level.rows[self.y][self.x]
        lines = [
            *rows,
            "",
            f"Editor de fases - {self.path} ({state})",
            f"Título: {level.title}   Tamanho: {len(level.rows[0])}x{len(level.rows)}   "
            f"Meta: {level.target}   Cursor: ({self.x}, {self.y}) {cell!r}",
            "Fase válida." if not problems else f"{len(problems)} problema(s):",
            *(f"  - {problem}" for problem in problems[:MAX_PROBLEMS]),
        ]
        if self.notice:
            lines.append(f"> {self.notice}")
        return "\n".join([*lines, "", *HELP])

    def press(self, key: str) -> bool:
        """Aplica uma tecla; devolve ``False`` quando o editor deve fechar."""
        level = self.level
        self.notice = ""
        if key in ("esc", "eof"):
            return False
        if key in MOVES:
            dx, dy = MOVES[key]
            self.x = min(max(self.x + dx, 0), len(level.rows[0]) - 1)
            self.y = min(max(self.y + dy, 0), len(level.rows) - 1)
        elif key in PAINT:
            self.level = paint(level, self.x, self.y, PAINT[key])
            self.dirty = True
        elif key in ("-", "="):
            target = max(0, level.target + (1 if key == "=" else -1))
            self.level = replace(level, target=target)
            self.dirty = True
        elif key == "g":
            save_level(self.path, level)
            self.dirty = False
            problems = len(validate(level))
            self.notice = f"Gravado em {self.path}" + (
                f" com {problems} problema(s): corrija antes de jogar." if problems else "."
            )
        elif key:
            self.notice = f"Tecla sem função: {key!r}."
        return True

    def run(self) -> None:
        """Laço do editor até o usuário sair com Esc."""
        try:
            while True:
                self.screen.draw(self.frame())
                if not self.press(self.read_key()):
                    return
        finally:
            self.screen.close()
