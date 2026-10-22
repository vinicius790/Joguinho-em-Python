"""Testes para Árvore de Habilidades (Skill Tree) e Eventos Dinâmicos."""

import pytest

from joguinho_apex.domain.entities import Position
from joguinho_apex.domain.enums import Action, GameMode, GameStatus
from joguinho_apex.domain.random_events import (
    DEFAULT_EVENTS,
    DynamicEvent,
    EventChoice,
    EventType,
    create_random_event,
)
from joguinho_apex.domain.skills import (
    DEFAULT_SKILL_TREE,
    SKILL_CATALOG,
    SkillBranch,
    SkillNode,
    SkillTree,
)
from joguinho_apex.engine.engine import GameEngine


def test_skill_tree_catalog_integrity():
    tree = DEFAULT_SKILL_TREE
    assert len(tree.all_skills) >= 12
    for node in tree.all_skills:
        assert node.cost > 0
        assert node.branch in SkillBranch
        for prereq in node.prerequisites:
            assert tree.get(prereq) is not None, f"Prerequisite {prereq} not in catalog"


def test_skill_tree_unlock_prerequisites():
    tree = SkillTree()
    unlocked: set[str] = set()

    # Tenta desbloquear tier 2 sem pré-requisito
    can, reason = tree.can_unlock(unlocked, "shield_master", available_sp=5)
    assert not can
    assert "Pré-requisitos pendentes" in reason

    # Falta de SP
    can, reason = tree.can_unlock(unlocked, "iron_skin", available_sp=0)
    assert not can
    assert "Pontos de habilidade insuficientes" in reason

    # Desbloqueia iron_skin
    can, reason = tree.can_unlock(unlocked, "iron_skin", available_sp=2)
    assert can
    unlocked, sp = tree.unlock(unlocked, "iron_skin", available_sp=2)
    assert "iron_skin" in unlocked
    assert sp == 1

    # Agora pode desbloquear shield_master com SP suficiente
    can, _ = tree.can_unlock(unlocked, "shield_master", available_sp=2)
    assert can
    unlocked, sp = tree.unlock(unlocked, "shield_master", available_sp=3)
    assert "shield_master" in unlocked
    assert sp == 1


def test_skill_tree_branch_progress():
    tree = SkillTree()
    unlocked = {"iron_skin", "shield_master"}
    done, total = tree.branch_progress(unlocked, SkillBranch.COMBAT)
    assert done == 2
    assert total == 4
    assert not tree.is_branch_complete(unlocked, SkillBranch.COMBAT)


def test_engine_skill_modifiers():
    # Motor com mapa simples onde a moeda está diretamente à direita
    rows = ["####", "#O$#", "####"]
    engine = GameEngine.from_rows(rows, target=10)

    # Concede SP e desbloqueia habilidades
    engine.state.player.skill_points = 10
    engine.unlock_skill("golden_touch")
    assert "golden_touch" in engine.state.player.skills

    # Pega moeda com golden_touch: ouro deve aumentar em 2 em vez de 1
    engine.step(Action.RIGHT)
    assert engine.state.player.gold == 2

    # Desbloqueia maestria alquímica
    engine.unlock_skill("alchemical_mastery")
    engine.state.player.items["potion"] = 1
    engine.state.player.hp = 1
    engine.state.player.max_hp = 5
    engine.step(Action.POTION)
    # Cura 2 HP em vez de 1
    assert engine.state.player.hp == 3


def test_phoenix_heart_cheat_death():
    rows = ["#####", "#OQ #", "#####"]
    engine = GameEngine.from_rows(rows, target=1)
    engine.state.player.skills.add("phoenix_heart")
    engine.state.player.hp = 1
    engine.state.player.shield = 0

    # Golpe letal recebido (com 1 de vida)
    engine._hurt("teste letal")
    # Deve evitar a morte e ficar com 1 HP
    assert engine.state.player.hp == 1
    assert engine.state.player.cheat_death_used is True
    assert engine.state.status == GameStatus.RUNNING


def test_random_events_generation_and_choice_resolution():
    engine = GameEngine.from_rows(["#####", "#O $#", "#####"], target=1)
    event = create_random_event(engine.rng)
    assert isinstance(event, DynamicEvent)
    assert len(event.choices) >= 2

    engine.trigger_event(event)
    assert engine.active_event == event
    assert engine.state.stats.events_encountered == 1

    # Aplica primeira escolha
    choice = event.choices[0]
    initial_gold = engine.state.player.gold
    initial_hp = engine.state.player.hp
    outcome = engine.resolve_event_choice(choice.choice_id)

    assert engine.active_event is None
    assert outcome is not None
