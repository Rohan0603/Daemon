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
    def __init__(self, memory: "Memory", history: "History",
                 diary_entries_ref: list[str]) -> None:
        self._memory = memory
        self._history = history
        self._diary = diary_entries_ref
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
        lines.append("Respond with a single JSON object.")
        return "\n".join(lines)

    def build_autonomous_trigger(self, mode: str, apm: int,
                                 idle_seconds: float, typing_content: str = "",
                                 screen_text: str = "") -> str:
        lines = [
            "Daemon is watching the user. She notices something worth thinking about.",
            "APM (actions per minute) is her main signal.",
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
        lines.append("She is thinking to herself. This is an internal monologue \u2014 she is NOT responding to the user.")
        lines.append("She should NOT say 'you asked' or 'you said' because the user did not say anything.")
        lines.append("Generate exactly 5 dialogs as a JSON array.")
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

    def _snapshot_current(self) -> None:
        self._snapshot = {
            "memory": dict(self._memory.get_all()),
            "diary_len": len(self._diary),
            "active_window": self._snapshot.get("active_window", ""),
            "apm_bucket": self._snapshot.get("apm_bucket", ""),
        }

    def snapshot_context(self, context_hint: str, apm: int) -> None:
        """Update active_window and apm_bucket in snapshot."""
        if self._snapshot:
            self._snapshot["active_window"] = context_hint
            self._snapshot["apm_bucket"] = _apm_bucket(apm)
