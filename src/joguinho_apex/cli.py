"""Interface de linha de comando: jogar, editar fases, simular e consultar o perfil."""

from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date
from functools import partial
from pathlib import Path
from typing import TextIO

from . import CODENAME, __version__
from .config import Settings
from .domain.enums import Action, Difficulty, GameMode, GameStatus
from .engine.engine import GameEngine
from .engine.shop import BY_TOKEN
from .levels.adventure import AdventureError, list_adventures, load_adventure
from .levels.catalog import MODES, custom_level, custom_level_names, daily_seed
from .levels.editor import LEVEL_SUFFIX, LevelError, blank_level, check, parse_level
from .levels.story import chapter_for
from .persistence.replay import Replay
from .persistence.sqlite_store import SQLiteStore
from .render.editor import LevelEditor
from .render.keys import KeyReader, make_key_reader
from .render.terminal import (
    Screen,
    format_daily,
    format_ranking,
    render_frame,
    render_shop,
    render_story,
    render_summary,
    supports_color,
    versus_hud,
)
from .services.achievements import ACHIEVEMENTS
from .services.progress import GameResult, rank_title, record_result
from .services.security import safe_name
from .services.versus import VersusMatch
from .simulation.benchmark import benchmark
from .simulation.runner import POLICY_NAMES, results_as_dicts, run_episodes, summarize

QUICK_SLOT = "rapido"
MAX_SEED = 2**31

KEYMAP: dict[str, Action] = {
    "w": Action.UP,
    "up": Action.UP,
    "a": Action.LEFT,
    "left": Action.LEFT,
    "s": Action.DOWN,
    "down": Action.DOWN,
    "d": Action.RIGHT,
    "right": Action.RIGHT,
    " ": Action.WAIT,
    ".": Action.WAIT,
    "enter": Action.WAIT,
    "wait": Action.WAIT,
    "e": Action.DASH,
    "dash": Action.DASH,
    "f": Action.PULSE,
    "pulse": Action.PULSE,
    "b": Action.BOMB,
    "bomb": Action.BOMB,
    "h": Action.POTION,
    "potion": Action.POTION,
}
QUIT_KEYS = ("q", "esc", "eof")


class TerminalGame:
    """Laço interativo de uma partida no terminal."""

    def __init__(
        self,
        store: SQLiteStore,
        player: str,
        new_engine: Callable[[], GameEngine],
        read_key: KeyReader,
        out: TextIO,
        color: bool,
        daily: str | None = None,
    ) -> None:
        """Guarda as dependências; ``new_engine`` cria a partida ao reiniciar.

        ``daily`` é o dia (``AAAA-MM-DD``) do desafio diário: com ele, cada
        partida encerrada também entra no ranking daquele dia.
        """
        self.daily = daily
        self.store = store
        self.player = player
        self.new_engine = new_engine
        self.read_key = read_key
        self.out = out
        self.screen = Screen(out, color)
        self.color = color
        self.saved = False

    def run(self, engine: GameEngine, from_save: bool = False) -> None:
        """Joga até o jogador sair; ao fim de cada partida grava o resultado."""
        self.saved = from_save
        notice = "Partida carregada." if from_save else ""
        intro = not from_save
        try:
            while True:
                status = engine.state.status
                if status in (GameStatus.WON, GameStatus.LOST):
                    if not self._finish(engine):
                        return
                    engine = self.new_engine()
                    notice = ""
                    intro = True
                    continue
                if intro:
                    intro = False
                    chapter = chapter_for(engine.state.level.level_id)
                    if chapter is not None:
                        self.screen.draw(render_story(engine, chapter))
                        if self.read_key() in QUIT_KEYS:
                            return
                shop = status is GameStatus.LEVEL_COMPLETE
                if shop:
                    frame = render_shop(engine)
                else:
                    frame = render_frame(engine, self.color, notice, self.screen.wide)
                self.screen.draw(frame)
                key = self.read_key()
                notice = ""
                if key in QUIT_KEYS:
                    return
                if shop:
                    if key in BY_TOKEN:
                        engine.buy(BY_TOKEN[key])
                    else:
                        engine.next_level()
                        intro = True
                elif key == "r":
                    engine = self.new_engine()
                    # O save (se houver) é da partida abandonada e continua no banco.
                    self.saved = False
                    notice = "Partida reiniciada."
                    intro = True
                elif key == "g":
                    self.store.save_game(self.player, QUICK_SLOT, engine)
                    self.saved = True
                    notice = "Jogo salvo. Use 'joguinho play --continue' para retomar."
                elif key in KEYMAP:
                    engine.step(KEYMAP[key])
                elif key:
                    notice = f"Tecla sem função: {key!r}."
        finally:
            self.screen.close()

    def _finish(self, engine: GameEngine) -> bool:
        """Mostra a tela final; devolve ``True`` se o jogador quer jogar de novo."""
        result: GameResult | None = record_result(self.store, self.player, engine)
        if self.saved:
            self.store.delete_save(self.player, QUICK_SLOT)
            self.saved = False
        # Partidas não ranqueadas (fases personalizadas) não mostram o ranking geral.
        top = self.store.leaderboard(engine.state.mode.value, 5) if engine.ranked else []
        summary = render_summary(engine, result, top)
        if self.daily is not None and engine.ranked:
            state = engine.state
            position = self.store.record_daily(self.daily, self.player, engine)
            entries = self.store.daily_leaderboard(
                self.daily, state.mode.value, state.difficulty.value, 5
            )
            summary += f"\n\n  Desafio diário de {self.daily}: você está em {position}º\n"
            summary += "\n".join(format_daily(entries))
        while True:
            self.screen.draw(summary)
            key = self.read_key()
            if key == "r":
                return True
            if key == "p":
                kind = (
                    "aventura"
                    if engine.is_custom and engine.level_total and engine.level_total > 1
                    else "fase"
                    if engine.is_custom
                    else engine.mode.value
                )
                path = Path(f"replay-{kind}-{engine.seed}.json")
                Replay.from_engine(engine).save(path)
                summary += f"\n  Replay salvo em {path}."
            elif key in QUIT_KEYS or key == "enter":
                return False


def _choose(
    title: str, options: Sequence[tuple[str, str]], read_key: KeyReader, out: TextIO
) -> int:
    """Menu numerado; devolve o índice escolhido ou ``-1`` se o jogador desistiu."""
    out.write(f"\n{title}\n")
    for number, (name, description) in enumerate(options, start=1):
        out.write(f"  {number}) {name:<14} {description}\n")
    out.write("  0) Voltar\nEscolha: ")
    out.flush()
    while True:
        key = read_key()
        if key in ("0", *QUIT_KEYS):
            out.write("\n")
            return -1
        if key.isdigit() and 1 <= int(key) <= len(options):
            out.write(f"{key}\n")
            return int(key) - 1


def _pick_mode(read_key: KeyReader, out: TextIO) -> GameMode | None:
    modes = list(GameMode)
    options = [(MODES[mode].title, MODES[mode].description) for mode in modes]
    index = _choose("Modo de jogo", options, read_key, out)
    return None if index < 0 else modes[index]


def _pick_difficulty(read_key: KeyReader, out: TextIO) -> Difficulty | None:
    descriptions = {
        Difficulty.STORY: "5 de vida, inimigos lentos, menos minas",
        Difficulty.NORMAL: "3 de vida, inimigos andam 2 de cada 3 turnos",
        Difficulty.HARD: "mais inimigos e minas, menos power-ups",
        Difficulty.NIGHTMARE: "inimigos na sua velocidade, dano dobrado",
        Difficulty.APOCALYPSE: "o dobro de inimigos, um golpe derrota",
    }
    levels = list(Difficulty)
    options = [(level.value, descriptions[level]) for level in levels]
    index = _choose("Dificuldade", options, read_key, out)
    return None if index < 0 else levels[index]


def _show_profile(store: SQLiteStore, player: str, out: TextIO) -> None:
    """Imprime totais, título e conquistas do perfil."""
    profile = store.profile(player)
    if profile is None:
        out.write(f"{player} ainda não terminou nenhuma partida.\n")
        return
    unlocked = set(store.achievements(player))
    out.write(
        f"{profile.name} - {rank_title(profile.total_score)}\n"
        f"  Partidas: {profile.games}  Vitórias: {profile.wins}  Derrotas: {profile.losses}\n"
        f"  Pontuação total: {profile.total_score}  Recorde: {profile.best_score}\n"
        f"  Moedas: {profile.coins}  Inimigos derrotados: {profile.enemies_defeated}\n"
        f"  Conquistas: {len(unlocked)}/{len(ACHIEVEMENTS)}\n"
    )
    streak = store.daily_streak(player)
    out.write(
        f"  Desafio diário: sequência atual {streak.current} dia(s), "
        f"recorde {streak.best} dia(s)\n"
    )
    for item in ACHIEVEMENTS:
        mark = "x" if item.achievement_id in unlocked else " "
        out.write(f"   [{mark}] {item.title}: {item.description}\n")


def _show_ranking(store: SQLiteStore, mode: str | None, limit: int, out: TextIO) -> None:
    """Imprime o ranking geral ou de um modo."""
    entries = store.leaderboard(mode, limit)
    scope = MODES[GameMode(mode)].title if mode else "todos os modos"
    out.write(f"Ranking - {scope}\n")
    if not entries:
        out.write("  Ainda não há partidas registradas.\n")
    for line in format_ranking(entries):
        out.write(line + "\n")


def _game_setup(
    args: argparse.Namespace, settings: Settings, read_key: KeyReader, out: TextIO
) -> tuple[int, GameMode, Difficulty] | None:
    """Define seed, modo e dificuldade de uma partida nova.

    O que não veio por argumento é perguntado em um menu (em terminal) ou
    assume o padrão (fora dele). Devolve ``None`` se o jogador desistiu.
    """
    interactive = sys.stdin.isatty() and out.isatty()
    mode: GameMode | None = GameMode(args.mode) if args.mode else None
    if mode is None:
        mode = _pick_mode(read_key, out) if interactive else GameMode.CAMPAIGN
    if mode is None:
        return None
    difficulty: Difficulty | None = Difficulty(args.difficulty) if args.difficulty else None
    if difficulty is None:
        difficulty = _pick_difficulty(read_key, out) if interactive else Difficulty.NORMAL
    if difficulty is None:
        return None
    if args.daily:
        seed = daily_seed()
    elif args.seed is not None:
        seed = args.seed
    elif settings.seed is not None:
        seed = settings.seed
    else:
        seed = secrets.randbelow(MAX_SEED)
    return seed, mode, difficulty


def _play_level(
    args: argparse.Namespace,
    settings: Settings,
    store: SQLiteStore,
    player: str,
    read_key: KeyReader,
    out: TextIO,
) -> int:
    """``play --level``: joga uma fase personalizada (caminho ou nome na pasta de fases)."""
    try:
        level = custom_level(args.level, settings.levels_dir)
    except (OSError, UnicodeDecodeError, LevelError) as error:
        out.write(f"Não foi possível carregar a fase {args.level!r}: {error}\n")
        names = custom_level_names(settings.levels_dir)
        if names:
            out.write(f"Fases em {settings.levels_dir}: {', '.join(names)}\n")
        return 1
    seed = args.seed or 0
    difficulty = args.difficulty or Difficulty.NORMAL.value

    def new_engine() -> GameEngine:
        return GameEngine.from_rows(level.rows, seed=seed, difficulty=difficulty, **level.options())

    color = not args.no_color and supports_color(out)
    TerminalGame(store, player, new_engine, read_key, out, color).run(new_engine())
    return 0


def _play(args: argparse.Namespace, settings: Settings, store: SQLiteStore, out: TextIO) -> int:
    """Comando ``play``: retoma o save ou começa uma partida nova e joga."""
    read_key = make_key_reader()
    player = safe_name(args.name or settings.player)
    if args.level:
        return _play_level(args, settings, store, player, read_key, out)
    saved: GameEngine | None = None
    new_engine: Callable[[], GameEngine]
    # ``play --daily`` vale para o ranking do dia como o comando ``daily``; uma
    # partida diária salva e retomada no mesmo dia também continua valendo.
    today = date.today()
    daily: str | None = None
    if args.resume:
        try:
            saved = store.load_game(player, QUICK_SLOT)
        except ValueError as error:
            out.write(f"{error}\n")
            return 1
        if saved is None:
            out.write(f"Não há partida salva para {player}.\n")
            return 1
        # Reiniciar refaz a mesma partida (inclusive uma fase personalizada salva).
        new_engine = saved.restart
        if not saved.is_custom and saved.seed == daily_seed(today):
            daily = today.isoformat()
    else:
        chosen = _game_setup(args, settings, read_key, out)
        if chosen is None:
            return 0
        new_engine = partial(GameEngine, *chosen)
        if args.daily:
            daily = today.isoformat()

    color = not args.no_color and supports_color(out)
    game = TerminalGame(store, player, new_engine, read_key, out, color, daily=daily)
    game.run(saved or new_engine(), from_save=saved is not None)
    return 0


def _parse_day(text: str | None) -> date:
    """Dia do desafio diário: hoje, ou uma data ``AAAA-MM-DD``."""
    return date.fromisoformat(text) if text else date.today()


def _daily(args: argparse.Namespace, store: SQLiteStore, player: str, out: TextIO) -> int:
    """Comando ``daily``: joga o desafio do dia ou mostra o ranking do dia."""
    try:
        day = _parse_day(args.date)
    except ValueError:
        out.write(f"Data inválida: {args.date!r}. Use AAAA-MM-DD.\n")
        return 2
    seed = daily_seed(day)
    if args.ranking:
        entries = store.daily_leaderboard(day.isoformat(), args.mode, args.difficulty, args.limit)
        title = MODES[GameMode(args.mode)].title
        out.write(
            f"Desafio diário de {day.isoformat()} - {title} ({args.difficulty}), seed {seed}\n"
        )
        if not entries:
            out.write("  Ninguém jogou o desafio deste dia ainda.\n")
        for line in format_daily(entries):
            out.write(line + "\n")
        return 0

    def new_engine() -> GameEngine:
        return GameEngine(seed, args.mode, args.difficulty)

    color = not args.no_color and supports_color(out)
    game = TerminalGame(
        store, player, new_engine, make_key_reader(), out, color, daily=day.isoformat()
    )
    game.run(new_engine())
    return 0


def _versus(
    args: argparse.Namespace, settings: Settings, store: SQLiteStore, player: str, out: TextIO
) -> int:
    """Comando ``versus``: dois jogadores alternam turnos no mesmo teclado."""
    names = (player, safe_name(args.name2))
    if names[0] == names[1]:
        out.write("Os dois jogadores precisam de nomes diferentes (--name e --name2).\n")
        return 2
    seed = args.seed
    if seed is None:
        seed = settings.seed if settings.seed is not None else secrets.randbelow(MAX_SEED)

    def new_engine() -> GameEngine:
        return GameEngine(seed, args.mode, args.difficulty)

    read_key = make_key_reader()
    color = not args.no_color and supports_color(out)
    screen = Screen(out, color)
    match = VersusMatch(names, new_engine)
    try:
        while True:
            if match.finished:
                screen.draw(_versus_summary(match, store))
                while (key := read_key()) not in ("r", "enter", *QUIT_KEYS):
                    pass
                if key != "r":
                    return 0
                match = VersusMatch(names, new_engine)
                continue
            engine = match.current
            shop = engine.state.status is GameStatus.LEVEL_COMPLETE
            body = render_shop(engine) if shop else render_frame(engine, color, "", screen.wide)
            screen.draw("\n".join([*versus_hud(names, match.engines, match.turn), body]))
            key = read_key()
            if key in QUIT_KEYS:
                return 0
            if shop and key in BY_TOKEN:
                match.buy(BY_TOKEN[key])
            elif shop or key in KEYMAP:
                match.step(KEYMAP.get(key, Action.WAIT))
    finally:
        screen.close()


def _versus_summary(match: VersusMatch, store: SQLiteStore) -> str:
    """Grava as duas partidas no perfil de cada jogador e monta a tela final."""
    winner = match.winner()
    verdict = "Empate!" if winner is None else f"Vitória de {match.names[winner]}!"
    lines = ["=" * 60, f"  VERSUS - {verdict}", "=" * 60]
    for name, engine in zip(match.names, match.engines, strict=True):
        state = engine.state
        result = record_result(store, name, engine)
        outcome = "concluiu" if state.status is GameStatus.WON else "caiu"
        lines.append(
            f"  {name}: {state.score} pontos, {outcome} na fase {state.level_index + 1}, "
            f"{state.stats.coins} moedas, {state.stats.ticks} turnos ({result.title})"
        )
        for achievement in result.new_achievements:
            lines.append(f"    * Nova conquista: {achievement.title}")
    lines += [
        "",
        "  Critério: quem conclui o modo vence; depois, a maior pontuação.",
        "",
        "  R revanche   Q sair",
    ]
    return "\n".join(lines)


def _validate(args: argparse.Namespace, out: TextIO) -> int:
    """Comando ``validar``: confere um arquivo de fase e lista os problemas."""
    try:
        level, problems = check(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        out.write(f"Não foi possível ler {args.file}: {error}\n")
        return 1
    if problems:
        out.write(f"{args.file}: {len(problems)} problema(s)\n")
        for problem in problems:
            out.write(f"  - {problem}\n")
        return 1
    size = f"{len(level.rows[0])}x{len(level.rows)}"
    out.write(f"{args.file}: fase válida - {level.title} ({size}).\n")
    return 0


def _edit(args: argparse.Namespace, out: TextIO) -> int:
    """Comando ``editar``: abre (ou cria) um arquivo de fase no editor do terminal."""
    path = Path(args.file)
    if not path.suffix:
        path = path.with_suffix(LEVEL_SUFFIX)
    if path.is_file():
        try:
            level, problems = parse_level(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            out.write(f"Não foi possível ler {path}: {error}\n")
            return 1
        if problems:
            out.write(f"{path}: cabeçalho inválido\n" + "".join(f"  - {p}\n" for p in problems))
            return 1
        if not level.rows:
            level = replace(level, rows=blank_level(args.width, args.height).rows)
        width = max(len(row) for row in level.rows)
        level = replace(level, rows=tuple(row.ljust(width) for row in level.rows))
    else:
        level = blank_level(args.width, args.height)
    color = not args.no_color and supports_color(out)
    LevelEditor(path, level, make_key_reader(), out, color).run()
    return 0


def _adventure_validate(path: str, out: TextIO) -> int:
    """Valida manifesto e todas as fases, sem abrir o banco do jogador."""
    try:
        pack = load_adventure(path)
    except (OSError, ValueError) as error:
        out.write(f"Aventura inválida: {error}\n")
        return 1
    out.write(f"{pack.title} [{pack.pack_id}] - {len(pack.stages)} fases válidas.\n")
    for index, stage in enumerate(pack.stages, start=1):
        out.write(f"  {index:02d}. {stage.level.title} ({stage.file})\n")
    return 0


def _adventure_list(directory: str | Path, out: TextIO) -> int:
    """Lista pacotes encontrados, sinalizando manifests que precisam de correção."""
    try:
        paths = list_adventures(directory)
    except AdventureError as error:
        out.write(f"Não foi possível listar aventuras: {error}\n")
        return 1
    if not paths:
        out.write(f"Nenhuma aventura em {directory}.\n")
        return 0
    failed = False
    for path in paths:
        try:
            pack = load_adventure(path)
        except (OSError, ValueError) as error:
            out.write(f"[inválida] {path.name}: {error}\n")
            failed = True
        else:
            out.write(f"{pack.title} [{pack.pack_id}] - {len(pack.stages)} fases ({path})\n")
    return int(failed)


def _play_adventure(
    args: argparse.Namespace,
    settings: Settings,
    store: SQLiteStore,
    player: str,
    out: TextIO,
) -> int:
    """Executa as fases do manifesto no motor normal, com progresso entre fases."""
    try:
        pack = load_adventure(args.file)
        stages = [(stage.stage_id, stage.level) for stage in pack.stages]
        seed = (
            args.seed
            if args.seed is not None
            else settings.seed
            if settings.seed is not None
            else secrets.randbelow(MAX_SEED)
        )
        new_engine = partial(
            GameEngine.from_levels,
            stages,
            seed=seed,
            difficulty=args.difficulty,
        )
        engine = new_engine()
    except (OSError, ValueError) as error:
        out.write(f"Não foi possível iniciar a aventura: {error}\n")
        return 1
    out.write(f"Aventura: {pack.title} [{pack.pack_id}] - seed {seed}\n")
    if pack.description:
        out.write(pack.description + "\n")
    color = not args.no_color and supports_color(out)
    TerminalGame(store, player, new_engine, make_key_reader(), out, color).run(engine)
    return 0


def _simulate(args: argparse.Namespace, out: TextIO) -> int:
    """Comando ``simulate``: joga várias partidas automáticas e resume."""
    results = run_episodes(
        args.episodes, args.seed, args.mode, args.difficulty, args.policy, args.max_steps
    )
    report = {
        "mode": args.mode,
        "difficulty": args.difficulty,
        "policy": args.policy,
        "summary": summarize(results),
    }
    if args.details:
        report["episodes"] = results_as_dicts(results)
    out.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


def _benchmark(args: argparse.Namespace, out: TextIO) -> int:
    """Comando ``benchmark``: mede turnos por segundo em um ou em todos os modos."""
    modes = [mode.value for mode in GameMode] if args.mode == "all" else [args.mode]
    out.write(f"{'modo':<10} {'política':<8} {'motor (turnos/s)':>18} {'total (turnos/s)':>18}\n")
    for mode in modes:
        report = benchmark(args.steps, args.seed, mode, args.difficulty, args.policy)
        out.write(
            f"{mode:<10} {args.policy:<8} {report['engine_steps_per_second']:>18} "
            f"{report['total_steps_per_second']:>18}\n"
        )
    return 0


def _replay(args: argparse.Namespace, out: TextIO) -> int:
    """Comando ``replay``: refaz uma partida gravada e confere o estado final."""
    try:
        replay = Replay.load(args.file)
        engine = replay.play()
    except (OSError, ValueError, TypeError, KeyError) as error:
        out.write(f"Não foi possível ler o replay: {error}\n")
        return 1
    matches = replay.matches(engine)
    state = engine.state
    out.write("\n".join(state.render_lines(fog=False)) + "\n")
    out.write(
        f"Modo {replay.mode} ({replay.difficulty}), seed {replay.seed}: "
        f"{len(replay.actions)} ações, status {state.status.value}, {state.score} pontos.\n"
    )
    out.write("Replay íntegro: o estado final confere.\n" if matches else "Replay NÃO confere.\n")
    return 0 if matches else 1


def _saves(store: SQLiteStore, player: str, out: TextIO) -> int:
    """Comando ``saves``: lista as partidas salvas do jogador."""
    saves = store.list_saves(player)
    if not saves:
        out.write(f"{player} não tem partidas salvas.\n")
    for save in saves:
        out.write(
            f"{save.slot}: {save.mode}/{save.difficulty}, fase {save.level}, "
            f"{save.score} pontos, salvo em {save.updated_at} UTC\n"
        )
    return 0


def _skills(args: argparse.Namespace, out: TextIO) -> int:
    """Comando ``skills``: exibe a árvore de habilidades e perks."""
    from .domain.skills import DEFAULT_SKILL_TREE, SkillBranch

    branch_filter = getattr(args, "branch", None)
    out.write("========================================\n")
    out.write("           ÁRVORE DE HABILIDADES        \n")
    out.write("========================================\n")
    for branch in SkillBranch:
        if branch_filter and branch.value != branch_filter:
            continue
        nodes = DEFAULT_SKILL_TREE.skills_in_branch(branch)
        out.write(f"\n[{branch.value.upper()}]\n")
        for node in nodes:
            reqs = f" (Requer: {', '.join(node.prerequisites)})" if node.prerequisites else ""
            out.write(f"  * {node.name} ({node.skill_id}) [Custo: {node.cost} SP]{reqs}\n")
            out.write(f"    {node.description}\n")
    return 0


def _autobattle(args: argparse.Namespace, out: TextIO) -> int:
    """Comando ``autobattle``: simulação tática autônoma com telemetria."""
    from .simulation.auto_battler import AutoBattler, TacticalProfile

    profile = TacticalProfile(args.profile)
    engine = GameEngine(args.seed, args.mode, args.difficulty)
    battler = AutoBattler(profile=profile)

    result = battler.run_battle(engine, max_ticks=args.max_steps)
    report = result.telemetry

    if getattr(args, "json", False):
        data = {
            "status": result.status,
            "turns": result.ticks,
            "score": result.score,
            "profile": profile.value,
            "skills": result.skills_unlocked,
            "telemetry": report.to_dict(),
        }
        out.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        out.write("========================================\n")
        out.write("        SIMULAÇÃO AUTO-BATTLER          \n")
        out.write("========================================\n")
        out.write(f"Status Final: {result.status.upper()}\n")
        out.write(f"Turnos Totais: {result.ticks} / {args.max_steps}\n")
        out.write(f"Pontuação: {result.score}\n")
        out.write(f"Perfil Tático: {profile.value}\n")
        out.write(f"Habilidades Desbloqueadas: {len(result.skills_unlocked)}\n\n")
        out.write(report.ascii_dashboard() + "\n")
    return 0


def _export_save(args: argparse.Namespace, store: SQLiteStore, player: str, out: TextIO) -> int:
    """Comando ``export-save``: exporta partida salva com envelope de integridade SHA-256."""
    from .persistence.save_file import export_save_file

    slot = args.slot or QUICK_SLOT
    try:
        engine = store.load_game(player, slot)
        export_save_file(engine, args.file, profile=player)
        out.write(f"Partida de '{player}' (slot: '{slot}') exportada com sucesso para '{args.file}'.\n")
        return 0
    except (ValueError, OSError) as error:
        out.write(f"Erro ao exportar partida: {error}\n")
        return 1


def _import_save(args: argparse.Namespace, store: SQLiteStore, player: str, out: TextIO) -> int:
    """Comando ``import-save``: importa arquivo de partida salva com verificação de integridade."""
    from .persistence.save_file import import_save_file
    from .persistence.sqlite_store import IntegrityError

    slot = args.slot or QUICK_SLOT
    try:
        engine, imported_profile, _ = import_save_file(args.file)
        target_player = player if player else imported_profile
        store.save_game(target_player, slot, engine)
        out.write(f"Partida importada com sucesso para '{target_player}' no slot '{slot}'.\n")
        return 0
    except IntegrityError as error:
        out.write(f"Erro de integridade ao importar: {error}\n")
        return 2
    except (ValueError, OSError) as error:
        out.write(f"Erro ao importar partida: {error}\n")
        return 1


def _positive_int(text: str) -> int:
    """Tipo do argparse para contagens que precisam ser maiores que zero."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"número inteiro esperado: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"precisa ser maior que zero: {value}")
    return value


def _map_size(text: str) -> int:
    """Tipo do argparse para largura e altura de uma fase nova (5 a 120)."""
    value = _positive_int(text)
    if not 5 <= value <= 120:
        raise argparse.ArgumentTypeError(f"precisa estar entre 5 e 120: {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Monta o analisador de argumentos com todos os subcomandos."""
    parser = argparse.ArgumentParser(
        prog="joguinho",
        description=f"{CODENAME} {__version__} - jogo de grade por turnos no terminal.",
    )
    parser.add_argument("--version", action="version", version=f"{CODENAME} {__version__}")
    parser.add_argument("--db", help="caminho do banco SQLite (padrão: JOGUINHO_DB)")
    parser.add_argument("--name", help="nome do jogador (padrão: JOGUINHO_PLAYER)")
    sub = parser.add_subparsers(dest="command")
    modes = [mode.value for mode in GameMode]
    difficulties = [level.value for level in Difficulty]

    play = sub.add_parser("play", help="jogar no terminal")
    play.add_argument("--mode", choices=modes, help="modo (sem isso, um menu pergunta)")
    play.add_argument("--difficulty", choices=difficulties, help="dificuldade")
    play.add_argument("--seed", type=int, help="seed para repetir exatamente os mesmos mapas")
    play.add_argument("--daily", action="store_true", help="usa a seed do desafio do dia")
    play.add_argument(
        "--continue", dest="resume", action="store_true", help="retoma a partida salva com G"
    )
    play.add_argument("--no-color", action="store_true", help="desliga as cores")
    play.add_argument(
        "--level", help="joga uma fase personalizada: caminho ou nome na pasta JOGUINHO_LEVELS"
    )

    daily = sub.add_parser("daily", help="desafio diário: mesma seed para todos, ranking do dia")
    daily.add_argument("--mode", choices=modes, default="campaign")
    daily.add_argument("--difficulty", choices=difficulties, default="normal")
    daily.add_argument("--date", help="dia do desafio, AAAA-MM-DD (padrão: hoje)")
    daily.add_argument("--ranking", action="store_true", help="só mostra o ranking do dia")
    daily.add_argument("--limit", type=_positive_int, default=10)
    daily.add_argument("--no-color", action="store_true", help="desliga as cores")

    versus = sub.add_parser("versus", help="dois jogadores em turnos, no mesmo teclado")
    versus.add_argument("--name2", default="Jogador 2", help="nome do segundo jogador")
    versus.add_argument("--mode", choices=modes, default="chase")
    versus.add_argument("--difficulty", choices=difficulties, default="normal")
    versus.add_argument("--seed", type=int, help="seed dos mapas (igual para os dois)")
    versus.add_argument("--no-color", action="store_true", help="desliga as cores")

    edit = sub.add_parser("editar", help="editor de fases no terminal")
    edit.add_argument("file", help="arquivo .nivel (criado se não existir)")
    edit.add_argument("--largura", dest="width", type=_map_size, default=30)
    edit.add_argument("--altura", dest="height", type=_map_size, default=12)
    edit.add_argument("--no-color", action="store_true", help="desliga as cores")
    validate = sub.add_parser("validar", help="confere um arquivo de fase")
    validate.add_argument("file", help="arquivo .nivel")

    adventure = sub.add_parser("aventura", help="cria e joga campanhas comunitárias em pacotes")
    adventure_sub = adventure.add_subparsers(dest="adventure_action", required=True)
    adventure_validate = adventure_sub.add_parser("validar", help="valida o manifesto e todas as fases")
    adventure_validate.add_argument("file", help="arquivo .aventura.json")
    adventure_list = adventure_sub.add_parser("listar", help="lista campanhas comunitárias")
    adventure_list.add_argument("directory", nargs="?", help="pasta (padrão: JOGUINHO_LEVELS)")
    adventure_play = adventure_sub.add_parser("jogar", help="joga uma campanha comunitária")
    adventure_play.add_argument("file", help="arquivo .aventura.json")
    adventure_play.add_argument("--difficulty", choices=difficulties, default="normal")
    adventure_play.add_argument("--seed", type=int, help="seed para repetir a aventura")
    adventure_play.add_argument("--no-color", action="store_true", help="desliga as cores")

    simulate = sub.add_parser("simulate", help="partidas automáticas e estatísticas")
    simulate.add_argument("--episodes", type=_positive_int, default=20)
    simulate.add_argument("--seed", type=int, default=0)
    simulate.add_argument("--mode", choices=modes, default="campaign")
    simulate.add_argument("--difficulty", choices=difficulties, default="normal")
    simulate.add_argument("--policy", choices=POLICY_NAMES, default="bot")
    simulate.add_argument("--max-steps", type=_positive_int, default=2000)
    simulate.add_argument("--details", action="store_true", help="inclui cada partida")

    bench = sub.add_parser("benchmark", help="mede turnos por segundo do motor")
    bench.add_argument("--steps", type=_positive_int, default=10_000)
    bench.add_argument("--seed", type=int, default=0)
    bench.add_argument("--mode", choices=[*modes, "all"], default="all")
    bench.add_argument("--difficulty", choices=difficulties, default="normal")
    bench.add_argument("--policy", choices=POLICY_NAMES, default="bot")

    sub.add_parser("profile", help="mostra perfil e conquistas do jogador")
    ranking = sub.add_parser("ranking", help="mostra as maiores pontuações")
    ranking.add_argument("--mode", choices=modes)
    ranking.add_argument("--limit", type=_positive_int, default=10)
    sub.add_parser("saves", help="lista as partidas salvas do jogador")
    replay = sub.add_parser("replay", help="refaz e confere um replay gravado")
    replay.add_argument("file", help="arquivo .json salvo com P na tela final")

    skills_parser = sub.add_parser("skills", help="exibe a árvore de habilidades")
    skills_parser.add_argument(
        "--branch", choices=["combat", "agility", "utility"], help="filtra por ramo de habilidade"
    )

    ab = sub.add_parser("autobattle", help="executa simulação autônoma com perfil tático e telemetria")
    ab.add_argument(
        "--profile",
        choices=["balanced", "aggressive", "survivor", "collector"],
        default="balanced",
        help="perfil tático do auto-battler",
    )
    ab.add_argument("--seed", type=int, default=0, help="semente pseudoaleatória")
    ab.add_argument("--mode", choices=modes, default="campaign", help="modo de jogo")
    ab.add_argument("--difficulty", choices=difficulties, default="normal", help="dificuldade")
    ab.add_argument("--max-steps", type=_positive_int, default=2000, help="máximo de turnos")
    ab.add_argument("--json", action="store_true", help="saída em formato JSON estruturado")

    exp = sub.add_parser("export-save", help="exporta partida salva com verificação de integridade SHA-256")
    exp.add_argument("file", help="arquivo de destino (.save.json)")
    exp.add_argument("--slot", default=QUICK_SLOT, help="slot do save (padrão: rapido)")

    imp = sub.add_parser("import-save", help="importa arquivo de save validando integridade criptográfica")
    imp.add_argument("file", help="arquivo de origem (.save.json)")
    imp.add_argument("--slot", default=QUICK_SLOT, help="slot do save de destino (padrão: rapido)")
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    """Ponto de entrada do comando ``joguinho``; devolve o código de saída."""
    stream = sys.stdout if out is None else out
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        if sys.stdin.isatty() and stream.isatty():
            args = parser.parse_args(["play"])
        else:
            parser.print_help(stream)
            return 0
    if args.command == "simulate":
        return _simulate(args, stream)
    if args.command == "benchmark":
        return _benchmark(args, stream)
    if args.command == "replay":
        return _replay(args, stream)
    if args.command == "validar":
        return _validate(args, stream)
    if args.command == "editar":
        return _edit(args, stream)
    if args.command == "skills":
        return _skills(args, stream)
    if args.command == "autobattle":
        return _autobattle(args, stream)
    if args.command == "aventura" and args.adventure_action == "validar":
        return _adventure_validate(args.file, stream)
    if args.command == "aventura" and args.adventure_action == "listar":
        try:
            settings = Settings.from_env()
        except ValueError as error:
            stream.write(f"Configuração inválida: {error}\n")
            return 2
        return _adventure_list(args.directory or settings.levels_dir, stream)

    try:
        settings = Settings.from_env()
    except ValueError as error:
        stream.write(f"Configuração inválida: {error}\n")
        return 2
    player = safe_name(getattr(args, "name", None) or settings.player)
    db_path = getattr(args, "db", None) or settings.db_path
    try:
        store = SQLiteStore(db_path)
    except (sqlite3.Error, OSError) as error:
        stream.write(f"Não foi possível abrir o banco {db_path}: {error}\n")
        return 2
    with store:
        if args.command == "export-save":
            return _export_save(args, store, player, stream)
        if args.command == "import-save":
            return _import_save(args, store, player, stream)
        if args.command == "aventura":
            try:
                return _play_adventure(args, settings, store, player, stream)
            except KeyboardInterrupt:
                stream.write("\n")
                return 130
        if args.command == "play":
            try:
                return _play(args, settings, store, stream)
            except KeyboardInterrupt:
                stream.write("\n")
                return 130
        if args.command in ("daily", "versus"):
            try:
                if args.command == "daily":
                    return _daily(args, store, player, stream)
                return _versus(args, settings, store, player, stream)
            except KeyboardInterrupt:
                stream.write("\n")
                return 130
        if args.command == "profile":
            _show_profile(store, player, stream)
            return 0
        if args.command == "ranking":
            _show_ranking(store, args.mode, args.limit, stream)
            return 0
        return _saves(store, player, stream)
