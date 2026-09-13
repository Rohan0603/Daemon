# Architecture Fixes Implementation Plan

**Date:** 2026-09-05
**Status:** Active
**Branch:** `task-architecture-fixes`

---

## Global Constraints

- **Test Gate**: All tests must pass (`py -m pytest tests/ -v`) and complete in < 50 seconds
- **No DEFAULT_CONFIG**: New config keys require `data/daemon_config.json` update or migration script
- **PetWindow in tests**: Use `safe_pet_window` fixture; manual init leaks timers/threads
- **Import Boundaries**: `ui → autonomy → {llm, system}` — no reverse imports
- **RAG System**: Already complete — do not modify embedding engine, retriever, or Firebase CRUD
- **God Object**: PetWindow decomposition in progress — BehaviorController extracted (Phase 52)

---

## Task 1: Fix 8 Test Failures (Schema Validation + Tier Merging Logic)

### Description
Fix 8 failing tests caused by the brain schema v2 migration (hierarchical tiers + `indexed` field requirement).

### Files to Modify
- `src/memory_manager.py` — `sync_to_local()` must merge all tiers, not just identity+profile
- `src/brain_schema.py` — ensure test schemas include `indexed` and `default` fields
- `tests/test_brain_load.py` — update assertion to match actual tier behavior
- `tests/test_brain_schema_dynamic.py` — fix test schema fixtures
- `tests/test_memory_manager_vectors.py` — ensure indexed fields are properly marked
- `tests/test_plugin_system.py` — fix plugin schema registration

### Acceptance Criteria
- All 970 tests pass
- Test suite completes in < 50 seconds
- `sync_to_local` correctly syncs all tier fields (identity, profile, personality, relationship, intel)

### Test Commands
```bash
py -m pytest tests/test_brain_load.py tests/test_brain_schema_dynamic.py tests/test_memory_manager_vectors.py tests/test_plugin_system.py -v
py -m pytest tests/ -v --ignore=tests/test_vector_migration.py
```

---

## Task 2: Complete PetWindow Decomposition (Phase 52+)

### Description
Continue extracting PetWindow monolith into focused components. BehaviorController already extracted.

### Files to Create/Modify
- `src/ui/pet_controller.py` — New: PetController (FSM + rendering + physics)
- `src/autonomy/autonomy_engine.py` — New: AutonomyEngine (behavior tree + timers)
- `src/llm/llm_interface.py` — New: LLMInterface (orchestrator + workers + context)
- `src/persistence_layer.py` — New: PersistenceLayer (memory + history + diary + write coalescer)
- `src/system/integration.py` — New: SystemIntegration (APM, typing, screen, TTS, click-through)
- `src/ui/pet_window.py` — Slim to ~500 lines, compose above components

### Acceptance Criteria
- PetWindow reduced to ~500 lines (from ~2,300)
- All components have single responsibility
- Import boundaries maintained
- All tests pass

### Test Commands
```bash
py -m pytest tests/test_pet_window.py tests/test_animator.py tests/test_fsm.py -v
py -m pytest tests/ -v --ignore=tests/test_vector_migration.py
```

---

## Task 3: Implement Packaging & Distribution Pipeline

### Description
Create turnkey packaging, installer, and distribution pipeline per spec.

### Files to Create/Modify
- `daemon.spec` — Update PyInstaller spec for all modular packages + deps
- `src/ui/onboarding_wizard.py` — 3-step setup (Firebase/Local, LLM Provider, Consent)
- `installer/daemon_setup.iss` — Inno Setup script
- `src/system/auto_updater.py` — GitHub Releases API checker
- `.github/workflows/build_release.yml` — CI/CD pipeline

### Acceptance Criteria
- Clean standalone executable build
- First-run onboarding wizard triggers on missing config
- Windows installer creates shortcuts + startup option
- Auto-updater checks GitHub Releases
- CI/CD builds on release tags

### Test Commands
```bash
py -m pytest tests/ -v --ignore=tests/test_vector_migration.py
# Manual: pyinstaller daemon.spec && test .exe on clean VM
```

---

## Task 4: Plugin Architecture + Multi-Pet + Voice Interaction (STT)

### Description
Implement strategic improvements for extensibility and new interaction modalities.

### Files to Create/Modify
- `src/plugin_manager.py` — Dynamic plugin loading via entry points
- `src/pet_manager.py` — Multi-pet spawning and management
- `src/system/stt_worker.py` — Whisper.cpp wake word + speech recognition
- `src/ui/pet_window.py` — Integrate plugin/pet-manager hooks

### Acceptance Criteria
- Plugins load dynamically without code changes
- Multiple PetWindow instances can run simultaneously
- Voice wake word triggers pet interaction
- All tests pass

### Test Commands
```bash
py -m pytest tests/ -v --ignore=tests/test_vector_migration.py
```

---

## Conflict Scan Results

| Task Pair | Shared Files/Interfaces | Finding |
|-----------|------------------------|---------|
| Task 1 ↔ Task 2 | `src/memory_manager.py`, `src/brain_schema.py` | Task 1 fixes memory_manager; Task 2 moves persistence to PersistenceLayer — Task 1 changes must be preserved in new layer |
| Task 2 ↔ Task 3 | `src/ui/pet_window.py`, `daemon.py` | Task 2 decomposes PetWindow; Task 3 needs updated daemon.spec — order: Task 2 before Task 3 |
| Task 2 ↔ Task 4 | `src/ui/pet_window.py`, `src/plugin_manager.py` | Task 2 creates plugin hooks; Task 4 implements plugin system — Task 2 provides integration points |
| Task 3 ↔ Task 4 | `installer/`, `src/system/` | Task 3 bundles assets; Task 4 adds STT deps — Task 3 spec must include new deps |

**Rulings:**
1. Task 1 changes to `memory_manager.py` will be refactored into `PersistenceLayer` in Task 2 — implement fix in current location, Task 2 preserves logic
2. Task 2 MUST complete before Task 3 (PetWindow decomposition affects PyInstaller spec)
3. Task 2 creates plugin integration points; Task 4 implements the plugin system
4. Task 3 spec updated to include STT dependencies from Task 4

---

## Spec References

- Multi-Layer Interaction Architecture: `docs/superpowers/specs/2026-08-22-multi-layer-interaction-architecture-design.md`
- Firestore Vector RAG: `docs/superpowers/specs/2026-08-22-firestore-vector-rag-memory-design.md`
- Packaging & Distribution: `docs/superpowers/specs/2026-08-22-packaging-and-distribution-design.md`
- Project Dev Memory: `memory/project-dev-memory.md`
- Agent Instructions: `AGENTS.md`