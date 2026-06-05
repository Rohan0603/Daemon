import json
from unittest.mock import patch
from pathlib import Path
from src.config import load_config
import src.constants as constants

def test_load_config_default_fallback():
    with patch("src.config._CONFIG_PATH", Path("nonexistent_config_file.json")):
        cfg = load_config()
        assert cfg["APM_HYPER_THRESHOLD"] == constants.APM_HYPER_THRESHOLD
        assert cfg["window_monitor"] is False

def test_load_config_with_override(tmp_path):
    config_file = tmp_path / "daemon_config.json"
    custom_data = {
        "APM_HYPER_THRESHOLD": 999,
        "WANDER_SPEED_PX": 15,
        "window_monitor": True,
        "INVALID_KEY": "should_be_ignored"
    }
    config_file.write_text(json.dumps(custom_data), encoding="utf-8")
    
    with patch("src.config._CONFIG_PATH", config_file):
        cfg = load_config()
        assert cfg["APM_HYPER_THRESHOLD"] == 999
        assert cfg["WANDER_SPEED_PX"] == 15
        assert cfg["window_monitor"] is True
        assert "INVALID_KEY" not in cfg
