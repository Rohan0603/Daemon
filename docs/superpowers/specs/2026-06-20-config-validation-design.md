# SSoT Configuration Validation Design

## Overview
The goal is to enforce a strict Single Source of Truth (SSoT) for mandatory configurations (such as `model_id`, `OPENCODE_API_KEY`, and Firebase API credentials). If any of these mandatory configurations are missing during the initial boot sequence, the application will pause its standard initialization and prompt the user to supply the missing keys via the Settings interface.

## 1. Validation Logic (`src/config.py`)
`src/config.py` acts as the definitive Single Source of Truth for configuration management. It loads values from the `.env` file and `daemon_config.json`.

**Implementation Details:**
- **Custom Exception:** Create a new custom exception class: `MissingConfigurationError(Exception)`.
- **Validation Function:** Implement a `validate_config(cfg: dict)` function. This function will be called immediately before `load_config()` returns the configuration.
- **Mandatory Fields Checked:**
  - `llm.model_id` (must not be empty)
  - `llm.api_key` (must not be empty)
  - `llm.server_url` (must not be empty)
  - `firebase.api_key` (must not be empty)
  - `firebase.project_id` (must not be empty)
- **Environmental & Path Checks:**
  - Verify that the physical Service Account JSON file specified by `firebase.credentials_path` exists on disk.
  - Verify that the application has write access to the `data/` directory (e.g., by attempting a quick temporary file write).
- **Error Condition:** If any of these fields are missing, empty, or if the environmental checks fail, the function will gather the names of the missing keys and failed checks and raise a `MissingConfigurationError` with a clear message.

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
