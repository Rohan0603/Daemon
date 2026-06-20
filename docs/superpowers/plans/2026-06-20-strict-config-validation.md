# Strict Config Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all hardcoded Python defaults, making `daemon_config.json` the strict single source of truth, and ensure safety via template copying.

**Architecture:** We will extract `DEFAULT_CONFIG` into a JSON template in `assets/`. `load_config()` will copy this template to `data/` if missing. `validate_config()` will be strict, enforcing that all top-level keys exist. `AGENTS.md` will be updated to warn future AI workers.

**Tech Stack:** Python, JSON

---

### Task 1: Create Template and Update Rules

**Files:**
- Create: `assets/daemon_config_template.json`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write the template JSON**
Create `assets/daemon_config_template.json` containing the exact contents of the current `DEFAULT_CONFIG` from `src/config.py`.
```json
{
  "llm": {
    "model_id": "gemini-2.5-flash",
    "provider": "opencode-zen",
    "server_url": "http://127.0.0.1:4096",
    "timeout_sec": 180,
    "api_key": ""
  },
  "pet": {
    "id": "kenny",
    "scale": 1.0,
    "opacity": 0.85,
    "speed_multiplier": 1.0,
    "chattiness": 1.0
  },
  "tts": {
    "enabled": true,
    "rate": 220,
    "volume": 1.0,
    "voice_id": "en-US-GuyNeural",
    "pitch": 1.15
  },
  "consent": {
    "allow_intrusive_animations": true,
    "allow_audio_disruptions": false,
    "allow_browser_redirection": false,
    "allow_clipboard_hijacking": false,
    "allow_mouse_interference": false,
    "allow_window_management": false,
    "allow_keyboard_injection": false
  },
  "window": {
    "monitor": false
  },
  "firebase": {
    "api_key": "",
    "project_id": "daemon-87f81",
    "credentials_path": "data/firebase-credentials.json"
  },
  "mcp": {
    "host": "127.0.0.1",
    "port": 4097
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
    "apm_state_change_cooldown": 5
  },
  "logging": {
    "level": "INFO",
    "dir": "logs",
    "retention_days": 7
  },
  "storage": {
    "memory_path": "data/.daemon_memory.json",
    "history_path": "data/.daemon_history.json",
    "diary_path": "data/.daemon_diary.json",
    "state_path": "data/.daemon_state.json",
    "auth_token_path": "data/.daemon_auth.json",
    "response_cache_path": "data/.daemon_response_cache.json",
    "thoughts_log_path": "data/.daemon_thoughts.log"
  }
}
```

- [ ] **Step 2: Add warning to AGENTS.md**
Append this rule to `AGENTS.md` at the bottom (or in a relevant configuration section):
```markdown
## Strict Configuration Validation
**CRITICAL CONFIG WARNING:** The application operates on strict configuration validation. There is NO `DEFAULT_CONFIG` dictionary in the codebase. If you add a new feature that requires a new configuration key (e.g., `"chase_speed"`), you **must** instruct the user to update their `data/daemon_config.json`, or you must explicitly provide a migration script to inject it. Otherwise, the app will instantly crash with a KeyError on boot.
```

- [ ] **Step 3: Commit**
```bash
git add assets/daemon_config_template.json AGENTS.md
git commit -m "chore: extract config template and update agent rules"
```

---

### Task 2: Strip Defaults and Rewire load_config

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Remove `DEFAULT_CONFIG`**
In `src/config.py`, delete the entire `DEFAULT_CONFIG` dictionary block (approx lines 22-119).

- [ ] **Step 2: Update `load_config()` to use template**
Replace `load_config` (and import `shutil` at the top of the file):
```python
import shutil

def load_config() -> dict:
    """Load config from CONFIG_PATH, copying from template if missing."""
    p = Path(_CONFIG_PATH)
    if not p.exists():
        logger.info("Config not found at %s — copying from template", p)
        template_path = Path(__file__).parent.parent / "assets" / "daemon_config_template.json"
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
        
    return _apply_env_overrides(data)
```

- [ ] **Step 3: Fix `save_config()` and `DEFAULT_SERVER_URL`**
Without `DEFAULT_CONFIG`, `save_config` cannot deepcopy it.
Also fix `DEFAULT_SERVER_URL` at the top of the file:
```python
DEFAULT_SERVER_URL: str = "http://127.0.0.1:4096"
```
And replace `save_config`:
```python
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
```

- [ ] **Step 4: Commit**
```bash
git add src/config.py
git commit -m "refactor(config): remove DEFAULT_CONFIG and use template file"
```

---

### Task 3: Strict Validation

**Files:**
- Modify: `src/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Enforce top-level keys in `validate_config()`**
In `src/config.py`, modify `validate_config()` to check top-level keys:
```python
def validate_config(cfg: dict) -> None:
    """Validates that mandatory config fields and environmental dependencies are present."""
    missing = []
    
    # 1. Top-Level Structure Checks
    required_sections = ["llm", "pet", "tts", "consent", "window", "firebase", "mcp", "behavior", "logging", "storage"]
    for section in required_sections:
        if section not in cfg or not isinstance(cfg[section], dict):
            missing.append(f"Section '{section}'")
            
    if missing:
        raise MissingConfigurationError(f"Missing or invalid configuration sections: {', '.join(missing)}. Please restore them from assets/daemon_config_template.json.")

    # 2. Mandatory Fields (existing)
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
        
    # 3. Environmental Checks (existing)
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
```

- [ ] **Step 2: Fix tests in `tests/test_config.py`**
Since `validate_config` now strictly requires *all* top-level keys, update the dummy configs in tests:
Replace the `valid_cfg` in `test_validate_config_passes_with_valid_data` and `test_validate_config_raises_on_missing_credentials_file`:
```python
def _get_minimal_valid_cfg():
    return {
        "llm": {"model_id": "test", "api_key": "test", "server_url": "http"},
        "firebase": {"api_key": "test", "project_id": "test", "credentials_path": "dummy.json"},
        "pet": {}, "tts": {}, "consent": {}, "window": {}, 
        "mcp": {}, "behavior": {}, "logging": {}, "storage": {}
    }
```
Update tests to use this helper. Update `test_load_config_default_fallback` if it relies on `DEFAULT_CONFIG` imports. Since we removed `DEFAULT_CONFIG` from `src.config`, you'll need to remove `DEFAULT_CONFIG` from `tests/test_config.py` imports and use a mock template file in tests.

Here is the exact code for the test updates (to put at the top of `test_config.py` replacing the old imports):
```python
import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch
from src.config import load_config, save_config, flatten_config, unflatten_config, validate_config, MissingConfigurationError
import src.config

def _get_minimal_valid_cfg():
    return {
        "llm": {"model_id": "test-model", "api_key": "test-key", "server_url": "http://localhost"},
        "firebase": {"api_key": "test-fb-key", "project_id": "test-id", "credentials_path": "dummy.json"},
        "pet": {}, "tts": {}, "consent": {}, "window": {}, 
        "mcp": {}, "behavior": {}, "logging": {}, "storage": {}
    }
```
And then update the body of `test_validate_config_passes_with_valid_data`:
```python
def test_validate_config_passes_with_valid_data():
    valid_cfg = _get_minimal_valid_cfg()
    with patch("os.path.exists", return_value=True), patch("os.access", return_value=True):
        validate_config(valid_cfg)
```
Update `test_validate_config_raises_on_missing_fields`:
```python
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
    assert "firebase.api_key" in msg
```
Update `test_validate_config_raises_on_missing_credentials_file`:
```python
def test_validate_config_raises_on_missing_credentials_file():
    valid_cfg = _get_minimal_valid_cfg()
    valid_cfg["firebase"]["credentials_path"] = "missing.json"
    with pytest.raises(MissingConfigurationError) as exc_info:
        with patch("os.path.exists", return_value=False):
            validate_config(valid_cfg)
    assert "firebase.credentials_path file not found" in str(exc_info.value)
```
Update `test_load_config_default_fallback`:
```python
def test_load_config_default_fallback(tmp_path):
    mock_conf = tmp_path / "test_config.json"
    mock_template = tmp_path / "mock_template.json"
    mock_template.write_text('{"llm": {"model_id": "fallback"}}')
    
    with patch.dict(os.environ, {}, clear=True):
        with patch("src.config._CONFIG_PATH", mock_conf):
            with patch("pathlib.Path.parent") as mock_parent:
                # Need to mock the template path resolving
                cfg = load_config()
```
*Wait, mocking Path is messy.* Just modify `test_load_config_default_fallback` to write a real template file to `src.config.Path(__file__).parent.parent / "assets" / "daemon_config_template.json"` before running, or properly mock the template read. Let's do a simple mock:
```python
@patch("shutil.copy2")
def test_load_config_default_fallback(mock_copy, tmp_path):
    mock_conf = tmp_path / "test_config.json"
    
    with patch.dict(os.environ, {}, clear=True):
        with patch("src.config._CONFIG_PATH", mock_conf):
            # Since the file doesn't exist, it will copy. 
            # We mock copy2, so the file still doesn't exist after copy,
            # load_config will hit the Exception and return empty dict.
            cfg = load_config()
            assert isinstance(cfg, dict)
            mock_copy.assert_called_once()
```

- [ ] **Step 3: Run the tests**
Run `py -m pytest tests/test_config.py -v`.
Expect them to pass.

- [ ] **Step 4: Commit**
```bash
git add src/config.py tests/test_config.py
git commit -m "feat(config): implement strict validation of top-level sections"
```
