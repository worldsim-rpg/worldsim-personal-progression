"""
Планировщик приобретения возможностей — v0.4-rev.

Публичная функция: plan_acquisition(input, *, client, model) -> AcquisitionPlan.

Последовательность шагов:
  LLM  → AcquisitionEval (шаги 1–5, 8)
  Py   → feasibility_score, feasibility_status (шаг 2)
  Py   → uniqueness (шаг 5)
  Py   → value, core, bonus (шаг 6)
  Py   → difficulty_target, saturation_penalty (шаг 7)
  Py   → conflict_status (шаг 8)
  Py   → routes (шаг 9)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from worldsim_prompts import AnthropicClient, call_json, load_prompt
from worldsim_schemas import (
    AcquisitionEval,
    AcquisitionPlan,
    AcquisitionRequest,
    ConflictStatus,
    FeasibilityStatus,
    PlayerProgression,
    VectorType,
)

from .acquisition_engine import (
    VIABLE_THRESHOLD,
    DecompositionConfig,
    calc_difficulty,
    calc_feasibility_score,
    calc_type_saturation,
    calc_uniqueness,
    calc_value,
    decompose_into_routes,
    get_capabilities_of_type,
    get_feasibility_status,
    resolve_conflict_status,
)

_PROMPTS = Path(__file__).parent.parent.parent / "prompts"


def plan_acquisition(
    input: dict[str, Any],
    *,
    client: AnthropicClient,
    model: str,
) -> AcquisitionPlan:
    """
    Строит план приобретения возможности.

    input:
      acquisition_request: {...}   # поля AcquisitionRequest
      player_progression: {...}    # поля PlayerProgression
      context: {...}               # TurnContext (срез мира)
    """
    request = AcquisitionRequest.model_validate(input["acquisition_request"])
    progression = PlayerProgression.model_validate(input["player_progression"])

    # ── Шаги 1–5, 8: LLM оценивает всё числовое ──────────────────────────
    system = load_prompt(_PROMPTS / "acquisition.md")
    user = json.dumps(input, ensure_ascii=False, indent=2)
    eval_: AcquisitionEval = call_json(
        client,
        system=system,
        user=user,
        model=model,
        schema=AcquisitionEval,
        max_tokens=800,
        temperature=0.2,
    )

    # ── Шаг 2: выполнимость ───────────────────────────────────────────────
    f_score = calc_feasibility_score(eval_)
    f_status = get_feasibility_status(f_score)

    if f_status == FeasibilityStatus.BLOCKED:
        return AcquisitionPlan(
            routes=[],
            value=0.0,
            value_core=0.0,
            value_bonus=0.0,
            difficulty_target=0.0,
            type_saturation_penalty=0.0,
            vector=eval_.chosen_vector,
            world_impact=eval_.impact.world_impact,
            persona_impact=eval_.impact.persona_impact,
            scenario_uniqueness=0.0,
            feasibility_status=f_status,
            feasibility_score=round(f_score, 3),
            partial_coverage=False,
            conflict_status=ConflictStatus.CLEAN,
            blocking_factor=eval_.blocking_factor,
        )

    partial_coverage = f_status == FeasibilityStatus.PARTIAL

    # ── Шаг 3: суммарное влияние ──────────────────────────────────────────
    total_impact = eval_.impact.world_impact + eval_.impact.persona_impact

    # ── Шаг 5: уникальность ───────────────────────────────────────────────
    uniqueness = calc_uniqueness(eval_)

    # ── Шаг 6: ценность ───────────────────────────────────────────────────
    value, core, bonus = calc_value(eval_, total_impact)

    # ── Шаг 7: сложность ──────────────────────────────────────────────────
    same_type_caps = get_capabilities_of_type(progression, request.type)
    saturation = calc_type_saturation(same_type_caps)
    difficulty, saturation_penalty = calc_difficulty(
        value, uniqueness, saturation, f_score, partial_coverage
    )

    # ── Шаг 8: конфликты ──────────────────────────────────────────────────
    conflict_status = resolve_conflict_status(eval_)

    # Полный конфликт — маршруты не строим, ждём решения персонажа
    if conflict_status == ConflictStatus.FULL_CONFLICT_PENDING:
        return AcquisitionPlan(
            routes=[],
            value=round(value, 2),
            value_core=round(core, 2),
            value_bonus=round(bonus, 2),
            difficulty_target=round(difficulty, 2),
            type_saturation_penalty=saturation_penalty,
            vector=eval_.chosen_vector,
            world_impact=eval_.impact.world_impact,
            persona_impact=eval_.impact.persona_impact,
            scenario_uniqueness=round(uniqueness, 3),
            feasibility_status=f_status,
            feasibility_score=round(f_score, 3),
            partial_coverage=partial_coverage,
            conflict_status=conflict_status,
            conflicting_capability_ids=eval_.conflicts.conflicting_capability_ids,
        )

    # ── Шаг 9: декомпозиция маршрутов ─────────────────────────────────────
    # При альтернативном маршруте — строим по каждому альтернативному вектору;
    # при частичном конфликте / чистом — строим по chosen_vector.
    if conflict_status == ConflictStatus.ALTERNATIVE_ROUTE and eval_.conflicts.alternative_vectors:
        route_vectors: list[VectorType] = eval_.conflicts.alternative_vectors
    else:
        route_vectors = [eval_.chosen_vector]

    config = DecompositionConfig()
    routes = []
    for vec in route_vectors:
        routes.extend(decompose_into_routes(difficulty, vec, 1, config=config))

    return AcquisitionPlan(
        routes=routes,
        value=round(value, 2),
        value_core=round(core, 2),
        value_bonus=round(bonus, 2),
        difficulty_target=round(difficulty, 2),
        type_saturation_penalty=saturation_penalty,
        vector=eval_.chosen_vector,
        world_impact=eval_.impact.world_impact,
        persona_impact=eval_.impact.persona_impact,
        scenario_uniqueness=round(uniqueness, 3),
        feasibility_status=f_status,
        feasibility_score=round(f_score, 3),
        partial_coverage=partial_coverage,
        conflict_status=conflict_status,
        conflicting_capability_ids=eval_.conflicts.conflicting_capability_ids,
    )
