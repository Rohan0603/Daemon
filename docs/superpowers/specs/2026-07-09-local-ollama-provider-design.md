# Local Ollama LLM Provider — Design Spec

**Date:** 2026-07-09
**Status:** Approved Design

## Overview

Add Ollama as a drop-in replacement LLM provider for Daemon, selectable via Settings → Connections. When Ollama is selected, Daemon manages the `ollama serve` subprocess lifecycle and sends prompts directly to Ollama's HTTP API, bypassing `opencode serve` entirely.

## Architecture

```
                         ┌─────────────────────┐
                         │    PetWindow         │
                         │  needs LLM response  │
                         └──────┬──────────────┘
                                │ provider == ?
                    ┌───────────┴───────────┐
                    │                       │
            ┌───────▼───────┐       ┌───────▼───────┐
            │ OpencodeWorker │       │ OllamaWorker  │
            │ (existing)     │       │ (new)         │
            │ POST :4096     │       │ POST :11434   │
            └───────┬───────┘       └───────┬───────┘
                    │                       │
            ┌───────▼───────┐       ┌───────▼───────┐
            │ opencode serve│       │  OllamaManager│ (new)
            │ (subprocess)  │       │  manages:     │
            └───────────────┘       │  ollama serve │
                                    │  ollama create │
                                    │  health checks │
                                    └───────────────┘
```

**Two new files in `src/llm/`:**
- `ollama_worker.py` — `OllamaWorker(QThread)`
- `ollama_manager.py` — `OllamaManager(QObject)`

## Components

### OllamaWorker(QThread)

Same signal interface as `OpencodeWorker`:
- `response_ready` / `trigger_ready` — `pyqtSignal(list)`
- `error_occurred` / `error` — `pyqtSignal(str)`
- `brain_update_ready` — `pyqtSignal(dict)`

Lifecycle (one-shot per query, same pattern as OpencodeWorker):
1. Check `_abort` flag
2. POST `/api/chat` with `{model, messages, stream: false}`
3. Parse `response.message.content` through the JSON parse chain
4. Emit `response_ready(items)` or `error(text)`

No session create/delete — Ollama is stateless.

SKILL.md is read once (cached) and sent as the system message in every request:
```
messages = [
    {"role": "system", "content": <SKILL.md contents>},
    {"role": "user", "content": <context_manager prompt>},
]
```

No MCP tool access in V1 — text-in/text-out only. Future V2 can map MCP tool definitions to Ollama's native `tools` parameter.

### OllamaManager(QObject)

Manages the `ollama` subprocess lifecycle using `QProcess`:

**start():**
1. Verify `ollama` on PATH
2. Check if `daemon-local` model exists (`ollama list` → grep)
3. If missing: `ollama create daemon-local -f <modelfile_path>`
4. Spawn `ollama serve` (CREATE_NO_WINDOW, detected already running → skip)
5. Health-check loop: GET /api/tags every 2s, max 10 retries
6. Emit `ready` signal on success, `error` on failure

**stop():**
1. Terminate QProcess
2. Wait 5s → kill if still alive

Signals:
- `status_changed(str)` — "starting" / "ready" / "error" / "stopped"
- `error_occurred(str)` — details

### Persona Injection (Single Source)

SKILL.md (.opencode/skills/<pet_id>/SKILL.md) is the **single source of truth** for persona. No hardcoded persona strings in `context_manager.py`.

**opencode serve path** (unchanged): opencode serve loads SKILL.md natively.

**Ollama path**: `OllamaWorker` reads the SKILL.md file once (cached) and sends it as the system message. The full file is sent — the LLM ignores irrelevant sections (MCP tool definitions, etc.).

**context_manager.py** becomes purely structural — builds the dynamic context (mode, APM, typing, screen) without persona text.

### Config Changes

New fields in `daemon_config.json` → `llm` section:

```json
"llm": {
    "provider": "opencode",
    "model_id": "gemini-2.5-flash",
    "server_url": "http://127.0.0.1:4096",
    "api_key": "",
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "daemon-local",
    "modelfile_path": "data/Modelfile"
}
```

New flat↔nested mappings in `config.py`:
- `LLM_PROVIDER` → `("llm", "provider")`
- `OLLAMA_URL` → `("llm", "ollama_url")`
- `OLLAMA_MODEL` → `("llm", "ollama_model")`
- `MODELFILE_PATH` → `("llm", "modelfile_path")`

`validate_config()` relaxed: `server_url` and `api_key` not mandatory when `provider == "ollama"`.

Modelfile moved from Desktop to `data/Modelfile` in the project repo.

### Settings UI — Connections Tab

Provider selector via QComboBox with two options:
- "opencode serve" (default) — shows Model ID, API Key, Server URL fields
- "Ollama (Local)" — shows Model name, Ollama URL, live status indicator, stop/restart button

Toggle hides/shows the relevant fields. Status label shows: ● Ready / ● Starting / ● Error.

When Ollama is not on PATH: settings shows "(not installed)" warning.

### PetWindow Changes

- `_llm_provider` attribute, checked before instantiating workers
- `_ensure_ollama_manager()` / `_teardown_ollama_manager()` — start/stop the
  `OllamaManager` (and its `ollama serve` subprocess) on boot and on runtime
  provider switch; `_teardown_ollama_manager()` also called at shutdown
- `ensure_opencode_serve_running()` skipped when `provider == "ollama"`
- Existing worker dispatch logic unchanged — just picks `OllamaWorker` vs `OpencodeWorker`
- `OllamaManager` warm-up runs off the Qt thread (`_warm_model_async()`) so the
  pet UI never freezes while the local model loads

### daemon.py Changes

- `ensure_opencode_serve_running()` gated on `provider != "ollama"`
- Boot sequence starts `OllamaManager` when provider is ollama
- Shutdown sequence stops `OllamaManager`

## Data Flow

### Ollama Query Pipeline
```
User input / autonomous trigger
  → ContextManager.build_*_trigger() → [structural context, NO persona]
  → OllamaWorker.run()
    → Read SKILL.md (cached)
    → POST /api/chat {model, messages: [system: SKILL.md, user: context], stream: false}
    → Parse response.message.content via JSON chain
    → Emit response_ready(items)
```

### Ollama Boot Pipeline
```
PetWindow.__init__()
  ├─ _llm_provider == "ollama"?
  ├─ OllamaManager.start()
  │   ├─ Find ollama on PATH
  │   ├─ ollama create daemon-local -f data/Modelfile (if needed)
  │   ├─ Spawn ollama serve
  │   └─ Health-check loop → emit ready
  └─ Normal boot continues
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Ollama not on PATH | Settings shows red warning, provider shows "(not installed)" |
| `ollama create` fails | Retry once, show error in Settings |
| `ollama serve` won't start | Retry 3x with 5s backoff, then graceful fallback (no LLM) |
| Ollama API unreachable | Worker emits `error_occurred("connection_refused")` |
| Model missing in Ollama | Auto `ollama create` on boot |
| Subprocess crash mid-session | OllamaManager auto-restarts, emits status change |

## Testing Plan

| Test File | Focus |
|-----------|-------|
| `tests/test_ollama_worker.py` | Unit tests with mocked `requests.post` — verify signals, parse chain, abort |
| `tests/test_ollama_manager.py` | Unit tests with mocked QProcess — lifecycle signals, health checks, retry |
| `tests/test_settings_dialog.py` | Provider toggle shows/hides correct fields |
| `tests/test_config.py` | New config keys, relaxed validation |
| `tests/test_pet_window.py` | Provider dispatch, boot sequence with mock OllamaManager |

## Future (V2)

- Map MCP tool definitions to Ollama's native `tools` parameter — tool-calling loop within OllamaWorker
- Model management UI in Settings (pull new models, browse GGUF files)
- Multiple pet personas with separate SKILL.md files
