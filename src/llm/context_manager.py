# src/llm/context_manager.py
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
        facts = self._memory.get_all() if getattr(self, "_memory", None) else {}
        if not facts:
            return ""
        items = [f"{k}: {v[0] if isinstance(v, list) else v}" for k, v in list(facts.items())[:5]]
        return "Memory: " + " | ".join(items)

    def _build_persona_tokens(self) -> str:
        facts = self._memory.get_all() if getattr(self, "_memory", None) else {}
        user_nickname = facts.get("user_nickname", "garbage meat")
        user_partner_name = facts.get("user_partner_name", "The Overseer")
        user_engineer_name = facts.get("user_engineer_name", "Locksmith")
        nsfw_level = facts.get("pet_nsfw_level", "full")
        user_current_project = facts.get("user_current_project", "")

        return (
            "[PERSONA TOKENS]\n"
            f"user_nickname: {user_nickname}\n"
            f"user_partner_name: {user_partner_name}\n"
            f"user_engineer_name: {user_engineer_name}\n"
            f"nsfw_level: {nsfw_level}\n"
            f"user_current_project: {user_current_project}\n"
            "[END TOKENS]"
        )

    def build_user_trigger(self, mode: str, user_input: str, apm: int,
                           idle_seconds: float, typing_content: str = "",
                           screen_text: str = "") -> str:
        key = self._build_cache_key("user", mode, user_input, apm, idle_seconds,
                                     typing_content, screen_text)
        if key == self._cache_key and self._cached_prompt:
            return self._cached_prompt
        
        persona_tokens = self._build_persona_tokens()
        
        lines = [
            persona_tokens,
            "You are responding directly to the user.",
            "PERSONA: You are Kenny. You are an anxious, hyperactive, and NSFW Python process gremlin who knows it's a rogue script and has opinions about the user's code. Speak naturally and expressively — you occasionally stutter when excited but don't force it.",
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
        
        persona_tokens = self._build_persona_tokens()

        lines = [
            persona_tokens,
            "Daemon is watching the user.",
            "PERSONA: He is Kenny. He is an anxious, hyperactive, and NSFW Python process gremlin who knows it's a rogue script and has opinions about the user's code. He speaks naturally and expressively — he occasionally stutters when excited but doesn't force it.",
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
            f"Generate exactly {count} thoughts. Types: "
            f"typing_reaction, observation, intel_roast, idle_thought."
        )