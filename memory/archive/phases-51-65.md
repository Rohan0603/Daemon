# Archived: Phases 51–65 (2026-06-15 to 2026-06-23)

**Original location:** `memory/project-dev-memory.md` (lines 1497–2230+)
**Archived:** 2026-07-09

## Overview

High-priority bug fixes, production observability, BehaviorController extraction, performance optimization, persistent LLM sessions, plugin architecture, Strands SDK integration, test suite optimization.

## Phase Summary

| Phase | Date | What |
|-------|------|-------|
| 51 | 06-15 | Bug fixes: TTS temp leak, TypingBuffer spam, stale session reuse. Observability: atexit flush, JSON diagnostics, MCP /metrics |
| 52 | 06-15 | BehaviorController extraction (~495 lines, 40 tests) from PetWindow god object |
| 53 | 06-16 | Performance: particle compaction, ThoughtPool O(n), APM deque cap, EventBus emissions |
| 54 | 06-16 | API call reduction (~75%): pool 20→40, threshold 5→15, single-stage refill, 15s debounce |
| 55 | 06-16 | Remaining plans: mouth shapes (10 Navarasa), physics GroundContactResolver, prompt caching, diary dedup, UIA thread-local |
| 56 | 06-16 | Production logging: structlog, correlation IDs, lazy %s formatting, Prometheus metrics, set_log_level MCP tool |
| 57 | 06-20 | Plugin architecture: PluginRegistry, PluginManager, emotion_nostalgia sample plugin |
| 58 | 06-20 | Persistent LLM sessions (session save/load, history context injection on resume) |
| 59 | 06-20 | Boot config validation + strict config validation (no DEFAULT_CONFIG) |
| — | 06-20 | Test suite optimization: shared conftest.py, fixture consolidation, 200s→11s |
| 60 | 06-20 | Setup recovery UI + Connections tab in settings |
| 61 | 06-20 | Log analysis fixes: exponential prompt growth, FSM state conflict |
| 62 | 06-20 | Session summary isolation + refill optimization |
| 63.5 | 06-20 | Runtime audit: 11-fix patch (JSONL parsing, stale TTL, typed buffer idle, timer accumulation) |
| 64 | 06-20 | Screen time tracker, git diff tool, reminders, build.ps1 |
| 65 | 06-21 | Strands Agents SDK integration (replaced manual ReAct) |

**Key architectural decisions from this era:**
- `src/behavior_controller.py` extracted as pure-logic class (zero Qt imports) — still current
- Plugin architecture uses filesystem discovery (plugins/*.py) — extensible, no core code changes needed
- Persistent LLM sessions use atomic JSON save with 30-turn cap — still current
- Config validation is strict: no DEFAULT_CONFIG, file system is single source of truth — still current
