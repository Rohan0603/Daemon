"""
Autonomy package for Daemon.

This package contains the autonomous behavior system extracted from the main application.
"""

from .behavior_controller import BehaviorController
from .response_manager import AutonomousResponseManager
from .response_pool import ThoughtPool
from .reactions import build_reminder_effect, evaluate_risky_typing_reaction

__all__ = [
    "BehaviorController",
    "AutonomousResponseManager",
    "ThoughtPool",
    "build_reminder_effect",
    "evaluate_risky_typing_reaction",
]