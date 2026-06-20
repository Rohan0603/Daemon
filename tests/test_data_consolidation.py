import os
import json
import pytest
from pathlib import Path
from src.brain_store import BrainStore
from src.memory import Memory
from src.history import History
from src.diary_store import DiaryStore

@pytest.fixture
def temp_brain(tmp_path):
    path = str(tmp_path / "daemon_brain.json")
    # Reset singleton for testing
    BrainStore._instances.clear()
    return path

def test_brain_store_initialization(temp_brain):
    brain = BrainStore.get_instance(temp_brain)
    assert brain.version == 2
    assert brain.facts == {}
    assert brain.diary == []
    assert brain.diary_synced == 0
    assert brain.history == []

def test_brain_store_save_and_load(temp_brain):
    brain = BrainStore.get_instance(temp_brain)
    brain.facts["user_name"] = "Alice"
    brain.diary.append({"content": "Hello", "hash": "123"})
    brain.diary_synced = 1
    brain.history.append({"user_input": "Hi", "daemon_response": "Hello"})
    brain.save()
    
    assert os.path.exists(temp_brain)
    
    BrainStore._instances.clear()
    brain2 = BrainStore.get_instance(temp_brain)
    
    assert brain2.facts["user_name"] == "Alice"
    assert len(brain2.diary) == 1
    assert brain2.diary_synced == 1
    assert len(brain2.history) == 1

def test_memory_history_diary_integration(temp_brain):
    mem = Memory(path=temp_brain)
    hist = History(path=temp_brain)
    diary = DiaryStore(path=temp_brain)
    
    mem.remember("favorite_color", "blue")
    hist.add_entry("test input", "test response", "idle")
    diary.add_diary_entry("First diary entry")
    diary.write(diary.get_entries(), synced=1)
    
    # Assert they all wrote to the same BrainStore instance
    brain = BrainStore.get_instance(temp_brain)
    assert brain.facts["favorite_color"] == "blue"
    assert len(brain.history) == 1
    assert brain.history[0]["user_input"] == "test input"
    assert len(brain.diary) == 1
    assert brain.diary_synced == 1
