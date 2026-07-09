# Codebase Cleanup & Agent Config Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the root codebase, delete stale files and old plans, consolidate all agent instructions into `AGENTS.md` (with graphify), and ensure `CLAUDE.md` / `GEMINI.md` only forward to `AGENTS.md`.

**Architecture:** `AGENTS.md` is already the canonical single-agent config. Root-level `CLAUDE.md` and `GEMINI.md` contain only a graphify snippet — they need to be replaced by simple forwards to `AGENTS.md` and the graphify block must live only in `AGENTS.md`. Stale scratch files, logs, bak files, and old plans from `.hermes/plans/` that predate `docs/superpowers/plans/` are deleted. The `memory/` scratch JSON files (`thoughts_agents_md.json`, `thoughts_test_pytest_ini.json`) are also deleted.

**Tech Stack:** Git (PowerShell), plain text editing. No Python code changes.

---

## File Map

| Action | Path | Reason |
|--------|------|--------|
| Modify | `AGENTS.md` | Verify graphify section is complete and correct |
| Replace | `CLAUDE.md` | Replace graphify content → forward-only pointer to `AGENTS.md` |
| Replace | `GEMINI.md` | Replace graphify content → forward-only pointer to `AGENTS.md` |
| Delete | `crash_dump.log` | Generated runtime artifact, not source |
| Delete | `coverage.txt` | Generated CI artifact, not source |
| Delete | `fix_tests.py` | One-off scratch script, already executed |
| Delete | `scratch_perf.py` | One-off scratch script |
| Delete | `temp_thoughts.json` | Temporary data file |
| Delete | `.daemon_diary.json.bak` | Runtime backup; gitignored, should not be committed |
| Delete | `.daemon_history.json.bak` | Runtime backup; gitignored, should not be committed |
| Delete | `memory/thoughts_agents_md.json` | Scratch reasoning file, no longer needed |
| Delete | `memory/thoughts_test_pytest_ini.json` | Scratch reasoning file, no longer needed |
| Delete | `memory/plans/typewriter-plan.md` | Stale one-off plan, predates superpowers structure |
| Delete | `.hermes/plans/` (all 19 files) | Old Hermes-era plans superseded by `docs/superpowers/plans/` |
| Delete | `.worktrees/` (empty dir) | Empty directory, unused |
| Delete | `parameter=pathsrc/` (empty dir) | Malformed directory name from a bad CLI invocation |
| Delete | `docs/plans/log-analysis-fixes.md` | Stale plan outside superpowers structure |
| Keep | `.hermes/` skeleton | Hermes may still be used as an agent tool |
| Keep | `.claude/`, `.gemini/`, `.opencode/` | Agent tool config directories |
| Keep | `AGENTS.md` | Canonical agent instructions — do NOT delete |

---

## Task 1: Verify AGENTS.md graphify section is correct

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Read the graphify section in AGENTS.md**

  Open `AGENTS.md` and locate the `## graphify` section (currently at lines 785–797). Confirm it contains:
  - `graphify query "<question>"` instruction
  - `graphify path "<A>" "<B>"` instruction
  - `graphify explain "<concept>"` instruction
  - `graphify update .` after-code-change reminder
  - Note about `graphify-out/wiki/index.md` and `GRAPH_REPORT.md`
  - Note about `/graphify` slash command trigger

  The current content is already correct. No edits needed — just verify and proceed.

- [ ] **Step 2: No commit needed (read-only verification)**

---

## Task 2: Replace CLAUDE.md with a forward-only pointer

**Files:**
- Replace: `CLAUDE.md`

The current root `CLAUDE.md` (781 bytes) contains only a graphify snippet that is now fully covered by `AGENTS.md`. Replace it with a minimal forward pointer so Claude still picks up the right file.

- [ ] **Step 1: Write the new CLAUDE.md content**

  Overwrite `CLAUDE.md` with exactly:

  ```markdown
  # Daemon — Agent Instructions

  **Read `AGENTS.md` in this directory.** It is the single source of truth for this project's conventions, architecture, testing rules, and graphify usage.

  `CLAUDE.md` exists only as a discovery hook. All instructions live in `AGENTS.md`.
  ```

- [ ] **Step 2: Verify file written correctly**

  Run:
  ```powershell
  Get-Content CLAUDE.md
  ```
  Expected output: the 4-line content above, no graphify block.

- [ ] **Step 3: Commit**

  ```powershell
  git add CLAUDE.md
  git commit -m "docs: replace CLAUDE.md with forward pointer to AGENTS.md"
  ```

---

## Task 3: Replace GEMINI.md with a forward-only pointer

**Files:**
- Replace: `GEMINI.md`

The current root `GEMINI.md` (781 bytes) is byte-for-byte identical to `CLAUDE.md` — both contain just the graphify snippet. Replace it with a minimal forward pointer.

- [ ] **Step 1: Write the new GEMINI.md content**

  Overwrite `GEMINI.md` with exactly:

  ```markdown
  # Daemon — Agent Instructions

  **Read `AGENTS.md` in this directory.** It is the single source of truth for this project's conventions, architecture, testing rules, and graphify usage.

  `GEMINI.md` exists only as a discovery hook. All instructions live in `AGENTS.md`.
  ```

- [ ] **Step 2: Verify file written correctly**

  Run:
  ```powershell
  Get-Content GEMINI.md
  ```
  Expected output: the 4-line content above.

- [ ] **Step 3: Commit**

  ```powershell
  git add GEMINI.md
  git commit -m "docs: replace GEMINI.md with forward pointer to AGENTS.md"
  ```

---

## Task 4: Delete root-level stale generated/scratch files

**Files:**
- Delete: `crash_dump.log`, `coverage.txt`, `fix_tests.py`, `scratch_perf.py`, `temp_thoughts.json`, `.daemon_diary.json.bak`, `.daemon_history.json.bak`

- [ ] **Step 1: Confirm files exist**

  ```powershell
  Get-Item crash_dump.log, coverage.txt, fix_tests.py, scratch_perf.py, temp_thoughts.json, .daemon_diary.json.bak, .daemon_history.json.bak | Select-Object Name, Length
  ```
  Expected: all 7 files listed with sizes.

- [ ] **Step 2: Check .gitignore to confirm .bak files are ignored**

  ```powershell
  Select-String -Path .gitignore -Pattern "\.bak"
  ```
  Expected: a line like `*.bak` is present. If not, add `*.bak` to `.gitignore` before deleting.

- [ ] **Step 3: Delete the files**

  ```powershell
  Remove-Item crash_dump.log, coverage.txt, fix_tests.py, scratch_perf.py, temp_thoughts.json, .daemon_diary.json.bak, .daemon_history.json.bak -ErrorAction SilentlyContinue
  ```

- [ ] **Step 4: Stage and commit only the tracked files**

  ```powershell
  git status --short
  ```
  The `.bak` files should NOT appear in git status (they're gitignored). The others should show as `D` (deleted).

  ```powershell
  git add -u crash_dump.log coverage.txt fix_tests.py scratch_perf.py temp_thoughts.json
  git commit -m "chore: remove stale scratch scripts, logs, and temp files"
  ```

---

## Task 5: Delete stale memory scratch JSON files

**Files:**
- Delete: `memory/thoughts_agents_md.json`, `memory/thoughts_test_pytest_ini.json`

These are reasoning scratch outputs from prior agent sessions, not runtime data.

- [ ] **Step 1: Preview contents to confirm they're scratch**

  ```powershell
  Get-Content memory/thoughts_agents_md.json | Select-Object -First 5
  Get-Content memory/thoughts_test_pytest_ini.json | Select-Object -First 5
  ```
  Expected: JSON arrays of agent reasoning notes, not real application data.

- [ ] **Step 2: Delete files**

  ```powershell
  Remove-Item memory/thoughts_agents_md.json, memory/thoughts_test_pytest_ini.json
  ```

- [ ] **Step 3: Commit**

  ```powershell
  git add -u memory/thoughts_agents_md.json memory/thoughts_test_pytest_ini.json
  git commit -m "chore: remove stale agent reasoning scratch files from memory/"
  ```

---

## Task 6: Delete stale memory/plans and docs/plans files

**Files:**
- Delete: `memory/plans/typewriter-plan.md`
- Delete: `docs/plans/log-analysis-fixes.md`

These are one-off plans outside the canonical `docs/superpowers/plans/` location.

- [ ] **Step 1: Preview to confirm they're old/stale**

  ```powershell
  Get-Content memory/plans/typewriter-plan.md | Select-Object -First 3
  Get-Content docs/plans/log-analysis-fixes.md | Select-Object -First 3
  ```

- [ ] **Step 2: Delete files**

  ```powershell
  Remove-Item memory/plans/typewriter-plan.md
  Remove-Item docs/plans/log-analysis-fixes.md
  ```

- [ ] **Step 3: Remove empty dirs if left empty**

  ```powershell
  if ((Get-ChildItem memory/plans).Count -eq 0) { Remove-Item memory/plans }
  if ((Get-ChildItem docs/plans).Count -eq 0) { Remove-Item docs/plans }
  ```

- [ ] **Step 4: Commit**

  ```powershell
  git add -u memory/plans/typewriter-plan.md docs/plans/log-analysis-fixes.md
  git commit -m "chore: remove stale plans outside canonical docs/superpowers/plans/"
  ```

---

## Task 7: Delete all old Hermes-era plans

**Files:**
- Delete: all 19 files in `.hermes/plans/`

These plans predate the `docs/superpowers/plans/` workflow and are all completed work. The `.hermes/` directory skeleton is kept.

Files to delete:
```
.hermes/plans/2025-08-27_1530-Future-TODOs-Plan.md
.hermes/plans/2026-06-15_120000-config-consolidation.md
.hermes/plans/2026-06-15_154500-high-priority-bugs.md
.hermes/plans/2026-06-15_161500-reduce-api-calls.md
.hermes/plans/2026-06-15_210000-codebase-cleanup.md
.hermes/plans/2026-06-15_235959-mouth-shapes.md
.hermes/plans/2026-06-15_235959-phase52-petcontroller-extraction.md
.hermes/plans/2026-06-16_000500-api-call-reduction.md
.hermes/plans/2026-06-16_121500-production-logging.md
.hermes/plans/2026-06-16_220000-opencode-zen.md
.hermes/plans/2026-06-16_233000-kenny-persona-enhancement-plan.md
.hermes/plans/2026-06-20_182000-phase63-fix-bugs.md
.hermes/plans/2026-06-21_test_optimization_plan.md
.hermes/plans/2026-06-28_003059-daemon-replatforming-plan.md
.hermes/plans/2026-06-28_203841-batch-4-resource-leaks-logic-fixes.md
.hermes/plans/2026-06-28_203841-batch-5-performance-network-optimizations.md
.hermes/plans/2026-06-28_222109-batch-6-strategic-enhancements.md
.hermes/plans/2026-06-28_222207-task-6-1-local-llm-fallback.md
.hermes/plans/2026-06-28_223044-task-6-2-yaml-rules-engine.md
```

- [ ] **Step 1: Confirm count**

  ```powershell
  (Get-ChildItem .hermes/plans/).Count
  ```
  Expected: `19`

- [ ] **Step 2: Delete all plan files in .hermes/plans/**

  ```powershell
  Remove-Item .hermes/plans/* -Force
  ```

- [ ] **Step 3: Verify plans dir is now empty**

  ```powershell
  Get-ChildItem .hermes/plans/
  ```
  Expected: no output (empty directory).

- [ ] **Step 4: Commit**

  ```powershell
  git add -u ".hermes/plans/"
  git commit -m "chore: remove completed Hermes-era plans (superseded by docs/superpowers/plans/)"
  ```

---

## Task 8: Remove empty and malformed directories

**Files:**
- Delete: `.worktrees/` (empty dir)
- Delete: `parameter=pathsrc/` (malformed dir from a bad CLI invocation)

- [ ] **Step 1: Confirm both are empty**

  ```powershell
  Get-ChildItem .worktrees/ -Force
  Get-ChildItem "parameter=pathsrc/" -Force
  ```
  Expected: no output for both.

- [ ] **Step 2: Delete directories**

  ```powershell
  Remove-Item .worktrees/ -Force -Recurse
  Remove-Item "parameter=pathsrc/" -Force -Recurse
  ```

- [ ] **Step 3: Commit**

  ```powershell
  git add -A
  git commit -m "chore: remove empty and malformed directories"
  ```

---

## Task 9: Update .gitignore to prevent future clutter

**Files:**
- Modify: `.gitignore`

Ensure the following patterns are present so these files never get committed again:

- [ ] **Step 1: Check current .gitignore**

  ```powershell
  Get-Content .gitignore
  ```

- [ ] **Step 2: Add missing patterns if not present**

  Open `.gitignore` and append at the bottom any of these that are missing:
  ```gitignore
  # Runtime generated files
  crash_dump.log
  coverage.txt
  temp_*.json
  scratch_*.py
  fix_*.py
  *.bak
  ```

- [ ] **Step 3: Verify no false positives**

  ```powershell
  git status --short
  ```
  Confirm no previously-tracked important files are newly ignored.

- [ ] **Step 4: Commit if changes were made**

  ```powershell
  git add .gitignore
  git commit -m "chore: add gitignore rules for crash logs, coverage, temp and scratch files"
  ```

---

## Task 10: Final verification

- [ ] **Step 1: Run tests to confirm nothing broke**

  ```powershell
  py -m pytest tests/ -v --tb=short -q
  ```
  Expected: 760 passed, 1 skipped. Any failure here is a pre-existing issue, not caused by this cleanup.

- [ ] **Step 2: Check root directory is clean**

  ```powershell
  Get-ChildItem -Path . | Sort-Object Name | Select-Object Name, @{N='Type';E={if($_.PSIsContainer){'dir'}else{'file'}}}
  ```

  **Should NOT be present:** `crash_dump.log`, `coverage.txt`, `fix_tests.py`, `scratch_perf.py`, `temp_thoughts.json`, `.worktrees/`, `parameter=pathsrc/`

- [ ] **Step 3: Verify graphify update runs cleanly**

  ```powershell
  graphify update .
  ```
  Expected: completes without error (AST-only, no API calls).

- [ ] **Step 4: Update project-dev-memory.md**

  Open `memory/project-dev-memory.md` and prepend a new entry at the very top of the completed tasks log:

  ```markdown
  ## 2026-07-09 — Codebase Cleanup & Agent Config Consolidation

  - CLAUDE.md and GEMINI.md replaced with forward pointers to AGENTS.md
  - Graphify rules consolidated into AGENTS.md (section already present, verified correct)
  - Deleted: crash_dump.log, coverage.txt, fix_tests.py, scratch_perf.py, temp_thoughts.json
  - Deleted: memory/thoughts_agents_md.json, memory/thoughts_test_pytest_ini.json
  - Deleted: memory/plans/typewriter-plan.md, docs/plans/log-analysis-fixes.md
  - Deleted: all 19 .hermes/plans/ files (Hermes-era plans, all completed)
  - Deleted: .worktrees/ (empty), parameter=pathsrc/ (malformed dir)
  - .gitignore updated with crash/temp/scratch patterns
  - graphify update . runs cleanly
  ```

- [ ] **Step 5: Final commit**

  ```powershell
  git add memory/project-dev-memory.md
  git commit -m "docs: update project-dev-memory with codebase cleanup task"
  ```
