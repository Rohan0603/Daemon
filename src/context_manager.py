# src/context_manager.py
"""ContextManager -- builds injection payloads and minimal trigger prompts."""
from __future__ import annotations
import logging
import time
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from src.opencode_worker import _SKILL_CONTENT, FORMAT_INSTRUCTIONS

if TYPE_CHECKING:
    from src.memory import Memory
    from src.history import History


def _apm_bucket(apm: int) -> str:
    if apm < 60:
        return "low"
    if apm <= 150:
        return "medium"
    return "high"


HEARTBEAT_TIMEOUT_SEC = 15 * 60  # 15 minutes


class ContextManager:
    def __init__(self, memory: "Memory", history: "History",
                 diary_entries_ref: list[str]) -> None:
        self._memory = memory
        self._history = history
        self._diary = diary_entries_ref
        self._snapshot: dict = {}
        self._diary_injected_up_to: int = 0
        self._last_activity: float = 0.0
        self._full_injected: bool = False

    def inject_full(self) -> str:
        """Build the one-time full session injection payload."""
        parts = []
        if _SKILL_CONTENT:
            parts.append(_SKILL_CONTENT)
        parts.append("ROLE: You are Daemon, the user's desktop pet. You are a sleeper agent owned by the user's wife. You surveil and roast.")
        mem_block = self._memory.get_context_block(None)
        if mem_block:
            parts.append(mem_block)
        if self._diary:
            lines = ["## Daemon's diary (recent):"]
            for entry in self._diary[-5:]:
                lines.append(f"- {entry}")
            parts.append("\n".join(lines))
        parts.append(FORMAT_INSTRUCTIONS)
        parts.append("INSTRUCTION: Respond ONLY with valid JSON as specified above. No markdown, no preamble.")
        self._full_injected = True
        self._snapshot_current()
        self._last_activity = time.monotonic()
        return "\n\n".join(parts)

    def inject_delta(self, context_hint: str, apm: int) -> str | None:
        """Build delta injection for state changes since last snapshot. Returns None if nothing changed."""
        if not self._snapshot:
            return None
        lines = ["DELTA CONTEXT UPDATE:"]
        prev_window = self._snapshot.get("active_window", "")
        if context_hint and context_hint != prev_window:
            lines.append(f"Active window changed to: {context_hint}")
        prev_bucket = self._snapshot.get("apm_bucket", "")
        current_bucket = _apm_bucket(apm)
        if current_bucket != prev_bucket:
            lines.append(f"APM level: {current_bucket}")
        prev_mem = self._snapshot.get("memory", {})
        new_facts = {}
        for k, v in self._memory.get_all().items():
            if prev_mem.get(k) != v:
                new_facts[k] = v
        if new_facts:
            lines.append("New facts learned:")
            for k, v in new_facts.items():
                lines.append(f"- {k}: {v}")
        if len(self._diary) > self._diary_injected_up_to:
            new_diary = self._diary[self._diary_injected_up_to:]
            lines.append("New diary entries:")
            for entry in new_diary[-3:]:
                lines.append(f"- {entry}")
        if len(lines) == 1:
            return None
        self._snapshot_current()
        return "\n".join(lines)

    def build_user_trigger(self, mode: str, user_input: str, apm: int,
                           idle_seconds: float, typing_content: str = "",
                           screen_text: str = "") -> str:
        self._last_activity = time.monotonic()
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
        self._last_activity = time.monotonic()
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

    def build_trigger(self, mode: str, user_input: str, apm: int,
                      idle_seconds: float, typing_content: str = "",
                      is_autonomous: bool = True) -> str:
        if is_autonomous:
            return self.build_autonomous_trigger(mode, apm, idle_seconds, typing_content)
        return self.build_user_trigger(mode, user_input, apm, idle_seconds, typing_content)

    def needs_reinjection(self) -> bool:
        """Return True if session idle > HEARTBEAT_TIMEOUT_SEC (15 min)."""
        if not self._full_injected:
            return True
        elapsed = time.monotonic() - self._last_activity
        return elapsed > HEARTBEAT_TIMEOUT_SEC

    def reset(self) -> None:
        """Force next call to use inject_full()."""
        self._full_injected = False
        self._snapshot = {}
        self._diary_injected_up_to = 0

    def has_injected_full(self) -> bool:
        return self._full_injected

    def _snapshot_current(self) -> None:
        self._snapshot = {
            "memory": dict(self._memory.get_all()),
            "diary_len": len(self._diary),
            "active_window": self._snapshot.get("active_window", ""),
            "apm_bucket": self._snapshot.get("apm_bucket", ""),
        }
        self._diary_injected_up_to = len(self._diary)

    def snapshot_context(self, context_hint: str, apm: int) -> None:
        """Update active_window and apm_bucket in snapshot."""
        if self._snapshot:
            self._snapshot["active_window"] = context_hint
            self._snapshot["apm_bucket"] = _apm_bucket(apm)
