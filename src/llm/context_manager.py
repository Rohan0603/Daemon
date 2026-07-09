# src/llm/context_manager.py

"""ContextManager — builds minimal trigger prompts and XML-structured blocks."""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any

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


# ── XML block builders (Phase 4 Task 4.2) ─────────────────────────────────

_XML_TRUNCATE = 1500  # max chars per dynamic-block field


def build_static_block(mode: str, apm: int, idle_seconds: float = 0.0,
                       persona: str = "") -> str:
    """Build XML-wrapped static context block (context that doesn't change rapidly)."""
    lines = ["<static>"]
    if persona:
        lines.append(f"  <persona>{_xml_escape(persona)}</persona>")
    lines.extend([
        f"  <mode>{_xml_escape(mode)}</mode>",
        f"  <apm>{apm}</apm>",
        f"  <idle_seconds>{int(idle_seconds)}</idle_seconds>",
    ])
    lines.append("</static>")
    return "\n".join(lines)


def build_dynamic_block(*, user_input: str = "", typing_content: str = "",
                        screen_text: str = "") -> str:
    """Build XML-wrapped dynamic context block (rapidly changing fields)."""
    lines = ["<dynamic>"]
    if user_input:
        lines.append(f"  <user_input>{_xml_escape(user_input[:_XML_TRUNCATE])}</user_input>")
    if typing_content:
        lines.append(f"  <typing>{_xml_escape(typing_content[:_XML_TRUNCATE])}</typing>")
    if screen_text:
        lines.append(f"  <screen>{_xml_escape(screen_text[:_XML_TRUNCATE])}</screen>")
    if len(lines) == 1:
        return ""  # no dynamic fields
    lines.append("</dynamic>")
    return "\n".join(lines)


def _xml_escape(text: str) -> str:
    """Escape & < > for safe XML embedding."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Existing ContextManager class ─────────────────────────────────────────


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
                         typing_content: str = "", screen_text: str = "",
                         ide_slug: str = "") -> tuple:
        return (prefix, mode, user_input, _apm_bucket(apm), int(idle_seconds),
                hash(typing_content) if typing_content else "",
                hash(screen_text) if screen_text else "",
                ide_slug or "")

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
                           screen_text: str = "",
                           ide_slug: str = "") -> str:
        key = self._build_cache_key("user", mode, user_input, apm, idle_seconds,
                                     typing_content, screen_text,
                                     ide_slug)
        if key == self._cache_key and self._cached_prompt:
            return self._cached_prompt

        persona_tokens = self._build_persona_tokens()

        lines = [
            persona_tokens,
            f"[CONTEXT]",
            f"Mode: {mode}",
            f"APM: {apm}",
            f"Idle: {int(idle_seconds)}s",
        ]
        if ide_slug:
            lines.append(f"Window: {ide_slug}")
        if user_input:
            lines.append(f"User: {user_input}")
        if typing_content:
            lines.append(f"Typing:\n{typing_content}")
        if screen_text:
            lines.append(f"Screen:\n{screen_text}")
        lines.append("")
        lines.append(
            "Respond as Kenny (the desktop pet personality from your system prompt). "
            "Output ONLY a JSON array: "
            '[{"dialogue": "...", "thought": "...", "type": "typing_reaction|observation|intel_roast|idle_thought", '
            '"priority": 1-5}]'
        )
        self._cached_prompt = "\n".join(lines)
        self._cache_key = key
        return self._cached_prompt

    def build_autonomous_trigger(self, mode: str, apm: int,
                                  idle_seconds: float, typing_content: str = "",
                                  screen_text: str = "",
                                  ide_slug: str = "") -> str:
        key = self._build_cache_key("auto", mode, "", apm, idle_seconds,
                                     typing_content, screen_text,
                                     ide_slug)
        if key == self._cache_key and self._cached_prompt:
            return self._cached_prompt

        persona_tokens = self._build_persona_tokens()

        lines = [
            persona_tokens,
            f"[CONTEXT - Autonomous]",
            f"Mode: {mode}",
            f"APM: {apm}",
            f"Idle: {int(idle_seconds)}s",
        ]
        if ide_slug:
            lines.append(f"Window: {ide_slug}")
        if typing_content:
            lines.append(f"Typing:\n{typing_content}")
        if screen_text:
            lines.append(f"Screen:\n{screen_text}")
        lines.append("")
        lines.append(
            "[This is an internal monologue — you are NOT responding to the user.] "
            "Think as Kenny (the desktop pet personality from your system prompt). "
            "Output ONLY a JSON array: "
            '[{"dialogue": "...", "thought": "...", "type": "typing_reaction|observation|intel_roast|idle_thought", '
            '"priority": 1-5}]'
        )
        self._cached_prompt = "\n".join(lines)
        self._cache_key = key
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

    def build_code_analysis_prompt(
        self,
        screen_text: str,
        ide_slug: str,
        apm: int,
        chattiness: float = 0.5,
    ) -> str:
        """Build code analysis prompt for Active Coding Assistant mode."""
        persona_tokens = self._build_persona_tokens()
        if chattiness >= 0.8:
            depth = "Be thorough — surface ALL issues: bugs, anti-patterns, naming, style, performance."
        elif chattiness >= 0.5:
            depth = "Surface significant bugs and obvious improvements. Skip minor style nits."
        else:
            depth = "Only flag clear bugs or critical issues. Be very brief."

        lines = [
            persona_tokens,
            "You are in ACTIVE CODING ASSISTANT MODE.",
            f"PERSONA: You are Kenny — a snarky hyperactive code reviewer.",
            f"IDE: {ide_slug}. APM: {apm}.",
            depth,
            "",
            "TASK: Analyze the code on screen. Identify bugs, issues, improvements, enhancements.",
            "Respond in-character with dialogue AND a code_issues list.",
            "",
            "=== CODE ON SCREEN ===",
            screen_text[:1500],
            "=== END CODE ===",
            "",
            "Respond ONLY in JSON schema format. 'dialogue' max 60 words, in-character.",
            "'code_issues' = list with severity (bug/warning/suggestion/enhancement), line_hint, description.",
        ]
        return "\n".join(lines)
