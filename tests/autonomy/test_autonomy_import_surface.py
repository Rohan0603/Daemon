# tests/autonomy/test_autonomy_import_surface.py
"""Verify that src.autonomy re-exports everything the rest of the project expects."""

from __future__ import annotations

from src.autonomy import (
    AutonomousResponseManager,
    BehaviorController,
    ThoughtPool,
    build_reminder_effect,
    evaluate_risky_typing_reaction,
)
from src.autonomy.behavior_controller import BehaviorController as ImplBehaviorController
from src.autonomy.response_manager import AutonomousResponseManager as ImplAutonomousResponseManager
from src.autonomy.response_pool import ThoughtPool as ImplThoughtPool
from src.autonomy.reactions import (
    build_reminder_effect as ImplBuildReminderEffect,
    evaluate_risky_typing_reaction as ImplEvaluateRiskyTypingReaction,
)


def test_autonomy_package_exports_current_services():
    assert BehaviorController is ImplBehaviorController
    assert AutonomousResponseManager is ImplAutonomousResponseManager
    assert ThoughtPool is ImplThoughtPool
    assert build_reminder_effect is ImplBuildReminderEffect
    assert evaluate_risky_typing_reaction is ImplEvaluateRiskyTypingReaction
