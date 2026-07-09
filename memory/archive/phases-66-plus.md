# Archived: Phases 66+ (2026-06-21 to 2026-07-09)

**Original location:** `memory/project-dev-memory.md` (lines 2231–3176)
**Archived:** 2026-07-09

## Overview

Strands fixes, MCP SSE broadcast, typewriter animation, stateless MCP pipeline, screen reader deep fixes, coding assistant mode, log audit fixes, and the agent guidelines update.

## Phase Summary

| Phase | Date | What |
|-------|------|-------|
| 66 | 06-21 | User input response immediate display fix (force=True, user_input history) |
| 67 | 06-21 | Strands integration crash fix (ContentBlock, MCP health ping, EventBus) |
| 68 | 06-21 | MCP server SSE broadcast support (active SSE handler registry) |
| 69 | 06-21 | Strands HookRegistry fix (add_listener → add_callback) |
| 70 | 06-21 | Strands OpenAIModel client_args fix (api_key/base_url in right place) |
| 71 | 06-21 | Strands direct API gateway routing (zen/v1 vs localhost:4096) |
| 72 | 06-21 | Strands AfterToolCallEvent metrics crash fix |
| 72b | 06-21 | API rate limit diagnosis (Cloudflare 429, cooldown wait) |
| 73 | 06-21 | Action Palette: ActionLayer, FSM migration (4 states removed), FSMActionBridge signal, renderer compositing, SKILL.md update |
| 74 | 06-21 | Dynamic brain schema (data/brain_schema.json), plugin brain field registration, storage backend ABC |
| 75 | 06-22 | Strands agent improvements: persistent sessions, tool stratification, streaming signals |
| 75b | 06-22 | Strands prompt integration + FSM migration cleanup |
| fix-5 | 06-22 | QRect/QPoint float TypeErrors in paintEvent |
| fix-6 | 06-22 | Robust JSON parsing in Strands worker |
| fix-7 | 06-22 | Log Audit Phase 1+2: 15 crash fixes + stability |
| — | 06-22 | Architecture review: 10 critical bugs (console flash, login Enter key, SSE drops) |
| — | 06-22 | Log Audit Phase 3: 16 fixes (brain_update dead code, EventStream circuit breaker, screen content detection) |
| — | 06-27 | Typewriter animation (paginated reveal, sentence-boundary splitting) |
| — | 06-27 | Log validation session: FSM oscillation fix, input field clamping, periodic Firestore sync, affinity progression |
| — | 06-28 | Strands dual-profile integration fixes (indentation, timer init order, missing constants) |
| — | 07-05 | Stateless MCP pipeline: FastMCP SSE, animation bridge, stateless burst executor, XML prompt builders, UIA pre-fetch cache, diary compaction |
| — | 07-06 | IDE Coding Assistant Mode: IDE detection, teal color, cursor blink, code_assist schema |
| — | 07-08 | Stateless Opencode + QThread error recovery (Strands removal, parts key fix, config migration) |
| — | 07-09 | Unit test optimization (safe_pet_window fixture, ~9min→30s) |
| — | 07-09 | Active Coding Assistant Mode + screen reader fixes |
| — | 07-09 | Log Audit Phase 70: FSM oscillation, timeout handling, shutdown fixes |

**Key fixed bugs from this era:**
- PERIMETER→CHASE oscillation (~2500 transitions/s) — state guard at pet_window.py:1108
- AUTONOMOUS_THINKING never entered — FSMContext hardcoded `autonomous_query_pending=False`
- Timeout misreported as parse_failed — added `_timed_out` flag in opencode_worker.py
- Incomplete ghost shutdown — full worker cleanup + QApplication.quit()
- QRect/QPoint float TypeErrors — explicit `int()` casts in renderer
- Strands metrics crash — AfterToolCallEvent attribute changes
