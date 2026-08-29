import json
import os
import shutil
import pytest
from unittest.mock import patch
from pathlib import Path
from src.config import load_config, flatten_config, unflatten_config, validate_config, MissingConfigurationError

_ORIGINAL_COPY2 = shutil.copy2


def _get_minimal_valid_cfg():
    return {
        "llm": {"model_id": "test-model", "api_key": "test-key", "server_url": "http://localhost"},
        "firebase": {"api_key": "test-fb-key", "project_id": "test-id", "credentials_path": "dummy.json"},
        "user": {}, "pet": {}, "tts": {}, "consent": {}, "window": {}, 
        "mcp": {}, "behavior": {}, "logging": {}, "storage": {},
        "visuals": {}, "triggers": {}
    }


@patch("src.config.shutil.copy2")
def test_load_config_default_fallback(mock_copy, tmp_path):
    mock_copy.side_effect = _ORIGINAL_COPY2
    mock_conf = tmp_path / "test_config.json"
    
    with patch.dict(os.environ, {"FIREBASE_API_KEY": "dummy-key"}, clear=True):
        with patch("src.config._CONFIG_PATH", mock_conf):
            cfg = load_config()
            assert isinstance(cfg, dict)
            mock_copy.assert_called_once()


def test_load_config_with_override(tmp_path):
    config_file = tmp_path / "daemon_config.json"
    custom_data = {
        "llm": {
            "model_id": "custom-model",
            "server_url": "http://custom-url:4096"
        },
        "pet": {
            "scale": 1.5
        },
        "window": {
            "monitor": True
        },
        "INVALID_KEY": "should_be_ignored"
    }
    config_file.write_text(json.dumps(custom_data), encoding="utf-8")

    with patch.dict(os.environ, {"FIREBASE_API_KEY": "test-fb-key"}, clear=True):
        with patch("src.config._CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg["llm"]["model_id"] == "custom-model"
        assert cfg["llm"]["server_url"] == "http://custom-url:4096"
        assert cfg["pet"]["scale"] == 1.5
        assert cfg["window"]["monitor"] is True
        assert cfg["pet"]["id"] == "kenny"


def test_flatten_and_unflatten_config():
    nested = {
        "llm": {
            "model_id": "model-1",
            "provider": "opencode",
            "server_url": "http://127.0.0.1:4096",
            "timeout_sec": 180
        },
        "pet": {
            "id": "kenny",
            "scale": 1.2,
            "opacity": 0.9,
            "speed_multiplier": 1.1,
            "chattiness": 1.0
        },
        "tts": {
            "enabled": True,
            "rate": 200,
            "volume": 0.8,
            "voice_id": "test-voice",
            "pitch": 1.2
        },
        "consent": {
            "allow_intrusive_animations": True,
            "allow_audio_disruptions": False,
            "allow_browser_redirection": True,
            "allow_clipboard_hijacking": False,
            "allow_mouse_interference": False,
            "allow_window_management": False,
            "allow_keyboard_injection": False
        },
        "window": {
            "monitor": True
        },
        "firebase": {
            "api_key": "custom-key"
        }
    }

    flat = flatten_config(nested)
    assert flat["OPENCODE_API_MODEL_ID"] == "model-1"
    assert flat["pet_scale"] == 1.2
    assert flat["pet_opacity"] == 0.9
    assert flat["pet_speed_multiplier"] == 1.1
    assert flat["window_monitor"] is True
    assert flat["FIREBASE_API_KEY"] == "custom-key"

    unflattened = unflatten_config(flat)
    assert unflattened["llm"]["model_id"] == "model-1"
    assert unflattened["pet"]["scale"] == 1.2
    assert unflattened["pet"]["opacity"] == 0.9
    assert unflattened["pet"]["speed_multiplier"] == 1.1
    assert unflattened["window"]["monitor"] is True
    assert unflattened["firebase"]["api_key"] == "custom-key"

def test_validate_config_passes_with_valid_data():
    valid_cfg = _get_minimal_valid_cfg()
    with patch("os.path.exists", return_value=True), patch("os.access", return_value=True):
        validate_config(valid_cfg)

def test_validate_config_raises_on_missing_fields():
    invalid_cfg = _get_minimal_valid_cfg()
    invalid_cfg["llm"]["model_id"] = ""
    invalid_cfg["llm"]["api_key"] = ""
    invalid_cfg["firebase"]["api_key"] = ""
    with pytest.raises(MissingConfigurationError) as exc_info:
        with patch("os.path.exists", return_value=True), patch("os.access", return_value=True):
            validate_config(invalid_cfg)
    msg = str(exc_info.value)
    assert "llm.model_id" in msg
    assert "llm.api_key" in msg

def test_validate_config_does_not_require_service_account_file():
    valid_cfg = _get_minimal_valid_cfg()
    valid_cfg["firebase"]["credentials_path"] = "missing.json"
    with patch("os.path.exists", return_value=False), patch("os.access", return_value=True):
        validate_config(valid_cfg)


# ── Session store ─────────────────────────────────────────────────────────────

class TestSessionStore:
    """session_set / session_get: non-persisted, GIL-safe, flat key-value store."""

    def setup_method(self):
        from src import config as cfg_module
        cfg_module._SESSION.clear()

    def test_get_returns_none_for_missing_key(self):
        from src.config import session_get
        assert session_get("nonexistent") is None

    def test_get_returns_default_for_missing_key(self):
        from src.config import session_get
        assert session_get("nonexistent", default=False) is False
        assert session_get("nonexistent", default=42) == 42

    def test_set_then_get_roundtrip(self):
        from src.config import session_set, session_get
        session_set("ollama_available", True)
        assert session_get("ollama_available") is True

    def test_set_overwrites_previous_value(self):
        from src.config import session_set, session_get
        session_set("key", "first")
        session_set("key", "second")
        assert session_get("key") == "second"

    def test_session_isolated_from_runtime_config(self):
        """session_get must NOT read from _RUNTIME_CONFIG."""
        from src.config import session_get, config_set
        config_set("some_key", "config_value")
        assert session_get("some_key") is None

    def test_session_does_not_trigger_async_save(self, monkeypatch):
        """session_set must not call _async_save."""
        from src import config as cfg_module
        save_called = []
        monkeypatch.setattr(cfg_module, "_async_save", lambda: save_called.append(1))
        cfg_module.session_set("x", 1)
        assert save_called == []