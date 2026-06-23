"""AutonomousResponseManager wrapper — defers import to first attribute access.

Provides backward compatibility while minimizing module-level side effects
during test discovery.
"""

_AutonomousResponseManager = None


def __getattr__(name):
    global _AutonomousResponseManager
    if _AutonomousResponseManager is None:
        from src.autonomy.response_manager import AutonomousResponseManager as _AutonomousResponseManager
    if name == "AutonomousResponseManager":
        return _AutonomousResponseManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["AutonomousResponseManager"]
