"""Wrapper for backward compatibility."""
_Wrapped = None
def __getattr__(name):
    global _Wrapped
    if _Wrapped is None:
        from src.ui.context_menu import PetContextMenu as _Wrapped
    if name == "PetContextMenu":
        return _Wrapped
    raise AttributeError(f"module 'src.context_menu' has no attribute '{name}'")
__all__ = ["PetContextMenu"]