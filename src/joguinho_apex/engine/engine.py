"""Motor do jogo: aplica uma ação por turno e resolve todas as regras.

Ordem de um turno (:meth:`GameEngine.step`):

1. cronômetros do jogador (recargas, efeitos, janela do combo);
2. ação do jogador (mover, dash, pulso ou esperar);
3. célula do jogador: moedas, power-ups, ímã, mina e fogo;
4. o fogo perde um turno de duração (depois de causar dano, nunca antes);
5. inimigos se movem e atacam; o chefe solta sua aura de fogo;
6. itens que nascem durante a fase (moedas, minas, inimigos, power-ups);
7. vitória, derrota ou fase concluída.

Entre fases (``LEVEL_COMPLETE``) a loja fica aberta: :meth:`GameEngine.buy`.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import deque
from collections.abc import Sequence
from random import Random
from typing import Any

from ..ai.strategies import AIContext, choose_move
from ..domain.entities import Enemy, LevelSpec, Player, Statistics
from ..domain.enums import Action, Difficulty, EnemyKind, GameMode, GameStatus, MapKind, PowerKind
from ..domain.events import Event, EventKind
from ..domain.geometry import Position
from ..domain.state import GameState
from ..levels.builder import LevelLayout, build_layout, layout_from_rows, layout_to_rows
from ..levels.catalog import CAMPAIGN_VERSION, CAMPAIGNS, level_count, level_for
from ..levels.editor import LevelFile
from . import rules, shop

SAVE_VERSION = 1
NEXT_LEVEL_TOKEN = ">"
MAX_EVENTS = 2000
SPAWN_ATTEMPTS = 30

_POWER_MESSAGES: dict[PowerKind, str] = {
    PowerKind.HEART: "Vida recuperada.",
    PowerKind.SHIELD: "Escudo reforçado.",
    PowerKind.FREEZE: "Inimigos congelados!",
    PowerKind.MAGNET: "Ímã ativado: moedas próximas vêm até você.",
    PowerKind.FURY: "Fúria! Encoste nos inimigos para derrotá-los.",
}


class GameEngine:
    """Uma partida: estado, gerador aleatório, eventos e histórico de ações.

    A mesma combinação de ``seed``, modo, dificuldade e ações sempre produz o
    mesmo estado, o que permite replays e testes reproduzíveis.
    """

    def __init__(
        self,
        seed: int = 0,
        mode: GameMode | str = GameMode.CAMPAIGN,
        difficulty: Difficulty | str = Difficulty.NORMAL,
        *,
        custom: tuple[LevelSpec, LevelLayout]
        | tuple[tuple[LevelSpec, LevelLayout], ...]
        | None = None,
        campaign: int = CAMPAIGN_VERSION,
        ranked: bool = True,
    ) -> None:
        """Inicia a partida na primeira fase do modo.

        ``custom`` substitui o catálogo por uma única fase pronta (usado por
        :meth:`from_rows`). ``campaign`` escolhe a versão da campanha (1 é a de
        sete fases da 21.0.0, usada para conferir replays antigos). ``ranked``
        diz se a partida vale para pontuação no perfil, ranking e conquistas.
        Modo, dificuldade ou versão inválidos levantam ``ValueError``.
        """
        self.seed = seed
        self.ranked = ranked
        self.campaign = campaign
        self.mode = GameMode(mode)
        self.difficulty = Difficulty(difficulty)
        self.tuning = rules.TUNINGS[self.difficulty]
        self.rng = Random(f"{seed}:{self.mode.value}:{self.difficulty.value}")
        self.events: deque[Event] = deque(maxlen=MAX_EVENTS)
        self.event_seq = 0
        self.history: list[str] = []
        self._custom = (
            None
            if custom is None
            else (custom,)
            if isinstance(custom[0], LevelSpec)
            else custom
        )
        self._enemy_serial = 0
        self._open_cells: list[Position] = []
        self.active_event: Any = None
        self.state = self._start_level(0, None)

    @classmethod
    def from_rows(
        cls,
        rows: Sequence[str],
        *,
        seed: int = 0,
        difficulty: Difficulty | str = Difficulty.NORMAL,
        target: int = 0,
        boss_hp: int = 0,
        time_limit: int | None = None,
        fog_radius: int = 0,
        boss: str = "guardian",
        title: str = "Fase personalizada",
        ranked: bool = False,
    ) -> GameEngine:
        """Cria uma partida de fase única a partir de um mapa em texto.

        Os símbolos são os mesmos da tela (ver ``layout_from_rows``). Se o
        mapa tem saída (``E``), ela passa a ser exigida; se tem chefe (``B``)
        e ``boss_hp`` não foi informado, o chefe recebe 3 de vida. Por padrão a
        partida não vale para ranking nem conquistas (``ranked=False``): um mapa
        feito à mão pode tornar qualquer uma delas trivial.
        """
        layout = layout_from_rows(rows)
        has_boss = any(kind is EnemyKind.BOSS for kind, _ in layout.enemies)
        if boss not in rules.BOSSES:
            raise ValueError(f"Chefe desconhecido: {boss!r}. Use um de {sorted(rules.BOSSES)}.")
        spec = LevelSpec(
            "custom",
            title,
            MapKind.OPEN,
            width=layout.board.width,
            height=layout.board.height,
            coins=len(layout.coins),
            target=target,
            boss_hp=(boss_hp or 3) if has_boss else 0,
            exit_required=layout.exit is not None,
            time_limit=time_limit,
            fog_radius=fog_radius,
            boss=boss if has_boss else "guardian",
        )
        return cls(seed, GameMode.SANDBOX, difficulty, custom=(spec, layout), ranked=ranked)

    @classmethod
    def from_levels(
        cls,
        levels: Sequence[tuple[str, LevelFile]],
        *,
        seed: int = 0,
        difficulty: Difficulty | str = Difficulty.NORMAL,
    ) -> GameEngine:
        """Cria uma campanha personalizada linear a partir de fases validadas."""
        if not 2 <= len(levels) <= 20:
            raise ValueError("Uma campanha personalizada precisa ter de 2 a 20 fases.")
        ids = [stage_id for stage_id, _ in levels]
        if len(set(ids)) != len(ids):
            raise ValueError("Os identificadores das fases precisam ser únicos.")
        custom: list[tuple[LevelSpec, LevelLayout]] = []
        for stage_id, level in levels:
            layout = layout_from_rows(level.rows)
            has_boss = any(kind is EnemyKind.BOSS for kind, _ in layout.enemies)
            spec = LevelSpec(
                f"adventure-{stage_id}",
                level.title,
                MapKind.OPEN,
                width=layout.board.width,
                height=layout.board.height,
                coins=len(layout.coins),
                target=level.target,
                boss_hp=(level.boss_hp or 3) if has_boss else 0,
                exit_required=layout.exit is not None,
                time_limit=level.time_limit or None,
                fog_radius=level.fog_radius,
                boss=level.boss if has_boss else "guardian",
            )
            custom.append((spec, layout))
        return cls(
            seed,
            GameMode.SANDBOX,
            difficulty,
            custom=tuple(custom),
            ranked=False,
        )

    # ------------------------------------------------------------------ fases

    def _spec(self, index: int) -> LevelSpec | None:
        """Receita da fase ``index`` (do catálogo ou da fase personalizada)."""
        if self._custom is not None:
            return self._custom[index][0] if 0 <= index < len(self._custom) else None
        return level_for(self.mode, index, self.campaign)

    @property
    def is_custom(self) -> bool:
        """Indica se a partida usa uma fase feita à mão (fora do catálogo)."""
        return self._custom is not None

    @property
    def level_total(self) -> int | None:
        """Quantidade de fases da partida; ``None`` no modo infinito."""
        return len(self._custom) if self._custom is not None else level_count(self.mode, self.campaign)

    def _start_level(self, index: int, previous: GameState | None) -> GameState:
        """Monta a fase ``index`` carregando pontuação e vida da fase anterior."""
        spec = self._spec(index)
        if spec is None:
            raise ValueError(f"O modo {self.mode.value} não tem a fase {index}.")
        if self._custom is not None:
            layout = self._custom[index][1]
        else:
            level_rng = Random(f"{self.seed}:{self.mode.value}:{self.difficulty.value}:{index}")
            layout = build_layout(spec, level_rng, self.tuning)
        tuning = self.tuning
        if previous is None:
            player = Player(layout.player, hp=tuning.player_hp, max_hp=tuning.player_hp)
        else:
            old = previous.player
            player = Player(
                layout.player,
                hp=min(old.max_hp, old.hp + 1),
                max_hp=old.max_hp,
                shield=old.shield,
                gold=old.gold,
                dash_bonus=old.dash_bonus,
                items=dict(old.items),
                skill_points=old.skill_points,
                skills=set(old.skills),
                cheat_death_used=old.cheat_death_used,
            )
        if "iron_skin" in player.skills and previous is None:
            player.max_hp += 1
            player.hp += 1
        if "shield_master" in player.skills:
            player.shield = min(rules.MAX_SHIELD, player.shield + 1)
        base_time = round(spec.time_limit * tuning.time_factor) if spec.time_limit else None
        if base_time is not None and "chrono_master" in player.skills:
            base_time = int(base_time * 1.3)
        state = GameState(
            session_id=str(uuid.uuid4()) if previous is None else previous.session_id,
            seed=self.seed,
            mode=self.mode,
            difficulty=self.difficulty,
            level_index=index,
            level=spec,
            board=layout.board,
            player=player,
            enemies=[self._make_enemy(kind, pos, spec) for kind, pos in layout.enemies],
            coins=set(layout.coins),
            mines=set(layout.mines),
            powerups=dict(layout.powerups),
            fires=dict(layout.fires),
            exit=layout.exit,
            stats=Statistics() if previous is None else previous.stats,
            tick=0 if previous is None else previous.tick,
            score=0 if previous is None else previous.score,
            time_limit=base_time,
            message=spec.objective,
        )
        self.state = state
        self._open_cells = layout.board.open_cells()
        self._emit(EventKind.LEVEL_START, level=spec.level_id, title=spec.title, index=index)
        return state

    def _make_enemy(self, kind: EnemyKind, pos: Position, spec: LevelSpec) -> Enemy:
        """Cria um inimigo com identificador único na partida."""
        self._enemy_serial += 1
        hp = 1
        if kind is EnemyKind.BOSS:
            hp = max(1, round(spec.boss_hp * self.tuning.enemy_factor))
        return Enemy(f"{kind.value}-{self._enemy_serial}", kind, pos, hp=hp, max_hp=hp)

    def next_level(self) -> bool:
        """Avança para a próxima fase; só funciona após ``LEVEL_COMPLETE``."""
        if self.state.status is not GameStatus.LEVEL_COMPLETE:
            return False
        self.history.append(NEXT_LEVEL_TOKEN)
        self._start_level(self.state.level_index + 1, self.state)
        return True

    # ------------------------------------------------------------------- loja

    def buy(self, item_id: str) -> bool:
        """Compra um item na loja, aberta só entre fases (``LEVEL_COMPLETE``).

        A compra entra no histórico (um dígito por item), então o replay a
        refaz. Devolve ``False``, com o motivo em ``state.message``, se a loja
        está fechada, o item não existe, falta ouro ou o item já está no máximo.
        """
        state = self.state
        player = state.player
        item = shop.BY_ID.get(item_id)
        if state.status is not GameStatus.LEVEL_COMPLETE or item is None:
            return False
        if player.gold < item.price:
            state.message = f"Ouro insuficiente para {item.title} ({player.gold}/{item.price})."
            return False
        if item_id == "heart":
            if player.max_hp >= rules.MAX_HP_CAP:
                state.message = "Sua vida máxima já está no limite."
                return False
            player.max_hp += 1
            player.hp += 1
        elif item_id == "shield":
            if player.shield >= rules.MAX_SHIELD:
                state.message = "Seu escudo já está no máximo."
                return False
            player.shield += 1
        elif item_id == "boots":
            if player.dash_bonus:
                state.message = "Você já tem as Botas."
                return False
            player.dash_bonus = rules.BOOTS_BONUS
        else:
            player.items[item_id] = player.items.get(item_id, 0) + 1
        player.gold -= item.price
        state.stats.purchases += 1
        state.message = f"Comprado: {item.title}. Ouro restante: {player.gold}."
        self.history.append(shop.TOKENS[item_id])
        self._emit(EventKind.PURCHASE, item=item_id, gold=player.gold)
        return True

    # ------------------------------------------------------------------ turno

    def step(self, action: Action) -> GameState:
        """Executa um turno com a ação do jogador e devolve o estado."""
        state = self.state
        if state.status is not GameStatus.RUNNING:
            return state
        self.history.append(action.value)
        state.tick += 1
        state.level_tick += 1
        state.stats.ticks += 1
        state.message = ""
        self._advance_timers()
        self._player_act(action)
        self._resolve_player_cell()
        self._decay_fires()
        if state.player.hp > 0:
            self._enemies_act()
            self._boss_fire()
            self._spawn()
        self._update_status()
        return state

    def _advance_timers(self) -> None:
        """Reduz recargas e efeitos temporários no início do turno."""
        state = self.state
        player = state.player
        if player.invulnerable:
            player.invulnerable -= 1
        if player.dash_cooldown:
            player.dash_cooldown -= 1
        if player.pulse_cooldown:
            player.pulse_cooldown -= 1
        if player.magnet:
            player.magnet -= 1
        if player.fury:
            player.fury -= 1
        if player.combo_timer:
            player.combo_timer -= 1
            if player.combo_timer == 0:
                player.combo = 0
        if state.freeze:
            state.freeze -= 1

    # ------------------------------------------------------- ações do jogador

    def _player_act(self, action: Action) -> None:
        """Aplica a ação escolhida pelo jogador."""
        delta = action.delta
        if delta is not None:
            self._move(delta)
        elif action is Action.DASH:
            self._dash()
        elif action is Action.PULSE:
            self._pulse()
        elif action is Action.BOMB:
            self._use_bomb()
        elif action is Action.POTION:
            self._use_potion()

    def _consume(self, item_id: str) -> bool:
        """Gasta um consumível do inventário; ``False`` se o jogador não tem."""
        state = self.state
        items = state.player.items
        if not items.get(item_id):
            state.message = f"Você não tem {shop.BY_ID[item_id].title}."
            return False
        items[item_id] -= 1
        if not items[item_id]:
            del items[item_id]
        state.stats.items_used += 1
        self._emit(EventKind.ITEM_USED, item=item_id)
        return True

    def _use_bomb(self) -> None:
        """Bomba: tira 1 de vida de cada inimigo a até ``BOMB_RADIUS`` células."""
        state = self.state
        here = state.player.position
        if not self._consume("bomb"):
            return
        radius = rules.BOMB_RADIUS + (1 if "alchemical_mastery" in state.player.skills else 0)
        hit = [e for e in state.enemies if e.position.chebyshev(here) <= radius]
        state.message = f"Bomba! {len(hit)} inimigo(s) atingido(s)."
        for enemy in hit:
            self._strike(enemy, "bomb")

    def _use_potion(self) -> None:
        """Poção: cura 1 de vida (2 com maestria alquímica); não é gasta com vida cheia."""
        state = self.state
        player = state.player
        if player.items.get("potion") and player.hp >= player.max_hp:
            state.message = "Vida cheia: a Poção foi guardada."
            return
        if self._consume("potion"):
            heal = 2 if "alchemical_mastery" in player.skills else 1
            player.hp = min(player.max_hp, player.hp + heal)
            state.message = f"Poção usada: +{heal} de vida recuperada."

    def _move(self, delta: tuple[int, int]) -> None:
        """Anda uma célula; esbarrar em inimigo fere (ou derrota, com Fúria)."""
        state = self.state
        player = state.player
        player.facing = delta
        target = player.position.moved(*delta)
        if state.board.blocked(target):
            state.message = "Movimento bloqueado."
            return
        enemy = self._enemy_at(target)
        if enemy is not None:
            if player.fury == 0:
                self._hurt(enemy.enemy_id)
                return
            self._strike(enemy, "fury")
            if enemy.hp > 0:
                return
        player.position = target
        state.stats.moves += 1

    def _dash(self) -> None:
        """Avança até ``DASH_RANGE`` células na direção atual.

        O dash salta por cima de minas e fogo nas células intermediárias,
        recolhe moedas e power-ups pelo caminho e para antes de paredes e
        inimigos. A célula de chegada é resolvida normalmente.
        """
        state = self.state
        player = state.player
        if player.dash_cooldown:
            state.message = f"Dash recarregando ({player.dash_cooldown})."
            return
        dash_range = rules.DASH_RANGE + (1 if "long_stride" in player.skills else 0)
        path: list[Position] = []
        cell = player.position
        for _ in range(dash_range):
            cell = cell.moved(*player.facing)
            if state.board.blocked(cell) or self._enemy_at(cell) is not None:
                break
            path.append(cell)
        if not path:
            state.message = "Sem espaço para o dash."
            return
        coins_before = state.level_coins
        for passed in path[:-1]:
            self._collect_at(passed)
        player.position = path[-1]
        cooldown_bonus = player.dash_bonus + (1 if "fleet_foot" in player.skills else 0)
        player.dash_cooldown = max(1, rules.DASH_COOLDOWN - cooldown_bonus)
        if "phase_shift" in player.skills:
            player.invulnerable = max(player.invulnerable, 2)
        if "momentum" in player.skills and state.level_coins > coins_before:
            player.dash_cooldown = 0
        state.stats.dashes += 1
        state.stats.moves += 1
        self._emit(EventKind.DASH, to=path[-1], cells=len(path))

    def _pulse(self) -> None:
        """Onda que atordoa inimigos próximos e fere o chefe."""
        state = self.state
        player = state.player
        if player.pulse_cooldown:
            state.message = f"Pulso recarregando ({player.pulse_cooldown})."
            return
        player.pulse_cooldown = rules.PULSE_COOLDOWN
        state.stats.pulses += 1
        pulse_radius = rules.PULSE_RADIUS + (1 if "shockwave" in player.skills else 0)
        hit = [
            enemy
            for enemy in state.enemies
            if enemy.position.manhattan(player.position) <= pulse_radius
        ]
        state.message = f"Pulso! {len(hit)} inimigo(s) atingido(s)."
        self._emit(EventKind.PULSE, hit=len(hit))
        for enemy in hit:
            if enemy.kind is EnemyKind.BOSS:
                enemy.stunned = max(enemy.stunned, rules.PULSE_BOSS_STUN)
                self._strike(enemy, "pulse")
            else:
                enemy.stunned = max(enemy.stunned, rules.PULSE_STUN)

    # ------------------------------------------------- célula do jogador

    def _resolve_player_cell(self) -> None:
        """Resolve o que há na célula do jogador: itens, ímã, mina e fogo."""
        state = self.state
        player = state.player
        self._collect_at(player.position)
        has_magnet = bool(player.magnet) or ("magnetic_aura" in player.skills)
        if has_magnet and state.coins:
            radius = rules.MAGNET_RADIUS if player.magnet else 2
            near = [
                coin
                for coin in state.coins
                if coin.manhattan(player.position) <= radius
            ]
            for coin in sorted(near):
                self._take_coin(coin)
        if player.position in state.mines:
            self._explode(player.position)
        if player.position in state.fires:
            self._hurt("fire")

    def _collect_at(self, cell: Position) -> None:
        """Recolhe moeda e power-up da célula, se houver."""
        if cell in self.state.coins:
            self._take_coin(cell)
        if cell in self.state.powerups:
            self._take_powerup(cell)

    def _take_coin(self, cell: Position) -> None:
        """Coleta uma moeda, atualizando combo, escudo de combo e saída."""
        state = self.state
        player = state.player
        state.coins.discard(cell)
        player.combo = player.combo + 1 if player.combo_timer else 1
        player.combo_timer = rules.COMBO_WINDOW
        gain = self._points(rules.SCORE_COIN * min(player.combo, rules.COMBO_CAP))
        state.score += gain
        state.stats.coins += 1
        state.stats.best_combo = max(state.stats.best_combo, player.combo)
        state.level_coins += 1
        gold_gain = 2 if "golden_touch" in player.skills else 1
        player.gold += gold_gain
        if player.combo % rules.COMBO_SHIELD_EVERY == 0:
            player.shield = min(rules.MAX_SHIELD, player.shield + 1)
        self._emit(EventKind.COLLECT, at=cell, gain=gain, combo=player.combo)
        if state.exit is not None and state.level_coins == state.level.target:
            for enemy in state.enemies:
                if enemy.kind is not EnemyKind.BOSS:
                    enemy.enraged = True
            state.message = "A saída abriu! Os inimigos ficaram enfurecidos."
            self._emit(EventKind.EXIT_OPEN, at=state.exit)

    def _take_powerup(self, cell: Position) -> None:
        """Aplica o efeito do power-up coletado."""
        state = self.state
        player = state.player
        kind = state.powerups.pop(cell)
        if kind is PowerKind.HEART:
            player.hp = min(player.max_hp, player.hp + 1)
        elif kind is PowerKind.SHIELD:
            player.shield = min(rules.MAX_SHIELD, player.shield + 2)
        elif kind is PowerKind.FREEZE:
            freeze_duration = rules.POWER_DURATION[kind] + (
                4 if "chrono_master" in player.skills else 0
            )
            state.freeze = freeze_duration
        elif kind is PowerKind.MAGNET:
            player.magnet = rules.POWER_DURATION[kind]
        else:
            player.fury = rules.POWER_DURATION[kind]
        state.score += self._points(rules.SCORE_POWERUP)
        state.stats.powerups += 1
        state.message = _POWER_MESSAGES[kind]
        self._emit(EventKind.POWERUP, at=cell, power=kind.value)

    def _decay_fires(self) -> None:
        """Tira um turno de duração de cada fogo e remove os apagados."""
        fires = self.state.fires
        if not fires:
            return
        for cell in list(fires):
            if fires[cell] <= 1:
                del fires[cell]
            else:
                fires[cell] -= 1

    # --------------------------------------------------------------- combate

    def _points(self, base: int) -> int:
        """Pontuação ajustada pela dificuldade."""
        return round(base * self.tuning.score_factor)

    def _enemy_at(self, cell: Position) -> Enemy | None:
        """Inimigo que ocupa a célula, se houver."""
        for enemy in self.state.enemies:
            if enemy.position == cell:
                return enemy
        return None

    def _hurt(self, source: str) -> None:
        """Fere o jogador, respeitando invulnerabilidade e escudo."""
        state = self.state
        player = state.player
        if player.invulnerable or player.hp <= 0:
            return
        player.invulnerable = rules.INVULNERABLE_TICKS
        if player.shield:
            player.shield -= 1
            state.message = "O escudo absorveu o golpe."
            self._emit(EventKind.SHIELD, source=source, shield=player.shield)
            return
        damage = min(player.hp, self.tuning.damage)
        player.hp -= damage
        player.combo = 0
        player.combo_timer = 0
        state.stats.damage_taken += damage
        if (
            player.hp <= 0
            and "phoenix_heart" in player.skills
            and not player.cheat_death_used
        ):
            player.hp = 1
            player.cheat_death_used = True
            player.invulnerable = 4
            for enemy in state.enemies:
                if enemy.position.manhattan(player.position) <= 3:
                    enemy.stunned = max(enemy.stunned, 3)
            state.message = "Coração de Fênix ativado! Morte evitada milagrosamente!"
            self._emit(EventKind.CHEAT_DEATH, hp=1)
            return
        state.message = "Você foi atingido!"
        self._emit(EventKind.DAMAGE, source=source, damage=damage, hp=player.hp)

    def _strike(self, enemy: Enemy, cause: str) -> None:
        """Tira 1 de vida do inimigo; ao zerar, ele é removido e pontua."""
        state = self.state
        enemy.hp -= 1
        if enemy.kind is EnemyKind.BOSS:
            self._emit(EventKind.BOSS_HIT, cause=cause, hp=enemy.hp)
            if enemy.hp > 0:
                phase = self._boss_phase(enemy)
                label = rules.BOSSES[state.level.boss].label
                state.message = f"{label} ferido ({enemy.hp}/{enemy.max_hp}) - fase {phase.name}."
                return
            state.score += self._points(rules.SCORE_BOSS)
            state.stats.bosses_defeated += 1
            state.player.skill_points += 1
            state.message = f"Chefe derrotado: {rules.BOSSES[state.level.boss].label}!"
        else:
            state.score += self._points(rules.SCORE_ENEMY)
            if cause == "mine":
                state.stats.mine_kills += 1
        state.enemies.remove(enemy)
        state.stats.enemies_defeated += 1
        self._emit(EventKind.ENEMY_DEFEATED, enemy=enemy.enemy_id, cause=cause)

    def _explode(self, origin: Position) -> None:
        """Detona a mina em ``origin`` e, em cadeia, as minas vizinhas.

        A explosão atinge as 8 células ao redor: fere o jogador, derrota
        inimigos comuns e tira 1 de vida do chefe.
        """
        state = self.state
        pending = [origin]
        while pending:
            cell = pending.pop()
            if cell not in state.mines:
                continue
            state.mines.discard(cell)
            state.stats.mines_triggered += 1
            self._emit(EventKind.EXPLOSION, at=cell)
            if state.player.position.chebyshev(cell) <= 1:
                self._hurt("mine")
            for enemy in list(state.enemies):
                if enemy.position.chebyshev(cell) <= 1:
                    self._strike(enemy, "mine")
            pending.extend(mine for mine in state.mines if mine.chebyshev(cell) <= 1)

    # -------------------------------------------------------------- inimigos

    def _boss_phase(self, boss: Enemy) -> rules.BossPhase:
        """Fase atual do chefe, conforme o perfil escolhido pela fase."""
        return rules.boss_phase(boss.hp, boss.max_hp, self.state.level.boss)

    def _speed(self, enemy: Enemy) -> tuple[int, int]:
        """Velocidade ``(passos, turnos)`` do inimigo neste momento."""
        if enemy.kind is EnemyKind.BOSS:
            return self._boss_phase(enemy).speed
        if enemy.enraged:
            return (1, 1)
        return self.tuning.enemy_speed

    def _enemies_act(self) -> None:
        """Move cada inimigo conforme sua velocidade e estratégia."""
        state = self.state
        if state.freeze or not state.enemies:
            return
        ctx = AIContext(state, self.rng)
        for enemy in list(state.enemies):
            if enemy.hp <= 0:
                continue
            if enemy.stunned:
                enemy.stunned -= 1
                continue
            steps, turns = self._speed(enemy)
            enemy.energy += steps
            # No máximo um passo por turno: a energia que sobrou de uma velocidade
            # menor (antes de enfurecer ou de o chefe mudar de fase) não vira passo extra.
            if enemy.energy >= turns and state.player.hp > 0:
                enemy.energy = min(enemy.energy - turns, turns - 1)
                self._enemy_step(enemy, ctx)

    def _enemy_step(self, enemy: Enemy, ctx: AIContext) -> None:
        """Executa um passo do inimigo: mover, atacar ou detonar uma mina."""
        state = self.state
        target = choose_move(ctx, enemy)
        if target == enemy.position:
            return
        if target == state.player.position:
            if state.player.fury:
                self._strike(enemy, "fury")
            else:
                self._hurt(enemy.enemy_id)
            return
        board = state.board
        previous = enemy.position
        ctx.occupied.discard(board.index(previous))
        ctx.occupied.add(board.index(target))
        enemy.position = target
        if enemy.kind is not EnemyKind.BOSS:
            return
        phase = self._boss_phase(enemy)
        if phase.trail:
            state.fires[previous] = rules.FIRE_TTL
        if target in state.mines:
            self._explode(target)
        if (
            phase.mine_trail
            and enemy.hp > 0
            and previous != state.exit
            and previous not in state.coins
            and previous not in state.powerups
            and previous.chebyshev(state.player.position) > 1
            and self._mine_fits(previous)
        ):
            state.mines.add(previous)
            # Os inimigos que ainda vão andar neste turno também precisam evitá-la.
            ctx.mine_cells = ctx.mine_cells | {board.index(previous)}

    def _boss_fire(self) -> None:
        """O chefe solta uma aura de fogo ao redor de si em intervalos regulares.

        O fogo nunca nasce na célula do jogador: quem entrar (ou ficar) em uma
        célula em chamas nos turnos seguintes é que se queima. A aura cresce
        a cada fase do chefe.
        """
        state = self.state
        boss = state.boss
        if boss is None or boss.stunned or state.freeze:
            return
        phase = self._boss_phase(boss)
        if (
            phase.summon_every
            and state.level_tick % phase.summon_every == 0
            and len(state.enemies) < rules.MAX_SPAWNED_ENEMIES
        ):
            cell = self._random_free_cell(rules.SPAWN_MINE_DISTANCE)
            if cell is not None:
                minion = self._make_enemy(EnemyKind.CHASER, cell, state.level)
                state.enemies.append(minion)
                state.message = f"{rules.BOSSES[state.level.boss].label}: reforços a caminho!"
                self._emit(EventKind.SPAWN, enemy=minion.enemy_id, at=cell)
        if state.level_tick % phase.fire_period:
            return
        lit = 0
        for dx, dy in phase.aura:
            cell = boss.position.moved(dx, dy)
            if not state.board.blocked(cell) and cell != state.player.position:
                state.fires[cell] = rules.FIRE_TTL
                lit += 1
        if lit:
            self._emit(EventKind.BOSS_FIRE, cells=lit, phase=phase.name)

    # ------------------------------------------------- itens durante a fase

    def _random_free_cell(self, min_distance: int = 1) -> Position | None:
        """Sorteia uma célula livre de tudo, a certa distância do jogador."""
        state = self.state
        occupied = {enemy.position for enemy in state.enemies}
        for _ in range(SPAWN_ATTEMPTS):
            cell = self.rng.choice(self._open_cells)
            if (
                cell.manhattan(state.player.position) >= min_distance
                and cell not in state.coins
                and cell not in state.mines
                and cell not in state.powerups
                and cell not in state.fires
                and cell not in occupied
                and cell != state.exit
            ):
                return cell
        return None

    def _mine_fits(self, cell: Position) -> bool:
        """Uma mina criada durante a fase precisa ter as 8 células ao redor livres.

        Assim sempre dá para contorná-la e a área livre continua conectada.
        """
        state = self.state
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                around = cell.moved(dx, dy)
                if state.board.blocked(around) or around in state.mines:
                    return False
        return True

    def _spawn(self) -> None:
        """Cria moedas, minas, inimigos e power-ups previstos pela fase."""
        state = self.state
        spec = state.level
        if spec.coin_respawn and len(state.coins) < spec.coins:
            cell = self._random_free_cell()
            if cell is not None:
                state.coins.add(cell)
        tick = state.level_tick
        mine_limit = round(rules.MAX_SPAWNED_MINES * self.tuning.mine_factor)
        if self._due(spec.mine_spawn_every) and len(state.mines) < mine_limit:
            cell = self._random_free_cell(rules.SPAWN_MINE_DISTANCE)
            if cell is not None and self._mine_fits(cell):
                state.mines.add(cell)
        if self._due(spec.enemy_spawn_every) and len(state.enemies) < rules.MAX_SPAWNED_ENEMIES:
            cell = self._random_free_cell(rules.SPAWN_ENEMY_DISTANCE)
            if cell is not None:
                kinds = spec.enemies or (EnemyKind.CHASER,)
                kind = kinds[(tick // spec.enemy_spawn_every) % len(kinds)]
                enemy = self._make_enemy(kind, cell, spec)
                state.enemies.append(enemy)
                self._emit(EventKind.SPAWN, enemy=enemy.enemy_id, at=cell)
        if self._due(spec.powerup_spawn_every) and len(state.powerups) < spec.powerups:
            cell = self._random_free_cell()
            if cell is not None:
                state.powerups[cell] = self.rng.choice(list(PowerKind))

    def _due(self, every: int) -> bool:
        """Indica se um evento periódico da fase acontece neste turno."""
        return every > 0 and self.state.level_tick % every == 0

    # ---------------------------------------------------------------- status

    def _objective_met(self) -> bool:
        """Verifica o objetivo da fase (chefe, moedas e/ou saída)."""
        state = self.state
        spec = state.level
        if spec.boss_hp > 0:
            return state.boss is None and state.level_coins >= spec.target
        if not spec.target and not spec.exit_required:
            return False
        if state.level_coins < spec.target:
            return False
        return not spec.exit_required or state.player.position == state.exit

    def _update_status(self) -> None:
        """Decide derrota, fase concluída ou vitória ao fim do turno."""
        state = self.state
        if state.player.hp <= 0:
            state.status = GameStatus.LOST
            state.message = "Você foi derrotado."
            self._emit(EventKind.LOSS, reason="hp", score=state.score)
            return
        if self._objective_met():
            time_left = state.time_left or 0
            bonus = self._points(
                rules.SCORE_LEVEL + time_left + rules.SCORE_PER_HP * state.player.hp
            )
            state.score += bonus
            state.stats.levels_completed += 1
            state.player.skill_points += 1
            limit = state.time_limit
            if limit is not None and state.level_tick <= limit * rules.FAST_CLEAR_FRACTION:
                state.stats.fast_clears += 1
            if self._spec(state.level_index + 1) is None:
                state.status = GameStatus.WON
                state.message = "Vitória! Você concluiu todas as fases."
                self._emit(EventKind.WIN, score=state.score)
            else:
                state.status = GameStatus.LEVEL_COMPLETE
                state.message = f"Fase concluída! Bônus de {bonus} pontos."
                self._emit(EventKind.LEVEL_COMPLETE, level=state.level.level_id, bonus=bonus)
            return
        if state.time_limit is not None and state.level_tick >= state.time_limit:
            state.status = GameStatus.LOST
            state.message = "Tempo esgotado."
            self._emit(EventKind.LOSS, reason="time", score=state.score)

    # ------------------------------------------------- eventos e serialização

    def _emit(self, kind: str, **payload: Any) -> None:
        """Registra um evento com número de sequência crescente."""
        self.event_seq += 1
        self.events.append(Event(self.event_seq, kind, self.state.tick, payload))

    def transcript(self, since: int = 0) -> list[dict[str, Any]]:
        """Eventos com sequência maior que ``since`` (os mais antigos expiram)."""
        return [event.as_dict() for event in self.events if event.seq > since]

    def can_unlock_skill(self, skill_id: str) -> tuple[bool, str]:
        """Confere se o jogador pode desbloquear a habilidade."""
        from ..domain.skills import DEFAULT_SKILL_TREE

        player = self.state.player
        return DEFAULT_SKILL_TREE.can_unlock(player.skills, skill_id, player.skill_points)

    def unlock_skill(self, skill_id: str) -> bool:
        """Desbloqueia a habilidade se atender aos pré-requisitos e custo de SP."""
        from ..domain.skills import DEFAULT_SKILL_TREE

        player = self.state.player
        ok, reason = self.can_unlock_skill(skill_id)
        if not ok:
            self.state.message = reason
            return False
        new_skills, remaining_sp = DEFAULT_SKILL_TREE.unlock(
            player.skills, skill_id, player.skill_points
        )
        player.skills = new_skills
        player.skill_points = remaining_sp
        self.state.stats.skills_unlocked += 1
        node = DEFAULT_SKILL_TREE.get(skill_id)
        name = node.name if node else skill_id
        if skill_id == "iron_skin":
            player.max_hp += 1
            player.hp = min(player.max_hp, player.hp + 1)
        self.state.message = f"Habilidade desbloqueada: {name}!"
        self._emit(EventKind.SKILL_UNLOCKED, skill=skill_id, remaining_sp=remaining_sp)
        return True

    def trigger_event(self, event_or_id: Any = None) -> Any:
        """Aciona um evento dinâmico aleatório (encontro, mercador ou santuário)."""
        from ..domain.random_events import DynamicEvent, EVENT_CATALOG, EVENTS_BY_ID

        if isinstance(event_or_id, DynamicEvent):
            event = event_or_id
        elif isinstance(event_or_id, str):
            event = EVENTS_BY_ID.get(event_or_id)
        else:
            event = self.rng.choice(EVENT_CATALOG)
        if event is None:
            return None
        self.active_event = event
        self.state.stats.events_encountered += 1
        self.state.message = f"Evento: {event.title}!"
        self._emit(EventKind.DYNAMIC_EVENT, event_id=event.event_id, title=event.title)
        return event

    def resolve_event_choice(self, choice_id: str) -> Any:
        """Aplica a escolha do jogador para o evento dinâmico ativo."""
        from ..domain.random_events import EventOutcome, EventType

        event = self.active_event
        if event is None:
            raise ValueError("Não há evento ativo no momento.")
        choice = next((c for c in event.choices if c.choice_id == choice_id), None)
        if choice is None:
            raise ValueError(f"Escolha inválida para o evento: {choice_id}.")

        player = self.state.player
        if choice.cost_gold > player.gold:
            raise ValueError(
                f"Ouro insuficiente: requer {choice.cost_gold}, você possui {player.gold}."
            )
        if choice.cost_hp >= player.hp:
            raise ValueError(
                f"Vida insuficiente: você possui apenas {player.hp} HP restante."
            )
        if choice.requires_item and not player.items.get(choice.requires_item):
            raise ValueError(f"Item necessário ausente: {choice.requires_item}.")

        if choice.cost_gold:
            player.gold -= choice.cost_gold
        if choice.cost_hp:
            player.hp -= choice.cost_hp
            self.state.stats.damage_taken += choice.cost_hp
        if choice.requires_item:
            self._consume(choice.requires_item)

        if event.event_type is EventType.SHRINE:
            self.state.stats.shrines_used += 1
        elif event.event_type is EventType.MERCHANT:
            self.state.stats.merchant_trades += 1

        msg = f"Decisão tomada: {choice.text}"
        hp_change = 0
        gold_change = 0
        sp_change = 0
        shield_change = 0

        if choice_id == "pray_heal":
            heal = min(player.max_hp - player.hp, 2)
            player.hp += heal
            hp_change = heal
            msg = f"O santuário cura suas feridas (+{heal} HP)."
        elif choice_id == "bathe_essence":
            player.max_hp += 1
            heal = player.max_hp - player.hp
            player.hp = player.max_hp
            msg = f"A essência primordial expande sua vida (+1 Max HP, +{heal} HP)."
        elif choice_id == "sacrifice_blood":
            player.gold += 35
            player.skill_points += 1
            gold_change = 35
            sp_change = 1
            msg = "O altar acolhe seu sacrifício (+35 ouro, +1 Ponto de Habilidade)!"
        elif choice_id == "purify_altar":
            player.shield = min(rules.MAX_SHIELD, player.shield + 2)
            shield_change = 2
            msg = "Uma barreira sagrada concede +2 de escudo!"
        elif choice_id == "channel_lightning":
            player.fury = max(player.fury, 15)
            self.state.freeze = max(self.state.freeze, 8)
            msg = "Eletricidade tempestuosa concede Fúria (15 turnos) e Congelamento (8 turnos)!"
        elif choice_id == "discharge_static":
            player.dash_cooldown = 0
            player.pulse_cooldown = 0
            msg = "A estática purga todas as recargas de habilidades!"
        elif choice_id == "buy_potion":
            player.items["potion"] = player.items.get("potion", 0) + 1
            msg = "Você adquiriu 1 Poção de Cura."
        elif choice_id == "buy_bombs":
            player.items["bomb"] = player.items.get("bomb", 0) + 2
            msg = "Você adquiriu 2 Bombas de Demolição."
        elif choice_id == "buy_tome":
            player.skill_points += 1
            sp_change = 1
            msg = "Você estudou o Tomo Arcano (+1 Ponto de Habilidade)!"
        elif choice_id == "mystery_box":
            loot = self.rng.choice(["gold", "potion", "shield"])
            if loot == "gold":
                player.gold += 45
                gold_change = 45
                msg = "O baú misterioso continha uma bolsa farta de +45 ouro!"
            elif loot == "potion":
                player.items["potion"] = player.items.get("potion", 0) + 1
                msg = "O baú continha um frasco de Poção rara!"
            else:
                player.shield = min(rules.MAX_SHIELD, player.shield + 2)
                shield_change = 2
                msg = "O baú liberou uma essência protetora (+2 Escudo)!"
        elif choice_id == "smuggler_shield":
            player.shield = min(rules.MAX_SHIELD, player.shield + 2)
            shield_change = 2
            msg = "Você comprou +2 de escudo do contrabandista."
        elif choice_id == "fight_goblin":
            player.gold += 35
            gold_change = 35
            msg = "Você interceptou o goblin e confiscou 35 moedas de ouro!"
        elif choice_id == "bomb_goblin":
            player.gold += 55
            gold_change = 55
            msg = "A bomba interceptou a rota de fuga: 55 ouro resgatados!"
        elif choice_id == "rescue_traveler":
            player.gold += 20
            player.skill_points += 1
            gold_change = 20
            sp_change = 1
            msg = "Explorador resgatado com sucesso (+20 ouro, +1 Ponto de Habilidade)!"
        elif choice_id == "give_potion":
            player.gold += 40
            player.skill_points += 1
            gold_change = 40
            sp_change = 1
            msg = "O explorador recompensou sua generosidade (+40 ouro, +1 SP)!"
        elif choice_id == "step_into_rift":
            player.dash_cooldown = 0
            player.pulse_cooldown = 0
            self.state.freeze = max(self.state.freeze, 10)
            msg = "A fenda recarregou suas perícias e congelou o tempo por 10 turnos!"
        elif choice_id == "harvest_chronos":
            player.gold += 25
            player.skill_points += 1
            gold_change = 25
            sp_change = 1
            msg = "Você recolheu éter cronológico (+25 ouro, +1 Ponto de Habilidade)!"

        self.state.message = msg
        outcome = EventOutcome(
            success=True,
            message=msg,
            hp_change=hp_change,
            gold_change=gold_change,
            sp_change=sp_change,
            shield_change=shield_change,
        )
        self._emit(
            EventKind.DYNAMIC_CHOICE,
            choice_id=choice_id,
            event_id=event.event_id,
            message=msg,
        )
        self.active_event = None
        return outcome

    def snapshot(self) -> dict[str, Any]:
        """Visão da partida para clientes, com o total de fases do modo."""
        data = self.state.snapshot()
        data["level"]["count"] = self.level_total
        data["active_event"] = self.active_event.to_dict() if self.active_event else None
        return data

    def to_dict(self) -> dict[str, Any]:
        """Serializa a partida inteira, incluindo o gerador aleatório."""
        version, internal, gauss = self.rng.getstate()
        custom = (
            None
            if self._custom is None or len(self._custom) != 1
            else self._custom[0][0].to_dict()
        )
        data: dict[str, Any] = {
            "version": SAVE_VERSION,
            "seed": self.seed,
            "mode": self.mode.value,
            "difficulty": self.difficulty.value,
            "custom": custom,
            "campaign": self.campaign,
            "ranked": self.ranked,
            "rng": [version, list(internal), gauss],
            "enemy_serial": self._enemy_serial,
            "history": "".join(self.history),
            "state": self.state.to_dict(),
            "active_event": self.active_event.event_id if self.active_event else None,
        }
        rows = self.custom_rows
        if rows is not None:
            # O mapa inicial da fase feita à mão, para que restart() funcione no save.
            data["custom_rows"] = rows
        if self._custom is not None and len(self._custom) > 1:
            data["custom_pack"] = [
                {"spec": spec.to_dict(), "rows": layout_to_rows(layout)}
                for spec, layout in self._custom
            ]
        return data

    @property
    def custom_rows(self) -> list[str] | None:
        """Mapa inicial da fase personalizada, em texto; ``None`` nas fases do catálogo."""
        return None if self._custom is None else layout_to_rows(self._custom[0][1])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameEngine:
        """Restaura uma partida salva por :meth:`to_dict`."""
        if data.get("version") != SAVE_VERSION:
            raise ValueError(f"Versão de save não suportada: {data.get('version')!r}.")
        engine = cls.__new__(cls)
        engine.seed = data["seed"]
        # Saves da 21.0.0 não têm "campaign" nem ouro: eram da campanha de sete fases.
        legacy = "gold" not in data["state"]["player"]
        engine.campaign = data.get("campaign", 1 if legacy else CAMPAIGN_VERSION)
        engine.ranked = data.get("ranked", data["custom"] is None)
        if engine.campaign not in CAMPAIGNS:
            raise ValueError(f"Versão de campanha desconhecida: {engine.campaign!r}.")
        engine.mode = GameMode(data["mode"])
        engine.difficulty = Difficulty(data["difficulty"])
        engine.tuning = rules.TUNINGS[engine.difficulty]
        engine.rng = Random()
        version, internal, gauss = data["rng"]
        engine.rng.setstate((version, tuple(internal), gauss))
        engine.events = deque(maxlen=MAX_EVENTS)
        engine.event_seq = 0
        engine.history = list(data["history"])
        engine._enemy_serial = data["enemy_serial"]
        engine.state = GameState.from_dict(data["state"])
        engine._open_cells = engine.state.board.open_cells()
        engine._custom = None
        if "custom_pack" in data:
            packed = data["custom_pack"]
            if not isinstance(packed, list) or not 2 <= len(packed) <= 20:
                raise ValueError("Pacote de fases salvo inválido.")
            stages: list[tuple[LevelSpec, LevelLayout]] = []
            for item in packed:
                if not isinstance(item, dict) or set(item) != {"spec", "rows"}:
                    raise ValueError("Fase de pacote salva inválida.")
                stages.append((LevelSpec.from_dict(item["spec"]), layout_from_rows(item["rows"])))
            engine._custom = tuple(stages)
        elif data["custom"] is not None:
            rows = data.get("custom_rows")
            if rows:
                layout = layout_from_rows(rows)
            else:  # save antigo, sem o mapa inicial
                layout = LevelLayout(engine.state.board, engine.state.player.position)
            engine._custom = ((LevelSpec.from_dict(data["custom"]), layout),)
        engine.active_event = None
        if data.get("active_event"):
            from ..domain.random_events import EVENTS_BY_ID

            engine.active_event = EVENTS_BY_ID.get(data["active_event"])
        return engine

    def restart(self) -> GameEngine:
        """Partida nova com a mesma seed, modo, dificuldade e fase personalizada."""
        return GameEngine(
            self.seed,
            self.mode,
            self.difficulty,
            custom=self._custom,
            campaign=self.campaign,
            ranked=self.ranked,
        )

    def fingerprint(self, legacy: bool = False) -> str:
        """SHA-256 do estado completo, sem o identificador da sessão.

        Duas partidas com a mesma seed e as mesmas ações têm a mesma impressão.
        ``legacy`` calcula a impressão no formato da 21.0.0 (sem ouro, itens,
        perfil de chefe nem versão da campanha), para conferir replays antigos.
        """
        data = self.to_dict()
        data["state"]["session_id"] = ""
        data.pop("ranked")  # vale para o perfil, não muda o jogo
        data.pop("active_event", None)
        if legacy:
            for key in ("campaign", "custom_rows"):
                data.pop(key, None)
            state = data["state"]
            for key in (
                "gold",
                "dash_bonus",
                "items",
                "skill_points",
                "skills",
                "cheat_death_used",
            ):
                state["player"].pop(key, None)
            for key in (
                "purchases",
                "items_used",
                "skills_unlocked",
                "shrines_used",
                "merchant_trades",
                "events_encountered",
                "auto_battler_wins",
                "telemetry_steps",
            ):
                state["stats"].pop(key, None)
            state["level"].pop("boss", None)
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()
