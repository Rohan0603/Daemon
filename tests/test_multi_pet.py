import pytest
from pathlib import Path
from src.config import load_config, save_config
from daemon import _resolve_skill_path

def test_config_user_and_pet_schema():
    cfg = load_config()
    assert "user" in cfg
    assert "uid" in cfg["user"]
    assert "pet" in cfg
    assert "active_personas" in cfg["pet"]

def test_resolve_skill_path_fallback():
    path = _resolve_skill_path("non_existent_pet_12345")
    assert "kenny" in str(path)
    assert path.name == "SKILL.md"
