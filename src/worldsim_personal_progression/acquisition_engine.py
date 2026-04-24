"""
Детерминированные вычисления алгоритма приобретения возможностей v0.4-rev.

Шаги 2, 5, 6, 7, 8, 9 — чистая математика без LLM.
LLM-оценка (шаги 1–5, 8) поступает снаружи как AcquisitionEval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from worldsim_schemas import (
    AcquisitionEval,
    AcquisitionRequest,
    Capability,
    CapabilityRoute,
    ConflictStatus,
    FeasibilityStatus,
    PlayerProgression,
    Trial,
    VectorType,
)

# --- константы (соответствуют таблице параметров v0.4-rev) ---------------

VIABLE_THRESHOLD = 0.60
FALLBACK_THRESHOLD = 0.30

_K_UI = 1.0        # регулировочный коэф. ядра
_B = 0.70          # доля ядра в итоговой ценности
_K_UNIQUE = 0.50   # коэф. скидки уникальности (потолок 50 %)
_K_TYPE = 0.30     # вес штрафа насыщения типа
_MAX_TYPE_POWER = 400.0  # порог насыщения (~2 возможности с max влиянием)


@dataclass
class DecompositionConfig:
    """Параметры рекурсивной декомпозиции маршрутов (шаг 9)."""

    a0: float = 0.40       # базовый коэф. раздутия (затухает с глубиной)
    depth_max: int = 3     # потолок глубины рекурсии
    d_atom: float = 10.0   # порог атомарности — ниже не дробится
    n_max: int = 5         # максимум ветвей на одном уровне
    epsilon: float = 0.02  # допуск точности суммы атомарных испытаний


# --- Шаг 2: выполнимость ------------------------------------------------


def calc_feasibility_score(eval_: AcquisitionEval) -> float:
    """score = 0.40·channel + 0.35·resources + 0.25·world"""
    f = eval_.feasibility
    return 0.40 * f.channel_access + 0.35 * f.resource_readiness + 0.25 * f.world_permission


def get_feasibility_status(score: float) -> FeasibilityStatus:
    if score >= VIABLE_THRESHOLD:
        return FeasibilityStatus.FULL
    if score >= FALLBACK_THRESHOLD:
        return FeasibilityStatus.PARTIAL
    return FeasibilityStatus.BLOCKED


# --- Шаг 5: уникальность ------------------------------------------------


def calc_uniqueness(eval_: AcquisitionEval) -> float:
    """uniqueness = 0.40·path_rarity + 0.35·persona_fit + 0.25·condition_rarity"""
    u = eval_.uniqueness
    return 0.40 * u.path_rarity + 0.35 * u.persona_fit + 0.25 * u.condition_rarity


# --- Шаг 6: ценность ----------------------------------------------------


def calc_value(
    eval_: AcquisitionEval,
    total_impact: float,
    *,
    k_ui: float = _K_UI,
    b: float = _B,
) -> tuple[float, float, float]:
    """
    Возвращает (value, core, bonus).

    Ядро = (universality/100) × (total_impact/200) × k_ui × 100
    Надбавка = 0.50·divergence + 0.30·(100−favorable) + 0.20·(100−prevalence)
    Итог = ядро·b + надбавка·(1−b), ограничен [0..100]
    """
    core = (eval_.universality / 100.0) * (total_impact / 200.0) * k_ui * 100.0

    bonus = (
        0.50 * eval_.divergence
        + 0.30 * (100.0 - eval_.favorable_factors)
        + 0.20 * (100.0 - eval_.prevalence)
    )

    value = core * b + bonus * (1.0 - b)
    return min(max(value, 0.0), 100.0), core, bonus


# --- Шаг 7: сложность ---------------------------------------------------


def get_capabilities_of_type(progression: PlayerProgression, type_: str) -> list[Capability]:
    return [c for c in progression.capabilities if c.type == type_]


def calc_type_saturation(caps: list[Capability]) -> float:
    """Σ (world_impact + persona_impact) по всем возможностям того же типа."""
    return sum(c.world_impact + c.persona_impact for c in caps)


def calc_difficulty(
    value: float,
    uniqueness: float,
    type_saturation: float,
    feasibility_score: float,
    partial_coverage: bool,
    *,
    k_unique: float = _K_UNIQUE,
    k_type: float = _K_TYPE,
    max_type_power: float = _MAX_TYPE_POWER,
) -> tuple[float, float]:
    """
    Возвращает (difficulty_target, saturation_penalty).

    Скидка = min(uniqueness × k_unique, 0.50)
    Базовая = value × (1 − скидка)
    Штраф насыщения = k_type × min(saturation / MAX_TYPE_POWER, 1) × 100
    При partial_coverage: итог × (feasibility_score / VIABLE_THRESHOLD)
    """
    discount = min(uniqueness * k_unique, 0.50)
    base = value * (1.0 - discount)
    penalty = k_type * min(type_saturation / max_type_power, 1.0) * 100.0
    difficulty = base + penalty
    if partial_coverage:
        difficulty *= feasibility_score / VIABLE_THRESHOLD
    return min(max(difficulty, 0.0), 100.0), round(penalty, 2)


# --- Шаг 8: конфликты ---------------------------------------------------


def resolve_conflict_status(eval_: AcquisitionEval) -> ConflictStatus:
    c = eval_.conflicts
    if not c.conflicting_capability_ids:
        return ConflictStatus.CLEAN
    if c.alternative_vectors:
        return ConflictStatus.ALTERNATIVE_ROUTE
    # Частичный конфликт: затронуты не все 4 типа вектора
    if c.conflict_types_affected < 4:
        return ConflictStatus.PARTIAL_CONFLICT
    return ConflictStatus.FULL_CONFLICT_PENDING


# --- Шаг 9: декомпозиция маршрутов --------------------------------------


def _decompose_recursive(
    difficulty: float,
    depth: int,
    config: DecompositionConfig,
    counter: list[int],
) -> list[Trial]:
    """
    Рекурсивно дробит difficulty на атомарные испытания.

    Условие остановки: difficulty ≤ d_atom ИЛИ depth ≥ depth_max.
    Раздутие на каждом уровне: D × (1 + a_eff × ln N), где a_eff = a0/(1+depth).
    """
    if difficulty <= config.d_atom or depth >= config.depth_max:
        counter[0] += 1
        tid = f"t{counter[0]}"
        return [
            Trial(
                id=tid,
                description=f"Испытание {counter[0]}",
                difficulty=round(difficulty, 2),
                error_chance=round(min(difficulty / 100.0, 1.0), 3),
                error_cost=round(min(difficulty * 0.5, 100.0), 2),
            )
        ]

    n = min(config.n_max, max(2, round(difficulty / config.d_atom)))
    a_eff = config.a0 / (1.0 + depth)
    inflated = difficulty * (1.0 + a_eff * math.log(n))
    part = inflated / n

    trials: list[Trial] = []
    for _ in range(n):
        trials.extend(_decompose_recursive(part, depth + 1, config, counter))
    return trials


def _apply_epsilon_correction(
    trials: list[Trial],
    target: float,
    config: DecompositionConfig,
) -> list[Trial]:
    """
    ε-проверка (шаг 9): сумма атомарных испытаний не должна отклоняться
    от расчётной суммы уровня более чем на ε.

    При нарушении равномерно корректируем все испытания.
    """
    if not trials or target == 0:
        return trials

    actual = sum(t.difficulty for t in trials)
    if actual == 0:
        return trials

    relative_error = abs(actual - target) / target
    if relative_error <= config.epsilon:
        return trials

    # Масштабируем все испытания так, чтобы сумма стала равна target
    scale = target / actual
    corrected = []
    for t in trials:
        new_diff = round(t.difficulty * scale, 2)
        new_diff = min(max(new_diff, 0.0), 100.0)
        corrected.append(
            Trial(
                id=t.id,
                description=t.description,
                difficulty=new_diff,
                error_chance=round(min(new_diff / 100.0, 1.0), 3),
                error_cost=round(min(new_diff * 0.5, 100.0), 2),
                irreversibility=t.irreversibility,
                accumulation=t.accumulation,
            )
        )
    return corrected


def decompose_into_routes(
    difficulty_target: float,
    vector: VectorType,
    n_routes: int = 1,
    *,
    config: DecompositionConfig | None = None,
) -> list[CapabilityRoute]:
    """
    Строит n_routes маршрутов, каждый — результат независимой декомпозиции
    difficulty_target. Все маршруты используют один и тот же вектор.
    """
    if config is None:
        config = DecompositionConfig()

    routes: list[CapabilityRoute] = []
    for _ in range(n_routes):
        counter = [0]
        trials = _decompose_recursive(difficulty_target, 0, config, counter)
        trials = _apply_epsilon_correction(trials, difficulty_target, config)

        total = sum(t.difficulty for t in trials)
        inflation = total / difficulty_target if difficulty_target > 0 else 1.0

        routes.append(
            CapabilityRoute(
                vector=vector,
                trials=trials,
                total_difficulty=round(total, 2),
                inflation_factor=round(inflation, 3),
            )
        )

    return routes
