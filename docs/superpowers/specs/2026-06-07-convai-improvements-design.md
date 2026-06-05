# Daemon — Convai-Inspired Improvements Design

**Date:** 2026-06-07
**Source:** Cross-reference with [Convai Desktop Pet](https://github.com/AkshitIreddy/convai-desktop-pet)
**Builds on:** Phase 25 (TypingBuffer), master commit `70681af`

---

## Overview

4 incremental phases improving the pet's audiovisual expressiveness, movement variety, and user customization. All phases are independent — each can be merged and shipped standalone.

---

## Phase 26 — TTS with Voice Modulation

### Summary
Daemon speaks its speech bubble text aloud with personality-matched voice modulation. Uses `pyttsx3` for fast offline TTS generation, `pydub` for real-time pitch-shift and speed manipulation ("Morty Filter"), and `simpleaudio` for non-blocking playback. This captures the frantic, stressed-out character energy without API keys, latency, or GPU load.

### New File: `src/tts_worker.py`

`TTSWorker(QThread)` — threaded speech queue with audio manipulation:

```
TTSWorker(QThread)
├── _queue: list[str]              # pending speech snippets
├── _speaking: bool                 # currently vocalising
├── _shutdown: bool                 # graceful stop flag
├── _enabled: bool                  # runtime toggle
├── _voice_id: str                  # cached male voice ID
│
├── enqueue(text: str)              # append to queue, wake worker
├── set_enabled(state: bool)        # toggle without destroying
├── _generate(text) → bytes        # pyttsx3 → wav bytes → pydub manipulation → wav bytes
├── run()                           # loop: pop queue → generate → play → emit done
├── stop()                          # set shutdown, wait()
│
└── signals:
    ├── speaking_started()
    └── speaking_finished()
```

### Audio Pipeline (`_generate`)

```
text → pyttsx3 engine (rate=200, male voice) → temp WAV → pydub AudioSegment
  → pitch shift: +0.5 octave (via sample-rate override → set_frame_rate(44100))
  → speed up: 1.2x playback tempo
  → export WAV bytes → return raw PCM data
```

Playback via `simpleaudio.play_buffer()` — non-blocking, so the thread can process the next queue item.

### Changes to Existing Files

**`src/pet_window.py`:**
- `__init__`: instantiate `TTSWorker`, call `start()`
- `_on_output_displayed(text)`: call `self._tts.enqueue(stripped_text)` (don't await)
- Shutdown path: call `_tts.stop()` before `QApplication.quit()`

**`src/constants.py`:**
```python
TTS_ENABLED: bool = True       # default on, overridable via config
TTS_BASE_RATE: int = 200       # pyttsx3 words-per-minute
TTS_PITCH_OCTAVES: float = 0.5 # pitch shift amount
TTS_SPEEDUP: float = 1.2       # playback speed multiplier
```

### Dependencies
```powershell
pip install pyttsx3 pydub simpleaudio
```
System requirement: `ffmpeg` on PATH (required by `pydub` for format conversions; install via `winget install ffmpeg` or Chocolatey).

### Tests
`tests/test_tts_worker.py` — mock `pyttsx3`, `pydub`, `simpleaudio`, verify:
- Enqueue adds to queue, processes in order
- pyttsx3 called with correct text, rate, voice
- pydub pitch shift + speedup applied
- simpleaudio.play_buffer called with final bytes
- `speaking_started`/`speaking_finished` signals emit
- `stop()` terminates cleanly
- `set_enabled(False)` makes enqueue a no-op
- Empty text skipped

---

## Phase 27 — Landing Squash/Stretch Animation

### Summary
When the pet lands from FALLING, play a 400ms cartoony squash→stretch→settle sequence. No new FSM states.

### RenderContext Addition
Add to the dataclass in `src/pet_renderer.py`:
```python
land_elapsed_ms: float = 0.0   # ms since last ground contact; 0.0 = no anim
```

### PetWindow Changes
In the FSM tick handler, when transitioning from FALLING → IDLE:
- Record `self._land_time = time.time()`
- On each `paintEvent` tick, compute `ms_since_land`:
  ```python
  ms = (time.time() - self._land_time) * 1000
  if ms > SQUASH_STRETCH_DURATION_MS:
      ms = 0.0   # done
  ctx.land_elapsed_ms = ms
  ```

### PetRenderer Transform
Applied via `QPainter.scale(sx, sy)` centered at bottom-center of the pet body (ground-contact point):

| Phase | Range (ms) | scaleX | scaleY | Visual |
|-------|-----------|--------|--------|--------|
| Squash | 0–120 | 1.25→1.3 | 0.85→0.7 | Compress down, widen |
| Stretch | 120–240 | 1.3→0.75 | 0.7→1.25 | Overshoot upward |
| Settle | 240–400 | 0.75→1.0 | 1.25→1.0 | Ease to identity |

Interpolation: linear within each phase.

### Constants
```python
SQUASH_STRETCH_DURATION_MS: int = 400
```

### Tests
`tests/test_pet_renderer.py`:
- `land_elapsed_ms=0` → no transform
- `land_elapsed_ms=60` → squash phase (scaleX > 1.0, scaleY < 1.0)
- `land_elapsed_ms=180` → stretch phase (scaleY > 1.0)
- `land_elapsed_ms=300` → settle phase (approaching 1.0)
- `land_elapsed_ms=500` → no transform (past duration)

---

## Phase 28 — Edge Climbing (Perimeter Patrol)

### Summary
Rename WANDER to PERIMETER. Pet patrols all 4 screen edges counter-clockwise. Random midpoint falls add emergent variety.

### FSM Changes

**`src/pet_fsm.py`:**
- Rename `WANDER` → `PERIMETER` (priority stays 9)
- `FSMContext` gains: `edge: str = "bottom"`, `facing: str = "right"`

### Tick Logic (`_tick_perimeter`)

```
PetWindow._tick_perimeter():
  advance position along edge at PERIMETER_SPEED px/s
  if at corner:
      switch to next edge (counter-clockwise: bottom→left→top→right→bottom)
  if on vertical edge and at midpoint (40-60% of edge):
      20% chance → transition to FALLING
  if on bottom edge and idle timer > SLEEP_TIMEOUT:
      transition to IDLE → SLEEP cascade
```

### Renderer Rotations

All transforms centered at pet body origin:

| Edge | Facing | QTransform |
|------|--------|------------|
| bottom | right | Identity |
| bottom | left | `scale(-1, 1)` |
| left | up | `rotate(-90)` |
| left | down | `rotate(90)` |
| right | up | `rotate(90)` |
| right | down | `rotate(-90)` |
| top | right | `rotate(180)` |
| top | left | `rotate(180) scale(-1, 1)` |

Eye pupil tracking uses screen-space `atan2` (already built in Phase 6.5) — continues working across rotations with the same ~15° max mismatch tradeoff.

### Coordinate Reference

**Screen edges:**
- Bottom: `y = available_geometry.bottom()` (taskbar-aware)
- Top: `y = 0`
- Left: `x = 0`
- Right: `x = available_geometry.right()`

**Corner thresholds:** half the pet body width/height ± `EDGE_TOLERANCE_PX`.

### Constants
```python
PERIMETER_FALL_CHANCE: float = 0.2
EDGE_TOLERANCE_PX: int = 5
PERIMETER_SPEED: int = <reuses WANDER_SPEED from constants>
```

### Tests
`tests/test_fsm.py`:
- PERIMETER state exists with priority 9
- Edge/facing fields in FSMContext
- Corner detection triggers edge change
- Midpoint random triggers FALLING transition

`tests/test_pet_renderer.py`:
- Each of 8 edge/facing combos produces correct painter transform
- Eye tracking still functional after rotation

---

## Phase 29 — Settings Panel

### Summary
`QDialog` with sliders for size, opacity, speed + voice toggle. Opened from system tray menu. Live previews changes, persisted to `~/.daemon_config.json`.

### New File: `src/settings_dialog.py`

```
SettingsDialog(QDialog)
├── _size_slider     QSlider(Qt.Horizontal, 50→200)
├── _opacity_slider  QSlider(Qt.Horizontal, 30→100)
├── _speed_slider    QSlider(Qt.Horizontal, 50→200)
├── _voice_checkbox  QCheckBox("Enable voice responses")
│
├── load_from_config(dict)       # populate from ~/.daemon_config.json
├── get_values() → dict          # current slider/checkbox values
│
└── signals:
    ├── value_changed()           # any slider moved
    └── accepted()                # OK clicked — parent persists
```

Layout: vertical `QVBoxLayout`, each row is `QLabel + QSlider + QLabel(value)`. Voice checkbox at bottom. OK/Cancel `QDialogButtonBox`.

### Changes to Existing Files

**`src/pet_window.py`:**
- Connect `value_changed` → instant live update:
  - `setFixedSize(base_size * scale)`
  - `setWindowOpacity(opacity)`
  - Store speed multiplier on `self._speed_multiplier` (read by FSM tick)
- Wire voice checkbox → `self._tts.set_enabled(state)`
- On `accepted` → call `save_config()` (existing `config.py`)
- Add "Settings..." `QAction` to tray menu, connected to `_open_settings()`

**`src/config.py` — new overridable keys:**
```json
{
    "pet_scale": 1.0,
    "pet_opacity": 0.85,
    "pet_speed": 1.0,
    "tts_enabled": true
}
```

### Constants
```python
SETTINGS_SCALE_MIN: float = 0.5
SETTINGS_SCALE_MAX: float = 2.0
SETTINGS_OPACITY_MIN: float = 0.3
SETTINGS_OPACITY_MAX: float = 1.0
SETTINGS_SPEED_MIN: float = 0.5
SETTINGS_SPEED_MAX: float = 2.0
```

### Tests
`tests/test_settings_dialog.py`:
- Slider value ranges match constants
- Slider change emits `value_changed`
- `load_from_config` populates correctly
- `get_values()` returns current state
- Default values when no config exists
- Voice checkbox state toggles and round-trips through config

---

## Implementation Order

| Phase | Feature | Files | Test Files | Risk | Dependencies |
|-------|---------|-------|------------|------|--------------|
| 26 | TTS + voice modulation | 1 new, 2 modified | 1 new | Low — isolated module | pyttsx3, pydub, simpleaudio, ffmpeg |
| 27 | Squash/stretch | 1 modified, 2 minor | 1 modified | Low — renderer math | none |
| 28 | Edge climbing | 3 modified | 2 modified | Medium — FSM rename + coord math | none |
| 29 | Settings panel | 1 new, 2 modified | 1 new | Low — QDialog is standard | none |

Each phase is independently mergeable.
