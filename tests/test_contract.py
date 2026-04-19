"""Contract-тесты personal-progression."""

import json
from unittest.mock import MagicMock, patch

import pytest

from worldsim_schemas import TurnPatch
from worldsim_personal_progression.agent import run


def _mock_client(response: str) -> MagicMock:
    client = MagicMock()
    client.complete.return_value = response
    return client


MINIMAL_INPUT = {
    "intent": {"intent": "converse", "raw_text": "говорю с Мирой"},
    "world_change_summary": "Мира рассказала о контрабандистах.",
    "turn_patch": {"world_changes": [], "new_facts": ["контрабандисты_активны"]},
    "player_progression_before": {"character_id": "pc", "attributes": {}, "skill_counters": {}},
}

PROGRESSION_RESPONSE = {
    "world_changes": [
        {
            "entity_type": "player_progression",
            "id": "_",
            "field": "skill_counters.talked_to_npcs",
            "op": "inc",
            "value": 1,
        }
    ],
    "new_facts": ["факт_который_будет_сброшен"],
    "timeline_event": {"tick": 1, "type": "t", "summary": "s"},
    "narrative_summary": "Нарратив который будет сброшен.",
}


# ---------------------------------------------------------------------------
# run — happy path
# ---------------------------------------------------------------------------


def test_run_returns_turn_patch():
    client = _mock_client(json.dumps(PROGRESSION_RESPONSE))
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        result = run(MINIMAL_INPUT, client=client, model="m")
    assert isinstance(result, TurnPatch)


def test_run_filters_all_changes_since_player_type_invalid():
    # Агент фильтрует entity_type == "player", но такого типа нет в PatchOp.
    # В результате все world_changes удаляются — это текущее поведение агента.
    response = {
        "world_changes": [
            {
                "entity_type": "character",
                "id": "npc_mira",
                "field": "attitude_to_player",
                "op": "set",
                "value": 0.9,
            },
            {
                "entity_type": "player_progression",
                "id": "_",
                "field": "skill_counters.talked",
                "op": "inc",
                "value": 1,
            },
        ],
        "new_facts": [],
        "timeline_event": None,
        "narrative_summary": "",
    }
    client = _mock_client(json.dumps(response))
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        result = run(MINIMAL_INPUT, client=client, model="m")
    # Фильтр c.entity_type == "player" убирает всё — известное поведение
    assert result.world_changes == []


def test_run_clears_new_facts():
    client = _mock_client(json.dumps(PROGRESSION_RESPONSE))
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        result = run(MINIMAL_INPUT, client=client, model="m")
    assert result.new_facts == []


def test_run_clears_timeline_event():
    client = _mock_client(json.dumps(PROGRESSION_RESPONSE))
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        result = run(MINIMAL_INPUT, client=client, model="m")
    assert result.timeline_event is None


def test_run_clears_narrative_summary():
    client = _mock_client(json.dumps(PROGRESSION_RESPONSE))
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        result = run(MINIMAL_INPUT, client=client, model="m")
    assert result.narrative_summary == ""


def test_run_empty_world_changes():
    response = {
        "world_changes": [],
        "new_facts": [],
        "timeline_event": None,
        "narrative_summary": "",
    }
    client = _mock_client(json.dumps(response))
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        result = run(MINIMAL_INPUT, client=client, model="m")
    assert result.world_changes == []


def test_run_passes_model_to_client():
    response = {"world_changes": [], "new_facts": [], "timeline_event": None, "narrative_summary": ""}
    client = _mock_client(json.dumps(response))
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        run(MINIMAL_INPUT, client=client, model="claude-haiku-4-5")
    assert client.complete.call_args[1]["model"] == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


def test_run_invalid_json_raises():
    client = _mock_client("Not JSON at all.")
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        with pytest.raises(Exception):
            run(MINIMAL_INPUT, client=client, model="m")


def test_run_world_changes_wrong_type_raises():
    # entity_type не из разрешённых Literal → ValidationError
    response = {
        "world_changes": [
            {"entity_type": "unknown_type", "id": "x", "field": "f", "op": "set", "value": 1}
        ],
        "new_facts": [],
        "timeline_event": None,
        "narrative_summary": "",
    }
    client = _mock_client(json.dumps(response))
    with patch("worldsim_personal_progression.agent.load_prompt", return_value="system"):
        with pytest.raises(Exception):
            run(MINIMAL_INPUT, client=client, model="m")


# ---------------------------------------------------------------------------
# MANIFEST
# ---------------------------------------------------------------------------


def test_manifest_exported():
    from worldsim_personal_progression import MANIFEST
    from worldsim_schemas import AgentPhase
    assert MANIFEST.phase == AgentPhase.PROGRESSION_UPDATE
    assert MANIFEST.optional is False


def test_manifest_entrypoint_callable():
    from worldsim_personal_progression import MANIFEST
    import worldsim_personal_progression as pkg
    assert callable(getattr(pkg, MANIFEST.entrypoint, None))
