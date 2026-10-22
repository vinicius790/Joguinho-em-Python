"""Desenho do jogo no terminal: grade, painel lateral, legenda e telas finais."""

from __future__ import annotations

import os
import shutil
import sys
import textwrap
from collections.abc import Sequence
from typing import TextIO

from .. import CODENAME, __version__
from ..domain.enums import GameMode, GameStatus
from ..engine.engine import GameEngine
from ..engine.rules import BOSSES
from ..engine.shop import BY_ID, SHOP
from ..levels.catalog import CAMPAIGN_VERSION, MODES
from ..levels.story import ENDING, Chapter
from ..persistence.sqlite_store import DailyEntry, ScoreEntry
from ..services.progress import GameResult

PANEL_WIDTH = 38
WIDE_COLUMNS = 100

RESET = "\x1b[0m"
HOME = "\x1b[H"
CLEAR = "\x1b[2J\x1b[H"
CLEAR_LINE = "\x1b[K"
CLEAR_BELOW = "\x1b[J"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"

_COLORS: dict[str, str] = {
    "#": "\x1b[90m",
    "~": "\x1b[90m",
    "O": "\x1b[1;92m",
    "$": "\x1b[93m",
    "Q": "\x1b[31m",
    "*": "\x1b[1;91m",
    "E": "\x1b[1;96m",
    "e": "\x1b[36m",
    "X": "\x1b[1;95m",
    "Y": "\x1b[1;95m",
    "W": "\x1b[35m",
    "A": "\x1b[1;95m",
    "z": "\x1b[35m",
    "B": "\x1b[1;97;41m",
    "+": "\x1b[1;94m",
    "S": "\x1b[1;94m",
    "F": "\x1b[1;94m",
    "M": "\x1b[1;94m",
    "!": "\x1b[1;94m",
}

LEGEND: tuple[str, ...] = (
    "O você   $ moeda   Q mina   E saída",
    "X Y W A inimigos   z dormindo",
    "B chefe   * fogo   ~ névoa",
    "+ vida  S escudo  F gelo  M ímã",
    "! fúria",
)

KEYS_HELP: tuple[str, ...] = (
    "WASD/setas mover   Espaço esperar",
    "E dash   F pulso   G salvar",
    "B bomba  H poção  R reiniciar  Q sair",
)


def supports_color(stream: TextIO) -> bool:
    """Decide se vale usar cores: terminal de verdade e sem ``NO_COLOR``."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    return stream.isatty()


def enable_ansi() -> None:
    """Liga o processamento de sequências ANSI no console do Windows.

    Chamar ``os.system("")`` faz o console entrar no modo de terminal virtual;
    em outros sistemas não é preciso fazer nada.
    """
    if sys.platform == "win32":
        os.system("")


def colorize(row: str) -> str:
    """Pinta uma linha da grade, trocando de cor só quando o símbolo muda."""
    out: list[str] = []
    current = ""
    for char in row:
        color = _COLORS.get(char, "")
        if color != current:
            out.append(color or RESET)
            current = color
        out.append(char)
    if current:
        out.append(RESET)
    return "".join(out)


def _bar(value: int, maximum: int) -> str:
    """Barra de vida em texto: ``[##-]``."""
    return "[" + "#" * value + "-" * (maximum - value) + "]"


def items_text(engine: GameEngine) -> str:
    """Consumíveis do inventário em uma linha: ``Poção x2, Bomba x1``."""
    items = engine.state.player.items
    return ", ".join(f"{BY_ID[item].title} x{count}" for item, count in sorted(items.items()))


def render_story(engine: GameEngine, chapter: Chapter) -> str:
    """Tela de história mostrada antes de cada fase da campanha."""
    state = engine.state
    lines = [
        "=" * 60,
        f"  {chapter.act}",
        f"  Fase {state.level_index + 1}: {state.level.title}",
        "=" * 60,
        "",
        *textwrap.wrap(chapter.text, 56, initial_indent="  ", subsequent_indent="  "),
        "",
        f"  Objetivo: {state.level.objective}",
        "",
        "  Tecle algo para continuar (Q sai).",
    ]
    return "\n".join(lines)


def render_shop(engine: GameEngine) -> str:
    """Tela da loja, aberta entre fases: preços, ouro e inventário do jogador."""
    state = engine.state
    player = state.player
    lines = [
        "=" * 60,
        f"  LOJA - fase concluída: {state.level.title}",
        "=" * 60,
        f"  Ouro {player.gold}   Vida {player.hp}/{player.max_hp}   Escudo {player.shield}   "
        f"Pontos {state.score}",
        f"  Itens: {items_text(engine) or 'nenhum'}"
        + ("   Botas calçadas" if player.dash_bonus else ""),
        "",
    ]
    for number, item in enumerate(SHOP, start=1):
        lines.append(f"  {number}) {item.title:<8} {item.price:>3} de ouro  {item.description}")
    lines += [
        "",
        f"  > {state.message}",
        "",
        f"  1-{len(SHOP)} comprar   qualquer outra tecla: próxima fase   Q sair",
    ]
    return "\n".join(lines)


def versus_hud(names: Sequence[str], engines: Sequence[GameEngine], turn: int) -> list[str]:
    """HUD duplo do modo versus: uma linha por jogador e a indicação da vez."""
    situation = {
        GameStatus.RUNNING: "jogando",
        GameStatus.LEVEL_COMPLETE: "na loja",
        GameStatus.WON: "venceu",
        GameStatus.LOST: "caiu",
    }
    lines = [f"VERSUS - vez de {names[turn]} (jogador {turn + 1})"]
    for index, (name, engine) in enumerate(zip(names, engines, strict=True)):
        state = engine.state
        player = state.player
        mark = ">" if index == turn else " "
        lines.append(
            f"{mark} {index + 1} {name:<16} fase {state.level_index + 1}  {state.score:>6} pts  "
            f"vida {player.hp}/{player.max_hp}  ouro {player.gold:>3}  {situation[state.status]}"
        )
    lines.append("-" * 60)
    return lines


def format_daily(entries: Sequence[DailyEntry]) -> list[str]:
    """Linhas do ranking do desafio diário."""
    lines = []
    for position, entry in enumerate(entries, start=1):
        mark = "venceu" if entry.won else "caiu"
        lines.append(
            f"  {position:>2}. {entry.profile:<24} {entry.score:>7}  "
            f"{entry.levels} fase(s)  {mark}  {entry.attempts} tentativa(s)"
        )
    return lines


def panel_lines(engine: GameEngine, notice: str = "") -> list[str]:
    """Linhas do painel: fase, objetivo, números, habilidades, mensagem e ajuda."""
    state = engine.state
    player = state.player
    spec = state.level
    total = engine.level_total
    count = "?" if total is None else str(total)
    lines = [
        f"{CODENAME} {__version__}",
        f"{MODES[state.mode].title} - {state.difficulty.value} - seed {state.seed}",
        f"Fase {state.level_index + 1}/{count}: {spec.title}",
        "",
    ]
    lines += textwrap.wrap(f"Objetivo: {spec.objective}", PANEL_WIDTH)
    lines.append("")
    coins = f"{state.level_coins}/{spec.target}" if spec.target else str(state.level_coins)
    lines.append(f"Pontos  {state.score}   Ouro {player.gold}")
    lines.append(f"Moedas  {coins}")
    lines.append(f"Vida    {player.hp}/{player.max_hp} {_bar(player.hp, player.max_hp)}")
    lines.append(f"Escudo  {player.shield}   Combo x{player.combo}")
    time_left = state.time_left
    clock = f"Tempo   {time_left}   " if time_left is not None else ""
    lines.append(f"{clock}Turno {state.tick}")
    boss = state.boss
    if boss is not None:
        label = BOSSES[spec.boss].label
        lines.append(f"{label} {boss.hp}/{boss.max_hp} {_bar(boss.hp, boss.max_hp)}")
    lines.append("")
    dash = "pronto" if player.dash_cooldown == 0 else f"em {player.dash_cooldown}"
    pulse = "pronto" if player.pulse_cooldown == 0 else f"em {player.pulse_cooldown}"
    lines.append(f"Dash [E] {dash}   Pulso [F] {pulse}")
    effects = [
        f"{label} {turns}"
        for label, turns in (("Fúria", player.fury), ("Ímã", player.magnet), ("Gelo", state.freeze))
        if turns
    ]
    lines.append("Efeitos: " + (", ".join(effects) if effects else "nenhum"))
    lines.append(f"Itens: {items_text(engine)}" if player.items else "")
    message = notice or state.message
    lines += textwrap.wrap(f"> {message}", PANEL_WIDTH) if message else [""]
    lines.append("")
    lines += LEGEND
    lines.append("")
    lines += KEYS_HELP
    return lines


def render_frame(
    engine: GameEngine, color: bool = False, notice: str = "", wide: bool = True
) -> str:
    """Monta a tela do jogo.

    Em terminais largos o painel fica ao lado da grade (a tela cabe em 30
    linhas); nos estreitos, fica embaixo.
    """
    rows = engine.state.render_lines()
    grid = [colorize(row) for row in rows] if color else rows
    panel = panel_lines(engine, notice)
    if not wide:
        return "\n".join([*grid, *panel])
    height = max(len(grid), len(panel))
    blank = " " * engine.state.board.width
    lines = []
    for index in range(height):
        left = grid[index] if index < len(grid) else blank
        right = panel[index] if index < len(panel) else ""
        lines.append(f"{left}  {right}".rstrip())
    return "\n".join(lines)


def render_summary(engine: GameEngine, result: GameResult | None, top: Sequence[ScoreEntry]) -> str:
    """Tela de fim de partida: resultado, números, conquistas novas e ranking."""
    state = engine.state
    stats = state.stats
    won = state.status is GameStatus.WON
    title = "VITÓRIA!" if won else "FIM DE JOGO"
    lines = [
        "=" * 60,
        f"  {title}  -  {state.message}",
        "=" * 60,
        f"  Modo {MODES[state.mode].title} ({state.difficulty.value}), seed {state.seed}",
        f"  Pontuação final: {state.score}",
        f"  Fases concluídas: {stats.levels_completed}   Turnos: {stats.ticks}",
        f"  Moedas: {stats.coins}   Melhor combo: x{stats.best_combo}",
        f"  Inimigos derrotados: {stats.enemies_defeated}   Dano sofrido: {stats.damage_taken}",
        f"  Ouro restante: {state.player.gold}   Compras: {stats.purchases}",
    ]
    if won and state.mode is GameMode.CAMPAIGN and engine.campaign == CAMPAIGN_VERSION:
        ending = textwrap.wrap(ENDING, 56, initial_indent="  ", subsequent_indent="  ")
        lines[3:3] = [*ending, "-" * 60]
    if result is not None:
        profile = result.profile
        lines += [
            "",
            f"  {profile.name}: {result.title} - {profile.games} partida(s), "
            f"{profile.wins} vitória(s), recorde {profile.best_score}",
        ]
        if result.position is None:
            lines.append("  Fase personalizada: conta no perfil, sem ranking nem conquistas.")
        else:
            lines.append(f"  Posição no ranking de {MODES[state.mode].title}: {result.position}º")
        for achievement in result.new_achievements:
            lines.append(f"  * Nova conquista: {achievement.title} - {achievement.description}")
    if top:
        lines += ["", f"  Ranking - {MODES[state.mode].title}"]
        lines += format_ranking(top)
    lines += ["", "  R jogar de novo   P salvar replay   Q sair"]
    return "\n".join(lines)


def format_ranking(entries: Sequence[ScoreEntry]) -> list[str]:
    """Linhas de uma tabela de ranking."""
    lines = []
    for position, entry in enumerate(entries, start=1):
        mark = "venceu" if entry.won else "caiu"
        lines.append(
            f"  {position:>2}. {entry.profile:<24} {entry.score:>7}  "
            f"{entry.mode}/{entry.difficulty}  {mark}"
        )
    return lines


class Screen:
    """Escreve quadros no terminal sem piscar.

    Em terminal de verdade, cada quadro é desenhado por cima do anterior (o
    cursor volta ao canto). Fora dele (saída redirecionada), os quadros são
    apenas impressos em sequência.
    """

    def __init__(self, out: TextIO, color: bool) -> None:
        """Prepara a tela; ``color`` também liga as sequências ANSI no Windows."""
        self.out = out
        self.color = color
        self.interactive = out.isatty()
        self._started = False
        if self.interactive:
            enable_ansi()

    @property
    def wide(self) -> bool:
        """Indica se o painel cabe ao lado da grade."""
        if not self.interactive:
            return False
        return shutil.get_terminal_size((80, 24)).columns >= WIDE_COLUMNS

    def draw(self, frame: str) -> None:
        """Desenha um quadro."""
        if not self.interactive:
            self.out.write(frame + "\n\n")
            self.out.flush()
            return
        size = shutil.get_terminal_size((80, 24))
        lines = frame.split("\n")
        fits = len(lines) <= size.lines
        prefix = HOME if self._started and fits else CLEAR
        body = (CLEAR_LINE + "\n").join(lines) + CLEAR_LINE + CLEAR_BELOW
        self.out.write((HIDE_CURSOR if not self._started else "") + prefix + body)
        self.out.flush()
        self._started = True

    def close(self) -> None:
        """Devolve o cursor e pula uma linha ao sair."""
        if self.interactive and self._started:
            self.out.write(SHOW_CURSOR + "\n")
            self.out.flush()
