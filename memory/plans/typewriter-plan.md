# Typewriter Animation Implementation Plan

**Source:** `docs/plans/log-analysis-fixes.md` — Items 5 (P1) and 17 (P3)

## Problem

The speech bubble text appears all at once (no typewriter reveal), has a fixed 8s duration regardless of text length, and doesn't paginate long text. The config has `typewriter_tick_ms`/`typewriter_chars_per_tick`/`bubble_ms_per_char` keys but they're unused.

## Tasks

### Task 1: Config mappings (config.py)

Add missing flat↔nested mappings for 6 config keys:

| Flat key | Nested path | Value |
|----------|-------------|-------|
| `BUBBLE_MS_PER_CHAR` | `behavior.bubble_ms_per_char` | 50 |
| `BUBBLE_MIN_DURATION_MS` | `behavior.bubble_min_duration_ms` | 2000 |
| `BUBBLE_MAX_DURATION_MS` | `behavior.bubble_max_duration_ms` | 30000 |
| `DIALOGUE_MAX_LENGTH` | `behavior.dialogue_max_length` | 150 |
| `TYPEWRITER_TICK_MS` | `visuals.typewriter_tick_ms` | 30 |
| `TYPEWRITER_CHARS_PER_TICK` | `visuals.typewriter_chars_per_tick` | 8 |

**Files:** `src/config.py`

### Task 2: Constants (constants.py)

Add 6 new constants that `config.py` patches at runtime:
- `BUBBLE_MS_PER_CHAR = 50`
- `BUBBLE_MIN_DURATION_MS = 2000`
- `BUBBLE_MAX_DURATION_MS = 30000`
- `DIALOGUE_MAX_LENGTH = 150`
- `TYPEWRITER_TICK_MS = 30`
- `TYPEWRITER_CHARS_PER_TICK = 8`

These are defaults; `config.py`'s `flatten_config` → `setattr` overrides them.

**Files:** `src/constants.py`

### Task 3: Typewriter animation + pagination (pet_window.py)

**New instance attributes in `__init__`:**
- `_typewriter_timer = QTimer(self)` with timeout → `_tick_typewriter`
- `_typewriter_buffer = ""` — full text being typed out
- `_typewriter_pos = 0` — current reveal position
- `_typewriter_active = False` — flag
- `_typewriter_chars_per_tick` — from config
- `_typewriter_tick_ms` — from config
- `_bubble_pages = []` — paginated pages
- `_bubble_page_index = 0` — current page index

**New methods:**
- `_start_typewriter(text: str)` — stops timer, reset buffer/pos, sets timer interval, starts it
- `_tick_typewriter()` — reveals `_typewriter_chars_per_tick` chars into `_bubble_text`; when full page revealed, moves to next page or sets proportional timer
- `_paginate_text(text: str, max_chars: int = None) -> list[str]` — splits at sentence boundaries (`.`, `!`), falls back to word boundary, then hard cut at `max_chars`

**Modified methods:**
- `_bubble_duration(text: str) -> int` — `clamp(len(text) * BUBBLE_MS_PER_CHAR, BUBBLE_MIN_DURATION_MS, BUBBLE_MAX_DURATION_MS)`
- `_show_bubble(text: str)` — paginate text, start typewriter for first page; if single page, skip pagination
- `_clear_bubble_queue()` — stop typewriter timer, reset pagination state
- `_tick()` bubble section — after typewriter finishes a page, set timer to proportional duration - typewriter reveal time, move to next page when timer expires

**Imports to add:**
`BUBBLE_MS_PER_CHAR, BUBBLE_MIN_DURATION_MS, BUBBLE_MAX_DURATION_MS, BUBBLE_MAX_CHARS, TYPEWRITER_TICK_MS, TYPEWRITER_CHARS_PER_TICK` from `src.constants`

**Files:** `src/ui/pet_window.py`

## Verification

```bash
py -m pytest tests/test_bubble_behavior.py -v
```

Test classes:
- `TestPagination` — 5 tests
- `TestProportionalDuration` — 6 tests
- `TestConfigurableCharLimit` — 5 tests
- `TestContextPreservation` — 2 tests
- `TestLowLatencyPlaceholder` — 3 tests
- `TestTypewriterSpeed` — 1 test
