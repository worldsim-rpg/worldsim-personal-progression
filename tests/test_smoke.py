def test_import():
    from worldsim_personal_progression import run  # noqa: F401


def test_import_acquisition():
    from worldsim_personal_progression import plan_acquisition  # noqa: F401


def test_prompt_exists():
    from pathlib import Path

    assert (Path(__file__).parent.parent / "prompts" / "progression.md").exists()


def test_acquisition_prompt_exists():
    from pathlib import Path

    assert (Path(__file__).parent.parent / "prompts" / "acquisition.md").exists()


def test_engine_math():
    """Детерминированная проверка формул без LLM."""
    from worldsim_schemas import AcquisitionEval, FeasibilityComponents, ImpactEstimate, UniquenessComponents, ConflictInfo, VectorType
    from worldsim_personal_progression.acquisition_engine import (
        calc_feasibility_score,
        get_feasibility_status,
        calc_uniqueness,
        calc_value,
        calc_difficulty,
        decompose_into_routes,
        DecompositionConfig,
        VIABLE_THRESHOLD,
        FeasibilityStatus,
    )

    eval_ = AcquisitionEval(
        universality=60.0,
        prevalence=40.0,
        divergence=75.0,
        favorable_factors=30.0,
        chosen_vector=VectorType.SKILLS,
        feasibility=FeasibilityComponents(channel_access=0.8, resource_readiness=0.7, world_permission=0.9),
        impact=ImpactEstimate(world_impact=20.0, persona_impact=60.0),
        uniqueness=UniquenessComponents(path_rarity=0.5, persona_fit=0.8, condition_rarity=0.4),
        conflicts=ConflictInfo(),
    )

    score = calc_feasibility_score(eval_)
    assert 0.0 <= score <= 1.0
    assert get_feasibility_status(score) == FeasibilityStatus.FULL

    uniqueness = calc_uniqueness(eval_)
    assert 0.0 <= uniqueness <= 1.0

    total_impact = eval_.impact.world_impact + eval_.impact.persona_impact
    value, core, bonus = calc_value(eval_, total_impact)
    assert 0.0 <= value <= 100.0

    difficulty, penalty = calc_difficulty(value, uniqueness, 0.0, score, False)
    assert 0.0 <= difficulty <= 100.0

    config = DecompositionConfig()
    routes = decompose_into_routes(difficulty, VectorType.SKILLS, 1, config=config)
    assert len(routes) == 1
    assert len(routes[0].trials) >= 1
    # ε-инвариант: сумма испытаний близка к difficulty_target
    total_trials = sum(t.difficulty for t in routes[0].trials)
    if difficulty > 0:
        assert abs(total_trials - routes[0].total_difficulty) < 0.01
