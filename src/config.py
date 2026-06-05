# src/config.py
from __future__ import annotations
import json
import logging
from pathlib import Path
import src.constants as _c
from src.constants import CONFIG_PATH

logger = logging.getLogger(__name__)

_CONFIG_PATH = CONFIG_PATH
_OVERRIDABLE = {
    "APM_HYPER_THRESHOLD", "SLEEP_IDLE_SECONDS", "WANDER_SPEED_PX",
    "CHASE_ENTER_RADIUS_PX", "CHASE_EXIT_RADIUS_PX",
    "SPEECH_BUBBLE_DURATION_MS", "FSM_TICK_MS", "GROUND_PADDING_PX",
    "window_monitor", "OPENCODE_SCRIPT_PATH",
    "OPENCODE_SERVER_URL", "OPENCODE_API_MODEL_ID",
    "pet_scale", "pet_opacity", "pet_speed", "tts_enabled", "FIREBASE_API_KEY",
    "tts_rate", "tts_volume", "tts_voice_id",
}

def load_config() -> dict:
    defaults = {k: getattr(_c, k) for k in _OVERRIDABLE if hasattr(_c, k)}
    defaults["window_monitor"] = False   # opt-in, off by default
    defaults["pet_scale"] = 1.0
    defaults["pet_opacity"] = 0.85
    defaults["pet_speed"] = 1.0
    defaults["tts_enabled"] = True
    defaults["tts_rate"] = 220
    defaults["tts_volume"] = 1.0
    defaults["tts_voice_id"] = "en-US-GuyNeural"
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        defaults.update({k: v for k, v in data.items() if k in _OVERRIDABLE})
    except Exception as e:
        logger.warning("Failed to load config from %s: %s", _CONFIG_PATH, e)
    return defaults


def save_config(config: dict) -> bool:
    """Persist overridable keys to ~/.daemon_config.json. Returns True on success."""
    filtered = {k: v for k, v in config.items() if k in _OVERRIDABLE}
    try:
        _CONFIG_PATH.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning("Failed to save config: %s", e)
        return False
