# src/config.py
from __future__ import annotations
import json
import logging
import copy
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Try to load .env from project root
load_dotenv()

logger = logging.getLogger(__name__)

class MissingConfigurationError(Exception):
    """Raised when critical configuration values or files are missing."""
    pass

STORAGE_DIR = Path(__file__).parent.parent / "data"
CONFIG_PATH = STORAGE_DIR / "daemon_config.json"

FLAT_TO_NESTED = {
    "USER_UID": ("user", "uid"),
    "USER_DISPLAY_NAME": ("user", "display_name"),
    "OPENCODE_API_MODEL_ID": ("llm", "model_id"),
    "OPENCODE_API_MODEL_PROVIDER": ("llm", "provider"),
    "OPENCODE_SERVER_URL": ("llm", "server_url"),
    "OPENCODE_API_TIMEOUT_SEC": ("llm", "timeout_sec"),
    "OPENCODE_API_KEY": ("llm", "api_key"),
    "pet_scale": ("pet", "scale"),
    "pet_opacity": ("pet", "opacity"),
    "pet_speed_multiplier": ("pet", "speed_multiplier"),
    "pet_speed": ("pet", "speed_multiplier"),
    "pet_speed": ("pet", "speed_multiplier"),
    "chattiness": ("pet", "chattiness"),
    "pet_id": ("pet", "id"),
    "PET_ACTIVE_PERSONAS": ("pet", "active_personas"),
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
    "PET_WIDTH": ("visuals", "pet_width"),
    "PET_HEIGHT": ("visuals", "pet_height"),
    "PET_CORNER_RADIUS": ("visuals", "pet_corner_radius"),
    "BODY_BLUE": ("visuals", "body_blue"),
    "BODY_DARK": ("visuals", "body_dark"),
    "EYE_WHITE": ("visuals", "eye_white"),
    "EYE_PUPIL": ("visuals", "eye_pupil"),
    "ACCENT_YELLOW": ("visuals", "accent_yellow"),
    "ACCENT_RED": ("visuals", "accent_red"),
    "BUBBLE_BG": ("visuals", "bubble_bg"),
    "BUBBLE_BORDER": ("visuals", "bubble_border"),
    "HYPER_FLASH": ("visuals", "hyper_flash"),
    "BUBBLE_TEXT_COLOR": ("visuals", "bubble_text_color"),
    "BUBBLE_MAX_WIDTH": ("visuals", "bubble_max_width"),
    "BUBBLE_PADDING": ("visuals", "bubble_padding"),
    "BUBBLE_CORNER_RADIUS": ("visuals", "bubble_corner_radius"),
    "BUBBLE_FONT_SIZE": ("visuals", "bubble_font_size"),
    "INPUT_WIDTH": ("visuals", "input_width"),
    "INPUT_HEIGHT": ("visuals", "input_height"),
    "INPUT_Y_OFFSET": ("visuals", "input_y_offset"),
    "_PERSONA_HINT": ("triggers", "persona_hint"),
    "RISKY_KEYWORDS": ("triggers", "risky_keywords"),
    "TASK_MANAGER_KEYWORDS": ("triggers", "task_manager_keywords"),
    "PROCRASTINATION_DOMAINS": ("triggers", "procrastination_domains"),
    "BUBBLE_QUEUE_MAX_SIZE": ("behavior", "bubble_queue_max_size"),
    "SHORT_BUBBLE_DURATION_MS": ("behavior", "short_bubble_duration_ms"),
    "SHORT_BUBBLE_CHAR_LIMIT": ("behavior", "short_bubble_char_limit"),
    "SQUASH_STRETCH_DURATION_MS": ("behavior", "squash_stretch_duration_ms"),
    "MIN_CHASE_DURATION_MS": ("behavior", "min_chase_duration_ms"),
    "PERIMETER_FALL_CHANCE": ("behavior", "perimeter_fall_chance"),
    "PARTICLE_MAX_COUNT": ("behavior", "particle_max_count"),
    "SHAKE_DURATION_MS": ("behavior", "shake_duration_ms"),
    "BOUNCE_DURATION_MS": ("behavior", "bounce_duration_ms"),
    "SPIN_DURATION_MS": ("behavior", "spin_duration_ms"),
    "LOOK_AWAY_DURATION_MS": ("behavior", "look_away_duration_ms"),
}

NESTED_TO_FLAT = {
    ("user", "uid"): "USER_UID",
    ("user", "display_name"): "USER_DISPLAY_NAME",
    ("llm", "model_id"): "OPENCODE_API_MODEL_ID",
    ("llm", "provider"): "OPENCODE_API_MODEL_PROVIDER",
    ("llm", "server_url"): "OPENCODE_SERVER_URL",
    ("llm", "timeout_sec"): "OPENCODE_API_TIMEOUT_SEC",
    ("llm", "api_key"): "OPENCODE_API_KEY",
    ("pet", "scale"): "pet_scale",
    ("pet", "opacity"): "pet_opacity",
    ("pet", "speed_multiplier"): "pet_speed_multiplier",
    ("pet", "speed_multiplier"): "pet_speed_multiplier",
    ("pet", "chattiness"): "chattiness",
    ("pet", "id"): "pet_id",
    ("pet", "active_personas"): "PET_ACTIVE_PERSONAS",
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
    ("visuals", "pet_width"): "PET_WIDTH",
    ("visuals", "pet_height"): "PET_HEIGHT",
    ("visuals", "pet_corner_radius"): "PET_CORNER_RADIUS",
    ("visuals", "body_blue"): "BODY_BLUE",
    ("visuals", "body_dark"): "BODY_DARK",
    ("visuals", "eye_white"): "EYE_WHITE",
    ("visuals", "eye_pupil"): "EYE_PUPIL",
    ("visuals", "accent_yellow"): "ACCENT_YELLOW",
    ("visuals", "accent_red"): "ACCENT_RED",
    ("visuals", "bubble_bg"): "BUBBLE_BG",
    ("visuals", "bubble_border"): "BUBBLE_BORDER",
    ("visuals", "hyper_flash"): "HYPER_FLASH",
    ("visuals", "bubble_text_color"): "BUBBLE_TEXT_COLOR",
    ("visuals", "bubble_max_width"): "BUBBLE_MAX_WIDTH",
    ("visuals", "bubble_padding"): "BUBBLE_PADDING",
    ("visuals", "bubble_corner_radius"): "BUBBLE_CORNER_RADIUS",
    ("visuals", "bubble_font_size"): "BUBBLE_FONT_SIZE",
    ("visuals", "input_width"): "INPUT_WIDTH",
    ("visuals", "input_height"): "INPUT_HEIGHT",
    ("visuals", "input_y_offset"): "INPUT_Y_OFFSET",
    ("triggers", "persona_hint"): "_PERSONA_HINT",
    ("triggers", "risky_keywords"): "RISKY_KEYWORDS",
    ("triggers", "task_manager_keywords"): "TASK_MANAGER_KEYWORDS",
    ("triggers", "procrastination_domains"): "PROCRASTINATION_DOMAINS",
    ("behavior", "bubble_queue_max_size"): "BUBBLE_QUEUE_MAX_SIZE",
    ("behavior", "short_bubble_duration_ms"): "SHORT_BUBBLE_DURATION_MS",
    ("behavior", "short_bubble_char_limit"): "SHORT_BUBBLE_CHAR_LIMIT",
    ("behavior", "squash_stretch_duration_ms"): "SQUASH_STRETCH_DURATION_MS",
    ("behavior", "min_chase_duration_ms"): "MIN_CHASE_DURATION_MS",
    ("behavior", "perimeter_fall_chance"): "PERIMETER_FALL_CHANCE",
    ("behavior", "particle_max_count"): "PARTICLE_MAX_COUNT",
    ("behavior", "shake_duration_ms"): "SHAKE_DURATION_MS",
    ("behavior", "bounce_duration_ms"): "BOUNCE_DURATION_MS",
    ("behavior", "spin_duration_ms"): "SPIN_DURATION_MS",
    ("behavior", "look_away_duration_ms"): "LOOK_AWAY_DURATION_MS",
}

# Keep _CONFIG_PATH for test compatibility
_CONFIG_PATH = CONFIG_PATH

# Convenience reference for the default opencode serve URL
DEFAULT_SERVER_URL: str = "http://127.0.0.1:4096"


def _deep_merge(target: dict, source: dict) -> None:
    """Recursively merge source dict into target dict in-place."""
    import copy
    for k, v in source.items():
        if k in target and isinstance(v, dict) and isinstance(target[k], dict):
            _deep_merge(target[k], v)
        else:
            target[k] = copy.deepcopy(v) if isinstance(v, (dict, list)) else v


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


def validate_config(cfg: dict) -> None:
    """Validates that mandatory config fields and environmental dependencies are present."""
    missing = []
    
    # 1. Top-Level Structure Checks
    required_sections = ["user", "llm", "pet", "tts", "consent", "window", "firebase", "mcp", "behavior", "logging", "storage", "visuals", "triggers"]
    for section in required_sections:
        if section not in cfg or not isinstance(cfg[section], dict):
            missing.append(f"Section '{section}'")
            
    if missing:
        raise MissingConfigurationError(f"Missing or invalid configuration sections: {', '.join(missing)}. Please restore them from assets/daemon_config_template.json.")

    # 2. Mandatory Fields
    if not cfg.get("llm", {}).get("model_id"):
        missing.append("llm.model_id")
    if not cfg.get("llm", {}).get("api_key"):
        missing.append("llm.api_key")
    if not cfg.get("llm", {}).get("server_url"):
        missing.append("llm.server_url")
    if not cfg.get("firebase", {}).get("api_key"):
        missing.append("firebase.api_key")
    if not cfg.get("firebase", {}).get("project_id"):
        missing.append("firebase.project_id")
        
    if missing:
        raise MissingConfigurationError(f"Missing mandatory configuration fields: {', '.join(missing)}")
        
    # 3. Environmental Checks
    cred_path = cfg.get("firebase", {}).get("credentials_path")
    if cred_path:
        project_root = Path(__file__).parent.parent
        resolved_path = project_root / cred_path if not os.path.isabs(cred_path) else Path(cred_path)
        if not resolved_path.exists():
            raise MissingConfigurationError(f"firebase.credentials_path file not found at {resolved_path}")

    # Write access check for data dir
    data_dir = Path(__file__).parent.parent / "data"
    if data_dir.exists() and not os.access(data_dir, os.W_OK):
        raise MissingConfigurationError(f"No write permissions for data directory: {data_dir}")


def load_config() -> dict:
    """Load config from CONFIG_PATH, merging missing keys from template."""
    p = Path(_CONFIG_PATH)
    template_path = Path(__file__).parent.parent / "assets" / "daemon_config_template.json"
    
    template_data = {}
    if template_path.exists():
        try:
            template_data = json.loads(template_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load template config: %s", e)

    if not p.exists():
        logger.info("Config not found at %s — copying from template", p)
        if template_path.exists():
            p.parent.mkdir(exist_ok=True)
            shutil.copy2(template_path, p)
        else:
            raise MissingConfigurationError("Template daemon_config_template.json missing from assets!")
            
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        is_flat = not any(isinstance(v, dict) for v in data.values())
        if is_flat:
            data = unflatten_config(data)
    except Exception as e:
        logger.warning("Failed to load config from %s: %s", _CONFIG_PATH, e)
        data = {}

    if template_data:
        _deep_merge(template_data, data)
        data = template_data
        
        # Auto-save so the missing sections are permanently written to the user's file
        if p.exists():
            save_config(data)

    final_data = _apply_env_overrides(data)
    
    # Patch constants module
    try:
        from src import constants
        flat = flatten_config(final_data)
        for k, v in flat.items():
            setattr(constants, k, v)
    except Exception as e:
        logger.warning("Failed to patch constants: %s", e)
        
    return final_data


def save_config(config: dict) -> bool:
    """Persist config to CONFIG_PATH."""
    p = Path(_CONFIG_PATH)
    current_cfg = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not any(isinstance(v, dict) for v in data.values()):
                data = unflatten_config(data)
            current_cfg = data
        except Exception:
            pass

    # Basic dictionary merging instead of deep merge since we assume structured replacement
    _deep_merge(current_cfg, config)

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
