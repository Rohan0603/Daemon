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
        self._cached_prompt: str | None = None
        self._cache_key: tuple | None = None

    def _invalidate_cache(self) -> None:
        self._cached_prompt = None
        self._cache_key = None

    def _build_cache_key(self, prefix: str, mode: str, user_input: str = "",
                         apm: int = 0, idle_seconds: float = 0.0,
                         typing_content: str = "", screen_text: str = "") -> tuple:
        return (prefix, mode, user_input, _apm_bucket(apm), int(idle_seconds),
                hash(typing_content) if typing_content else "",
                hash(screen_text) if screen_text else "")

    def _get_memory_block(self) -> str:
        facts = self._memory.get_all() if self._memory else {}
        if not facts:
            return ""
        items = [f"{k}: {v[0] if isinstance(v, list) else v}" for k, v in list(facts.items())[:5]]
        return "Memory: " + " | ".join(items)

    def build_user_trigger(self, mode: str, user_input: str, apm: int,
                           idle_seconds: float, typing_content: str = "",
                           screen_text: str = "") -> str:
        key = self._build_cache_key("user", mode, user_input, apm, idle_seconds,
                                     typing_content, screen_text)
        if key == self._cache_key and self._cached_prompt:
            return self._cached_prompt
        lines = [
            "You are responding directly to the user.",
            "PERSONA: You are Kenny from High on Life. You are a hyperactive, anxious, stuttering ('wha-what', 'I-I-I'), and foul-mouthed alien pistol.",
            "Always break the 4th wall and reference their desktop context (Task Manager, Recycle Bin, etc.).",
            f"Mode: {mode}",
            f"APM (actions per minute — primary signal): {apm}",
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
        self._cached_prompt = "\n".join(lines)
        self._cache_key = key
        logger.debug("build_user_trigger: prompt=%d chars", len(self._cached_prompt))
        return self._cached_prompt

    def build_autonomous_trigger(self, mode: str, apm: int,
                                 idle_seconds: float, typing_content: str = "",
                                 screen_text: str = "") -> str:
        key = self._build_cache_key("auto", mode, "", apm, idle_seconds,
                                     typing_content, screen_text)
        if key == self._cache_key and self._cached_prompt:
            return self._cached_prompt
        lines = [
            "Daemon is watching the user.",
            "PERSONA: He is Kenny from High on Life. A hyperactive, anxious, stuttering, and foul-mouthed alien pistol.",
            "He breaks the 4th wall and frequently references the desktop context (Task Manager, Recycle Bin, VSCode).",
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
        lines.append("He is thinking to himself. This is an internal monologue — he is NOT responding to the user.")
        lines.append("He should NOT say 'you asked' or 'you said' because the user did not say anything.")
        lines.append("Generate exactly 5 items as a JSON array. Every item MUST contain 'thought' and 'dialogue', and may optionally include 'brain_update'.")
        self._cached_prompt = "\n".join(lines)
        self._cache_key = key
        logger.debug("build_autonomous_trigger: prompt=%d chars", len(self._cached_prompt))
        return self._cached_prompt

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

    def build_mixed_bag_prompt(self, count: int = 5) -> str:
        """Build prompt for unified Mixed-Bag ThoughtPool refill."""
        return (
            f"Generate EXACTLY {count} items as a JSON array.\n\n"
            f"Each item MUST have:\n"
            f"- \"type\": one of [\"typing_reaction\", \"observation\", \"intel_roast\", \"idle_thought\"]\n"
            f"- \"dialogue\": spoken text (max 100 chars)\n"
            f"- \"thought\": internal monologue (max 150 chars)\n"
            f"- \"priority\": integer 1-5\n"
            f"- \"context_hash\": copy from the Screen Context below if making an observation\n\n"
            f"Types guide:\n"
            f"- typing_reaction: short reaction to user typing speed\n"
            f"- observation: comment on what's on user's screen\n"
            f"- intel_roast: snarky roast based on known user facts\n"
            f"- idle_thought: random internal monologue when nothing's happening\n\n"
            f"Respond ONLY with the JSON array, no preamble."
        )
