# Phase 48: The Awakening (Sight, Vandalism, & Touch)

## Overview
This milestone gives Daemon the ability to "see" non-text applications via OCR, physically vandalize the desktop with persistent sticky notes, and react dynamically to being pet or poked by the user's cursor.

## Components

### Task 1: The "Sight" Upgrade (OCR Integration)
- **Target:** `src/screen_reader.py`
- **Dependency Injection:** Add `pytesseract` and `Pillow` to `requirements.txt`.
- **Logic:** In `ScreenReader.get_screen_context()` (or `get_foreground_text()`):
  - Run the standard UIA text extraction.
  - If the extracted text is `< 50 characters` AND the active window is NOT `Explorer.EXE` or the Desktop:
    - Use `ImageGrab.grab(bbox=window_rect)` to take a screenshot of the active window.
    - Pass the image to `pytesseract.image_to_string()`.
    - Prepend `[OCR Extracted]: ` to the result.
- **Caching & Performance:** 
  - OCR is CPU-heavy and blocking. Run the OCR fallback a maximum of once every 10 seconds.
  - *Refinement:* Because `pytesseract` is a blocking call, we will execute the OCR extraction in a background thread (e.g., using a short-lived `QThread` or `concurrent.futures`) so it doesn't stutter the `_tick` loop of the PyQt6 FSM. While waiting, the system will return the `_last_ocr_text` cache.

### Task 2: Desktop Vandalism (Sticky Notes)
- **Target:** `src/sticky_note.py` (NEW), `src/mcp_server.py`, `src/pet_window.py`
- **UI Class (`src/sticky_note.py`):**
  - Create `StickyNoteWindow(QWidget)`.
  - Flags: `FramelessWindowHint | WindowStaysOnTopHint | Tool`.
  - Style: Yellow background (`#FFF9B1`), drop shadow (`QGraphicsDropShadowEffect`), handwritten-style font ("Comic Sans MS" or "Segoe Print"), and a small "X" button.
  - Behavior: Support drag-to-move.
- **MCP Tool (`src/mcp_server.py`):**
  - Add `spawn_sticky_note(x: int, y: int, text: str)`.
  - Gate behind Consent Matrix key: `allow_desktop_vandalism` (Default: `False`, Tier 2).
  - Emit signal via `FSMActionBridge`.
- **Manager (`src/pet_window.py`):**
  - Maintain `self._active_sticky_notes = []`.
  - On signal, instantiate, `.show()`, and append. Remove and `.deleteLater()` on "X" click.

### Task 3: Tactile Interaction (Petting, Poking, & Dodging)
- **Target:** `src/pet_window.py`, `src/pet_fsm.py`
- **Event Overrides:**
  - `self.setMouseTracking(True)` in `PetWindow`.
  - Override `enterEvent`, `leaveEvent`, and `mouseMoveEvent`.
- **Touch Math:**
  - Track `(x, y)` delta over time inside the pet's bounding box.
  - **Petting (Smooth/Slow):** Low velocity back and forth for > 2 seconds triggers `Emotion.DEVOTION`.
  - **Poking (Fast/Erratic):** High velocity or rapid clicking triggers `Emotion.ANGER`.
- **Dodge Mechanic (`src/pet_fsm.py`):**
  - Add `PetState.DODGE` (Priority 2).
  - If `Emotion.ANGER` is active and user clicks the pet, transition to `DODGE`.
  - Apply horizontal impulse (`_vx = 20` or `-20`) and vertical hop (`_vy = -5`). Let friction handle the halt.

### Task 4: Upgrading the LLM's Brain
- **Target:** `.opencode/skills/kenny/SKILL.md`
- **Tool:** Document `spawn_sticky_note(x, y, text)`. Instruct to leave passive-aggressive notes.
- **Sense:** Instruct on `[OCR Extracted]` text to roast gameplay or images.
- **Feeling:** Instruct on forced `DEVOTION` or `ANGER` to react to petting or poking.

## Execution Plan
We will dispatch OpenCode subagents sequentially:
1. Agent 1: Task 1 (OCR Vision Engine)
2. Agent 2: Task 2 (Sticky Notes)
3. Agent 3: Task 3 (Tactile/Dodge)
