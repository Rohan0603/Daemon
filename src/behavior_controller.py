"""BehaviorController wrapper — defers import to first attribute access.

Provides backward compatibility while minimizing module-level side effects
during test discovery.
"""

_BehaviorController = None


def __getattr__(name):
    global _BehaviorController
    if _BehaviorController is None:
        from src.autonomy.behavior_controller import BehaviorController as _BehaviorController
    if name == "BehaviorController":
        return _BehaviorController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BehaviorController"]
