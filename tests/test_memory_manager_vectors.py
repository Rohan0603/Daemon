from unittest.mock import Mock

from src.memory_manager import MemoryManager


def test_sync_from_local_writes_vector_sidecar():
    crud = Mock()
    crud.available = True
    crud.get.return_value = {}
    manager = MemoryManager(crud, "user-1", "pet-1")
    memory = Mock()
    memory.get_all.return_value = {"pet_likes": "tea"}

    manager.sync_from_local(memory)

    calls = [call for call in crud.set.call_args_list if "/memories" in call.args[0]]
    assert len(calls) == 1
    assert calls[0].args[2]["content"] == "tea"
    assert len(calls[0].args[2]["embedding"]) == 384
