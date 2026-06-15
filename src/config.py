# src/config.py
from __future__ import annotations
import json
import logging
import copy
import os
from pathlib import Path
from dotenv import load_dotenv

# Try to load .env from project root
load_dotenv()

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent.parent / "data"
CONFIG_PATH = STORAGE_DIR / "daemon_config.json"

DEFAULT_CONFIG = {
    "llm": {
      "model_id": "north-mini-code-free",
      "provider": "opencode-zen",
      "server_url": "http://127.0.0.1:4096",
      "timeout_sec": 180,
      "api_key": ""  # loaded from .env or env var
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
        "allow_audio_disruptions": False,
        "allow_browser_redirection": False,
        "allow_clipboard_hijacking": False,
        "allow_mouse_interference": False,
        "allow_window_management": False,
        "allow_keyboard_injection": False
    },
    "window": {
        "monitor": False
    },
    "firebase": {
        "api_key": "",        # loaded from .env or env var
        "project_id": "daemon-87f81",
        "credentials_path": "data/firebase-credentials.json",
    },
    "mcp": {
        "host": "127.0.0.1",
        "port": 4097,
    },
    "behavior": {
        "apm_hyper_threshold": 150,
        "apm_window_seconds": 60,
        "speech_bubble_duration_ms": 8000,
        "opencode_timeout_seconds": 90,
        "wander_speed_px": 2,
        "hyper_speed_multiplier": 3.0,
        "gravity_acceleration": 0.5,
        "throw_velocity_threshold": 5.0,
        "throw_friction": 0.95,
        "ground_padding_px": 0,
        "chase_enter_radius_px": 120,
        "chase_exit_radius_px": 250,
        "sleep_idle_seconds": 300,
        "boredom_timeout_sec": 30,
        "autonomous_query_interval_sec": 20,
        "active_chat_interval_sec": 25,
        "joke_interval_sec": 60,
        "autonomous_cooldown_sec": 45,
        "behavior_tick_ms": 1000,
        "write_coalesce_flush_sec": 8,
        "silence_threshold": 5,
        "engaged_threshold": 2,
        "base_interval_sec": 15,
        "max_backoff_sec": 120,
        "backoff_multiplier": 1.5,
        "emotion_tick_sec": 5,
        "rapid_window_switch_threshold": 3,
        "fsm_tick_ms": 33,
        "click_through_poll_ms": 50,
        "thought_pool_size": 20,
        "thought_pool_threshold": 5,
        "thought_pool_refill_count": 5,
        "pool_decay_interval_sec": 120,
        "pool_refill_periodic_sec": 600,
        "apm_panic_threshold_low": 10,
        "apm_panic_threshold_high": 200,
        "apm_panic_cooldown_sec": 30,
        "apm_state_change_cooldown": 5,
    },
    "logging": {
        "level": "INFO",
        "dir": "logs",
        "retention_days": 7,
    },
    "storage": {
        "memory_path": ".daemon_memory.json",
        "history_path": ".daemon_history.json",
        "diary_path": ".daemon_diary.json",
        "state_path": ".daemon_state.json",
        "auth_token_path": ".daemon_auth.json",
        "response_cache_path": ".daemon_response_cache.json",
        "thoughts_log_path": ".daemon_thoughts.log",
    },
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
    "allow_audio_disruptions": ("consent", "allow_audio_disruptions"),
    "allow_browser_redirection": ("consent", "allow_browser_redirection"),
    "allow_clipboard_hijacking": ("consent", "allow_clipboard_hijacking"),
    "allow_mouse_interference": ("consent", "allow_mouse_interference"),
    "allow_keyboard_injection": ("consent", "allow_keyboard_injection"),
    "allow_window_management": ("consent", "allow_window_management"),
    "window_monitor": ("window", "monitor"),
    "FIREBASE_API_KEY": ("firebase", "api_key"),
    "FIREBASE_PROJECT_ID": ("firebase", "project_id"),
    "FIREBASE_CREDENTIALS_PATH": ("firebase", "credentials_path"),
    "MCP_HOST": ("mcp", "host"),
    "MCP_PORT": ("mcp", "port"),
    "APM_HYPER_THRESHOLD": ("behavior", "apm_hyper_threshold"),
    "APM_WINDOW_SECONDS": ("behavior", "apm_window_seconds"),
    "SPEECH_BUBBLE_DURATION_MS": ("behavior", "speech_bubble_duration_ms"),
    "OPENCODE_TIMEOUT_SECONDS": ("behavior", "opencode_timeout_seconds"),
    "WANDER_SPEED_PX": ("behavior", "wander_speed_px"),
    "HYPER_SPEED_MULTIPLIER": ("behavior", "hyper_speed_multiplier"),
    "GRAVITY_ACCELERATION": ("behavior", "gravity_acceleration"),
    "THROW_VELOCITY_THRESHOLD": ("behavior", "throw_velocity_threshold"),
    "THROW_FRICTION": ("behavior", "throw_friction"),
    "GROUND_PADDING_PX": ("behavior", "ground_padding_px"),
    "CHASE_ENTER_RADIUS_PX": ("behavior", "chase_enter_radius_px"),
    "CHASE_EXIT_RADIUS_PX": ("behavior", "chase_exit_radius_px"),
    "SLEEP_IDLE_SECONDS": ("behavior", "sleep_idle_seconds"),
    "BOREDOM_TIMEOUT_SEC": ("behavior", "boredom_timeout_sec"),
    "AUTONOMOUS_QUERY_INTERVAL_SEC": ("behavior", "autonomous_query_interval_sec"),
    "ACTIVE_CHAT_INTERVAL_SEC": ("behavior", "active_chat_interval_sec"),
    "JOKE_INTERVAL_SEC": ("behavior", "joke_interval_sec"),
    "AUTONOMOUS_COOLDOWN_SEC": ("behavior", "autonomous_cooldown_sec"),
    "BEHAVIOR_TICK_MS": ("behavior", "behavior_tick_ms"),
    "WRITE_COALESCE_FLUSH_SEC": ("behavior", "write_coalesce_flush_sec"),
    "SILENCE_THRESHOLD": ("behavior", "silence_threshold"),
    "ENGAGED_THRESHOLD": ("behavior", "engaged_threshold"),
    "BASE_INTERVAL_SEC": ("behavior", "base_interval_sec"),
    "MAX_BACKOFF_SEC": ("behavior", "max_backoff_sec"),
    "BACKOFF_MULTIPLIER": ("behavior", "backoff_multiplier"),
    "EMOTION_TICK_SEC": ("behavior", "emotion_tick_sec"),
    "RAPID_WINDOW_SWITCH_THRESHOLD": ("behavior", "rapid_window_switch_threshold"),
    "FSM_TICK_MS": ("behavior", "fsm_tick_ms"),
    "CLICK_THROUGH_POLL_MS": ("behavior", "click_through_poll_ms"),
    "THOUGHT_POOL_SIZE": ("behavior", "thought_pool_size"),
    "THOUGHT_POOL_THRESHOLD": ("behavior", "thought_pool_threshold"),
    "THOUGHT_POOL_REFILL_COUNT": ("behavior", "thought_pool_refill_count"),
    "POOL_DECAY_INTERVAL_SEC": ("behavior", "pool_decay_interval_sec"),
    "POOL_REFILL_PERIODIC_SEC": ("behavior", "pool_refill_periodic_sec"),
    "APM_PANIC_THRESHOLD_LOW": ("behavior", "apm_panic_threshold_low"),
    "APM_PANIC_THRESHOLD_HIGH": ("behavior", "apm_panic_threshold_high"),
    "APM_PANIC_COOLDOWN_SEC": ("behavior", "apm_panic_cooldown_sec"),
    "APM_STATE_CHANGE_COOLDOWN": ("behavior", "apm_state_change_cooldown"),
    "LOG_LEVEL": ("logging", "level"),
    "LOG_DIR": ("logging", "dir"),
    "LOG_RETENTION_DAYS": ("logging", "retention_days"),
    "MEMORY_PATH": ("storage", "memory_path"),
    "HISTORY_PATH": ("storage", "history_path"),
    "DIARY_PATH": ("storage", "diary_path"),
    "STATE_PATH": ("storage", "state_path"),
    "AUTH_TOKEN_PATH": ("storage", "auth_token_path"),
    "RESPONSE_CACHE_PATH": ("storage", "response_cache_path"),
    "THOUGHTS_LOG_PATH": ("storage", "thoughts_log_path"),
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
    ("consent", "allow_audio_disruptions"): "allow_audio_disruptions",
    ("consent", "allow_browser_redirection"): "allow_browser_redirection",
    ("consent", "allow_clipboard_hijacking"): "allow_clipboard_hijacking",
    ("consent", "allow_mouse_interference"): "allow_mouse_interference",
    ("consent", "allow_keyboard_injection"): "allow_keyboard_injection",
    ("consent", "allow_window_management"): "allow_window_management",
    ("window", "monitor"): "window_monitor",
    ("firebase", "api_key"): "FIREBASE_API_KEY",
    ("firebase", "project_id"): "FIREBASE_PROJECT_ID",
    ("firebase", "credentials_path"): "FIREBASE_CREDENTIALS_PATH",
    ("mcp", "host"): "MCP_HOST",
    ("mcp", "port"): "MCP_PORT",
    ("behavior", "apm_hyper_threshold"): "APM_HYPER_THRESHOLD",
    ("behavior", "apm_window_seconds"): "APM_WINDOW_SECONDS",
    ("behavior", "speech_bubble_duration_ms"): "SPEECH_BUBBLE_DURATION_MS",
    ("behavior", "opencode_timeout_seconds"): "OPENCODE_TIMEOUT_SECONDS",
    ("behavior", "wander_speed_px"): "WANDER_SPEED_PX",
    ("behavior", "hyper_speed_multiplier"): "HYPER_SPEED_MULTIPLIER",
    ("behavior", "gravity_acceleration"): "GRAVITY_ACCELERATION",
    ("behavior", "throw_velocity_threshold"): "THROW_VELOCITY_THRESHOLD",
    ("behavior", "throw_friction"): "THROW_FRICTION",
    ("behavior", "ground_padding_px"): "GROUND_PADDING_PX",
    ("behavior", "chase_enter_radius_px"): "CHASE_ENTER_RADIUS_PX",
    ("behavior", "chase_exit_radius_px"): "CHASE_EXIT_RADIUS_PX",
    ("behavior", "sleep_idle_seconds"): "SLEEP_IDLE_SECONDS",
    ("behavior", "boredom_timeout_sec"): "BOREDOM_TIMEOUT_SEC",
    ("behavior", "autonomous_query_interval_sec"): "AUTONOMOUS_QUERY_INTERVAL_SEC",
    ("behavior", "active_chat_interval_sec"): "ACTIVE_CHAT_INTERVAL_SEC",
    ("behavior", "joke_interval_sec"): "JOKE_INTERVAL_SEC",
    ("behavior", "autonomous_cooldown_sec"): "AUTONOMOUS_COOLDOWN_SEC",
    ("behavior", "behavior_tick_ms"): "BEHAVIOR_TICK_MS",
    ("behavior", "write_coalesce_flush_sec"): "WRITE_COALESCE_FLUSH_SEC",
    ("behavior", "silence_threshold"): "SILENCE_THRESHOLD",
    ("behavior", "engaged_threshold"): "ENGAGED_THRESHOLD",
    ("behavior", "base_interval_sec"): "BASE_INTERVAL_SEC",
    ("behavior", "max_backoff_sec"): "MAX_BACKOFF_SEC",
    ("behavior", "backoff_multiplier"): "BACKOFF_MULTIPLIER",
    ("behavior", "emotion_tick_sec"): "EMOTION_TICK_SEC",
    ("behavior", "rapid_window_switch_threshold"): "RAPID_WINDOW_SWITCH_THRESHOLD",
    ("behavior", "fsm_tick_ms"): "FSM_TICK_MS",
    ("behavior", "click_through_poll_ms"): "CLICK_THROUGH_POLL_MS",
    ("behavior", "thought_pool_size"): "THOUGHT_POOL_SIZE",
    ("behavior", "thought_pool_threshold"): "THOUGHT_POOL_THRESHOLD",
    ("behavior", "thought_pool_refill_count"): "THOUGHT_POOL_REFILL_COUNT",
    ("behavior", "pool_decay_interval_sec"): "POOL_DECAY_INTERVAL_SEC",
    ("behavior", "pool_refill_periodic_sec"): "POOL_REFILL_PERIODIC_SEC",
    ("behavior", "apm_panic_threshold_low"): "APM_PANIC_THRESHOLD_LOW",
    ("behavior", "apm_panic_threshold_high"): "APM_PANIC_THRESHOLD_HIGH",
    ("behavior", "apm_panic_cooldown_sec"): "APM_PANIC_COOLDOWN_SEC",
    ("behavior", "apm_state_change_cooldown"): "APM_STATE_CHANGE_COOLDOWN",
    ("logging", "level"): "LOG_LEVEL",
    ("logging", "dir"): "LOG_DIR",
    ("logging", "retention_days"): "LOG_RETENTION_DAYS",
    ("storage", "memory_path"): "MEMORY_PATH",
    ("storage", "history_path"): "HISTORY_PATH",
    ("storage", "diary_path"): "DIARY_PATH",
    ("storage", "state_path"): "STATE_PATH",
    ("storage", "auth_token_path"): "AUTH_TOKEN_PATH",
    ("storage", "response_cache_path"): "RESPONSE_CACHE_PATH",
    ("storage", "thoughts_log_path"): "THOUGHTS_LOG_PATH",
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


def _apply_env_overrides(cfg: dict) -> dict:
    """Override config from environment variables (highest priority).
    Called after JSON file merge so .env / env vars win over file values.
    """
    env_map: dict[str, tuple[str, str]] = {
        "OPENCODE_API_KEY": ("llm", "api_key"),
        "FIREBASE_API_KEY": ("firebase", "api_key"),
        "FIREBASE_PROJECT_ID": ("firebase", "project_id"),
    }
    for env_key, (section, subkey) in env_map.items():
        val = os.environ.get(env_key)
        if val and val.strip():
            if section not in cfg:
                cfg[section] = {}
            cfg[section][subkey] = val.strip()
    return cfg


def load_config() -> dict:
    """Load config from CONFIG_PATH, deep-merge with defaults, apply env overrides."""
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
    return _apply_env_overrides(cfg)


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
