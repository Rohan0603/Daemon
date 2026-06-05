# Structured Logging Design

> **Goal:** Replace the three parallel logging mechanisms (`print`, `debug_log`, `logging.*`) with a unified, configurable stdlib `logging` system.

**Architecture:** A single `setup_logging()` function in a new `src/logging_setup.py` configures formatters, handlers, and per-module levels at daemon startup. Each source file gets a module-level `logger = logging.getLogger(__name__)`. The old `constants.DEBUG` bool and `debug_log()` are removed. Silent `except: pass` blocks are replaced with logged warnings.

**Tech Stack:** Python stdlib `logging`, `RotatingFileHandler`.

---

## 1. Log File Location

Logs go in `logs/daemon.log` relative to the project root. The `logs/` directory is added to `.gitignore`.

- File path: `logs/daemon.log`
- Max size: 1 MB per file
- Backups: 3 rotated copies (`daemon.log.1`, `.2`, `.3`)
- `.gitignore` entry: `logs/`

## 2. Central Configuration: `setup_logging()`

New file `src/logging_setup.py` with a single function:

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(
    *,
    debug: bool = False,
    log_dir: str = "logs",
    config_overrides: dict[str, str] | None = None,
) -> None:
```

**Behavior:**

1. Creates `log_dir` if it doesn't exist
2. Configures the root logger:
   - Level: `DEBUG` if `debug=True`, else `INFO`
   - Format: `[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s`
   - Date format: `%Y-%m-%d %H:%M:%S`
3. Adds two handlers:
   - **Console handler:** stdout, level = root level, same format
   - **File handler:** `RotatingFileHandler(log_dir/daemon.log, maxBytes=1_048_576, backupCount=3)`, level = `DEBUG` always
4. Applies per-module level overrides from `config_overrides` (e.g., `{"pet_renderer": "WARNING"}`)
5. Captures `warnings.warn()` via `logging.captureWarnings(True)`
6. Returns `None` — logging is a global side effect

## 3. Module-Level Logger Pattern

Every source file (except `pet_renderer.py` and `pet_fsm.py`) gets:

```python
import logging
logger = logging.getLogger(__name__)
```

For `daemon.py` (where `__name__` is `__main__`):

```python
logger = logging.getLogger("daemon")
```

## 4. Migration Rules

| Old Call | New Call | When |
|----------|----------|------|
| `print(f"[daemon] ...")` | `logger.info(...)` | General status messages |
| `debug_log(...)` | `logger.debug(...)` | High-frequency / detailed tracing |
| `logging.info(...)` | `logger.info(...)` | No change in semantics |
| `logging.warning(...)` | `logger.warning(...)` | No change in semantics |
| silent `except: pass` | `logger.warning(...)` | I/O failures, non-fatal errors |

## 5. File-by-File Plan

See the implementation plan for exact call-site details. Summary:

| File | Migration |
|------|-----------|
| `src/logging_setup.py` | NEW — `setup_logging()` |
| `.gitignore` | Add `logs/` |
| `daemon.py` | Add logger, call `setup_logging()`, migrate 2 `print` + 1 `debug_log` |
| `constants.py` | Remove `DEBUG` bool and `debug_log()` |
| `src/pet_window.py` | Migrate 32 `print` → `info`, 21 `debug_log` → `debug` |
| `src/opencode_worker.py` | Migrate 26 `print` → `info/warning`, 4 `debug_log` → `debug` |
| `src/memory_manager.py` | Replace bare `logging.info/warning` with `logger.info/warning`, migrate 12 `debug_log` → `debug` |
| `src/opencode_serve_manager.py` | Migrate 9 `debug_log` → `debug` |
| `src/write_coalescer.py` | Replace bare `logging.warning` with `logger.warning` |
| `src/trigger_coalescer.py` | Replace bare `logging.info` with `logger.info` |
| `src/config.py` | Add logger, log load failures |
| `src/active_window.py` | Add logger, log Win32 failures |
| `src/apm_worker.py` | Add logger, log listener failures and APM ticks |
| `src/click_through.py` | Add logger, log toggle events |
| `src/context_menu.py` | Add logger, log menu actions |
| `src/persistence.py` | Add logger, replace silent `except: pass` |
| `src/memory.py` | Add logger, replace silent `except: pass` |
| `src/history.py` | Add logger, replace silent `except: pass` |
| `src/context_builder.py` | Add logger, log build/reset events |
| `seed_brain.py` | Add logger, log progress |
| `optimize_brain.py` | Add logger, log progress |

## 6. Files With NO Logging Added

- `src/pet_renderer.py` — pure rendering, no I/O or state
- `src/pet_fsm.py` — pure logic, no I/O or state
- `src/__init__.py` — empty

## 7. Sensitivity

No API keys, tokens, or passwords are or will be logged. Verified during exploration.

## 8. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| RotatingFileHandler doesn't exist on all platforms | stdlib, available everywhere |
| log_dir creation fails | `os.makedirs(exist_ok=True)` wrapped in try/except |
| Config override references non-existent module | Silently skipped with a `logger.debug` note |
| Performance impact of `DEBUG` file logging | File handler always DEBUG; console handler level matches root. In production (INFO), hundreds of debug calls per tick are filtered before format-string evaluation using `logger.isEnabledFor(logging.DEBUG)` if needed, but lazy %-formatting already defers string building |
