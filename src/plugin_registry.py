"""PluginRegistry — central registry where plugins register contributions.

Plugins loaded by PluginManager call registry methods to register:
- Emotion profile overrides / additions
- Emotion evaluation rules (context → Emotion)
- Behavior triggers
- Any future extensible component

Thread-safety: called at boot (single-threaded) and never at runtime.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.animator import Emotion, EmotionProfile

logger = logging.getLogger(__name__)


@dataclass
class EmotionRule:
    """An emotion evaluation rule contributed by a plugin.

    `fn` receives the context dict (current APM, idle seconds, window
    title, typing content, etc.) and returns an Emotion or None.
    """

    name: str
    plugin: str
    fn: Callable[[dict], Optional[Emotion]]
    priority: int = 0


@dataclass
class BehaviorTrigger:
    """A behavior trigger contributed by a plugin.

    `fn` is called during _master_tick and receives the current context.
    If it returns a dict with keys like "mode", "emotion", "message",
    the trigger fires. Returns None to skip.
    """

    name: str
    plugin: str
    fn: Callable[[dict], Optional[dict]]
    priority: int = 0
    cooldown_sec: float = 60.0
    _last_fired: float = 0.0


class PluginRegistry:
    """Registry for plugin-contributed components."""

    def __init__(self) -> None:
        # Emotion profile overrides keyed by Emotion enum value
        self._emotion_profiles: dict[Emotion, EmotionProfile] = {}

        # Emotion rules sorted by priority (lower = higher priority)
        self._emotion_rules: list[EmotionRule] = []

        # Behavior triggers sorted by priority
        self._behavior_triggers: list[BehaviorTrigger] = []

        # Plugins that have registered (for dedup)
        self._registered_plugins: set[str] = set()

    # ── Registration API ──────────────────────────────────────────────

    def register_emotion_profile(
        self,
        emotion: Emotion,
        profile: EmotionProfile,
        plugin_name: str = "unknown",
    ) -> None:
        """Override or add an emotion profile.

        Plugin-provided profiles take precedence over built-in defaults.
        Call this to visually customize an existing emotion.
        """
        self._emotion_profiles[emotion] = profile
        logger.info(
            "Plugin '%s' registered emotion profile for %s",
            plugin_name,
            emotion.value,
        )

    def register_emotion_rule(
        self,
        name: str,
        fn: Callable[[dict], Optional[Emotion]],
        plugin_name: str = "unknown",
        priority: int = 0,
    ) -> None:
        """Register a context → Emotion evaluation rule.

        Lower priority numbers run first (higher precedence).
        The first rule that returns an Emotion wins.
        Built-in rules run at priority 100.
        """
        rule = EmotionRule(
            name=name,
            plugin=plugin_name,
            fn=fn,
            priority=priority,
        )
        self._emotion_rules.append(rule)
        self._emotion_rules.sort(key=lambda r: r.priority)
        logger.info(
            "Plugin '%s' registered emotion rule '%s' (priority=%d)",
            plugin_name,
            name,
            priority,
        )

    def register_behavior_trigger(
        self,
        name: str,
        fn: Callable[[dict], Optional[dict]],
        plugin_name: str = "unknown",
        priority: int = 0,
        cooldown_sec: float = 60.0,
    ) -> None:
        """Register a behavior trigger.

        `fn` is called each master tick. If it returns a non-None dict
        the trigger is considered "fired" and the dict is dispatched to
        the behavior controller.
        """
        trigger = BehaviorTrigger(
            name=name,
            plugin=plugin_name,
            fn=fn,
            priority=priority,
            cooldown_sec=cooldown_sec,
        )
        self._behavior_triggers.append(trigger)
        self._behavior_triggers.sort(key=lambda t: t.priority)
        logger.info(
            "Plugin '%s' registered behavior trigger '%s' (priority=%d, cooldown=%ss)",
            plugin_name,
            name,
            priority,
            cooldown_sec,
        )

    # ── Query API (called by core modules) ────────────────────────────

    def get_emotion_profiles(self) -> dict[Emotion, EmotionProfile]:
        """Return all plugin-registered emotion profiles."""
        return dict(self._emotion_profiles)

    def evaluate_emotion(
        self,
        context: dict,
    ) -> Optional[Emotion]:
        """Run all emotion rules. Returns first matching Emotion or None.

        Context dict should contain:
          - apm: int
          - idle_seconds: float
          - window_title: str
          - typing_content: str
          - window_switch_count: int
          - last_risky_match: str | None
          - (any other context available in behavior controller)
        """
        for rule in self._emotion_rules:
            try:
                result = rule.fn(context)
                if result is not None:
                    logger.debug(
                        "Emotion rule '%s' (plugin=%s) returned %s",
                        rule.name,
                        rule.plugin,
                        result.value,
                    )
                    return result
            except Exception as e:
                logger.exception(
                    "Emotion rule '%s' (plugin=%s) raised: %s",
                    rule.name,
                    rule.plugin,
                    e,
                )
        return None

    def get_ready_behavior_triggers(self, context: dict) -> list[dict]:
        """Return all behavior triggers whose conditions are met.

        Respects per-trigger cooldown.
        """
        now = time.time()
        fired: list[dict] = []
        for trigger in self._behavior_triggers:
            if now - trigger._last_fired < trigger.cooldown_sec:
                continue
            try:
                result = trigger.fn(context)
                if result is not None:
                    result.setdefault("_trigger_name", trigger.name)
                    result.setdefault("_plugin", trigger.plugin)
                    fired.append(result)
                    trigger._last_fired = now
            except Exception as e:
                logger.exception(
                    "Behavior trigger '%s' (plugin=%s) raised: %s",
                    trigger.name,
                    trigger.plugin,
                    e,
                )
        return fired

    # ── Metrics ──────────────────────────────────────────────────────

    @property
    def plugin_count(self) -> int:
        return len(self._registered_plugins)

    @property
    def emotion_rule_count(self) -> int:
        return len(self._emotion_rules)

    @property
    def behavior_trigger_count(self) -> int:
        return len(self._behavior_triggers)
