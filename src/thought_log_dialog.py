"""Wrapper for backward compatibility."""
_Wrapped = None
def __getattr__(name):
    global _Wrapped
    if _Wrapped is None:
        from src.ui.thought_log_dialog import ThoughtLogDialog as _Wrapped
    if name == "ThoughtLogDialog":
        return _Wrapped
    raise AttributeError(f"module 'src.thought_log_dialog' has no attribute '{name}'")
__all__ = ["ThoughtLogDialog"]