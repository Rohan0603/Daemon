# src/config.py
from __future__ import annotations
import json
import logging
import copy
import os
from pathlib import Path

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "data"
CONFIG_PATH = STORAGE_DIR / "daemon_config.json"

DEFAULT_CONFIG = {
    "llm": {
      "model_id": "north-mini-code-free",
      "provider": "opencode-zen",
      "server_url": "http://127.0.0.1:4096",
      "timeout_sec": 180,
      "api_key": os.environ.get("OPENCODE_API_KEY", "your-opencode-api-key-here")
    },
    "pet": {
        "id": "kenny",
        "scale": 1.0,
        "opacity": 0.85,
        "speed_multiplier": 1.0,
        "chattiness": 1.0
    },
    "tts": {
        "enabled": True,
        "rate": 220,
        "volume": 1.0,
        "voice_id": "en-US-GuyNeural",
        "pitch": 1.15
    },
    "consent": {
        "allow_intrusive_animations": True,
        "allow_system_notifications": False,
        "allow_browser_redirection": False,
        "allow_clipboard_reading": False,
        "allow_mouse_interference": False,
        "allow_keyboard_injection": False,
        "allow_screenshot_capture": False,
        "allow_file_listing": True,
        "allow_file_reading": True,
        "allow_codebase_search": True,
        "allow_memory_access": True,
        "allow_diary_access": True
    },
    "window": {
        "monitor": False
    },
    "firebase": {
        "api_key": os.environ.get("FIREBASE_API_KEY", "your-firebase-api-key-here")
    }
}

FLAT_TO_NESTED = {
    "OPENCODE_API_MODEL_ID": ("llm", "model_id"),
    "OPENCODE_API_MODEL_PROVIDER": ("llm", "provider"),
    "OPENCODE_SERVER_URL": ("llm", "server_url"),
    "OPENCODE_API_TIMEOUT_SEC": ("llm", "timeout_sec"),
    "OPENCODE_API_KEY": ("llm", "api_key"),
    "pet_scale": ("pet", "scale"),
    "pet_opacity": ("pet", "opacity"),
    "pet_speed_multiplier": ("pet", "speed_multiplier"),
    "pet_speed": ("pet", "speed_multiplier"),
    "chattiness": ("pet", "chattiness"),
    "pet_id": ("pet", "id"),
    "tts_enabled": ("tts", "enabled"),
    "tts_rate": ("tts", "rate"),
    "tts_volume": ("tts", "volume"),
    "tts_voice_id": ("tts", "voice_id"),
    "tts_pitch": ("tts", "pitch"),
    "allow_intrusive_animations": ("consent", "allow_intrusive_animations"),
    "allow_system_notifications": ("consent", "allow_system_notifications"),
    "allow_browser_redirection": ("consent", "allow_browser_redirection"),
    "allow_clipboard_reading": ("consent", "allow_clipboard_reading"),
    "allow_mouse_interference": ("consent", "allow_mouse_interference"),
    "allow_keyboard_injection": ("consent", "allow_keyboard_injection"),
    "allow_screenshot_capture": ("consent", "allow_screenshot_capture"),
    "allow_file_listing": ("consent", "allow_file_listing"),
    "allow_file_reading": ("consent", "allow_file_reading"),
    "allow_codebase_search": ("consent", "allow_codebase_search"),
    "allow_memory_access": ("consent", "allow_memory_access"),
    "allow_diary_access": ("consent", "allow_diary_access"),
    "window_monitor": ("window", "monitor"),
    "FIREBASE_API_KEY": ("firebase", "api_key"),
}

NESTED_TO_FLAT = {
    ("llm", "model_id"): "OPENCODE_API_MODEL_ID",
    ("llm", "provider"): "OPENCODE_API_MODEL_PROVIDER",
    ("llm", "server_url"): "OPENCODE_SERVER_URL",
    ("llm", "timeout_sec"): "OPENCODE_API_TIMEOUT_SEC",
    ("llm", "api_key"): "OPENCODE_API_KEY",
    ("pet", "scale"): "pet_scale",
    ("pet", "opacity"): "pet_opacity",
    ("pet", "speed_multiplier"): "pet_speed_multiplier",
    ("pet", "chattiness"): "chattiness",
    ("pet", "id"): "pet_id",
    ("tts", "enabled"): "tts_enabled",
    ("tts", "rate"): "tts_rate",
    ("tts", "volume"): "tts_volume",
    ("tts", "voice_id"): "tts_voice_id",
    ("tts", "pitch"): "tts_pitch",
    ("consent", "allow_intrusive_animations"): "allow_intrusive_animations",
    ("consent", "allow_system_notifications"): "allow_system_notifications",
    ("consent", "allow_browser_redirection"): "allow_browser_redirection",
    ("consent", "allow_clipboard_reading"): "allow_clipboard_reading",
    ("consent", "allow_mouse_interference"): "allow_mouse_interference",
    ("consent", "allow_keyboard_injection"): "allow_keyboard_injection",
    ("consent", "allow_screenshot_capture"): "allow_screenshot_capture",
    ("consent", "allow_file_listing"): "allow_file_listing",
    ("consent", "allow_file_reading"): "allow_file_reading",
    ("consent", "allow_codebase_search"): "allow_codebase_search",
    ("consent", "allow_memory_access"): "allow_memory_access",
    ("consent", "allow_diary_access"): "allow_diary_access",
    ("window", "monitor"): "window_monitor",
    ("firebase", "api_key"): "FIREBASE_API_KEY",
}

# Keep _CONFIG_PATH for test compatibility
_CONFIG_PATH = CONFIG_PATH


def _deep_merge(target: dict, source: dict) -> None:
    """Recursively merge source dict into target dict in-place, filtering by target keys."""
    for k, v in source.items():
        if k in target:
            if isinstance(v, dict) and isinstance(target[k], dict):
                _deep_merge(target[k], v)
            else:
                target[k] = v


def load_config() -> dict:
    """Load config from CONFIG_PATH, deep-merge with defaults, and return nested dict."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    try:
        # Resolve path dynamically in case it's patched in tests
        p = Path(_CONFIG_PATH)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            # If the loaded data is flat, unflatten it first
            is_flat = not any(isinstance(v, dict) for v in data.values())
            if is_flat:
                data = unflatten_config(data)
            _deep_merge(cfg, data)
        else:
            logger.info("Config not found at %s — creating with defaults", p)
            save_config(cfg)
    except Exception as e:
        logger.warning("Failed to load config from %s: %s", _CONFIG_PATH, e)
    return cfg


def save_config(config: dict) -> bool:
    """Persist nested config to CONFIG_PATH. Accepts flat or nested dict."""
    is_nested = any(k in config and isinstance(config[k], dict) for k in DEFAULT_CONFIG.keys())
    
    p = Path(_CONFIG_PATH)
    current_cfg = copy.deepcopy(DEFAULT_CONFIG)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not any(isinstance(v, dict) for v in data.values()):
                data = unflatten_config(data)
            _deep_merge(current_cfg, data)
        except Exception:
            pass

    if is_nested:
        _deep_merge(current_cfg, config)
    else:
        nested_update = unflatten_config(config)
        _deep_merge(current_cfg, nested_update)

    try:
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(current_cfg, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning("Failed to save config: %s", e)
        return False


def flatten_config(nested: dict) -> dict:
    """Convert nested config dictionary to flat dict for compatibility."""
    flat = {}
    for section, subdict in nested.items():
        if isinstance(subdict, dict):
            for key, val in subdict.items():
                flat_key = NESTED_TO_FLAT.get((section, key))
                if flat_key:
                    flat[flat_key] = val
                else:
                    flat[f"{section}_{key}"] = val
        else:
            flat[section] = subdict
    return flat


def unflatten_config(flat: dict) -> dict:
    """Convert flat dict to nested dictionary structure."""
    nested = {}
    for flat_key, val in flat.items():
        if flat_key in FLAT_TO_NESTED:
            sec, subkey = FLAT_TO_NESTED[flat_key]
            if sec not in nested:
                nested[sec] = {}
            nested[sec][subkey] = val
        else:
            # Keep other keys at top-level
            nested[flat_key] = val
    return nested
