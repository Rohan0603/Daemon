# Global Project Progress Ledger

**Location**: `docs/PROGRESS_LEDGER.md` — used for all tasks in the project
**Purpose**: Track TODO item completion across all development work, surviving compaction and task re-dispatch
**Pattern**: Each todo item tracked with status, plan doc reference, and commit range

---

## Task Tracking Format

```markdown
### Task N: <task description>
- **Plan doc**: `<path-to-plan-file.md>`
- **Status**: `<complete|pending|cancelled>`
- **SDD ledger updated**: `<Yes|No>`
- **Tests**: `<passing/total> passing`
- **Commits**: `<sha-range>`
- **Rulings**: `<one-line ruling summary if any>`
- **Findings parked**: `<count>` (if any)
```

---

## Current Task Status

### Task 1: Fix 8 test failures (schema validation + tier merging logic)
- **Plan doc**: `docs/superpowers/plans/2026-09-05-architecture-fixes.md`
- **Status**: **complete**
- **SDD ledger updated**: Yes
- **Tests**: 29/29 passing (test_brain_load, test_brain_schema_dynamic, test_memory_manager_vectors, test_plugin_system)
- **Commits**: f1b9dc94756e34d9073bf13d271e210812474193
- **Rulings**:
  - Task 1 changes to memory_manager.py will be refactored into PersistenceLayer in Task 2
  - Task 2 MUST complete before Task 3 (PetWindow decomposition affects PyInstaller spec)
  - Task 2 creates plugin integration points; Task 4 implements the plugin system
  - Task 3 spec updated to include STT dependencies from Task 4

### Task 2: Complete PetWindow decomposition
- **Plan doc**: `docs/superpowers/plans/2026-09-05-architecture-fixes.md`
- **Status**: pending
- **Dependencies**: Task 1 (memory_manager fixes preserved in PersistenceLayer)
- **Target**: Reduce PetWindow from ~2300 lines to ~500 lines

### Task 3: Implement Packaging & Distribution pipeline
- **Plan doc**: `docs/superpowers/specs/2026-08-22-packaging-and-distribution-design.md`
- **Status**: pending
- **Dependencies**: Task 2 (PetWindow decomposition complete first)
- **Target**: PyInstaller build + Onboarding Wizard + Inno Setup installer + Auto-Updater CI/CD

### Task 4: Plugin Architecture + Multi-Pet + Voice Interaction
- **Plan doc**: `docs/superpowers/specs/2026-08-22-multi-layer-interaction-architecture-design.md`
- **Status**: pending
- **Dependencies**: Task 2 (provides plugin integration points in pet_window.py)
- **Target**: Dynamic plugin loading, multi-pet support, STT wake word

---

## Global Constraints (binding authority)

- **Test Gate**: All tests must pass (`py -m pytest tests/ -v`) and complete in < 50 seconds
- **No DEFAULT_CONFIG**: New config keys require `data/daemon_config.json` update or migration script
- **PetWindow in tests**: Use `safe_pet_window` fixture; manual init leaks timers/threads
- **Import Boundaries**: `ui → autonomy → {llm, system}` — no reverse imports
- **RAG System**: Already complete — do not modify embedding engine, retriever, or Firebase CRUD
- **God Object**: PetWindow decomposition in progress — BehaviorController extracted (Phase 52)

---

## Rulings Record

| Finding | Ruling | Why |
|---------|--------|-----|
| Task 1 memory_manager changes → PersistenceLayer | Preserve logic in current location, Task 2 refactors | Task 2 needs the sync_to_local logic for its PersistenceLayer |
| Task 2 before Task 3 | Task 2 completes first | PetWindow decomposition affects PyInstaller spec configuration |
| Plugin integration points | Task 2 creates; Task 4 implements | Task 2 defines hooks in pet_window.py; Task 4 builds plugin system |
| Task 3 spec STT deps | Include from Task 4 | Auto-updater and build pipeline need STT dependency knowledge |

---

## Usage

1. **Before starting any task**: Check `docs/PROGRESS_LEDGER.md` for current status
2. **After completing a task**: Update this ledger with:
   - Task status (complete/pending/cancelled)
   - Plan doc reference
   - Test results
   - Commit range (if applicable)
   - Any rulings made
3. **Before committing**: Verify no open Critical/Important findings
4. **Cross-session**: Trust the ledger and `git log` over recollection

---

**This file replaces per-plan SDD workspaces for global tracking.**
Per-plan directories at `.superpowers\sdd\` may still exist for individual plan artifacts,
but all TODO item tracking for the project goes through this global ledger.

**Update protocol**: Append new task sections above; never remove existing entries.
Record rulings immediately — they are the binding authority for dependent tasks.