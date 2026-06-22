from abc import ABC
from src.storage_backend import StorageBackend


def test_storage_backend_is_abstract():
    assert issubclass(StorageBackend, ABC)


def test_storage_backend_has_required_methods():
    for method in ("get", "set", "query", "all_entries", "count"):
        assert hasattr(StorageBackend, method), f"Missing method: {method}"


def test_concrete_without_methods_raises():
    class IncompleteBackend(StorageBackend):
        pass
    import pytest
    with pytest.raises(TypeError):
        IncompleteBackend()
