"""Árvore de habilidades (Skill Tree) do jogador.

Define nós organizados em três ramificações temáticas (Combate, Agilidade e Utilidade),
com pré-requisitos, custos em pontos de habilidade (SP) e modificadores de atributos.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SkillBranch(StrEnum):
    """Ramificações da árvore de habilidades."""

    COMBAT = "combat"
    AGILITY = "agility"
    UTILITY = "utility"


@dataclass(frozen=True, slots=True)
class SkillNode:
    """Nó individual da árvore de habilidades."""

    skill_id: str
    name: str
    description: str
    branch: SkillBranch
    tier: int
    cost: int
    prerequisites: tuple[str, ...]
    effect: str

    def to_dict(self) -> dict[str, Any]:
        """Serializa o nó da habilidade."""
        return {
            "id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "branch": self.branch.value,
            "tier": self.tier,
            "cost": self.cost,
            "prerequisites": list(self.prerequisites),
            "effect": self.effect,
        }


# Catálogo completo de habilidades
SKILL_CATALOG: tuple[SkillNode, ...] = (
    # Ramificação COMBATE / VITALIDADE
    SkillNode(
        skill_id="iron_skin",
        name="Pele de Ferro",
        description="Aumenta a vida máxima em +1 e a vida inicial da fase.",
        branch=SkillBranch.COMBAT,
        tier=1,
        cost=1,
        prerequisites=(),
        effect="max_hp_plus_1",
    ),
    SkillNode(
        skill_id="shield_master",
        name="Mestre do Escudo",
        description="Inicia cada fase com +1 escudo de proteção.",
        branch=SkillBranch.COMBAT,
        tier=2,
        cost=2,
        prerequisites=("iron_skin",),
        effect="start_shield_plus_1",
    ),
    SkillNode(
        skill_id="shockwave",
        name="Onda de Choque",
        description="Aumenta o raio do pulso em +1 célula (raio 4).",
        branch=SkillBranch.COMBAT,
        tier=2,
        cost=2,
        prerequisites=("iron_skin",),
        effect="pulse_radius_plus_1",
    ),
    SkillNode(
        skill_id="phoenix_heart",
        name="Coração de Fênix",
        description="Evita um golpe letal por partida, sobrevivendo com 1 HP e repelindo ameaças.",
        branch=SkillBranch.COMBAT,
        tier=3,
        cost=3,
        prerequisites=("shield_master", "shockwave"),
        effect="cheat_death_once",
    ),
    # Ramificação AGILIDADE / MOBILIDADE
    SkillNode(
        skill_id="fleet_foot",
        name="Passo Ligeiro",
        description="Reduz o tempo de recarga do dash em 1 turno.",
        branch=SkillBranch.AGILITY,
        tier=1,
        cost=1,
        prerequisites=(),
        effect="dash_cooldown_minus_1",
    ),
    SkillNode(
        skill_id="long_stride",
        name="Salto Longo",
        description="Aumenta o alcance do dash para 4 células.",
        branch=SkillBranch.AGILITY,
        tier=2,
        cost=2,
        prerequisites=("fleet_foot",),
        effect="dash_range_4",
    ),
    SkillNode(
        skill_id="phase_shift",
        name="Mudança de Fase",
        description="Concede 1 turno de invulnerabilidade imediatamente após realizar um dash.",
        branch=SkillBranch.AGILITY,
        tier=2,
        cost=2,
        prerequisites=("fleet_foot",),
        effect="dash_invulnerable_1",
    ),
    SkillNode(
        skill_id="momentum",
        name="Ímpeto Cinético",
        description="Eliminar inimigo ou coletar moedas durante o dash reseta instantaneamente o cooldown.",
        branch=SkillBranch.AGILITY,
        tier=3,
        cost=3,
        prerequisites=("long_stride", "phase_shift"),
        effect="dash_reset_on_collect",
    ),
    # Ramificação UTILIDADE / FORTUNA
    SkillNode(
        skill_id="golden_touch",
        name="Toque Dourado",
        description="Cada moeda coletada concede +1 de ouro extra (2 de ouro por moeda).",
        branch=SkillBranch.UTILITY,
        tier=1,
        cost=1,
        prerequisites=(),
        effect="gold_multiplier_2",
    ),
    SkillNode(
        skill_id="magnetic_aura",
        name="Aura Magnética",
        description="Atrai moedas automaticamente em um raio passivo permanente de 2 células.",
        branch=SkillBranch.UTILITY,
        tier=2,
        cost=2,
        prerequisites=("golden_touch",),
        effect="passive_magnet_2",
    ),
    SkillNode(
        skill_id="alchemical_mastery",
        name="Maestria Alquímica",
        description="Poções curam +1 de vida (2 HP por poção) e bombas têm raio expandido em +1.",
        branch=SkillBranch.UTILITY,
        tier=2,
        cost=2,
        prerequisites=("golden_touch",),
        effect="boosted_consumables",
    ),
    SkillNode(
        skill_id="chrono_master",
        name="Senhor do Tempo",
        description="O efeito de congelamento dura +4 turnos e fases com tempo ganham +30% de turnos.",
        branch=SkillBranch.UTILITY,
        tier=3,
        cost=3,
        prerequisites=("magnetic_aura", "alchemical_mastery"),
        effect="extended_timers",
    ),
)

SKILLS_BY_ID: dict[str, SkillNode] = {node.skill_id: node for node in SKILL_CATALOG}


class SkillTree:
    """Gerenciador da árvore de habilidades."""

    def __init__(self, catalog: tuple[SkillNode, ...] = SKILL_CATALOG) -> None:
        """Inicializa a árvore com um catálogo de nós."""
        self._catalog = catalog
        self._by_id = {node.skill_id: node for node in catalog}

    @property
    def all_skills(self) -> tuple[SkillNode, ...]:
        """Devolve todas as habilidades registradas."""
        return self._catalog

    def get(self, skill_id: str) -> SkillNode | None:
        """Obtém um nó de habilidade pelo identificador."""
        return self._by_id.get(skill_id)

    def can_unlock(
        self, unlocked: set[str], skill_id: str, available_sp: int
    ) -> tuple[bool, str]:
        """Confere se a habilidade pode ser desbloqueada."""
        node = self._by_id.get(skill_id)
        if node is None:
            return False, f"Habilidade desconhecida: {skill_id}."
        if skill_id in unlocked:
            return False, f"Habilidade '{node.name}' já está desbloqueada."
        if available_sp < node.cost:
            return (
                False,
                f"Pontos de habilidade insuficientes ({available_sp}/{node.cost} SP necessários).",
            )
        missing_prereqs = [req for req in node.prerequisites if req not in unlocked]
        if missing_prereqs:
            req_names = [self._by_id[req].name for req in missing_prereqs if req in self._by_id]
            return False, f"Pré-requisitos pendentes: {', '.join(req_names)}."
        return True, ""

    def unlock(
        self, unlocked: set[str], skill_id: str, available_sp: int
    ) -> tuple[set[str], int]:
        """Desbloqueia a habilidade e deduz o custo em SP.

        Levanta ValueError se a habilidade não puder ser desbloqueada.
        """
        ok, reason = self.can_unlock(unlocked, skill_id, available_sp)
        if not ok:
            raise ValueError(reason)
        node = self._by_id[skill_id]
        new_unlocked = set(unlocked)
        new_unlocked.add(skill_id)
        remaining_sp = available_sp - node.cost
        return new_unlocked, remaining_sp

    def branch_skills(self, branch: SkillBranch) -> list[SkillNode]:
        """Filtra habilidades de uma ramificação específica."""
        return [node for node in self._catalog if node.branch == branch]

    skills_in_branch = branch_skills

    def branch_progress(self, unlocked: set[str], branch: SkillBranch) -> tuple[int, int]:
        """Devolve (desbloqueadas, total) em uma ramificação."""
        branch_nodes = self.branch_skills(branch)
        unlocked_count = sum(1 for node in branch_nodes if node.skill_id in unlocked)
        return unlocked_count, len(branch_nodes)

    def is_branch_complete(self, unlocked: set[str], branch: SkillBranch) -> bool:
        """Indica se toda a ramificação foi desbloqueada."""
        unlocked_count, total = self.branch_progress(unlocked, branch)
        return unlocked_count == total and total > 0


# Instância global padrão
DEFAULT_SKILL_TREE = SkillTree()
