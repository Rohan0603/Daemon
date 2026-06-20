# Strict Configuration Validation Design

## Objective
Remove all hardcoded configuration defaults from the Python source code and enforce strict, explicit configuration management where `data/daemon_config.json` acts as the absolute single source of truth.

## Rationale
The application currently uses a large hardcoded `DEFAULT_CONFIG` dictionary in `src/config.py`. While this provides a safety net for missing values, it obscures the configuration schema, creates a dual-source-of-truth problem, and makes `config.py` unnecessarily large. By adopting strict validation, the architecture becomes entirely declarative and file-driven.

## Architecture & Changes

### 1. Removal of Defaults
- The `DEFAULT_CONFIG` dictionary will be completely deleted from `src/config.py`.
- The `load_config()` method will no longer merge file contents with defaults. It will simply load `data/daemon_config.json`, unflatten it if necessary, and apply environmental overrides.

### 2. Strict Validation Strategy
- `validate_config(cfg)` will be expanded.
- It will assert the presence of all top-level keys (`llm`, `pet`, `tts`, `consent`, `window`, `firebase`, `mcp`, `behavior`, `logging`, `storage`).
- If `daemon_config.json` is missing entirely or structurally incomplete, `validate_config` will raise `MissingConfigurationError`.
- This error is intercepted by the existing boot-gate in `daemon.py` to trigger the `SettingsDialog`.

### 3. Missing File Handling
- To prevent an unrecoverable bootstrap paradox (where the app can't boot to show the Settings UI because it has no config), we must supply a static baseline config.
- A new file `assets/daemon_config_template.json` will be created containing the full configuration schema.
- If `load_config()` detects that `data/daemon_config.json` is missing, it will automatically copy the `assets/daemon_config_template.json` file into the `data/` directory before proceeding.

### 4. Adjustments to Flattening
- `FLAT_TO_NESTED` and `NESTED_TO_FLAT` dictionaries in `config.py` will be retained as they are critical for the Settings UI and backwards compatibility. 

### 5. AI Developer Guidelines (AGENTS.md)
Since this strict approach removes the LLM's ability to safely "assume" config keys will be defaulted, future AI agents could accidentally break the app when adding new features.
- An explicit warning will be added to `AGENTS.md` in the "End-to-End Architecture" section:
> **CRITICAL CONFIG WARNING:** The application operates on strict configuration validation. There is NO `DEFAULT_CONFIG` dictionary in the codebase. If you add a new feature that requires a new configuration key (e.g., `"chase_speed"`), you **must** instruct the user to update their `data/daemon_config.json`, or you must explicitly provide a migration script to inject it. Otherwise, the app will instantly crash with a KeyError on boot.

## Testing Strategy
- Update `tests/test_config.py` to remove assumptions about `DEFAULT_CONFIG`.
- Test the fallback mechanism where `assets/daemon_config_template.json` is copied to the data directory.
- Verify that `MissingConfigurationError` is correctly thrown when a required top-level section is missing from the loaded JSON.

## Rollout Plan
1. Create `assets/daemon_config_template.json` based on the current `DEFAULT_CONFIG`.
2. Update `AGENTS.md` with the critical warning rule.
3. Strip `DEFAULT_CONFIG` and modify `load_config()` and `validate_config()` in `src/config.py`.
4. Run full test suite and fix broken tests that rely on `DEFAULT_CONFIG`.
