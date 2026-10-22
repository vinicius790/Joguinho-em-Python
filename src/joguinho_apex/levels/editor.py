"""Fases feitas à mão: formato de arquivo ``.nivel``, validação e gravação.

O arquivo é texto puro em UTF-8: um cabeçalho opcional de linhas
``chave: valor`` e, depois, o mapa desenhado com os mesmos símbolos da tela::

    ; linhas começadas com ponto e vírgula são comentários
    titulo: Cofre
    meta: 2
    tempo: 120

    #########
    #O $ $ E#
    #########

Chaves aceitas: ``titulo``, ``meta`` (moedas exigidas), ``vida_chefe``,
``chefe`` (um nome de ``engine.rules.BOSSES``), ``tempo`` (limite de turnos)
e ``nevoa`` (raio de visão). O mapa começa na primeira linha iniciada por ``#``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..ai.pathfinding import distance_map
from ..domain.enums import ENEMY_SYMBOLS, POWER_SYMBOLS, SLEEPING_AMBUSHER, EnemyKind, Tile
from ..engine.rules import BOSSES
from .builder import LevelLayout, layout_from_rows

LEVEL_SUFFIX = ".nivel"
MIN_SIZE = 3
MAX_WIDTH = 120
MAX_HEIGHT = 60
MAX_BOSS_HP = 30
MAX_TEXT = 40
MAX_DIGITS = 6
COMMENT = ";"
BOM = "﻿"

SYMBOLS: str = (
    "".join(tile.value for tile in Tile if tile is not Tile.FOG)
    + "".join(ENEMY_SYMBOLS.values())
    + SLEEPING_AMBUSHER
    + "".join(POWER_SYMBOLS.values())
)

_INT_KEYS = {
    "meta": "target",
    "vida_chefe": "boss_hp",
    "tempo": "time_limit",
    "nevoa": "fog_radius",
}
_TEXT_KEYS = {"titulo": "title", "chefe": "boss"}


class LevelError(ValueError):
    """Arquivo de fase inválido; ``problems`` lista tudo o que foi encontrado."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True, slots=True)
class LevelFile:
    """Conteúdo de um arquivo de fase: o mapa e as opções do cabeçalho."""

    rows: tuple[str, ...]
    title: str = "Fase personalizada"
    target: int = 0
    boss_hp: int = 0
    time_limit: int = 0
    fog_radius: int = 0
    boss: str = "guardian"

    def options(self) -> dict[str, Any]:
        """Argumentos nomeados para ``GameEngine.from_rows(rows, **options)``."""
        return {
            "target": self.target,
            "boss_hp": self.boss_hp,
            "time_limit": self.time_limit or None,
            "fog_radius": self.fog_radius,
            "boss": self.boss,
            "title": self.title,
        }


def blank_level(width: int = 30, height: int = 12) -> LevelFile:
    """Fase vazia cercada de paredes, com o jogador no canto e uma saída."""
    inner = " " * (width - 2)
    rows = ["#" * width, *(f"#{inner}#" for _ in range(height - 2)), "#" * width]
    rows[1] = "#O" + rows[1][2:]
    rows[-2] = rows[-2][:-2] + "E#"
    return LevelFile(tuple(rows), title="Nova fase")


def parse_level(text: str) -> tuple[LevelFile, list[str]]:
    """Lê o texto de um arquivo de fase; devolve a fase e os problemas do cabeçalho.

    Não valida o mapa: use :func:`validate` (ou :func:`check`) para isso.
    """
    problems: list[str] = []
    fields: dict[str, Any] = {}
    lines = text.lstrip(BOM).splitlines()
    start = len(lines)
    for number, line in enumerate(lines, start=1):
        if line.startswith(Tile.WALL.value):
            start = number - 1
            break
        stripped = line.strip()
        if not stripped or stripped.startswith(COMMENT):
            continue
        key, separator, value = stripped.partition(":")
        key, value = key.strip().lower(), value.strip()
        if not separator:
            problems.append(f"Linha {number}: esperado 'chave: valor' ou uma linha do mapa (#...).")
        elif key in _TEXT_KEYS:
            # Sem caracteres de controle: o título vai direto para o terminal.
            if value.isprintable() and len(value) <= MAX_TEXT:
                fields[_TEXT_KEYS[key]] = value
            else:
                problems.append(
                    f"Linha {number}: '{key}' precisa ser um texto de até {MAX_TEXT} "
                    "caracteres, sem caracteres de controle."
                )
        elif key in _INT_KEYS:
            # isdecimal (e não isdigit): int() recusa dígitos como '²'.
            if value.isdecimal() and len(value) <= MAX_DIGITS:
                fields[_INT_KEYS[key]] = int(value)
            else:
                problems.append(
                    f"Linha {number}: '{key}' precisa ser um número inteiro >= 0 "
                    f"(até {MAX_DIGITS} dígitos)."
                )
        else:
            known = ", ".join(sorted([*_TEXT_KEYS, *_INT_KEYS]))
            problems.append(f"Linha {number}: chave desconhecida '{key}' (use {known}).")
    rows = [line.rstrip("\r\n") for line in lines[start:]]
    while rows and not rows[-1].strip():
        rows.pop()
    return LevelFile(tuple(rows), **fields), problems


def validate(level: LevelFile) -> list[str]:
    """Lista os problemas da fase; lista vazia significa que ela é jogável.

    Confere tamanho, símbolos, jogador único, opções coerentes, existência de
    objetivo e se moedas, power-ups, inimigos e saída são alcançáveis sem
    pisar em minas.
    """
    rows = level.rows
    if not rows:
        return ["O arquivo não tem mapa (a primeira linha do mapa começa com #)."]
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        sizes = sorted({len(row) for row in rows})
        return [f"As linhas do mapa têm comprimentos diferentes: {sizes}."]
    problems: list[str] = []
    if not (MIN_SIZE <= width <= MAX_WIDTH and MIN_SIZE <= len(rows) <= MAX_HEIGHT):
        problems.append(
            f"Tamanho {width}x{len(rows)} fora do permitido "
            f"({MIN_SIZE}x{MIN_SIZE} a {MAX_WIDTH}x{MAX_HEIGHT})."
        )
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char not in SYMBOLS:
                problems.append(f"Símbolo desconhecido {char!r} em ({x}, {y}).")
    players = sum(row.count(Tile.PLAYER.value) for row in rows)
    if players != 1:
        problems.append(f"O mapa precisa ter exatamente um jogador (O); tem {players}.")
    if level.boss not in BOSSES:
        problems.append(f"Chefe desconhecido '{level.boss}' (use {', '.join(sorted(BOSSES))}).")
    if problems:
        return problems

    layout = layout_from_rows(rows)
    bosses = sum(kind is EnemyKind.BOSS for kind, _ in layout.enemies)
    exits = sum(row.count("E") + row.count("e") for row in rows)
    if bosses > 1:
        problems.append(f"Só pode haver um chefe (B); o mapa tem {bosses}.")
    if exits > 1:
        problems.append(f"Só pode haver uma saída (E); o mapa tem {exits}.")
    if level.boss_hp and not bosses:
        problems.append("'vida_chefe' foi informada, mas o mapa não tem chefe (B).")
    if level.boss_hp > MAX_BOSS_HP:
        problems.append(f"'vida_chefe' vai de 0 a {MAX_BOSS_HP}; o arquivo tem {level.boss_hp}.")
    if level.target > len(layout.coins):
        coins = len(layout.coins)
        problems.append(f"A meta ({level.target}) é maior que as moedas do mapa ({coins}).")
    if not (level.target or exits or bosses):
        problems.append("A fase não tem objetivo: defina 'meta', uma saída (E) ou um chefe (B).")
    problems += _unreachable(layout)
    return problems


def _unreachable(layout: LevelLayout) -> list[str]:
    """Itens que o jogador não alcança contornando as minas."""
    board = layout.board
    reach = distance_map(board, layout.player, {board.index(mine) for mine in layout.mines})
    things = [("Moeda", pos) for pos in sorted(layout.coins)]
    things += [("Power-up", pos) for pos in sorted(layout.powerups)]
    things += [("Inimigo", pos) for _, pos in layout.enemies]
    if layout.exit is not None:
        things.append(("Saída", layout.exit))
    return [
        f"{name} inalcançável em ({pos.x}, {pos.y})."
        for name, pos in things
        if reach[board.index(pos)] < 0
    ]


def check(text: str) -> tuple[LevelFile, list[str]]:
    """Lê e valida de uma vez: devolve a fase e todos os problemas."""
    level, problems = parse_level(text)
    return level, problems + validate(level)


def load_level(path: str | Path) -> LevelFile:
    """Lê um arquivo de fase; levanta :class:`LevelError` se houver problemas."""
    level, problems = check(Path(path).read_text(encoding="utf-8"))
    if problems:
        raise LevelError(problems)
    return level


def format_level(level: LevelFile) -> str:
    """Texto do arquivo de fase (o inverso de :func:`parse_level`)."""
    default = LevelFile(())
    header = [f"titulo: {level.title}"]
    names = {**_INT_KEYS, "chefe": "boss"}
    for key, attribute in names.items():
        value = getattr(level, attribute)
        if value != getattr(default, attribute):
            header.append(f"{key}: {value}")
    return "\n".join([*header, "", *level.rows]) + "\n"


def save_level(path: str | Path, level: LevelFile) -> None:
    """Grava a fase em ``path`` (UTF-8), criando a pasta se preciso."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_level(level), encoding="utf-8", newline="\n")


def paint(level: LevelFile, x: int, y: int, symbol: str) -> LevelFile:
    """Devolve a fase com ``symbol`` na célula; o jogador (O) é sempre único."""
    rows = list(level.rows)
    if symbol == Tile.PLAYER.value:
        rows = [row.replace(Tile.PLAYER.value, Tile.EMPTY.value) for row in rows]
    rows[y] = rows[y][:x] + symbol + rows[y][x + 1 :]
    return replace(level, rows=tuple(rows))
