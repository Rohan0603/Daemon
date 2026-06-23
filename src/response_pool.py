"""ThoughtPool wrapper — defers import to first attribute access.

Provides backward compatibility while minimizing module-level side effects
during test discovery.
"""

_ThoughtPool = None


def __getattr__(name):
    global _ThoughtPool
    if _ThoughtPool is None:
        from src.autonomy.response_pool import ThoughtPool as _ThoughtPool
    if name == "ThoughtPool":
        return _ThoughtPool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ThoughtPool"]
