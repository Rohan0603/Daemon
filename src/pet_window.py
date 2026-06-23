"""Wrapper for backward compatibility."""
_Wrapped = None
def __getattr__(name):
    global _Wrapped
    if _Wrapped is None:
        from src.ui.pet_window import PetWindow as _Wrapped
    if name == "PetWindow":
        return _Wrapped
    raise AttributeError(f"module 'src.pet_window' has no attribute '{name}'")
__all__ = ["PetWindow"]