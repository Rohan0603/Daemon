# Persona-Infused Authentication & Expanded Dialogue System

**Date:** 2026-06-08
**Phase:** 35b
**Status:** Design

---

## Overview

Phase 35b adds Kenny+Morty persona flavor to the Firebase Auth flow (Phase 35) and expands Daemon's reactive dialogue system with interruptive fast-path roasts and a multiplexed "Bickering Pair" argument system. Five subsystems, one coherent design.

---

## 1. LoginDialog Persona Infusion

### Current State
Generic labels: "Welcome to Daemon", "Email" placeholder, "Password" placeholder, "Sign In" / "Create Account" buttons, red error strings.

### Target State
Persona-driven UI text throughout:

| Element | Sign-In Mode | Sign-Up Mode |
|---------|-------------|--------------|
| Title | `"Daemon: Clearance Check"` | `"Daemon: Identity Registration"` |
| Email placeholder | `"Email. And don't mess this up, man."` | `"Email. Making a new identity, huh?"` |
| Password placeholder | `"Password. No peeking."` | `"Password. Make it good."` |
| Action button | `"Access the Brain"` | `"Register Identity"` |
| Toggle button | `"Wait, I need a new identity!"` | `"Oh wait, I already have one!"` |
| Generic error | `"That ain't it, chief. You're locked out."` | `"Registration glitched. Try again, man."` |
| Connection error | `"Brain's offline. Can't reach Firebase."` | *(same)* |

### Error Email Butchery
On sign-in failure, if the email contains a dot or `@`, apply a simple butchery function before showing the error:
```
"You call that an email? '{butchered}'? Geez, man."
```
Butchery logic: inline helper in `login_dialog.py` — randomly swap a vowel for another vowel, or append a random character at the `@` boundary. Pure function, no dependencies.
```python
def _butcher_email(email: str) -> str:
    import random
    at = email.find("@")
    local = email[:at] if at > 0 else email
    if len(local) < 3:
        return local + str(random.randint(0, 9))
    idx = random.randint(1, len(local) - 2)
    return local[:idx] + random.choice("aeiou") + local[idx + 1:]
```

### Voice Field
The `LoginDialog.__init__` already accepts `on_sign_in`/`on_sign_up` callbacks — no structural changes needed. Only UI strings change.

---

## 2. Hostile Onboarding Flow

The auth gate currently lives in `daemon.py` and silently exits if cancelled. Phase 35b moves the persona reaction into PetWindow, which already has the QWidget + FSM + bubble infrastructure.

### Data Flow

```
daemon.py:
  auth = FirebaseAuth()
  fresh_login = not auth.load()
  if fresh_login:
      crud = ...  # (done after dialog, still in daemon.py)
  else:
      crud = ...  # (token refresh)
  window = PetWindow(auth=auth, crud=crud, fresh_login=fresh_login)

PetWindow.__init__:
  QTimer.singleShot(500, self._on_boot_check_auth)  // wait for paint

PetWindow._on_boot_check_auth:
  if fresh_login:
      self._fsm.current_state = PetState.DEVASTATED
      self._show_bubble("INTRUDER! I don't recognize your clearance!", 5000ms)
      QTimer.singleShot(5500, ...)  // transition to IDLE, show "oh it's just you"
  else:
      self._fsm.current_state = PetState.IDLE
      self._show_bubble("Oh, it's just you. You coulda said so, jeez.", 3000ms)
```

### Key Rules
- `fresh_login` is computed in `daemon.py` before PetWindow exists — no circular dependency
- PetWindow must be visible before `_on_boot_check_auth` fires → `QTimer.singleShot(500)` guarantees `showEvent` has run
- DEVASTATED state displays the pet collapsed on the ground, reinforcing the "intruder alarm" vibe
- The FSM reset to IDLE must happen via timer, not `_tick`, to ensure DEVASTATED renders for the full duration

---

## 3. Bickering Pair Multiplexer (Option A)

Leverages the existing multiplexed JSON contract in `daemon-skill.md` with new modes `kenny_roast` and `morty_panic`.

### daemon-skill.md Addition

Append to section 7 (Multiplexed Output Contract):

```
### BICKERING PAIR PROTOCOL (Multiplexed Conflict)
- Trigger: modes=["kenny_roast", "morty_panic"]
- Return EXACTLY 2 items representing a real-time argument:
  Item 1 (kenny_roast): Kenny makes a reckless/impulsive/violent observation
    about the user's current context.
  Item 2 (morty_panic): Morty immediately reacts to what Kenny just said
    with stammering anxiety.
- Cohesion rule: Item 2's dialogue MUST directly reference Item 1's content.
- Both items carry mode field matching their position.
```

Add new mode entries to the available modes list:
```diff
 Available modes:
 - user_input
 - active_chat
 - joke
 - curiosity
 - boredom
+- kenny_roast
+- morty_panic
```

### PetWindow: _dispatch_multiplexed(modes)

New method that builds a prompt with `modes` field and dispatches via OpencodeWorker. Reuses the existing `trigger_ready` signal (emits `list[dict]`) — no new signals needed. The prompt is built by appending `modes=["kenny_roast","morty_panic"]` to the existing trigger format — the daemon-skill.md already defines how the LLM handles multiplexed arrays when modes are specified.

```python
def _dispatch_multiplexed(self, modes: list[str]) -> None:
    base = self._context_manager.build_autonomous_trigger(
        mode=modes[0], apm=self._current_apm, idle_seconds=self._idle_seconds,
    )
    prompt = base + f"\nmodes: {json.dumps(modes)}"
    worker = OpencodeWorker(
        prompt=prompt, is_autonomous=True,
        session_id=self._opencode_session_id,
    )
    worker.trigger_ready.connect(self._on_structured_multiplexed)
    worker.start()
```

### PetWindow: _on_structured_multiplexed(items)

```python
def _on_structured_multiplexed(self, items: list[dict]) -> None:
    if not items:
        return

    is_bickering = (
        len(items) == 2
        and items[0].get("mode") == "kenny_roast"
    )

    if is_bickering:
        self._dispatch_structured(items[0], force=True)
        QTimer.singleShot(3500, lambda: self._dispatch_structured(items[1], force=True))
        return

    # Standard path: dispatch first, cache rest
    self._dispatch_structured(items[0], force=True)
    for item in items[1:]:
        pool_type = item.get("pool_type", "jokes_blackmail")
        self._response_manager.add_items(pool_type, [item])
```

### Trigger Probability

Add to existing timer handlers that support autonomous triggers:

- `_on_active_chat_tick`: 10% chance → `_dispatch_multiplexed(["kenny_roast", "morty_panic"])`
- `_on_joke_tick`: 15% chance → same
- `_trigger_boredom_query`: 10% chance → same (instead of pool draw)

Add a helper:

```python
def _maybe_dispatch_bickering(self) -> bool:
    if random.random() < 0.10:
        self._dispatch_multiplexed(["kenny_roast", "morty_panic"])
        return True
    return False
```

### FSM Mapping for Bickering Items

| Item | Action | FSM State | Visual |
|------|--------|-----------|--------|
| Kenny roast | `"shake"` or `"hyper"` | SHAKING / HYPER | Vibrate / rainbow flash |
| Morty panic | `"spin"` or `"look_away"` | SPINNING / LOOK_AWAY | Spin / avert gaze |

---

## 4. Interruptive Interrogator Fast Path

### Constants (src/constants.py)

```python
from typing import Final

RISKY_KEYWORDS: Final[dict[str, list[dict]]] = {
    "--force": [
        {"dialogue": "Holy crap, --force?! You're gonna break everything!", "action": "shake"},
        {"dialogue": "Aw geez, force-pushing? That's how repos die, man!", "action": "shake"},
    ],
    "rm -rf": [
        {"dialogue": "RM — RF?! ARE YOU INSANE?!", "action": "shake"},
        {"dialogue": "Oh man, oh man, recursive delete? I-I can't watch!", "action": "look_away"},
    ],
    "drop table": [
        {"dialogue": "DROP TABLE?! You're gonna delete data, man! Holy crap!", "action": "hyper"},
        {"dialogue": "Aw geez, not the— the database, man! That's where things live!", "action": "shake"},
    ],
    "TODO": [
        {"dialogue": "A TODO? That's not a plan, that's a graveyard for dreams.", "action": "idle"},
        {"dialogue": "Oh look, another TODO. You know that's never getting done, right?", "action": "look_away"},
    ],
    "FIXME": [
        {"dialogue": "FIXME? You wrote the bug AND left a note about it. That's rich.", "action": "shake"},
        {"dialogue": "Aw geez, you're leaving FIXMEs for Future You? Poor guy...", "action": "devastated"},
    ],
    "git push": [
        {"dialogue": "Pushing without testing? You're a gambler, huh?", "action": "idle"},
        {"dialogue": "Straight to prod? No PR? No review? You maniac!", "action": "shake"},
    ],
}
```

### Detection in _on_typing_debounce

Modify `_on_typing_debounce()` in `pet_window.py`:

```python
def _on_typing_debounce(self) -> None:
    typing_content = self._typing_buffer.get_context() or ""
    lower = typing_content.lower()

    for keyword, responses in RISKY_KEYWORDS.items():
        if keyword.lower() in lower:
            self._clear_bubble_queue()
            self._fsm.current_state = PetState.SHAKING
            item = random.choice(responses)
            self._show_bubble(item["dialogue"])
            self._triggered_action = item["action"]
            self._typing_last_len = self._typing_buffer.char_count()
            return

    # Original behavior: check new_chars >= 10
    current_len = self._typing_buffer.char_count()
    new_chars = current_len - self._typing_last_len
    self._typing_last_len = current_len
    if new_chars >= 10 and not self._autonomous_query_pending:
        self._trigger_autonomous_query()
```

Key behaviors:
- **0ms latency**: keyword detection is O(n) dict lookup + substring check on the typing buffer
- **Bypass**: no OpencodeWorker — straight to `_show_bubble` + FSM state change
- **Bubble queue cleared**: the roast replaces anything queued, ensuring immediate delivery
- **State override**: sets FSM to SHAKING and enqueues `triggered_action` for the duration-based animation
- **`_typing_last_len` reset**: prevents the keyword match from also triggering an autonomous query

### FSM Integration
- `SHAKING` (priority 8) is duration-based (2000ms) — the pet vibrates orange for 2s, then auto-exits to IDLE
- This is fast enough for comedic timing but long enough to catch user attention
- `HYPER` (priority 4) can fire for severe keywords like `drop table`

---

## 5. Expanded Dialogue Matrix

22-24 lines across 7 categories. All stored as module-level constants in `pet_window.py` (auth/auth-failure) and `constants.py` (risky keywords).

### Auth Lines (3) — pet_window.py

```python
_LOGIN_PROMPT = "Identify yourself! I don't recognize your clearance, man!"
_LOGIN_SUCCESS = "Oh, it's just you. You coulda said so, jeez."
_SIGNUP_SUCCESS = "New identity registered. Don't make me regret this."
```

### Auth Failure Lines (3) — pet_window.py

```python
_LOGIN_FAILURE = "That ain't it, chief. You're locked out of the brain."
_SESSION_EXPIRED = "Your session expired. Get new clearance."
_NETWORK_ERROR = "Brain's offline. Can't reach Firebase, man."
```

### Debugging (2 pairs = 4 lines) — pet_window.py

```python
_BICKER_DEBUGGING = [
    {"dialogue": "Stop staring at the code! You're making it nervous, just run it!",
     "action": "shake", "mode": "kenny_roast"},
    {"dialogue": "Looking at code isn't making it nervous, it's analyzing syntax! Geez, Kenny!",
     "action": "idle", "mode": "morty_panic"},
]

_BICKER_ERROR = [
    {"dialogue": "Ha! Another exception. I told you it was a piece of junk.",
     "action": "idle", "mode": "kenny_roast"},
    {"dialogue": "The stack trace is huge! It's a mile long! We're doomed!",
     "action": "spin", "mode": "morty_panic"},
]
```

### Boredom / Typing (2 pairs = 4 lines) — pet_window.py

```python
_BICKER_BOREDOM = [
    {"dialogue": "This is boring. Let's start a fire. Or something.",
     "action": "wander", "mode": "kenny_roast"},
    {"dialogue": "No fires! We're waiting for them to be productive, man!",
     "action": "shake", "mode": "morty_panic"},
]

_BICKER_TYPING = [
    {"dialogue": "You type slower than a sloth. Give me the keyboard!",
     "action": "shake", "mode": "kenny_roast"},
    {"dialogue": "They're thinking! It's how humans work, you maniac!",
     "action": "idle", "mode": "morty_panic"},
]
```

### Fast Path Dialogue — constants.py (already defined in section 4)

---

## 6. FSM & Priority Integration

| Dialogue Flow | FSM State | Priority | Duration |
|--------------|-----------|----------|----------|
| Login prompt | DEVASTATED | 7 | until dialog dismissed |
| Login success | IDLE | 15 | auto |
| Auth failure | DEVASTATED | 7 | 5s |
| Bickering pair item 1 | SHAKING / HYPER | 8 / 4 | 2s / sustained |
| Bickering pair item 2 | SPINNING / LOOK_AWAY | 10 / 12 | 1.5s / 4s |
| Risky keyword match | SHAKING | 8 | 2s |

The FSM priority system (1=highest) ensures DRAGGED/FALLING/THINKING interrupt any dialogue animation, and duration-based states auto-exit before the next bubble arrives.

---

## 7. Affected Files

| File | Change |
|------|--------|
| `src/login_dialog.py` | Persona UI strings, butchered email error |
| `src/pet_window.py` | Hostile onboarding, bickering dispatch, keyword detection, dialogue constants |
| `src/constants.py` | `RISKY_KEYWORDS` dict |
| `assets/daemon-skill.md` | Bickering Pair protocol section, new modes |
| `daemon.py` | Pass `fresh_login` flag to PetWindow |

---

## 8. What Does NOT Change

- FirebaseAuth / FirebaseCRUD — no functional changes (Phase 35 is untouched)
- `opencode_worker.py` — no new signals needed (`trigger_ready` already emits `list[dict]`)
- `pet_fsm.py` — no new states needed (SHAKING, HYPER, SPINNING, LOOK_AWAY already exist)
- Test count impact: ~468 + 2 pre-existing failures (0 new failures expected)
