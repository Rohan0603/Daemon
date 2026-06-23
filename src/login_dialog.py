"""Wrapper for backward compatibility."""
_Wrapped = None
def __getattr__(name):
    global _Wrapped
    if _Wrapped is None:
        from src.ui.login_dialog import LoginDialog as _Wrapped
    if name == "LoginDialog":
        return _Wrapped
    raise AttributeError(f"module 'src.login_dialog' has no attribute '{name}'")
__all__ = ["LoginDialog"]