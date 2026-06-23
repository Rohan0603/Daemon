"""Wrapper for backward compatibility."""
_PetRenderer = None
_RenderContext = None


def __getattr__(name):
    global _PetRenderer, _RenderContext
    if _PetRenderer is None:
        from src.ui.pet_renderer import PetRenderer, RenderContext
        _PetRenderer = PetRenderer
        _RenderContext = RenderContext
    if name == "PetRenderer":
        return _PetRenderer
    if name == "RenderContext":
        return _RenderContext
    raise AttributeError(f"module 'src.pet_renderer' has no attribute '{name}'")


__all__ = ["PetRenderer", "RenderContext"]
