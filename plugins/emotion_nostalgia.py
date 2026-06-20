"""Nostalgia emotion — a warm, sepia-toned emotion triggered when the
active window title contains 'legacy', 'old', or 'archive'.

This is a sample plugin demonstrating the Plugin Architecture.
"""

from __future__ import annotations

import math
from PyQt6.QtGui import QColor

from src.animator import Emotion, EmotionProfile

metadata = {
    "name": "Nostalgia Emotion",
    "version": "1.0.0",
    "description": "Adds a warm sepia-tinted NOSTALGIA emotion with a rule that triggers on legacy windows",
}

# ── Emotion profile ──────────────────────────────────────────────────
# Override the default PATHOS profile to use our warmer look
_NOSTALGIA_PROFILE = EmotionProfile(
    name="nostalgia",
    color_override="#D4A574",
    # Gentle sine-wave pulse between 0.8 and 0.95
    opacity_func=lambda t: 0.875 + 0.075 * math.sin(t * math.pi / 1500),
    pupil_scale=0.8,
    pupil_color_override="#8B7355",
    brow_angle=5.0,
    mouth_shape="flat",
    overlay_kind="aura",
    overlay_color="#D4A574",
    overlay_alpha_func=lambda t: 60,
    particle_count=1,
    particle_color="#D4A574",
    particle_gravity=-0.02,  # gentle upward drift
    single_fire_decay_ms=4000,
)


def register(registry) -> None:
    """Register the nostalgia emotion profile and evaluation rule.

    Args:
        registry: A PluginRegistry instance (from src.plugin_registry).
    """
    # Override the PATHOS emotion with our nostalgia look
    registry.register_emotion_profile(
        Emotion.PATHOS,
        _NOSTALGIA_PROFILE,
        plugin_name="emotion_nostalgia",
    )

    # Add a custom emotion rule that fires nostalgia when archive/legacy
    # windows are open — runs at priority 50 (before built-in rules at 100)
    registry.register_emotion_rule(
        name="nostalgia_on_legacy_windows",
        fn=_nostalgia_rule,
        plugin_name="emotion_nostalgia",
        priority=50,
    )

    # Also add a behavior trigger for when the user is browsing archives
    registry.register_behavior_trigger(
        name="nostalgia_quote_on_archive",
        fn=_archive_trigger,
        plugin_name="emotion_nostalgia",
        priority=100,
        cooldown_sec=120.0,
    )


def _nostalgia_rule(context: dict) -> Emotion | None:
    """Fire PATHOS (with nostalgia look) when legacy windows are detected."""
    title = (context.get("window_title") or "").lower()
    keywords = {"legacy", "old", "archive", "retro", "classic", "vintage"}
    if any(kw in title for kw in keywords):
        return Emotion.PATHOS
    return None


def _archive_trigger(context: dict) -> dict | None:
    """Return a nostalgic thought when the user browses archives."""
    title = (context.get("window_title") or "").lower()
    if "archive" in title and context.get("apm", 0) < 20:
        return {
            "mode": "observation",
            "emotion": Emotion.PATHOS,
            "message": "That takes me back... I remember when I was first compiled.",
            "dialogue": "Ah, the good old days of COBOL and punch cards...",
        }
    return None
