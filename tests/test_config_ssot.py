import pytest
import sys
import importlib

def test_constants_patched_by_config():
    from src.config import load_config
    from src import constants
    # Verify that load_config() injects behavioral values into constants
    config = load_config()
    # Check a few known keys
    assert hasattr(constants, "APM_HYPER_THRESHOLD")
    assert getattr(constants, "APM_HYPER_THRESHOLD") == config.get("behavior", {}).get("apm_hyper_threshold", 150)
    assert getattr(constants, "SPEECH_BUBBLE_DURATION_MS") == config.get("behavior", {}).get("speech_bubble_duration_ms", 8000)

def test_constants_has_no_hardcoded_behavioral():
    # We must cleanly load the source to verify it lacks the attribute
    with open("src/constants.py", "r", encoding="utf-8") as f:
        source = f.read()
    assert "APM_HYPER_THRESHOLD" not in source
    assert "SPEECH_BUBBLE_DURATION_MS" not in source
