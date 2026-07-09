# Design Specification: AI Agent Guidelines Update (AGENTS.md)

## 1. Overview
This design outlines the updates to `AGENTS.md` to make the Daemon project more resilient and friendly for autonomous AI agents. The updates focus on managing context limits, enforcing strict verification before commits, guiding structural exploration, and providing clear recovery steps for common failures.

## 2. Dev Memory Archiving Strategy
**Goal:** Prevent `project-dev-memory.md` from exceeding agent context limits.
**Implementation:**
- Limit `memory/project-dev-memory.md` to active tasks, current blockers, and high-level architectural pointers. Target size: < 200 lines.
- Introduce an archive directory: `memory/archive/`.
- Agents will be instructed to migrate completed phases, resolved bugs, and outdated context into standalone archive files (e.g., `memory/archive/2026-07-09-phase-1-architecture.md`).
- `project-dev-memory.md` will contain an "Archive Index" linking to these historical files for reference.

## 3. Codebase Exploration via Graphify
**Goal:** Prevent hallucinations and inefficient file-by-file reading when understanding architecture.
**Implementation:**
- Add a new top-level section: **Codebase Exploration (Graphify)**.
- Enforce a strict rule: Agents MUST use `graphify` (when available in their toolset) to map dependencies, trace data flows, and understand module relationships before making cross-module changes.

## 4. Strict Pre-Commit Verification
**Goal:** Prevent broken builds, Qt event loop pollution, and unverified code from entering the repository.
**Implementation:**
- Update the **Git Workflow** section.
- Add mandatory steps before `git commit`:
  1. Run `py -m pytest tests/ -v`.
  2. Verify that total test execution remains under the 50-second threshold (indicating clean teardown of Qt components).
  3. Resolve all failures locally before committing. No blind or speculative commits allowed.

## 5. Agent Debugging & Fallbacks
**Goal:** Provide actionable recovery steps for common agent-induced errors.
**Implementation:**
- Add a new section: **Common Failures & Troubleshooting**.
- **Qt Threading/Timer Hangs:** Instruct agents to verify the use of `safe_pet_window` in tests and ensure manual `stop()` calls on all `QTimer` and `QThread` instances during teardown.
- **Port 4097 Binding Errors:** Instruct agents to look for zombie Python test processes holding the MCP port and kill them before retrying.
- **Circular Imports:** Reiterate the strict `ui → autonomy → {llm, system}` boundary and instruct agents to use `graphify` to analyze import chains if an `ImportError` occurs.
