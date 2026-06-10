# src/context_manager.py
"""ContextManager -- builds minimal trigger prompts."""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.memory import Memory
    from src.history import History


def _apm_bucket(apm: int) -> str:
    if apm < 60:
        return "low"
    if apm <= 150:
        return "medium"
    return "high"


class ContextManager:
    def __init__(self, memory: "Memory", history: "History") -> None:
        self._memory = memory
        self._history = history
        self._snapshot: dict = {}

    def _get_memory_block(self) -> str:
        facts = self._memory.get_all() if self._memory else {}
        if not facts:
            return ""
        items = [f"{k}: {v[0] if isinstance(v, list) else v}" for k, v in list(facts.items())[:5]]
        return "Memory: " + " | ".join(items)

    def build_user_trigger(self, mode: str, user_input: str, apm: int,
                           idle_seconds: float, typing_content: str = "",
                           screen_text: str = "") -> str:
        lines = [
            "You are responding directly to the user.",
            f"Mode: {mode}",
            f"APM (actions per minute \u2014 primary signal): {apm}",
            f"Idle seconds: {int(idle_seconds)}",
        ]
        if user_input:
            lines.append(f"User said: {user_input}")
        if typing_content:
            lines.append("")
            lines.append(typing_content)
        if screen_text:
            lines.append("")
            lines.append(f"Screen: {screen_text}")
        lines.append("Respond with a JSON array containing EXACTLY ONE object. Every item MUST contain 'thought' and 'dialogue'.")
        logger.debug("build_user_trigger: prompt=%d chars (SKILL.md is NOT injected here — loaded natively by opencode serve)", sum(len(l) for l in lines))
        return "\n".join(lines)

    def build_autonomous_trigger(self, mode: str, apm: int,
                                 idle_seconds: float, typing_content: str = "",
                                 screen_text: str = "") -> str:
        lines = [
            "Daemon is watching the user. He is a hyperactive, panicked, and foul-mouthed Python script.",
            "APM (actions per minute) is his main signal.",
            f"APM: {apm}",
            f"Mode: {mode}",
            f"Idle seconds: {int(idle_seconds)}",
        ]
        if typing_content:
            lines.append("")
            lines.append(typing_content)
        if screen_text:
            lines.append("")
            lines.append(f"Screen: {screen_text}")
        lines.append("")
        lines.append("He is thinking to himself. This is an internal monologue \u2014 he is NOT responding to the user.")
        lines.append("He should NOT say 'you asked' or 'you said' because the user did not say anything.")
        lines.append("Generate exactly 5 items as a JSON array. Every item MUST contain 'thought' and 'dialogue', and may optionally include 'brain_update'.")
        logger.debug("build_autonomous_trigger: prompt=%d chars (SKILL.md is NOT injected here — loaded natively by opencode serve)", sum(len(l) for l in lines))
        return "\n".join(lines)

    def build_context(self, mode: str, user_input: str = "", apm: int = 0,
                      idle_seconds: float = 0.0, typing_content: str = "",
                      screen_text: str = "") -> str:
        parts = [f"Mode: {mode}"]
        parts.append(f"APM: {apm}")
        if idle_seconds > 0:
            parts.append(f"(idle {int(idle_seconds)}s)")
        window = self._snapshot.get("active_window", "")
        if window:
            parts.append(f'Window: "{window}"')
        mem_block = self._get_memory_block()
        if mem_block:
            parts.append(mem_block)
        context = " | ".join(parts)
        if user_input:
            context = f"{context}\nUser: {user_input}"
        if typing_content:
            context = f"{context}\n{typing_content}"
        if screen_text:
            context = f"{context}\nScreen: {screen_text}"
        return context

    def reset(self) -> None:
        self._snapshot = {}

    def snapshot_context(self, context_hint: str, apm: int) -> None:
        """Update active_window and apm_bucket in snapshot."""
        if self._snapshot:
            self._snapshot["active_window"] = context_hint
            self._snapshot["apm_bucket"] = _apm_bucket(apm)

    def build_pool_refill_prompt(self, pool_type: str, apm: int, count: int = 5) -> str:
        """Build prompt for API-driven pool refill."""
        if pool_type == "typing_reactions":
            if apm > 60:
                vibe = "User is typing frantically. You are panicked by their speed."
            elif apm < 10:
                vibe = "User is typing painfully slow. You are bored and condescending."
            else:
                vibe = "User is typing at a normal pace. You are easily distracted."

            return (
                "You are silently restocking your local reaction cache for USER TYPING.\n"
                f"Context: {vibe}\n"
                f"APM: {apm}\n\n"
                f"Generate EXACTLY {count} short, punchy one-liner reactions (max 10 words each) "
                "to the user's typing. These must be pure Kenny—foul-mouthed, nervous, or snarky. "
                "No preamble.\n"
                f"Respond with a JSON array containing EXACTLY {count} objects. "
                "Every item MUST contain 'thought' and 'dialogue'."
            )
        # Fallback for other pool types
        return (
            f"Generate {count} autonomous thoughts/jokes as a JSON array. "
            "Every item MUST contain 'thought' and 'dialogue', "
            "and may optionally include 'brain_update'."
        )
