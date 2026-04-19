"""
personal-progression — патчи на player_progression.

Возвращает TurnPatch, в котором world_changes касаются только
entity_type='player'. Если LLM попытается прописать что-то ещё —
отфильтруем и залогируем.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from worldsim_prompts import AnthropicClient, call_json, load_prompt
from worldsim_schemas import TurnPatch

_PROMPTS = Path(__file__).parent.parent.parent / "prompts"


def run(
    input: dict[str, Any], *, client: AnthropicClient, model: str
) -> TurnPatch:
    """
    input:
      intent: {...}
      world_change_summary: str
      turn_patch: {...}
      player_progression_before: {...}
    """

    system = load_prompt(_PROMPTS / "progression.md")
    user = json.dumps(input, ensure_ascii=False, indent=2)

    patch = call_json(
        client,
        system=system,
        user=user,
        model=model,
        schema=TurnPatch,
        max_tokens=1200,
        temperature=0.3,
    )

    # Жёсткий фильтр: оставляем только entity_type='player'.
    safe_changes = [c for c in patch.world_changes if c.entity_type == "player"]
    patch.world_changes = safe_changes
    patch.new_facts = []
    patch.timeline_event = None
    patch.narrative_summary = ""

    return patch
