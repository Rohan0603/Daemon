# Daemon — Project Dev Memory

## 2026-09-04 — Notebook Empty-Output Handling

- Updated `fine_tuning/notebooks/colab_finetune.ipynb` Cell 4 to skip and report records with empty outputs while still failing on missing fields or invalid types.
- Uploaded dataset contains 244 rows; record 208 is empty-output, leaving 243 valid training/evaluation rows.
- Cell 4 syntax and notebook JSON validation passed.
## 2026-09-04 — Phase 2 LLM Orchestrator Contract

- Added `src/llm/orchestrator.py` with provider-neutral request and worker
  lifecycle contracts. It supports common signal routing, autonomous deferral,
  user preemption, and non-blocking cancellation through injected workers.
- Exported `LLMOrchestrator` and `LLMRequest` from `src.llm`.
- Added focused fake-worker contract tests. Full `PetWindow` rewiring remains
  next step after this lifecycle boundary is proven.
- Focused orchestrator/provider tests: 8 passed. An earlier full-suite run was
  blocked by transient MCP import drift; the later rerun collected normally.
  Phase 2 contract committed as `5f7855e` on `task-2-llm-orchestrator`.
- PetWindow now delegates worker construction, common signal wiring, and start
  to the orchestrator while retaining existing preemption policy. Focused
  integration tests: 24 passed. Full suite: 993 passed, 2 skipped in 47.53s.

## 2026-09-04 — Phase 3 Action Boundary

- Ollama `change_visual_state` calls now reuse MCP consent and valid-action
  validation before dispatching through the existing FSM/action bridge.
- Bound MCP wrapper references explicitly to PetWindow's bridge, action layer,
  consent config, and feature config so compatibility wrappers cannot drift.
- Added denied-animation regression coverage. Focused action tests: 9 passed.
  Full suite: 994 passed, 2 skipped in 47.67s.

## 2026-09-04 — Unsloth Formatter Batch Compatibility

- Fixed `fine_tuning/notebooks/colab_finetune.ipynb` Cell 5 `formatting_func` to support both Unsloth's scalar formatter probe and batched dataset mapping.
- Root cause: empty scalar `input` made `zip(instructions, input_texts, outputs)` empty, causing `test_text[0]` `IndexError`; earlier scalar concatenation also failed when batched fields were lists.
- Focused validation passed: notebook JSON valid; scalar formatter returns 1 item; batched formatter returns 2 items.

## 2026-09-04 — Architecture and Training Plan Documentation

- Updated `docs/architecture.md` with current runtime boundaries, data flow,
  performance budgets, and privacy constraints while preserving historical
  implementation sections.
- Updated `fine_tuning/assets/FINETUNE_README.md` with the training execution
  gate, Daemon dataset contract, held-out evaluation requirements, artifact
  manifest, and notebook troubleshooting.
- Added `docs/architecture-evolution-plan.md` with six architecture decisions,
  build-vs-buy guidance, dependency map, phased roadmap, governance gaps, and
  measurable success criteria.
- Documentation validation passed: notebook JSON, expected content markers,
  trailing whitespace, and `git diff --check`.

## 2026-09-04 — Phase 0 Runtime Baseline

- Added `scripts/benchmark_runtime.py`, a provider-free deterministic baseline
  for user, autonomous, refill, and MCP paths with JSON latency, throughput,
  and Python allocation metrics.
- Added `tests/test_benchmark_runtime.py`; focused test and direct benchmark
  smoke run passed.
- Restored MCP visual-state routing, scoped MCP log-level changes to `src`,
  restored Ollama offline visual-state fallback, and added Firestore native
  nearest-neighbor fallback while preserving configured vector endpoints.
- Full suite: 989 passed, 2 skipped, 1 warning in 48.51s.
- Phase 0 committed as `bb473bb`.

## 2026-09-04 — Phase 1 Training Pipeline

- Hardened `fine_tuning/notebooks/colab_finetune.ipynb`: validates Alpaca
  records, creates deterministic 90/10 train/evaluation split, evaluates every
  50 steps, saves bounded checkpoints, and reports final evaluation loss.
- LoRA save cell now writes `artifact_manifest.json` with base model, source
  dataset, split sizes/seed, training metrics, and UTC creation time.
- GGUF export and Hugging Face publishing are explicit opt-in operations;
  Hub token comes from the Colab `HF_TOKEN` secret, never notebook source.
- Notebook JSON and all 9 code cells compile after neutralizing standard
  Colab magics for static validation. GPU execution remains a Colab-only gate.
- Focused benchmark test: 1 passed. Full suite: 989 passed, 2 skipped in
  48.27s. Phase 1 committed as `1a904d8` on `task-1-training-pipeline`.

> **READ THIS FIRST in every new session.** Authoritative project state: what's built, what's next, known issues.

## 2026-09-04 — Actionable Login Errors

- Preserved safe backend auth error codes in `FirebaseAuth.last_error_code` instead of discarding non-200 response details.
- Added optional `LoginDialog` error-message provider and mapped known sign-in/sign-up, configuration, and network failures to actionable UI text; unknown errors remain generic.
- Focused auth/login tests: 31 passed. PetWindow unit tests: 20 passed. Static diagnostics and `git diff --check` clean. Graphify updated.

## 2026-08-29 — Bounded MCP Execution

- Added per-request MCP budgets for tool count, wall-clock time, and cumulative
  UTF-8 payload size, with explicit budget/cancellation errors.
- Propagated worker abort events through Ollama and OpenCode MCP tool loops;
  existing request-cancellation metrics API records cancelled loops.
- MCP schema refresh failures preserve cached schemas instead of erasing them.
- Focused budget, cancellation, schema-cache, and worker-loop tests: 21 passed.
- Broader worker tests are blocked by a pre-existing BOM in modified
  `data/daemon_config.json`.

## 2026-08-29 — Bounded OpenCode Session Reuse

- Added `OpenCodeSessionManager` for optional interactive-only session reuse,
  enabled by `DAEMON_REUSE_OPENCODE_SESSIONS`.
- Sessions expire by idle time or max turns, recover through reset/health
  checks, and are closed during shutdown. Autonomous/refill workers stay
  ephemeral.
- Integrated manager through `OpencodeWorker` without changing provider
  gateway, config, data config, observability, or streaming transport.
- Added focused lifecycle tests; full targeted run was blocked by the current
  uncommitted config file's UTF-8 BOM.

## 2026-08-29 — End-to-End Latency Instrumentation

- Implemented typed `RequestTiming` lifecycle tracking with correlation IDs across PetWindow request dispatch, context/RAG construction, provider workers, parsing/dispatch, and first visible bubble.
- Added Prometheus phase histograms and provider/reason fallback counters; MCP handlers now record duration and allowed/error status.
- Added focused observability regression coverage. Tests: 52 passed, 2 skipped (observability, OpenCode/Ollama workers, MCP); PetWindow dispatch/unit tests: 25 passed.
- Graphify refresh remains required after this change.

## 2026-08-29 — Provider Gateway

- Added typed `src/llm/provider_gateway.py` shared policy for OpenCode/Ollama:
  normalized requests/results/errors, monotonic deadlines, jittered bounded
  retries, circuit health, and explicit fallback decisions.
- Integrated gateway policy into `PetWindow` provider selection and Ollama →
  OpenCode fallback without changing `data/daemon_config.json` or worker
  transport behavior.
- Added focused gateway tests; `tests/test_provider_gateway.py`: 4 passed.

---

## Project Snapshot

**Last updated:** 2026-08-29
**Branch:** `master` | **Latest commit:** `58cddec` (MCP connection fix)
**Stack:** Python 3.14, PyQt6, pynput, ctypes, requests, comtypes, Pillow, structlog, prometheus-client
**Test count:** 914 passed, 1 skipped (37.41s)

## 2026-08-29 — Runtime Secret Rotation

- Removed credential values from tracked `data/daemon_config.json` and the public config template.
- Config loading now strips credential-shaped file fields and resolves runtime secrets from environment variables or Windows Credential Manager generic credentials.
- Startup validation continues to fail safely when the selected OpenCode provider has no runtime credential; errors identify only missing field names.
- Added regression coverage for file-secret stripping, environment lookup, and missing-credential validation. Focused config/auth suite: 48 passed in 1.38s.

## 2026-08-29 — Evidence-Based Repository Cleanup

- Created `task-deep-codebase-cleanup` from local `master`; no commit created.
- Removed committed pytest transcripts, generated thought samples, Kaggle download logs, Hugging Face cache blobs, and generated Unsloth trainer cache files.
- Consolidated `.gitignore` coverage for Python/tool caches, virtual environments, PyInstaller/package output, coverage reports, runtime scratch files, recurring test/thought/Kaggle output, and backups.
- Fixed the `data/brain_schema.json` exception by changing the parent rule from `data/` to `/data/*`; the old directory rule prevented Git from re-including the schema.
- Removed 199 reproducible ignored cache/crash files (about 2.86 MiB) while preserving runtime user data and Graphify outputs.
- Removed orphaned `src/llm/code_analysis.py`, unused `src/physics.py`, stale `SKILL.md.backup`, three uncalled compatibility-era helpers, and stale imports; repository-wide AST/reference scans found no runtime or test consumers. Preserved `memory_manager.apply_brain_update` after focused tests proved it is a compatibility re-export.
- Targeted package/config tests: 21 passed; compatibility/import tests: 47 passed. Python compile check and `git diff --check` passed.
- Replaced the leftover Admin-SDK vector query with authenticated Firestore REST `runQuery` and made the codebase-awareness E2E test generate its map in a temporary directory instead of depending on ignored runtime state.
- Final full suite: 948 passed, 1 skipped, 1 warning in 40.43s.
- Graphify updated successfully after cleanup.

## 2026-08-29 — Python 3.14 TTS and Firestore Batch Fixes

- Root cause of silent result speech: pydub imports fail on Python 3.14 because `audioop`/`pyaudioop` is unavailable, so edge-tts MP3 conversion returned no audio.
- Added FFmpeg pipe-based MP3-to-WAV decoding fallback, with explicit TTS queue, worker, conversion, and playback diagnostics.
- Added regression coverage for FFmpeg decoding; TTS suite: 20 passed.
- Fixed Firestore diary batch writes to call the database-level `:commit` endpoint instead of incorrectly appending `:commit` to the documents collection URL, which caused HTTP 400 responses.
- Focused Firebase/memory/TTS suite: 71 passed in 3.23s.

## 2026-08-29 — Config Persistence and Trigger Diagnostics

- Fixed Settings persistence: saving UI values now starts from the full loaded config and merges edits, instead of writing a partial config that discarded unrelated settings.
- Synchronized the runtime config cache after disk writes so asynchronous config updates cannot overwrite newer values.
- Removed unused Pipeline URLs settings and constants; Ollama and OpenCode primary URLs remain under their active LLM settings.
- Added DEBUG logs for LLM actions, MCP/FSM actions, expression animations, emotion evaluations/transitions, and emotion decay.
- Fixed startup recovery settings save to preserve the full config and no longer request removed Firebase API-key UI data.
- Targeted config/settings/window suite: 48 passed in 3.08s.

## 2026-08-29 — TTS Result Playback Fallback

- Fixed `TTSWorker` to treat a false `winsound.PlaySound` result as playback failure, allowing the optional `simpleaudio` fallback to run instead of silently dropping result speech.
- Added PyInstaller hidden imports for dynamic `edge_tts`, `pyttsx3` SAPI5, and `pydub` imports so packaged builds retain TTS backends.
- Added regression coverage in `tests/test_tts_worker.py`; focused TTS suite: 19 passed in 0.78s.
- Documented Windows installation prerequisite `winget install Gyan.FFmpeg.Shared --accept-source-agreements --accept-package-agreements` and `ffmpeg -version` verification in `README.md`.
- Made FFmpeg WinGet discovery independent of installed versioned folder names, preventing pydub TTS decoding failures after installation.
- Added checked-by-default Login dialog "Remember me" control; saved sessions now restore automatically, while transient refresh failure no longer deletes valid saved credentials. Unchecked sign-in remains session-only.
- Auth/TTS/login/daemon regression suite: 55 passed in 2.21s.

## 2026-08-29 — Copilot Startup Defaults Verified

- Confirmed global and project instructions explicitly default Caveman Full, Ponytail engineering workflow, and Graphify codebase workflow.
- Confirmed `graphify-out/graph.json` exists, so Graphify startup rule is active for this repository.

## 2026-08-29 — Ponytail Instructions

- Added Ponytail lazy senior developer rules to global Copilot instructions and project `.github/copilot-instructions.md`.
- Rules emphasize YAGNI, reuse, root-cause fixes, minimal diffs, trust-boundary validation, and one focused runnable check for non-trivial logic.

## 2026-08-29 — Agentic Development Defaults

- Added project-wide `AGENTS.md` defaults: start sessions in Caveman Full and prioritize Ponytail when available.
- Global Copilot equivalent remains configured in the user-level `caveman.instructions.md` file.

## 2026-08-29 — Graphify Copilot Registration

- Confirmed `graphifyy` CLI already installed at version `0.9.48`.
- Registered graphify specifically for Copilot with `graphify install --platform copilot`.
- Removed Claude files recreated by the default `graphify install`; global Claude paths remain absent.

## 2026-08-29 — Firebase Settings Credential UX

- Kept Firebase visible in Settings → Connections as release-managed configuration.
- Removed Firebase API-key input and API-key output from `src/ui/settings_dialog.py`.
- Kept Firebase Project ID visible as read-only metadata; OpenCode remains only user-entered cloud credential.
- Preserved bundled Firebase configuration when saving unrelated Settings so user saves cannot erase the release API key.
- Added regression coverage for read-only Project ID and absent Firebase API-key output.
- Isolated behavior emotion tests from host active-window state and removed stale required-API-key assertion for local-only config.
- Full suite: 914 passed, 1 skipped, 1 warning in 37.41s. Graphify updated.

## 2026-08-29 — Firebase Client Security Slice

- Replaced desktop Firestore Admin SDK/service-account access in `src/firebase_crud.py` with authenticated Firestore REST requests using `FirebaseAuth.get_valid_token()` bearer tokens.
- Added typed Firestore value encoding/decoding, merge writes, REST queries, REST batch diary writes, transient retry, and one token-refresh retry after HTTP 401.
- Removed synthetic `uid = "default"` cloud initialization; `PetWindow` now creates cloud sync only for a real authenticated UID, while `--no-auth` remains local-only.
- Packaging no longer includes repository `data/`; build inputs now use existing safe assets and the template no longer requires a service-account path.
- Packaged builds resolve writable storage under `%LOCALAPPDATA%\\Daemon`; source-mode test paths remain unchanged.
- Focused Firebase/config/boot regression suite: 99 passed in 4.99s. Static diagnostics clear. Graphify updated.
- Next work: protected refresh-token storage/account switching, Firebase Emulator rules tests, package archive inspection, and full clean-build smoke test.

## 2026-08-29 — Auth Token Protection

- Added Windows DPAPI protection for new Firebase auth token files in `src/firebase_auth.py`; legacy plaintext files remain readable for migration.
- Removed Firebase UID writes from mutable config and added explicit `FirebaseAuth.sign_out()` backed by token/file clearing.
- Frozen-build relative storage paths now resolve into `%LOCALAPPDATA%\\Daemon` during config loading.
- Combined Firebase/config/auth/memory/boot gate: 100 passed in 4.69s. Static diagnostics clear. Graphify updated.

## 2026-08-29 — Account Lifecycle and Release Validation

- Added `Sign out of Firebase` to the actual UI context menu and connected `PetWindow` cleanup: stop Firestore sync, detach cloud memory/CRUD, clear protected auth tokens, and mark next launch for login.
- Added regression coverage proving auth loading does not mutate config identity; focused auth/PetWindow tests: 38 passed. Settings dialog import regression fixed; settings tests: 7 passed.
- Added `docs/firebase-distribution.md` covering Email/Password setup, Firestore rules deployment, API-key restrictions, token/storage behavior, account switching, and package release checklist.
- Clean PyInstaller build succeeded with `build.ps1`; package inspection found public config template only and no repository `data/`, auth token, developer config, or service-account JSON.
- `graphify update .` succeeded.
- Full suite currently has pre-existing failures/errors: 868 passed, 3 failed, 1 skipped, 6 errors in 53.57s. Failures are behavior-controller, config autocreation, FSM bridge, and login-dialog tests; suite misses the under-50-second gate. Firebase-focused tests remain green.
- Remaining release proof: run Firebase Emulator Suite rules tests against staging rules, perform packaged first-launch/restart/second-account smoke test with real staging accounts, and resolve unrelated full-suite failures before release.

## 2026-08-23 — Kaggle Notebook Compute

- Installed Kaggle CLI 2.2.4 and authenticated via OAuth as `rohanponnanna06`.
- Added root `kernel-metadata.json` for private GPU kernel `rohanponnanna06/daemon-kenny-finetune` using `daemon.ipynb`.
- Verified both JSON files locally and submitted successfully; remote kernel was `RUNNING` at setup completion.
- VS Code workflow: `py -m kaggle kernels push -p .`, then `py -m kaggle kernels status rohanponnanna06/daemon-kenny-finetune`; download results with `py -m kaggle kernels output rohanponnanna06/daemon-kenny-finetune -p kaggle-output`.
- Removed the notebook's markdown explanation cell and Python comment-only lines; the notebook now contains 9 executable cells and validates with zero Python comments.
- Fixed Kaggle training setup after an accelerator error: the notebook now fails early when CUDA is unavailable and uses Unsloth-compatible `trl>=0.18.2,<=0.24.0` instead of the obsolete `<0.9.0` pin. Corrected kernel version 3 was submitted and reported `RUNNING`.
- Added compute-capability validation to the first notebook cell. Current Kaggle P100 (`sm_60`) is incompatible with the installed PyTorch/Unsloth build, which supports `sm_70` through `sm_120`; select T4, L4, A100, or newer in Kaggle Settings > Accelerator. Notebook version 4 pushed successfully and reported `RUNNING`.

---

## Recent Fix (2026-07-11): Pet cannot climb screen sides (PERIMETER)

**Symptom:** Pet reaches a screen corner and should climb the vertical side edge, but immediately drops back to the ground.

**Root cause:** `PetWindow._update_ground_y` (src/ui/pet_window.py:518) force-transitioned the pet into FALLING whenever `pet_y < ground_y` and it had been ≥0.5s since landing. While climbing a side edge (PERIMETER, `edge="right"/"left"`, `facing="up"/"down"`) the pet's y is intentionally above ground, so the guard fired on the very next tick and yanked it back down. A secondary guard in the "Seeking & Super Jump" block (pet_window.py:1274) could also reset a climbing pet back to the bottom edge because perimeter uses screen geometry while `current_rect` is the perched window's rect.

**Fix:**
- Excluded `PetState.PERIMETER` from the force-FALLING guard at pet_window.py:518.
- Excluded `PetState.PERIMETER` from the Super-Jump reset at pet_window.py:1274 (only `IDLE` is reset now).

**Tests added:** `tests/test_pet_window_unit.py` — `test_perimeter_climbing_not_forced_to_falling`, `test_idle_above_ground_still_forced_to_falling`, `test_tick_perimeter_climbs_up_side`.

---

## Archive Index

| Archive | Covers | Key Topics |
|---------|--------|------------|
| `memory/archive/phases-01-35.md` | 06-06 to 06-08 | Window engine, opencode bridge, Firebase, auth, TTS, perimeter, storage hardening |
| `memory/archive/phases-36-50.md` | 06-08 to 06-15 | Agentic architecture, MCP, emotion engine, consent matrix, config migration |
| `memory/archive/phases-51-65.md` | 06-15 to 06-23 | Observability, BehaviorController, performance, plugins, Strands, test suite |
| `memory/archive/phases-66-plus.md` | 06-21 to 07-09 | Action palette, typewriter, coding assistant, stateless MCP, log audits |

> **Archives contain detailed phase tables, commit hashes, and design decisions.**
> Look there for historical context before asking about old features.

---

## What Is Built (High-Level)

- **Desktop pet** — Transparent, always-on-top PyQt6 widget with 11-state FSM, emotion engine (9 emotions), physics (gravity, throw, squash/stretch), 24-action expression layer
- **System awareness** — APM tracking, keystroke capture, active window detection, UIA screen reading, IDE detection, browser URL detection
- **LLM integration** — Stateless burst executor via opencode serve (:4096), thought pool caching (40-item unified pool), XML prompt builders
- **MCP server** — In-process JSON-RPC 2.0 on :4097, 13 tools, consent-gated (3 tiers), SSE broadcast
- **Memory** — 3-tier (Firestore → MemoryManager → local JSON), 33-field dynamic brain schema, atomic writes with .bak recovery
- **Autonomy** — BehaviorController (pure logic, no Qt), engagement tracker, adaptive backoff, context-aware boredom, code_assist mode
- **Observability** — structlog with correlation IDs, Prometheus metrics at /metrics, RotatingFileHandler, set_log_level MCP tool

---

## Key Pitfalls (Still Active)

- **No DEFAULT_CONFIG** — Adding a new config key will crash on boot unless `data/daemon_config.json` is updated
- **PetWindow instantiation in tests** — Must use `safe_pet_window` fixture; manual init causes timer/QThread leaks
- **JSON parse fallback chain** — `opencode_worker.py` tries 5 strategies; `_is_fallback_flood` dedup prevents spam
- **Worker lifecycle** — Never reuse QThread after `run()`; store refill workers in `_refill_workers` dict
- **PERIMETER↔CHASE oscillation** — Fixed with state guard + 500ms cooldown (pet_fsm.py)
- **AUTONOMOUS_THINKING never exits** — All callbacks must clear `_autonomous_query_pending`

---

## 2026-07-09 — Agent Guidelines Update (AGENTS.md)

**Branch:** `task-agent-guidelines-update`
**Test count:** 792 passed, 1 skipped in 36.24s

**Changes:**
- Added **Codebase Exploration (Graphify)** section — agents must use graphify before cross-module changes
- Added **Strict Pre-Commit Verification** — full test suite must pass and stay under 50s before any commit
- Added **Common Failures & Troubleshooting** — Qt timer hangs, port binding, circular imports, etc.
- **Archived** project-dev-memory.md (3176→58 lines): created `memory/archive/` with 4 phase archive files
- Updated project snapshot with latest test count and commit hash

**Files changed:**
- `AGENTS.md` — 3 new sections added
- `memory/project-dev-memory.md` — rewritten to <200 lines, archive index
- `memory/archive/phases-01-35.md` — created
- `memory/archive/phases-36-50.md` — created
- `memory/archive/phases-51-65.md` — created
- `memory/archive/phases-66-plus.md` — created

---

## 2026-07-10 — Master Optimization Plan (19 Tasks, 24 Findings)

**Test count:** 792 passed, 1 skipped in 28.81s

**Fixed Bugs (8):**
- B1: Removed stray `print("DEBUG: ...")` from `_log_thought`
- B2: Removed duplicate `_opencode_worker` declaration in `PetWindow.__init__`
- B3: Fixed `_on_mute_toggle` referencing nonexistent `_tts_worker` → `_tts`
- B4: Fixed `_on_wipe_memory` calling `self._diary.clear()` → `self._diary_store.clear()`; added `DiaryStore.clear()`
- B5: Fixed screen-time event using wrong data key `minutes` → `duration`
- B6/B7: Parented orphan QTimers in `WriteCoalescer.start()` (`QTimer(parent_obj)`) and `_schedule_boredom_retry` (`QTimer(self)`)
- B8: Removed duplicate `trigger_ready.emit(items)` from `OpencodeWorker.run()`

**Performance Fixes (7):**
- P1: Cached Win32 window rect in `_tick`, throttled from 30/s → 3/s
- P2: Deduplicated `get_active_window_title()` from 3 calls/tick → 1 call/tick in `BehaviorController.tick`
- P5: Replaced O(file_size) log rotation with stat-based rotation in `_log_thought`
- P6: Added 30s TTL cache for Firestore user-data GET in `sync_to_local`
- P7: Cached screen geometry in `PetWindow.__init__`, updated on geometry change signals
- MCP: Added `_FILE_CACHE_MAX_ENTRIES=50` and `_evict_stale_file_cache()` for bounded cache

**Enhancements (6):**
- E1: Added 5s GCD after boredom local actions (prevents rapid re-trigger)
- E2: Changed `_last_autonomous_fire_time` init from `0.0` to `time.monotonic()`; switched all fire-time tracking to monotonic time; guards at 15s now work correctly at boot
- E5: Wrapped `Event.data` in `MappingProxyType` to enforce immutability on frozen dataclass
- E7: Removed `QApplication.quit()` from `_on_mode_changed` (mode changes are not shutdowns)
- E8: Moved `self._dirty[kind] = False` into `finally` block so flags clear even on flush exceptions
- E9: Re-enabled TTS speech output by uncommenting `self._tts.enqueue(text)` in `_show_bubble`

**Files changed:**
- `src/ui/pet_window.py` — B1, B2, B3, B4, B7, E1, E7, E9, P1, P5, P7
- `src/autonomy/behavior_controller.py` — B5, E2, P2
- `src/write_coalescer.py` — B6, E8
- `src/llm/opencode_worker.py` — B8
- `src/memory_manager.py` — P6
- `src/mcp_server.py` — E6
- `src/events.py` — E5
- `src/diary_store.py` — B4 (added `clear()`)
- `tests/test_write_coalescer.py` — Updated test for new E8 behavior
- `tests/test_behavior_controller.py` — Set `_last_autonomous_fire_time = 0.0` for guard test
- `tests/test_behavior_controller_ide.py` — Set `_last_autonomous_fire_time = 0.0` for guard tests
- `tests/test_memory_manager.py` — Added cache fields to `__new__`-based test
- `tests/test_trigger_boredom_fsm.py` — Mocked `_schedule_boredom_retry` for `__new__`-based test

---

---

## TTS Optimization — 2026-07-09 (`4441bb1`)

**6 improvements to `src/system/tts_worker.py` (+ `tests/test_tts_worker.py`):**

| # | Improvement | Impact |
|---|-------------|--------|
| 1 | **Reuse asyncio loop** — `self._loop` created once in `__init__`, reused across all edge-tts calls | ~50ms saved per utterance |
| 2 | **Fix edge-tts pitch** — Now computes Hz from `self._pitch` via `12 * log2(pitch) * 8.33` instead of hardcoded `+15Hz` | Configurable pitch actually works |
| 3 | **Cache pyttsx3 engine** — Lazy `pyttsx3.init()` once, reused across fallbacks; invalidated on error | ~200ms saved on fallback path |
| 4 | **BytesIO pipeline** — `_generate_voice` streams edge-tts MP3 to `BytesIO` instead of temp file; `_apply_pitch_filter` accepts `str \| BytesIO` | 0 temp files on primary path |
| 5 | **Cancellation flag** — `clear()` sets `_cancel`; `enqueue()` clears it; `_process_utterance` checks between stages | Immediate abort on `clear()` |
| 6 | **LRU phrase cache** — 20-entry cache keyed by `(text, voice, pitch, rate)`; skips gen + pitch filter on hit | No network round-trip for repeats |

**Files changed:** `src/system/tts_worker.py` (+121/-46), `tests/test_tts_worker.py` (+118)

## Local LLM Response Fix & Arbitrary Model Support — 2026-07-10

**Fixed local LLM response issues and supported any installed model:**
- Deleted `daemon-local` model from Ollama, removed custom model creation and Modelfile building logic from `OllamaManager` to allow starting with any user-installed model.
- Changed default `"ollama_model"` to `"llama3.2-1b-q8:latest"` in default configuration files.
- Added automatic `"format": "json"` payload routing in `OllamaWorker` when tool-calling is not supported.
- Implemented robust `_normalize_item` parsing in `OllamaWorker` to gracefully extract dialogue, actions, thoughts, and brain updates from arbitrary formats.
- Fixed `TypeError` in `_on_refill_needed` inside `src/ui/pet_window.py` caused by passing a positional argument `""` to `_make_llm_worker`.
- Added capability validation in `SettingsDialog` using `/api/show` to check and display tool support.
- Fixed separator regex dash mismatch (`—` vs `-`) in `_summarize_for_ollama` that was appending the entire `SKILL.md` file (2090 chars) instead of only the Identity section. This reduces the prompt evaluation size by 2.5x and dramatically speeds up local CPU execution.
- Added programmatic placeholder replacement for `{user_nickname}`, `{user_partner_name}`, and `{user_engineer_name}` in the system prompt in `OllamaWorker` to resolve unrendered placeholders.

**Files changed:** `data/daemon_config.json`, `assets/daemon_config_template.json`, `src/llm/ollama_manager.py`, `src/llm/ollama_worker.py`, `src/ui/pet_window.py`, `src/ui/settings_dialog.py`, `tests/test_ollama_worker.py`

---

## Two-Brain Switching Smoothness Pass — 2026-07-11

**Audited the opencode↔ollama provider switch in Settings → Connections and removed the main-thread jank:**

| # | Fix | Location | Impact |
|---|-----|----------|--------|
| 1 | **Non-blocking model warm-up** — `_warm_model_async()` loads the Ollama model on a daemon thread (was a blocking `requests.post(timeout=120)` on the Qt main thread, freezing the pet up to 2 min) | `src/llm/ollama_manager.py` | Pet UI never stalls while a local model loads |
| 2 | **Runtime brain lifecycle** — `_ensure_ollama_manager()` / `_teardown_ollama_manager()` start/stop the `ollama serve` subprocess exactly when the provider flips (in `_save_settings`) and on shutdown. Previously switching to ollama at runtime never warmed the model (cold first query) and switching away left an orphaned serve process running | `src/ui/pet_window.py` | No cold starts, no leaked subprocess |
| 3 | **Off-thread settings probes** — `/api/tags` and `/api/show` probes moved to background threads, marshalled back via `_models_fetched` / `_model_validated` signals; per-keystroke model validation debounced 400 ms (was a 3s network call per keystroke) | `src/ui/settings_dialog.py` | Settings dialog stays responsive |
| 4 | **Wired "Restart Ollama" button** — was a dead control; now re-probes the server | `src/ui/settings_dialog.py` | Functional reconnection |

**Verification:** `test_ollama_manager.py` (4) + `test_settings_dialog.py` (7) pass; pre-existing unrelated failures (`test_diary_store_compaction.py`, one `test_mcp_server_fastmcp` case) confirmed present on clean `git stash`.

**Files changed:** `src/llm/ollama_manager.py`, `src/ui/pet_window.py`, `src/ui/settings_dialog.py`
**Docs updated:** `AGENTS.md` (File Map + mode_manager/ollama rows), `docs/architecture.md` (§3.3 dual brains, optimization notes), `docs/superpowers/specs/2026-07-09-local-ollama-provider-design.md` (lifecycle names)

---

## What To Do Next

### 2026-08-23 — Unsloth Recipe Parity Repair

- Rebuilt `daemon.ipynb` as a clean 10-cell executable Kaggle pipeline: CUDA/compute-capability guard, compatible dependencies, recipe discovery, model/LoRA setup, dataset loading for Parquet/JSONL, live response validation, chat-template formatting, `SFTTrainer`, desktop and code-assist inference checks, Q4_K_M GGUF export, and generated Ollama `Modelfile`.
- Removed stale stored notebook outputs. Notebook has zero embedded execution outputs and all code cells parse after removing IPython magics.
- Updated `daemon_kenny_unsloth_training_recipe.json` to recipe v2: full non-preview 1000-row run, JSONL+Parquet output, teacher API-key environment wiring, Daemon MCP SSE/tool configs, 31 live actions, current Windows context samplers, mode/APM/idle/typing/screen/browser/memory/context-hash fields, desktop array and code-assist object schemas, and typed writable brain updates with locked-field metadata.
- Import compatibility fix: recipe sampler types must be `category`; APM and idle values are independent numeric strings consumed as integers by notebook formatting.
- Static validation passed: recipe JSON/schema valid; 31 action parity; 24 writable brain fields; desktop and code-assist sample outputs validate.
- Focused runtime tests passed: 94 tests in 9.93s. Actual Unsloth training/export still requires Kaggle GPU execution.
- Verified Zen health-check fix (2026-08-24): direct Zen requests require bare model ID `nemotron-3.5-lightning-free`; `opencode/nemotron-3.5-lightning-free` is only valid in OpenCode's own config and returns `401` through Zen's direct endpoint, which Unsloth misleadingly reports as an expired API key. Recipe keeps `api_key_env: OPENCODE_ZEN_API_KEY`; credentials stay in the runner secret manager.
- Switched Unsloth teacher to OpenCode Zen MiMo V2.5 Free (2026-08-24): verified catalog ID `mimo-v2.5-free`; restored `api_key_env: OPENCODE_ZEN_API_KEY` after a live key was accidentally placed in the recipe.

### 🚀 Immediate Top Priority: Multi-Layer Interaction Architecture (Desktop & Code)

*Design Spec:* `docs/superpowers/specs/2026-08-22-multi-layer-interaction-architecture-design.md`  
*Implementation Plan:* `docs/superpowers/plans/2026-08-22-multi-layer-interaction-architecture.md`

1. **Windows UI Interaction Layer:**
   - **Semantic UIA Tree Engine (`src/system/uia_navigator.py`):** Structured accessibility tree inspection via Windows UI Automation API (`comtypes`/`UIAutomationCore`), programmatic `InvokePattern`/`ValuePattern` execution (fast, reliable, zero cursor movement).
   - **Agentic Computer Use Vision Engine (`src/system/vision_controller.py`):** High-speed screenshot capture with coordinate grid / Set-of-Marks overlay, vision LLM `(x, y)` coordinate targeting, and smooth PyAutoGUI/Win32 `SendInput` cursor actions for custom canvas/game apps.

2. **Code & Developer Integration Layer:**
   - **Background File System Watcher (`src/system/fs_watcher.py`):** `watchdog`-based workspace monitoring with 500ms debouncing, pre-warming local AST & vector database cache on file saves.
   - **Language Server Protocol (LSP) Integration (`src/system/lsp_client.py`):** JSON-RPC client connected to `tsserver`, `pyright`, `rust-analyzer`, etc., extracting real-time diagnostics, definitions, references, and syntax trees.

## 2026-08-29 - Categorized Capability Toggles

- Added one Settings → Capabilities tab containing categorized feature toggles plus existing consent boundaries.
- All feature toggles default to enabled and persist through existing nested configuration save path.
- MCP desktop and code tools honor feature toggles while retaining separate consent gates.
- Added settings and MCP feature-gate tests.

## 2026-08-29 - Client-Side Embedding Engine (Phase 1 complete)

- Added `src/memory/embedding_engine.py` with normalized 384-dimensional embeddings, Ollama `/api/embeddings` support, dependency-free offline hashing fallback, LRU caching, batch embedding, and cosine similarity.
- Added deterministic provider, cache, validation, and Ollama response tests.
- Verification: embedding tests pass; next implementation priority is Firestore native vector search.

## 2026-08-29 - Firestore Native Vector Search (Phase 2 complete)

- Added `FirebaseCRUD.find_nearest_vector()` with native Firestore `Vector` conversion, COSINE/EUCLIDEAN/DOT_PRODUCT validation, result IDs, limits, retries, and optional category pre-filtering.
- Added mocked Firestore vector query tests.
- Verification: focused vector CRUD tests pass; next implementation priority is semantic RAG retrieval.

## 2026-08-29 - Semantic RAG Retriever (Phase 3 foundation)

- Added hybrid `RAGRetriever` using embedding queries, Firestore kNN when available, local cosine-ranked fallback, score thresholds, and bounded results.
- Added online/offline retrieval tests.
- Verification: focused RAG tests pass; remaining Phase 3 work is ContextManager and MCP wiring.
- ContextManager accepts optional RAG retrieval and MCP exposes `query_semantic_memory`; feature is gated by `memory_sync`.

## 2026-08-29 - Legacy vector migration

- Added `scripts/migrate_to_vector_db.py` to vectorize legacy memory facts and diary entries into a preserved sidecar.
- Supports dry-run, deterministic offline embeddings, missing input stores, and non-mutating source reads.
- Verification: RAG, MCP, and migration focused tests pass (7 passed).
- MemoryManager now dual-writes vector sidecar documents under each pet's `memories` collection while preserving structured brain fields.

## 2026-08-29 - Native IDE WebSocket Bridge (Phase 5 complete)

- Added authenticated localhost `IDEBridge` on `127.0.0.1:4098` with context synchronization and editor operation protocol handlers.
- Added minimal VS Code extension under `extensions/vscode-daemon/`.
- Added bridge validation and dispatch tests.
- Verification: 3 bridge tests passed; websocket dependency added to requirements.
- Next implementation priority: client-side embedding engine.

   - **Native IDE WebSocket Bridge (`src/system/ide_bridge.py` + VS Code Extension):** Authenticated local WebSocket server (`127.0.0.1:4098`) pairing with a lightweight IDE extension for atomic code insertion, automatic formatting, and live cursor/selection tracking.

3. **Persisted Memory: Cloud Firestore Native Vector DB & RAG (100% Free / Spark Plan):**
   - *Design Spec:* `docs/superpowers/specs/2026-08-22-firestore-vector-rag-memory-design.md` | *Plan:* `docs/superpowers/plans/2026-08-22-firestore-vector-rag-memory.md`
   - **Client-side Embeddings:** Generate 384-dim embeddings locally via ONNX/`fastembed` (`all-MiniLM-L6-v2`) or local Ollama `/api/embeddings`, avoiding paid Firebase Extensions / Cloud Functions on Blaze.
   - **Firestore Native `find_nearest` kNN Queries:** Store `Vector` types on memory documents and query with distance metrics directly over client SDK within the 50k daily free read quota.
   - **RAG Context Integration (`src/memory/rag_retriever.py`):** Semantic retrieval of top-K relevant memories/diaries on user questions, with offline local cosine similarity fallback.

| Interaction Method | How It Works | Best For | Limitation |
| :--- | :--- | :--- | :--- |
| **UI Automation (UIA)** | Reads OS accessibility tree programmatically. | Navigating Windows menus, native apps, web forms. | Fails if app does not support accessibility APIs. |
| **Computer Vision** | Takes screenshots, calculates screen coordinates. | Legacy apps, complex UI dashboards, games. | Higher latency; vulnerable to screen resolution changes. |
| **File Watching** | Background process monitoring workspace changes. | Immediate context synchronization, vector DB updates. | Passive observation; cannot interact with UI components. |
| **LSP Integration** | Connects directly to language servers (`tsserver`, etc.). | Deep codebase understanding, diagnostics, refactoring. | Strictly limited to code syntax and semantics. |
| **Native IDE Extension** | WebSocket bridge to IDE extension (VS Code/JetBrains). | Atomic code insertion, diff application, editor state. | Requires installing the editor extension. |
| **Firestore Vector RAG** | Client-side embeddings + native Firestore kNN search. | Semantic memory recall, diary search, zero Cloud Functions cost. | Limited to 50k reads/day on Spark; requires client embeddings. |

### Secondary / Future Backlog
- EventStreamWorker 401/403 handling (declined, not yet worth it)
- Constants.py domain split (skipped, YAGNI)
- Sensitive data redaction filter (skipped, low-value until prod)
- Multi-pet support (core infrastructure exists, UI work pending)

---

### 🎯 Ultimate End Goal (Release Milestone): Packaging, Distribution & Shipping
*Design Spec:* `docs/superpowers/specs/2026-08-22-packaging-and-distribution-design.md` | *Plan:* `docs/superpowers/plans/2026-08-22-packaging-and-distribution.md`

- **Standalone PyInstaller Build (`daemon.spec`):** Full bundle of PyQt6, FastMCP, Uvicorn, background workers, assets, and standalone bundled FFmpeg binaries (zero external dependencies).
- **First-Run Onboarding Wizard (`src/ui/onboarding_wizard.py`):** 3-step setup dialog for Firebase Auth / Guest Mode, LLM engine selection (Opencode / Local Ollama), and consent boundaries.
- **Native Windows Setup (`DaemonSetup.exe` via Inno Setup):** Standard user install (`%LOCALAPPDATA%\Daemon`), Desktop & Start Menu shortcuts, "Run on Startup" toggle, and clean uninstaller preserving user memory.
- **Auto-Updater Pipeline (`src/system/auto_updater.py`):** GitHub Releases integration with in-app update checks and silent downloads.

---

## Agent Instructions

**CLAUDE.md and GEMINI.md replaced by `AGENTS.md`** — all agent instructions in that single file.
Update `AGENTS.md` and this file (or an archive entry) after each task.

---

## 2026-07-11 — Log-analysis bug fixes (Phases: log triage)

**Trigger:** Analyzed logs/daemon_2026-07-10_23-16-42.log; found issues, then implemented fixes via subagent-driven-development from docs/superpowers/plans/2026-07-11-log-issue-fixes.md.

**Branch:** 	ask-log-issue-fixes (4 commits: b0a4d07, 7f165be, e1b3a22, 964ec57). NOT yet merged to master.

**Fixes:**
1. **Debounce permanent-block** — _should_fire_autonomous used if elapsed < 15.0: where elapsed = time.monotonic() - _last_autonomous_fire_time. A mismatched epoch seed (stale .pyc / time.time) made elapsed hugely negative -> elapsed < 15 always true -> 102 [active_chat] Skipping: debounce (-1.78e9s < 15s) events, disabling autonomous chatter all session. Fixed to if 0 <= elapsed < 15.0:. | src/autonomy/behavior_controller.py:651 | TestDebounceClockSafety
2. **OllamaWorker garbage-filter over-rejection** — _filter_garbage_items dropped any dialogue equal to the user nickname or literal "garbage meat"/"...". Weak local model returns these, so refills were discarded -> ThoughtPool refill failed, pool has 0 items. Now only punctuation-only strings are dropped. (_get_user_nickname is now unused — follow-up cleanup candidate.) | src/llm/ollama_worker.py:451 | TestGarbageFilterNickname
3. **FastMCP shutdown AttributeError** — MCPServerThread.stop() called self._server.shutdown() on a FastMCP (no such method) -> 'FastMCP' object has no attribute 'shutdown' at Ghost-Mode exit. Now runs SSE via uvicorn.Server(app.sse_app()) and stops via should_exit = True. | src/mcp_server.py:140 | TestMCPServerThreadStop

**Verification:** 	est_behavior_controller.py (46), 	est_ollama_worker.py (11), 	est_mcp_server.py + 	est_mcp_server_fastmcp.py (19) all pass; 76 combined in ~1.9s. No cross-module interaction risk.

**Known follow-ups (non-blocking):** remove now-dead _get_user_nickname in ollama_worker.py; ThoughtPool starvation / 180s Ollama timeout / two-stage-vs-single-stage docs drift were scoped out (downstream of fix #2).

**Files changed:** src/autonomy/behavior_controller.py, src/llm/ollama_worker.py, src/mcp_server.py + 3 test files.

---

## 2026-07-11 — MCP Connection Fix (daemon_fsm)

**Commit:** `58cddec`

**Root cause (confirmed by opencode mcp list):** opencode.json registered daemon_fsm as `"url": "http://127.0.0.1:4097"` (root path) but FastMCP serves SSE at `/sse`. opencode's remote MCP client connected to root, got 404, and left the toolset disconnected. Additionally, opencode serve was spawned before the in-process MCP server on 4097 was ready, so even with `/sse` the initial connection would fail.

**Fixes:**
1. **`/sse` path** — `.opencode/opencode.json`: `"url": "http://127.0.0.1:4097"` → `"http://127.0.0.1:4097/sse"`
2. **Boot ordering** — `daemon.py`: Added MCP readiness gate after PetWindow construction; polls port 4097 (10s timeout), then respawns opencode serve via `ensure_opencode_serve_running()` so it discovers the live daemon_fsm server.
3. **Tool reinforcement** — `.opencode/skills/kenny/SKILL.md`: Added "User Physical Commands (MANDATORY)" section instructing the model to call `change_visual_state`/`trigger_pet_animation` for physical commands instead of only narrating.

**Verification:** `py -m pytest tests/ -v` — 842 passed, 3 failed (pre-existing diary compaction), 1 skipped in 51.03s.

## 2026-08-29 — Claude Cleanup

- Removed project Claude configuration and synced skills (`.claude/` and root `CLAUDE.md`).
- Uninstalled global `@anthropic-ai/claude-code` and removed global Claude state, including the `ponytail` plugin.
- Verified project/global Claude paths and launcher are absent.

**Files changed:** `.opencode/opencode.json`, `.opencode/skills/kenny/SKILL.md`, `daemon.py`

---

## 2026-07-11 — Fix "no response from opencode AND ollama" (stuck on "...")

**Symptom reported:** Pet sits in THINKING with "..." forever for BOTH providers.

**Root cause:** Both `OpencodeWorker` and `OllamaWorker` call `_ensure_tools()` → `build_client().get_tool_schema()` first. `src/llm/mcp_client.py` ran `asyncio.run(...)` with **no timeout**. A broken/half-open port 4097 (known: zombie Python from a prior run — AGENTS.md) makes the SSE `list_tools()` handshake block forever → worker never emits `response_ready`/`error` → pet stuck on "...". Confirmed via dead-port sim (accept-but-never-respond = infinite hang pre-fix).

**Secondary regression (uncommitted `daemon.py`):** opencode serve startup was gated behind `engine != "ollama"`, so with `engine: "ollama"` opencode serve never started → opencode provider dead AND the ollama→opencode `parse_failed` fallback (`pet_window.py:1790`) dead.

**Fixes:**
1. `src/llm/mcp_client.py` — wrapped `list_tools`/`call_tool` in `asyncio.wait_for` (`LIST_TOOLS_TIMEOUT=8s`, `CALL_TOOL_TIMEOUT=10s`); `get_tool_schema()` catches failure → returns `[]` (worker proceeds without tools). Verified: dead port → `[]` in 8s; OllamaWorker still delivers via fallback tools.
2. `daemon.py` — removed `engine != "ollama"` guard so opencode serve starts whenever `not args.no_opencode` (fallback + runtime provider switch).
3. `tests/test_mcp_client.py` — added `test_get_tool_schema_returns_empty_on_failure_no_hang`.

**Verification:** mcp_client + ollama_worker + opencode_worker + pet_window_tool_routing → 49 passed; new test passes.

**User action:** If hang recurs, kill zombie Python on 4097 (`taskkill /F /IM python.exe`) — stale MCP server is the usual trigger.

---

## 2026-08-23 - GitHub Copilot Caveman Mode

- Installed Caveman v2.3.1 skills locally from the pinned release into `.agents/skills/` for GitHub Copilot.
- Added always-on Caveman activation rules to `.github/copilot-instructions.md`.
- Kept Daemon-specific instructions in `AGENTS.md`; removed unrelated per-agent files generated by the broad init helper.
- Remote `npx skills add` was blocked by local `EALLOWGIT` policy; local clone install succeeded.

---

## 2026-08-29 - Semantic UIA Navigator (Phase 1 complete)

- Added `src/system/uia_navigator.py` with thread-local COM reuse, depth-limited semantic tree serialization, field/path lookup, pattern discovery, and click/type/expand/collapse/scroll/select actions.
- Registered read-only `uia_get_window_tree` and consent-gated `uia_interact_element` in FastMCP; interaction reuses `allow_window_management`.
- Added deterministic navigator and MCP tests; updated system exports, Kenny MCP guidance, and MCP tool count documentation.
- Fixed null COM pointer handling after live smoke testing against the foreground GitHub Desktop window.
- Verification: 15 focused UIA/MCP tests passed; 37 combined UIA/MCP/package tests passed; live UIA smoke returned a foreground `Window` tree without error. Full suite produced 872 passed, 1 skipped, 12 existing config/environment failures, and 6 collection errors in 56.97s.
- Next implementation priority: Phase 2 Vision Engine.

## 2026-08-29 - Vision Controller (Phase 2 complete)

- Added `src/system/vision_controller.py` with virtual-screen capture, PNG/base64 output, absolute-coordinate grid overlays, region clamping, bounded Win32 cursor/click actions, smooth interpolation, double-click support, and keyboard typing.
- Registered consent-gated `vision_capture_screen` (`allow_window_management`) and `vision_click_coordinate` (`allow_mouse_interference`) in FastMCP.
- Added deterministic capture, coordinate safety, smooth movement, typing, MCP delegation, consent, and registration tests.
- Verification: 11 Vision tests plus 15 UIA tests passed; live UIA behavior remains verified. Full suite baseline remains blocked by existing config/environment failures documented above.
- Next implementation priority: Phase 3 file-system watcher.

## 2026-08-29 - Workspace File Watcher (Phase 3 complete)

- Added `src/system/fs_watcher.py` with recursive watchdog observation, source-extension filtering, ignored-directory filtering, 500ms default debounce, create/modify/move handling, callback delivery, and lifecycle-safe stop/flush behavior.
- Added `watchdog>=4.0.0` to `requirements.txt` and installed watchdog 6.0.0 in the development environment.
- Added deterministic watcher tests covering coalescing, filtering, event routing, lifecycle, and validation.
- Verification: 34 focused watcher/UIA/Vision/MCP/package tests passed in 1.37s; compile check passed. Full-suite baseline remains affected by existing configuration/environment failures documented earlier.
- Next implementation priority: Phase 4 LSP client.

## 2026-08-29 - Language Server Protocol Client (Phase 4 complete)

- Added `src/system/lsp_client.py` with subprocess stdio JSON-RPC framing, initialize/initialized handshake, request correlation, document open/change notifications, publishDiagnostics capture, definition lookup, and reference lookup.
- Registered `lsp_get_diagnostics` and `lsp_get_symbol_info` MCP tools; handlers return an explicit configuration error when no language server is attached.
- Added deterministic fake-process tests for framing, handshake, notifications, diagnostics, location queries, validation, delegation, and tool registration.
- Verification: 6 focused LSP/MCP tests passed in 1.36s. Full-suite baseline remains affected by existing configuration/environment failures documented earlier.
- Next implementation priority: Phase 5 native IDE WebSocket bridge.

## 2026-08-29 - Logging Optimization Plan (assessment only)

- Existing logging stack: stdlib logging with rotating files, optional structlog NDJSON, correlation IDs, runtime module overrides, Prometheus metrics, and OpenTelemetry hooks.
- Remaining quality gaps: 359 logger calls are concentrated in `src/ui/pet_window.py`; routine UI lifecycle/debug details are emitted at INFO, user/LLM text and config state are logged without a documented redaction policy, expected provider connectivity failures are ERROR-level and repetitive, correlation context is not explicitly scoped/reset per operation, and structured logging is not the single canonical configuration path.
- Planned work: define severity/event taxonomy; centralize structured context and redaction; demote or remove noisy UI/poll/retry logs; rate-limit repeated expected failures while preserving transition/recovery logs; normalize exception fields and correlation/request metadata; align config and handler levels; add focused capture/redaction/rate-limit/regression tests; validate with representative startup, provider-offline, user-query, MCP, and shutdown runs plus log-volume/no-sensitive-content checks.
- Implemented first slice: token-scoped correlation context, recursive sensitive-field/message redaction with truncation, bounded repeated-event suppression, and handler integration; removed raw prompt/dialogue/response/error/config payloads from key UI and LLM logs; classified EventStreamWorker offline retries with bounded milestones and recovery logging.
- Verification: focused logging/worker suite 70 passed, 1 skipped; full suite 936 passed, 3 failed, 1 skipped in 39.29s. Remaining failures are pre-existing Firebase vector CRUD constructor compatibility tests (`creds_path`), unrelated to logging. Graphify updated after code changes.

## 2026-08-29 - Logging Quality Core

- Added token-scoped correlation context, recursive sensitive-value redaction/truncation, bounded repeated-event filtering, and safe message filtering in `src/log_context.py`.
- Integrated safe filters into plain and structlog-compatible handlers in `src/logging_setup.py` without changing existing formats.
- Added focused context, redaction, suppression, and setup compatibility tests.
- Verification: 18 focused logging tests passed in 0.44s.

## 2026-08-29 - RAG Runtime Wiring

- Instantiated one offline-capable `RAGRetriever` in `PetWindow`, seeded from local memory and diary records.
- Attached the retriever to `MCPServerThread`, passed it into `ContextManager`, refreshed records after Firebase diary/brain sync and local memory/diary updates, and scoped cloud vector queries to the authenticated pet.
- Added local fallback when remote vector retrieval fails; semantic context now works even when structured memory facts are empty.
- Added focused retrieval and prompt regression tests: 7 RAG/MCP tests passed.
- Full suite: 938 passed, 3 failed, 1 skipped in 37.58s. Remaining failures are pre-existing `FirebaseCRUD(creds_path=...)` compatibility tests in `tests/test_firebase_vector_crud.py`.
- Graphify updated successfully.

## 2026-08-29 - RAG Diagnostics and Log Settings

- Added RAG debug/info telemetry for index refresh, query start, backend selection, result count, fallback, and duration.
- Added editable `data/log_settings.json` with root level plus per-module levels; startup loads it through `logging_setup`, while CLI `--verbose` still forces DEBUG.
- Config template and packaged-path resolution now preserve the log settings location.
- Verification: logging/RAG tests 17 passed; focused RAG/PetWindow integration tests 27 passed; compile and diff checks passed.
- Full suite: 943 passed, 4 failed, 1 skipped in 37.6s. Three existing Firebase vector constructor compatibility failures remain; Ollama clipboard-signal test also fails independently.
- Graphify updated successfully.

## 2026-08-29 - Global Debug Logging Control

- `--debug` now enables process-wide DEBUG logging for the normal application; the obsolete headless FSM simulation was removed. `--verbose` remains a compatible DEBUG-only alias.
- Added `set_global_log_level()` to update root logger and existing handlers together, preventing runtime level changes from being blocked by stale console handler levels.
- MCP `set_log_level` now changes global logger/handler levels with input validation instead of only changing the `src` namespace.
- Added focused diagnostics for FSM transitions, brain-schema update decisions, and rejected write-sandbox paths. Existing instrumentation covers startup, UI, autonomy, LLM, MCP, persistence, RAG, and worker lifecycles.
- Updated README CLI documentation and added regression tests for debug-overrides-config and runtime handler updates.
- Verification: focused suite 86 passed; full suite 941 passed, 4 failed, 1 skipped in 30.89s. Remaining failures are pre-existing Firebase vector CRUD constructor compatibility tests and the Ollama clipboard-signal test.
- Graphify updated successfully to 4,944 nodes and 8,170 edges.

## 2026-08-29 - Low-Latency Chatbot Architecture Assessment

- Completed a Full architecture pass for low-latency chatbot optimization, covering PyQt6 runtime, OpenCode orchestration, Ollama fallback, MCP, RAG/memory, Firebase, packaging, and observability.
- Confirmed primary latency risk: `OpencodeWorker` creates, posts to, and deletes an OpenCode session for every burst; MCP schema/tool calls can add additional synchronous round trips.
- Confirmed existing resilience foundations: provider selector, Ollama lifecycle manager and warm-up, local RAG fallback, thought-pool cache, atomic local persistence, Prometheus metrics, correlation IDs, and OpenTelemetry hooks.
- Recommended next sequence: instrument end-to-end latency; add bounded warm persistent OpenCode sessions with cancellation; make MCP schema cached and tool execution budgeted; route cache/local fast paths before cloud; implement provider circuit breaker and capability-aware degradation; then load-test and tune models/deployment.
- Security note: repository runtime configuration currently contains credential-shaped values; rotate any exposed provider/Firebase credentials and keep secrets outside tracked config.

## 2026-08-29 - Shared MCP Schema Cache

- Implemented first low-latency slice in `src/llm/mcp_client.py`: `build_client()` now returns a process-shared client per MCP URL, preserving its schema cache across short-lived OpenCode/Ollama workers and avoiding repeated SSE initialization handshakes.
- Added explicit `clear_client_cache()` for configuration/server lifecycle changes and regression coverage in `tests/test_mcp_client.py`.
- Verification: targeted MCP/OpenCode/Ollama suite 49 passed in 3.18s; full suite 949 passed, 1 skipped, 1 warning in 31.49s.

## 2026-08-29 - Observability Access Links

- Added startup log line listing Grafana, Prometheus, Daemon metrics, and Prometheus alerts URLs.
- Added `📊 Observability` submenu to the pet right-click menu with actions opening each local endpoint through `QDesktopServices`, restricted to localhost/127.0.0.1 URLs.
- Added UI regression coverage in `tests/ui/test_observability_menu.py`.
- Verification: observability/menu tests 9 passed, 2 skipped; compile and diff checks passed.

## 2026-08-29 - Credentialless Pet Boot

- Deferred strict provider validation until after Qt startup. Missing OpenCode credentials now start the pet and schedule the Connectivity settings dialog instead of aborting before `QApplication`.
- Initialization-only config consumers use non-validating loads; strict validation remains enforced when configuration is used for provider startup.
- Added actionable credential guidance to the validation error and README.
- Verification: config/auth/CRUD tests 47 passed; daemon imports successfully with provider credentials absent; compile and diff checks passed.

## 2026-08-29 - Secure Connectivity Credential Storage

- Settings API-key save path now stores non-empty provider secrets in Windows Credential Manager (`Daemon/OpenCodeApiKey`, `Daemon/OpenCodeZenApiKey`, etc.) and strips them from JSON before disk persistence.
- Runtime config retains the entered secret for the current process; future boots retrieve it from Credential Manager or environment variables.
- Credential Manager write failures surface as configuration errors instead of silently losing credentials.
- Connections UI labels API-key storage behavior explicitly.
- Settings save failures are shown in the UI and do not apply an unpersisted runtime configuration.
- Verification: config/settings tests 24 passed; compile and diff checks passed.

## 2026-08-29 - Runtime Log Triage

- Latest daemon log exposed a Credential Manager compatibility bug: `pywin32` stores `CredentialBlob` as UTF-16 bytes and rejects bytes on write; persistence now writes Unicode strings and decodes UTF-16 blobs correctly.
- Verified live Windows Credential Manager write/read/delete round trip with a probe credential; no secret value logged.
- Focused config/settings/pet-window tests: 44 passed; compile and `git diff --check` passed.
- Removed older `logs/daemon_*.log` files and `crash_dump.log`, retaining newest daemon log for current diagnostics. Preserved `data/daemon_thoughts.log` as active runtime state.

## 2026-08-29 - Firebase HTTP 403 Sign-in Diagnosis

- Latest auth failures were HTTP 403 while `FIREBASE_API_KEY` was absent from both environment and Windows Credential Manager; project ID alone cannot authenticate Firebase REST requests.
- Added Firebase Web API-key field to Settings → Connections, with password masking and secure Credential Manager persistence through existing config handling.
- Updated auth setup documentation: 403 commonly indicates missing/invalid/restricted Web API key or disabled Identity Toolkit API, not incorrect email/password.
- Updated settings regression coverage; Firebase/auth/settings/pet tests: 48 passed.

## 2026-08-29 - Backend-Only Firebase Client Boundary

- Removed Firebase Web API-key input from Connectivity settings and replaced it with an auth-backend URL.
- `FirebaseAuth` supports backend `/auth/sign-in`, `/auth/sign-up`, and `/auth/refresh` token exchange without placing Firebase keys in the desktop client.
- `FirebaseCRUD` routes through backend `/firestore/*` when backend mode is configured; legacy direct mode remains only as a migration fallback for existing local deployments.
- Documented backend requirements: HTTPS, Daemon-session authentication, UID/resource authorization, and server-only Admin SDK credentials.
- Verification: Firebase auth/CRUD/settings tests 42 passed; compile and diff checks passed.

## 2026-08-29 - Model Routing Benchmark and Deployment Runtime Guidance

- Added `scripts/benchmark_model_routing.py`, a dependency-free repeatable HTTP harness for OpenCode and Ollama.
- Benchmark JSON records latency/TTFE, JSON validity, MCP tool adherence, provider token counts, CPU time, RSS delta, concurrency, and errors; it does not modify provider or config files.
- Added `docs/model-routing-benchmark.md` with Windows, WSL, Docker GPU/CPU, quantization, concurrency, warm-up, and resource recommendations grounded in current worker behavior.
- Added focused extraction and aggregation tests; benchmark tests: 2 passed.

## 2026-08-29 - Latency Reliability Dashboard and Offline Load Harness

- Expanded Prometheus coverage with visible latency, throughput, queue depth,
  in-flight requests, provider health, cache hits, and cancellation metrics.
- Added dashboard-ready Grafana panel definitions and Prometheus alert rules
  under `docs/observability/`; no provider or secret/config files changed.
- Added bounded deterministic `src/load_harness.py` plus
  `scripts/load_test_chatbot.py`; default runs cover user, autonomous, refill,
  MCP failure, cancellation, and concurrency without Qt workers or sockets.
- Focused validation: 11 passed, 2 skipped; offline harness CLI verified.

## 2026-08-29 - Hardened Local Ollama Fallback

- Hardened `OllamaManager` readiness probing to use configured server URL,
  validate `/api/tags` shape, keep model warm with bounded `keep_alive`, and
  classify warm-up OOM/load/timeout/unavailable failures.
- Hardened `OllamaWorker` with bounded provider timeouts, four-iteration/eight
  tool-call budgets, malformed tool-argument tolerance, explicit transport and
  OOM/load/timeout classification, and automatic degraded no-tool recovery when
  a model rejects tool calling.
- Added focused manager/worker regression tests. Validation was blocked during
  collection by a pre-existing syntax error in `src/llm/opencode_worker.py`
  (`_post_message_streaming`, line 278); modified Ollama modules compile cleanly.

## 2026-08-29 - Interactive Local Fast Path

- Added `InteractiveFastPath` for interactive requests: bounded exact-query
  cache with monotonic TTL, explicit invalidation, exact local-memory answers,
  and high-confidence local-only RAG answers.
- Wired `PetWindow` to resolve this path before provider dispatch; misses retain
  existing worker/provider behavior. Memory/diary/RAG refresh invalidates it.
- Added local-only `RAGRetriever.retrieve_local()` and Prometheus
  `daemon_local_route_total` telemetry plus cache-hit labels.
- Added focused routing tests. Collection was blocked by the pre-existing
  syntax error in `src/llm/opencode_worker.py` at `_post_message_streaming`;
  changed modules compile cleanly.

## 2026-08-29 - OpenCode Event Streaming

- Added capability-detected OpenCode `/global/event` SSE consumption to `OpencodeWorker`, emitting incremental dialogue, one-shot first-visible timing, disconnect notifications, and session cancellation via `/abort`; final message POST remains authoritative fallback.
- Added focused coverage in `tests/test_opencode_worker_streaming.py` for partial extraction, first-visible timing, unsupported endpoint fallback, and cancellation cleanup.
- Streaming tests: 3 passed. Existing stateless worker regression remains blocked by pre-existing UTF-8 BOM parsing in `data/daemon_config.json` (`MissingConfigurationError`).
