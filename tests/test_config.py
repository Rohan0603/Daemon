import json
import os
import shutil
import pytest
from unittest.mock import patch
from pathlib import Path
from src.config import (
    load_config,
    flatten_config,
    unflatten_config,
    validate_config,
    MissingConfigurationError,
    _secret_value,
)

_ORIGINAL_COPY2 = shutil.copy2


def _get_minimal_valid_cfg():
    return {
        "llm": {"model_id": "test-model", "api_key": "test-key", "server_url": "http://localhost"},
        "firebase": {"project_id": "test-id", "auth_backend_url": "https://auth.example.test"},
        "user": {}, "pet": {}, "tts": {}, "consent": {}, "window": {}, 
        "mcp": {}, "behavior": {}, "logging": {}, "storage": {},
        "visuals": {}, "triggers": {}
    }


@patch("src.config.shutil.copy2")
def test_load_config_default_fallback(mock_copy, tmp_path):
    mock_copy.side_effect = _ORIGINAL_COPY2
    mock_conf = tmp_path / "test_config.json"
    
    with patch.dict(os.environ, {"OPENCODE_API_KEY": "test-key"}, clear=True):
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

    with patch.dict(os.environ, {"OPENCODE_API_KEY": "test-key"}, clear=True):
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
            "auth_backend_url": "https://auth.example.test"
        }
    }

    flat = flatten_config(nested)
    assert flat["OPENCODE_API_MODEL_ID"] == "model-1"
    assert flat["pet_scale"] == 1.2
    assert flat["pet_opacity"] == 0.9
    assert flat["pet_speed_multiplier"] == 1.1
    assert flat["window_monitor"] is True
    assert flat["FIREBASE_AUTH_BACKEND_URL"] == "https://auth.example.test"

    unflattened = unflatten_config(flat)
    assert unflattened["llm"]["model_id"] == "model-1"
    assert unflattened["pet"]["scale"] == 1.2
    assert unflattened["pet"]["opacity"] == 0.9
    assert unflattened["pet"]["speed_multiplier"] == 1.1
    assert unflattened["window"]["monitor"] is True
    assert unflattened["firebase"]["auth_backend_url"] == "https://auth.example.test"

def test_validate_config_passes_with_valid_data():
    valid_cfg = _get_minimal_valid_cfg()
    with patch("os.path.exists", return_value=True), patch("os.access", return_value=True):
        validate_config(valid_cfg)

def test_validate_config_raises_on_missing_fields():
    invalid_cfg = _get_minimal_valid_cfg()
    invalid_cfg["llm"]["model_id"] = ""
    invalid_cfg["llm"]["api_key"] = ""
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


def test_load_config_ignores_firebase_credentials_in_file_and_uses_environment(tmp_path):
    template = Path("assets/daemon_config_template.json")
    config_file = tmp_path / "daemon_config.json"
    file_cfg = json.loads(template.read_text(encoding="utf-8"))
    file_cfg["llm"]["api_key"] = "disk-value"
    file_cfg["llm"]["zen_api_key"] = "disk-value"
    file_cfg["firebase"]["api_key"] = "disk-value"
    file_cfg["firebase"]["credentials_path"] = "disk-credentials.json"
    file_cfg["firebase"]["auth_backend_url"] = "https://disk-auth.example.test"
    file_cfg["ide_bridge"]["token"] = "disk-value"
    config_file.write_text(json.dumps(file_cfg), encoding="utf-8")

    env = {
        "OPENCODE_API_KEY": "environment-value",
        "FIREBASE_AUTH_BACKEND_URL": "https://env-auth.example.test",
    }
    with patch.dict(os.environ, env, clear=True), \
         patch("src.config._CONFIG_PATH", config_file), \
         patch("src.config._credential_manager_value", return_value=""):
        cfg = load_config()

    assert cfg["llm"]["api_key"] == env["OPENCODE_API_KEY"]
    assert cfg["llm"]["zen_api_key"] == ""
    assert "api_key" not in cfg["firebase"]
    assert "credentials_path" not in cfg["firebase"]
    assert cfg["firebase"]["auth_backend_url"] == env["FIREBASE_AUTH_BACKEND_URL"]
    assert cfg["ide_bridge"]["token"] == ""


def test_validate_config_requires_runtime_llm_credential():
    cfg = _get_minimal_valid_cfg()
    cfg["llm"].pop("api_key")
    with pytest.raises(MissingConfigurationError, match="llm.api_key"):
        validate_config(cfg)


def test_secret_lookup_falls_back_to_credential_manager(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.setattr("src.config._credential_manager_value", lambda target: "stored-runtime-key")
    assert _secret_value("OPENCODE_API_KEY", "Daemon/OpenCodeApiKey") == "stored-runtime-key"


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