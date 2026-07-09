# Archived: Phases 1–35 (2026-06-06 to 2026-06-08)

**Original location:** `memory/project-dev-memory.md` (lines 1–753)
**Archived:** 2026-07-09 — migrated to standalone archive to keep dev memory under 200 lines.

## Overview

Early foundation work for the Daemon desktop pet: window engine, opencode bridge, Firebase auth/memory, animation engine, screen reader, autonomous behavior, TTS, perimeter patrol, settings panel, storage hardening.

## Phase Summary

| Phase | Date | What |
|-------|------|------|
| 1 | 06-06 | Window engine: PetFSM (4→11 states), PetRenderer, ClickThroughManager, PetWindow, daemon.py |
| 2 | 06-06 | APMWorker, PetContextMenu, full FSM wiring |
| 3 | 06-06 | opencode Bridge: speech bubble, QLineEdit input, OpencodeWorker |
| 4 | 06-06 | Polish: persistence, system tray, hotkeys, onboarding, memory UX, pin |
| 5 | 06-06 | opencode Integration: rename from AGY, OpencodeWorker, CLI args, PS1 migration |
| 6 | 06-06 | Autonomous Behavior: AUTONOMOUS_THINKING FSM, active window, boredom timer, eye tracking |
| 7 | 06-06 | API-first pipeline (requests HTTP, PS1 fallback) |
| 8 | 06-06 | Active chatter timers (45s→15s), personality rewrite (Kenny Gatlian) |
| 9 | 06-06 | Action matrix expansion: SHAKE/BOUNCE/SPIN/LOOK_AWAY + dialog caching |
| 10 | 06-06 | Cloud memory persistence: MemoryManager, Firebase dual-brain |
| 11 | 06-06 | OpenRouter SDK Migration (openai SDK, meta-llama) |
| 12 | 06-06 | Council Stability Fixes: dialog cache, rate-limit, Firebase fail, shutdown |
| 13 | 06-06 | Verbose diagnostic logs |
| 14 | 06-06 | Configurable API key |
| 15 | 06-06 | Overridable OpenRouter model |
| 16 | 06-06 | Local-first diary, curiosity feature, prompt fix |
| 17 | 06-07 | opencode session persistence + parser robustness |
| 18 | 06-07 | Dialog cache fix + full skill loading + debug mode |
| 19 | 06-07 | OpenCode ADK API + DeepSeek V4 Flash + CLI failover |
| 20 | 06-07 | Memory & LLM Optimization: WriteCoalescer, TriggerCoalescer, ContextBuilder, Kenny/Kenny persona |
| 21 | 06-07 | Auto-start `opencode serve` |
| 22 | 06-07 | Linguistic butchery brain seeding |
| 23 | 06-07 | Engagement tracker + adaptive backoff |
| 24 | 06-07 | Multi-pool response cache + context enrichment (3-pool system) |
| 25 | 06-07 | TypingBuffer full keystroke capture |
| 26 | 06-07 | TTS with voice modulation (pyttsx3 + pydub pitch shift) |
| 27 | 06-07 | Landing squash/stretch animation |
| 28 | 06-07 | Perimeter patrol (8-way, counter-clockwise) |
| 29 | 06-07 | Settings panel (size/opacity/speed/voice) |
| 30 | 06-07 | TTS polish: stuttering + winsound fallback |
| 31 | 06-08 | Storage hardening + noReply context injection |
| 32 | 06-08 | Reusable Firebase CRUD layer |
| 33 | 06-08 | noReply bug fixes + E2E verification |
| 34 | 06-08 | Screen reading, APM priority, autonomous framing, storage relocation |
| 35 | 06-08 | Firebase Auth login + Firestore REST API + PyInstaller |
| 35b | 06-08 | Persona auth + dialogue expansion + hostile onboarding |

**Key architectural decisions from this era (now superseded or evolved):**
- 3-pool response system (jokes_blackmail + system + typing) → unified ThoughtPool in Phase 42
- `noReply` context injection → removed in Phase 36 (SKILL.md native)
- `assets/daemon-skill.md` → `.opencode/skills/kenny/SKILL.md` in Phase 36
- `simpleaudio` TTS → `edge_tts` primary in later phases
- `OpenRouter` API → direct opencode serve/AI gateway in later phases
