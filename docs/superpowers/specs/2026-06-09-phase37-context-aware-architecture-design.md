# Phase 37: Context-Aware Behavioral Architecture

**Date:** 2026-06-09
**Status:** Approved

## Overview

Transform Daemon from independent timer-based autonomous queries into a centralized **Master Tick Loop** with a **Dynamic Global Cooldown (GCD)**. This architecture makes Daemon context-aware: it respects deep work (Flow State), reacts instantly to typing (zero-latency local reactions), and manages API token efficiency through dynamic throttling.

## Core Mechanisms

### 1. Master Tick Loop & Chattiness Multiplier

Replaces three independent `QTimer` instances (`_active_chat_timer`, `_joke_timer`, `_boredom_timer_ms`) with a single, centralized 1-second tick.

- **Configurable interval:** `BEHAVIOR_TICK_MS = 1000` (default 1s)
- **Chattiness Parameter:** Global multiplier (default 1.0) that scales all base thresholds dynamically
- **Formula:** `Dynamic_Threshold = Base_Interval / Chattiness_Multiplier`
- **Range:** 0.5 (quiet) to 3.0 (hyperactive), default 1.0

### 2. Dynamic Global Cooldown (GCD) Lockdown

Prevents back-to-back API spam and ensures natural pacing. **Applies ONLY to speech actions** (any `_show_bubble` call). Silent FSM transitions (wander, shake, spin) bypass the GCD entirely.

- **Trigger:** Activated immediately after any FSM action/speech completes
- **Dynamic Scaling:** Base 8 seconds + 1 second per 30 characters spoken
- **Formula:** `GCD_Duration = 8.0 + (len(dialogue_text) / 30.0)`
- **Gatekeeper:** Rejects all autonomous queries while active, regardless of timer threshold status

### 3. Zero-Latency Typing Reactions

A new `"typing_reactions"` pool in `ResponseManager` provides instant local reactions while API calls run in the background. These are hardcoded Kenny-style 1-liners that fire the moment the TypingBuffer detects 10+ new characters.

- **Pool size:** 20 items (hardcoded, never refilled via API)
- **Threshold:** 0 (never triggers API refill)
- **Trigger:** `_on_typing_debounce()` when `new_chars >= 10`

### 4. Joke Interval Modifier (APM-Scaled)

Inverse APM scaling ensures jokes are frequent when the user is idle but rare when they're active.

| APM Range | Modifier | Effective Interval (at chattiness=1.0) |
|-----------|----------|----------------------------------------|
| < 10 | 0.5 | 30s (rapid fire) |
| 10-19 | 1.0 | 60s (normal) |
| 20-39 | 2.0 | 120s (rare) |
| 40+ | 3.0 | 180s (very rare) |

## Behavioral Decision Tree

Evaluated every tick in strict priority order:

| Priority | State | Condition | Daemon Action |
|----------|-------|-----------|---------------|
| **1** | **Flow State** | APM > 80 | **Silence.** Returns immediately. Respects deep work. |
| **2** | **Active Chat** | Chat timer >= threshold AND `_has_significant_delta()` | **Contextual React.** Instant zero-latency local bubble, followed by background API call. |
| **3** | **Joke** | Joke timer >= threshold AND APM < 20 | **Entertain.** Joke interval scales inversely with APM. |
| **4** | **Boredom** | Idle >= 60s AND APM == 0 | **Self-Play.** Operates strictly on local FSM (wandering, sighing). Only hits API every 3rd/4th boredom tick. |

## Settings Integration

- **UI:** QSlider in SettingsDialog (range 5-30, mapped to 0.5-3.0)
- **Persistence:** Written to `~/.daemon_config.json` as `"chattiness"` key
- **Default:** 1.0 (canonical pacing)

## Files to Modify

| File | Changes |
|------|---------|
| `src/constants.py` | Add `BEHAVIOR_TICK_MS`, `CHATTINESS_DEFAULT/MIN/MAX` |
| `src/pet_window.py` | Replace 3 timers with `_behavior_timer`; implement `_master_tick`, `_calculate_joke_modifier`, `_has_significant_delta`, `_trigger_chat`, `_trigger_joke`, `_trigger_boredom_fsm`; integrate GCD in `_dispatch_structured`; load/save chattiness |
| `src/response_manager.py` | Add `typing_reactions` pool; implement `_load_local_typing_reactions` |
| `src/settings_dialog.py` | Add chattiness slider (5-30 range) |
| `src/config.py` | Add chattiness to load/save |

## Data Flow

```
Master Tick (1s)
    |
    +---> GCD Check ---> [LOCKED] ---> return
    |
    +---> APM > 80 ---> [FLOW STATE] ---> return (SILENCE)
    |
    +---> Chat Timer >= Threshold + Delta ---> _trigger_chat()
    |       |
    |       +---> Local typing_reactions (instant)
    |       +---> OpencodeWorker (background)
    |
    +---> Joke Timer >= Threshold + APM < 20 ---> _trigger_joke()
    |       +---> OpencodeWorker (background)
    |
    +---> Idle >= 60s + APM == 0 ---> _trigger_boredom_fsm()
            |
            +---> Silent FSM transition (wander/shake/spin) -- NO GCD
            +---> Every 3rd/4th tick ---> OpencodeWorker (background)
```

## Testing Strategy

- `tests/test_master_tick.py` — Master tick logic with mocked timers
- `tests/test_gcd.py` — Dynamic GCD duration calculation
- `tests/test_chattiness_scaling.py` — Threshold math at 0.5, 1.0, 2.0, 3.0
- `tests/test_priority_tree.py` — Flow State > Chat > Joke > Boredom ordering
- `tests/test_typing_reactions.py` — Zero-latency pool draw
- `tests/test_joke_modifier.py` — APM-based interval scaling
- `tests/test_boredom_fsm.py` — Local FSM actions + API cadence
