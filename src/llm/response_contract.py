"""Shared lean response contract for provider-neutral LLM parsing."""
from __future__ import annotations

from typing import Any

from src.brain_schema import apply_brain_update

RESPONSE_FIELDS = frozenset({"dialogue", "action", "visual_state", "brain_update"})


def normalize_response_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalize model items without preserving legacy fields."""
    from src.animator import Emotion
    from src.mcp_server import VALID_ACTIONS

    valid_visual_states = {emotion.value for emotion in Emotion}
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or set(item) - RESPONSE_FIELDS:
            continue
        dialogue = item.get("dialogue")
        if not isinstance(dialogue, str):
            continue
        dialogue = dialogue.strip()
        if not dialogue:
            continue

        result: dict[str, Any] = {"dialogue": dialogue[:150]}
        action = item.get("action")
        if action is not None:
            if not isinstance(action, str) or action not in VALID_ACTIONS:
                continue
            result["action"] = action
        visual_state = item.get("visual_state")
        if visual_state is not None:
            if not isinstance(visual_state, str) or visual_state not in valid_visual_states:
                continue
            result["visual_state"] = visual_state
        brain_update = item.get("brain_update")
        if brain_update is not None:
            if not isinstance(brain_update, dict):
                continue
            result["brain_update"] = apply_brain_update(brain_update)
        normalized.append(result)
    return normalized
