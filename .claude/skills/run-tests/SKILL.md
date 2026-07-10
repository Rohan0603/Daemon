---
name: run-tests
description: Use when running, debugging, or verifying the Daemon pytest suite before a commit. Enforces the strict pre-commit gate (full suite green + under 50s) and the safe_pet_window / mock_background_workers fixtures that prevent Qt event-loop pollution and zombie timers.
version: 1.0.0
author: Daemon Project
license: MIT
metadata:
  hermes:
    tags: [testing, pytest, pre-commit, qt, daemon]
    related_skills: [git-workflow]
---

# Run the Daemon Test Suite

## Overview

Daemon is a PyQt6 desktop pet. Its tests spin up real `QTimer`s, `FastMCP`
servers, APM/TTS workers, and socket bindings (MCP server on `:4097`,
opencode serve on `:4096`). Done carelessly this pollutes the Qt event loop,
leaves zombie threads, and turns a 50s suite into 15s+ hangs per test.

There is a **mandatory pre-commit gate**: the full suite must be green AND
finish in **under 50 seconds**. This is enforced by `AGENTS.md` and is the
single most common way agents break the repo.

## When to Use

- Before any `git commit` (required — see git-workflow skill)
- After any change touching `src/ui/`, `src/autonomy/`, `src/llm/`,
  `src/system/`, or `src/mcp_server.py`
- When a test hangs, leaks timers, or the suite runtime exceeds 50s
- When writing a new test that needs a `PetWindow` or background workers

Do NOT use for: linting/type-checking only (no test runner needed), or
one-off scripts outside the suite.

## Commands (Windows — use `py`, never `python`/`python3`)

```bash
# Full suite (the pre-commit gate)
py -m pytest tests/ -v

# Confirm the <50s runtime budget is respected
py -m pytest tests/ -v   # watch the "finished in XX.XXs" line; must be < 50s

# Run a focused subset while iterating
py -m pytest tests/test_pet_renderer_ide.py -v

# Slow test that legitimately runs ~24s — give it headroom
py -m pytest tests/ -v --timeout=120

# Coverage check when modifying tests
py -m pytest --cov
```

## Hard Rules

1. **Never instantiate `PetWindow()` directly in a test.** It starts multiple
   `QTimer`s and background workers → "Timers cannot be stopped from another
   thread", socket bind errors, 15s+ teardown hangs. Use the `safe_pet_window`
   fixture from `conftest.py`.
2. **Use `mock_background_workers`** for any logic that lives outside the
   background threads, so real `FastMCP`/`APMWorker`/`TTSWorker` threads never
   start.
3. **Runtime must stay under 50s.** If it blows past, hunt the leak: an
   unstopped timer, an un-joined thread, or a socket left bound. Fix the
   cleanup, don't raise the budget.
4. **All failures resolved locally before commit.** No blind/speculative
   commits. Pre-existing known-failures (diary compaction, 3 tests) are out of
   scope — do not "fix" them as part of unrelated work.

## Common Pitfalls

1. Using `python`/`python3` instead of `py` → command not found on this
   Windows setup. Always `py`.
2. Building a `PetWindow` by hand "just to check one field" → event-loop
   pollution. Reach for `safe_pet_window`.
3. Leaving real background workers running because `mock_background_workers`
   wasn't applied → suite creep past 50s and port conflicts.
4. Committing with 1-2 red tests "that aren't related" → violates the gate.
   Fix or quarantine them properly first.
5. Raising `--timeout` to mask a hang instead of fixing the leaked resource.

## Verification Checklist

- [ ] `py -m pytest tests/ -v` exits green (modulo the known out-of-scope
      diary compaction failures)
- [ ] Reported "finished in" time is **under 50 seconds**
- [ ] No `QObject::~QObject: Timers cannot be stopped from another thread`
      warnings in output
- [ ] No port-already-in-use errors on `:4097` / `:4096`
- [ ] `safe_pet_window` / `mock_background_workers` used wherever a window or
      background worker was needed
