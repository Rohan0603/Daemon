"""Wrapper for backward compatibility."""
_Wrapped = None
def __getattr__(name):
    global _Wrapped
    if _Wrapped is None:
        from src.ui.data_viewer_dialog import DataViewerDialog as _Wrapped
    if name == "DataViewerDialog":
        return _Wrapped
    raise AttributeError(f"module 'src.data_viewer_dialog' has no attribute '{name}'")
__all__ = ["DataViewerDialog"]