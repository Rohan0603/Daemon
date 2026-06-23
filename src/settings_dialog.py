"""Wrapper for backward compatibility."""
_Wrapped = None
def __getattr__(name):
    global _Wrapped
    if _Wrapped is None:
        from src.ui.settings_dialog import SettingsDialog as _Wrapped
    if name == "SettingsDialog":
        return _Wrapped
    raise AttributeError(f"module 'src.settings_dialog' has no attribute '{name}'")
__all__ = ["SettingsDialog"]