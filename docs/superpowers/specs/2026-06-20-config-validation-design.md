# SSoT Configuration Validation Design

## Overview
The goal is to enforce a strict Single Source of Truth (SSoT) for mandatory configurations (such as `model_id`, `OPENCODE_API_KEY`, and Firebase API credentials). If any of these mandatory configurations are missing during the initial boot sequence, the application will pause its standard initialization and prompt the user to supply the missing keys via the Settings interface.

## 1. Validation Logic (`src/config.py`)
`src/config.py` acts as the definitive Single Source of Truth for configuration management. It loads values from the `.env` file and `daemon_config.json`.

**Implementation Details:**
- **Custom Exception:** Create a new custom exception class: `MissingConfigurationError(Exception)`.
- **Validation Function:** Implement a `validate_config(cfg: dict)` function. This function will be called immediately before `load_config()` returns the configuration.
- **Mandatory Fields Checked:**
  - `llm.model_id`
  - `llm.api_key`
  - `firebase.api_key`
- **Error Condition:** If any of these fields are missing, `None`, or evaluate to an empty string, the function will gather the names of the missing fields and raise a `MissingConfigurationError(f"Missing mandatory configuration fields: {missing_keys}")`.

## 2. Boot Sequence Interception (`daemon.py`)
We must handle the `MissingConfigurationError` gracefully to provide an Interactive Prompt, rather than letting the application crash entirely.

**Implementation Details:**
- Wrap the initial `load_config()` call in `daemon.py` with a `try...except MissingConfigurationError`.
- **On Exception:**
  1. The normal boot process is suspended.
  2. Instantiate `QApplication(sys.argv)` (if it hasn't been instantiated yet).
  3. Import and launch the `SettingsDialog` modally.
  4. The user is presented with the Settings dialog where they can input the missing API keys and save.
- **Resumption / Exit:**
  - When the dialog is closed, check if the configuration is now valid (e.g., attempt `load_config()` again).
  - If valid, resume the standard application boot sequence.
  - If still invalid (e.g., the user cancelled the dialog), exit the application gracefully using `sys.exit(1)`.

## 3. Scope and Edge Cases
- **No Background Spawning:** The pet's main window, TTS workers, FSM timers, and MCP server will not be started if the configuration is invalid.
- **Missing File:** If `daemon_config.json` doesn't exist, it is generated with `DEFAULT_CONFIG`. The validation will immediately run against this default state and throw the error since the default API keys are empty.

## End State
This design ensures that:
1. `src/config.py` remains the SSoT for evaluating config completeness.
2. The system explicitly throws an error when config is missing.
3. The user is gently guided to fix the issue instead of facing a hard crash.
