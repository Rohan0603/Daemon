import json
import os
import pytest
from unittest.mock import patch
from pathlib import Path
from src.config import load_config, flatten_config, unflatten_config, DEFAULT_CONFIG, validate_config, MissingConfigurationError


def test_load_config_default_fallback():
    with patch("src.config._CONFIG_PATH", Path("this_file_surely_does_not_exist_98765.json")):
        cfg = load_config()
        assert cfg["llm"]["model_id"] == DEFAULT_CONFIG["llm"]["model_id"]
        assert cfg["window"]["monitor"] is False
        assert cfg["pet"]["id"] == "kenny"


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

    with patch("src.config._CONFIG_PATH", config_file):
        cfg = load_config()
        assert cfg["llm"]["model_id"] == "custom-model"
        assert cfg["llm"]["server_url"] == "http://custom-url:4096"
        assert cfg["pet"]["scale"] == 1.5
        assert cfg["window"]["monitor"] is True
        # Fallback fields should remain as default
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
    valid_cfg = {
        "llm": {"model_id": "test-model", "api_key": "test-key", "server_url": "http://localhost"},
        "firebase": {"api_key": "test-fb-key", "project_id": "test-id", "credentials_path": "dummy.json"}
    }
    with patch("os.path.exists", return_value=True), patch("os.access", return_value=True):
        # Should not raise
        validate_config(valid_cfg)

def test_validate_config_raises_on_missing_fields():
    invalid_cfg = {
        "llm": {"model_id": "", "api_key": "", "server_url": ""},
        "firebase": {"api_key": "", "project_id": "", "credentials_path": "dummy.json"}
    }
    with pytest.raises(MissingConfigurationError) as exc_info:
        with patch("os.path.exists", return_value=True), patch("os.access", return_value=True):
            validate_config(invalid_cfg)
    
    msg = str(exc_info.value)
    assert "llm.model_id" in msg
    assert "llm.api_key" in msg
    assert "firebase.api_key" in msg

def test_validate_config_raises_on_missing_credentials_file():
    valid_cfg = {
        "llm": {"model_id": "test-model", "api_key": "test-key", "server_url": "http://localhost"},
        "firebase": {"api_key": "test-fb-key", "project_id": "test-id", "credentials_path": "missing.json"}
    }
    with pytest.raises(MissingConfigurationError) as exc_info:
        with patch("os.path.exists", return_value=False):
            validate_config(valid_cfg)
    
    assert "firebase.credentials_path file not found" in str(exc_info.value)