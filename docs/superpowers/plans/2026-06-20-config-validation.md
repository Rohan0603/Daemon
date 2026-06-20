# Configuration Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a Single Source of Truth validation system that strictly checks mandatory config values and environmental dependencies at boot, throwing a custom error to trigger an interactive setup modal if anything is missing.

**Architecture:** We will introduce a `MissingConfigurationError` and a `validate_config` function inside `src/config.py`. `load_config` will call this validation step. In `daemon.py`, we will wrap the config load in a try-except block, intercepting the validation error to spawn `QApplication` early and prompt the user via the `SettingsDialog`.

**Tech Stack:** Python 3.11+, PyQt6, pytest

---

### Task 1: `MissingConfigurationError` and `validate_config` in `src/config.py`

**Files:**
- Modify: `src/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test for `validate_config`**

Modify `tests/test_config.py` to add these tests at the end:
```python
import pytest
from src.config import validate_config, MissingConfigurationError
import os
from unittest.mock import patch

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_config.py::test_validate_config_raises_on_missing_fields -v`
Expected: FAIL because `MissingConfigurationError` is not imported/defined.

- [ ] **Step 3: Implement `MissingConfigurationError` and `validate_config`**

Modify `src/config.py`. First, at the top (around line 14, after imports):
```python
class MissingConfigurationError(Exception):
    """Raised when critical configuration values or files are missing."""
    pass
```

Next, add the `validate_config` function (above `load_config`):
```python
def validate_config(cfg: dict) -> None:
    """Validates that mandatory config fields and environmental dependencies are present."""
    missing = []
    
    # 1. Mandatory Fields
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
        
    # 2. Environmental Checks
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

Finally, modify `load_config` in `src/config.py` to call it before returning.
Find `return _apply_env_overrides(cfg)` (around line 329):
```python
    final_cfg = _apply_env_overrides(cfg)
    validate_config(final_cfg)
    return final_cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_config.py -v`
Expected: PASS (if the defaults are empty, test_load_config_default_fallback may fail, we will patch it in the next task). Note: If tests using `load_config()` fail globally because of missing defaults, you may need to patch `validate_config` in those tests or we adjust `load_config` to only validate in a separate call. Wait, if `load_config` strictly raises, tests that load default config with empty keys will break!
**Correction for Step 3**: Actually, modifying `load_config` to always raise will break every single test that calls it without a valid `.env`. Let's NOT call `validate_config(final_cfg)` inside `load_config()`. Instead, `daemon.py` will explicitly call `validate_config(cfg)` after loading.

*Fix for Step 3:* Revert the change to `load_config`. Leave `return _apply_env_overrides(cfg)` exactly as it was. `validate_config` will remain a separate function that `daemon.py` invokes explicitly.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat(config): add validate_config and MissingConfigurationError"
```

---

### Task 2: Intercept Validation Error in `daemon.py`

**Files:**
- Modify: `daemon.py`

- [ ] **Step 1: Intercept `load_config` and `validate_config` in `daemon.py`**

Open `daemon.py`. Locate the `main()` function, around line 117.
```python
    cfg = load_config()
    from src.config import validate_config, MissingConfigurationError
    try:
        validate_config(cfg)
    except MissingConfigurationError as e:
        logger.error(f"Configuration Validation Failed: {e}")
        # Need to spawn Settings UI here
        app = QApplication.instance() or QApplication(sys.argv)
        from src.settings_dialog import SettingsDialog
        dialog = SettingsDialog()
        result = dialog.exec()
        if result == dialog.DialogCode.Accepted:
            # User saved, reload config and re-validate
            cfg = load_config()
            try:
                validate_config(cfg)
            except MissingConfigurationError as e2:
                logger.fatal(f"Configuration still invalid after setup: {e2}")
                sys.exit(1)
        else:
            logger.fatal("Setup cancelled by user. Exiting.")
            sys.exit(1)
```

Replace the initial `cfg = load_config()` with the block above. Ensure `QApplication` is imported at the top (it already is).

- [ ] **Step 2: Clean up duplicate validation warnings**

In `daemon.py`, further down (around line 160), there is a section `# ── Config validation ───`. Since we now have strict validation, you can delete this entire redundant block:
```python
    # ── Config validation ────────────────────────────────────────────────
    firebase_key = cfg.get("firebase", {}).get("api_key", "")
    if not firebase_key:
        logger.warning("[CONFIG] firebase.api_key is empty — Firebase Auth will fail")
    opencode_url = cfg.get("llm", {}).get("server_url", "")
    opencode_api_key = cfg.get("llm", {}).get("api_key", "")
    if not opencode_api_key and "opencode" not in opencode_url:
        logger.warning("[CONFIG] llm.api_key is empty — opencode may not authenticate")
```
Delete those 8 lines.

- [ ] **Step 3: Run the app to verify setup mode**

Run: `py daemon.py`
If your `data/daemon_config.json` is missing keys, the app should immediately pop up the Settings Dialog! If you close it, the app exits. If you fill it out and save, it should proceed (and likely crash later if keys are fake, which is expected).

- [ ] **Step 4: Commit**

```bash
git add daemon.py
git commit -m "feat(daemon): intercept MissingConfigurationError and launch setup mode"
```
