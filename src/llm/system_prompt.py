"""src/llm/system_prompt.py

SINGLE SOURCE OF TRUTH for the LLM system prompt.

Both LLM routes must read the same Kenny persona:

* opencode route  -> opencode serve loads ``.opencode/skills/<pet_id>/SKILL.md``
                      natively (configured in ``.opencode/opencode.json``).
* ollama route    -> this module loads the *same* SKILL.md file.

Neither worker hardcodes the persona or the tool directive. The tool
directive is generated from the live MCP tool schema (see
``build_tool_directive``) so it can never drift from ``mcp_server.py``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Placeholders substituted from Memory facts. Defaults keep the pet coherent
# even before the user has taught anything.
_PLACEHOLDERS: dict[str, str] = {
    "user_nickname": "garbage meat",
    "user_partner_name": "The Overseer",
    "user_engineer_name": "Locksmith",
}


def skill_md_path(pet_id: str) -> Path:
    """Absolute path to the canonical SKILL.md for a pet."""
    return Path(__file__).parent.parent.parent / ".opencode" / "skills" / pet_id / "SKILL.md"


def load_skill_md(pet_id: str) -> str | None:
    """Read the canonical SKILL.md, or None if it is missing."""
    path = skill_md_path(pet_id)
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("system_prompt: SKILL.md not found at %s", path)
    return None


def substitute_placeholders(text: str, memory: dict | None = None) -> str:
    """Fill {user_nickname} etc. from Memory facts; unknown -> default."""
    facts = memory or {}
    for key, default in _PLACEHOLDERS.items():
        text = text.replace("{" + key + "}", facts.get(key, default))
    return text


def build_system_prompt(
    pet_id: str,
    memory: dict | None = None,
    *,
    compact: bool = False,
    max_chars: int = 4000,
) -> str:
    """Return the full Kenny persona from SKILL.md (single source of truth).

    ``compact`` only *truncates* the real SKILL.md to fit a small local model;
    it never re-narrates the persona, so the Ollama route cannot drift into a
    second hardcoded copy of Kenny.
    """
    raw = load_skill_md(pet_id)
    if not raw:
        # Neutral, non-persona last resort so the pet is at least system-aware.
        return (
            "You are Kenny, a hyperactive desktop pet with full system awareness. "
            "You know the user's desktop context and react to their activity."
        )
    text = substitute_placeholders(raw, memory)
    if compact and len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n"
    return text


def build_tool_directive(schema: Iterable[dict] | None) -> str:
    """Generate the 'you have tools' directive from the live MCP schema.

    Replaces the previously hardcoded action list. Tool names (and therefore
    the change_visual_state actions) come from the server, never from a string
    literal in this module.
    """
    schema = list(schema or [])
    names: list[str] = []
    for t in schema:
        fn = t.get("function") if isinstance(t, dict) else None
        name = (fn or {}).get("name") if fn else t.get("name")
        if name:
            names.append(name)
    if not names:
        return ""
    lines = [
        "TOOLS: You have MCP tools and SHOULD use them.",
        'Call change_visual_state on EVERY response to animate (layer="expression" for physical moves, layer="fsm" for behaviour states).',
        "If the user gives a physical command, call the tool FIRST, then speak.",
        "Available tools: " + ", ".join(names) + ".",
        "Always CALL the tool, do not just describe the action in dialogue.",
    ]
    return "\n".join(lines)
