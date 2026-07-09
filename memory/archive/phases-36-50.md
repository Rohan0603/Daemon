# Archived: Phases 36–50 (2026-06-08 to 2026-06-15)

**Original location:** `memory/project-dev-memory.md` (lines 754–1497)
**Archived:** 2026-07-09

## Overview

Agentic architecture, MCP bridge, emotion engine, consent matrix, Puppeteer tools, config consolidation, and the BehaviorController extraction.

## Phase Summary

| Phase | Date | What |
|-------|------|-------|
| 36 | 06-08 | Agentic Architecture: SKILL.md, JSON schema structured output, MCP FSM Bridge (FSMActionBridge + MCPServer on :4097) |
| 37 | 06-09 | Surveillance & Sabotage MCP tools: read_clipboard, capture_screenshot, system_toast |
| 38 | 06-09 | COM UIA caching, SLEEP state integration, exponential boredom backoff, read-only MCP tools (list_directory, read_file, search_codebase), write sandbox, AST codebase map |
| 39 | 06-11 | Multi-pet refactor: pet_id wiring, Firebase multi-pet paths, diary hash dedup, MCP memory tools, brain schema standardize |
| 39.5 | 06-11 | Two-stage agentic refill (investigation → generation) |
| 40 | 06-11 | The Sentinel: health monitoring, thought log UI, screen text delta |
| 42 | 06-11 | Stream of Consciousness: unified ThoughtPool (4 types, spatial TTL, Mixed-Bag schema) |
| 43 | 06-11 | Consent Matrix (7-tier permission gating for MCP tools) |
| 44 | 06-11 | Emotion Engine: ParticleSystem, 9 emotions, throw physics, window tracking |
| 44.5 | 06-11 | QA sweep: consent gate, animator constraint testing, SSE keepalive |
| 44.6 | 06-12 | Log audit bugfixes: zombie worker, click-through thrashing, FSM double-fire, stale idle seconds, Firebase docs |
| 45 | 06-11 | The Puppeteer: simulate_keystroke, move_mouse, browser_navigation MCP tools |
| 45.4 | 06-11 | Unified config migration (nested JSON, flat↔nested adapters) |
| 46 | 06-13 | EmotionProfile + Eye Modifier Architecture (11 emotion profiles, declarative registry) |
| 47 | 06-13 | SKILL.md complete rewrite (280+ lines, 15-point audit fix) |
| 48 | 06-14 | Consent matrix migration: 11→7 tools, tool rename, read-only always-allowed |
| 49 | 06-14 | Architecture review: 6 critical bug fixes, EventBus creation |
| 49.1 | 06-14 | Consent matrix refinement (naming alignment) |
| 50 | 06-15 | Config consolidation (python-dotenv, env var overrides, 5 new config sections) |
| 50.5 | 06-15 | Codebase cleanup (pycache, stale docs, gitignore) |

**Key architectural decisions from this era:**
- MCP tools use consent-gated dispatch via `_CONSENT_TOOL_MAP` (still current)
- EmotionAnimator is pure visual overlay — never writes X/Y (still current)
- Single `change_visual_state` MCP tool (not 11 separate) — still current
- Config nested JSON is single source of truth — still current
