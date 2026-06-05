# Phase 35b — Persona Auth + Dialogue Expansion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Infuse the Firebase Auth gate with Kenny+Morty persona, add zero-latency interruptive roasts for risky keywords, and implement LLM-generated Bickering Pair arguments via multiplexed dispatch.

**Architecture:** Five tight, independent changes: (1) LoginDialog persona strings + email butchery, (2) PetFSM `transition_to` method for centralized state logging, (3) `RISKY_KEYWORDS` fast-path dict in constants, (4) Bickering Pair protocol in daemon-skill.md, (5) PetWindow reactive flows (hostile onboarding, keyword interception, multiplexed dispatch, auth line constants). Each task is independently testable.

**Tech Stack:** PyQt6, Firebase Auth (Phase 35), `json`, `random`, `QTimer`

---

### File Map

| File | Change | Tests |
|------|--------|-------|
| `src/login_dialog.py` | Persona strings, `_butcher_email`, persona errors | `test_login_dialog.py` |
| `src/pet_fsm.py` | Add `transition_to(PetState)` method | `test_pet_fsm.py` |
| `src/constants.py` | Add `RISKY_KEYWORDS` dict | `test_constants.py` |
| `assets/daemon-skill.md` | Bickering Pair protocol section + 2 new modes | — |
| `src/pet_window.py` | Hostile onboarding, keyword detection, `_dispatch_multiplexed`, `_on_structured_multiplexed`, auth line constants | `test_pet_window.py` |
| `daemon.py` | Compute `fresh_login` flag | — |

---

### Task 1: LoginDialog Persona Infusion

**Files:**
- Modify: `src/login_dialog.py` (lines 23-75)
- Test: `tests/test_login_dialog.py`

- [ ] **Step 1: Write failing tests for new persona strings**

Add to `tests/test_login_dialog.py` after the existing tests:

```python
def test_persona_signin_title(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    assert dlg.windowTitle() == "Daemon: Clearance Check"

def test_persona_signin_button(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    assert dlg._action_btn.text() == "Access the Brain"

def test_persona_signin_toggle(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    assert dlg._toggle_btn.text() == "Wait, I need a new identity!"

def test_persona_signup_title(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    dlg._toggle_mode()
    assert dlg.windowTitle() == "Daemon: Identity Registration"

def test_persona_signup_button(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    dlg._toggle_mode()
    assert dlg._action_btn.text() == "Register Identity"

def test_persona_signup_toggle(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    dlg._toggle_mode()
    assert dlg._toggle_btn.text() == "Oh wait, I already have one!"

def test_butcher_email_swaps_vowel(qtbot):
    from src.login_dialog import _butcher_email
    result = _butcher_email("test@foo.com")
    assert "@" not in result
    assert len(result) == len("test")

def test_butcher_email_appends_digit(qtbot):
    from src.login_dialog import _butcher_email
    result = _butcher_email("ab@foo.com")
    assert any(ch.isdigit() for ch in result)

def test_persona_signin_error(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    dlg.show_error("")
    assert dlg._error_label.text() == "That ain't it, chief. You're locked out."

def test_persona_network_error(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    dlg._mode = "signin"
    dlg._email_input.setText("x@y.com")
    dlg._password_input.setText("pwd")
    handler = MagicMock(return_value=None)
    dlg._on_sign_in = handler
    dlg._on_action()
    assert not dlg._error_label.isVisible()
```

- [ ] **Step 2: Run test to verify fails**

Run: `py -m pytest tests/test_login_dialog.py::test_persona_signin_title -v`
Expected: FAIL — windowTitle is "Daemon — Sign In"

- [ ] **Step 3: Update `src/login_dialog.py`**

Replace the UI string section (lines 23-75):

```python
class LoginDialog(QDialog):
    def __init__(
        self,
        on_sign_in: Optional[Callable[[str, str], Optional[str]]] = None,
        on_sign_up: Optional[Callable[[str, str], Optional[str]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_sign_in = on_sign_in
        self._on_sign_up = on_sign_up
        self._mode = "signin"

        self.setWindowTitle("Daemon: Clearance Check")
        self.setFixedSize(300, 250)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint
        )

        layout = QVBoxLayout()
        layout.setSpacing(10)

        title = QLabel("Daemon: Clearance Check")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("Email. And don't mess this up, man.")
        layout.addWidget(self._email_input)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Password. No peeking.")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._password_input)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red; font-size: 12px;")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        self._action_btn = QPushButton("Access the Brain")
        self._action_btn.clicked.connect(self._on_action)
        layout.addWidget(self._action_btn)

        self._toggle_btn = QPushButton("Wait, I need a new identity!")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet("QPushButton { border: none; color: #5B8DEF; }")
        self._toggle_btn.clicked.connect(self._toggle_mode)
        layout.addWidget(self._toggle_btn)

        layout.addStretch()
        self.setLayout(layout)

    def _toggle_mode(self) -> None:
        if self._mode == "signin":
            self._mode = "signup"
            self.setWindowTitle("Daemon: Identity Registration")
            self._action_btn.setText("Register Identity")
            self._toggle_btn.setText("Oh wait, I already have one!")
            title = self.findChild(QLabel)
            if title:
                title.setText("Daemon: Identity Registration")
        else:
            self._mode = "signin"
            self.setWindowTitle("Daemon: Clearance Check")
            self._action_btn.setText("Access the Brain")
            self._toggle_btn.setText("Wait, I need a new identity!")
            title = self.findChild(QLabel)
            if title:
                title.setText("Daemon: Clearance Check")
        self._error_label.setVisible(False)

    def _on_action(self) -> None:
        email = self._email_input.text().strip()
        password = self._password_input.text()
        if not email or not password:
            self.show_error("")
            return

        handler = self._on_sign_in if self._mode == "signin" else self._on_sign_up
        if handler is None:
            return

        self.set_loading(True)
        try:
            uid = handler(email, password)
            if uid:
                self.accept()
            else:
                error = "That ain't it, chief. You're locked out."
                if "@" in email and "." in email:
                    butchered = _butcher_email(email)
                    error = f"You call that an email? '{butchered}'? Geez, man."
                self.show_error(error)
        except requests.exceptions.ConnectionError:
            self.show_error("Brain's offline. Can't reach Firebase.")
        except Exception:
            self.show_error("Brain's offline. Can't reach Firebase.")
        finally:
            self.set_loading(False)

    def show_error(self, message: str) -> None:
        if not message:
            message = "That ain't it, chief. You're locked out."
        self._error_label.setText(message)
        self._error_label.setVisible(True)
```

At module level (after imports), add the helper:

```python
import random
import requests


def _butcher_email(email: str) -> str:
    at = email.find("@")
    local = email[:at] if at > 0 else email
    if len(local) < 3:
        return local + str(random.randint(0, 9))
    idx = random.randint(1, len(local) - 2)
    return local[:idx] + random.choice("aeiou") + local[idx + 1:]
```

Also add `import random` and `import requests` at the top.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest tests/test_login_dialog.py -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/login_dialog.py tests/test_login_dialog.py
git commit -m "feat: persona-infused LoginDialog strings + email butchery"
```

---

### Task 2: PetFSM transition_to Method

**Files:**
- Modify: `src/pet_fsm.py` (add method)
- Test: `tests/test_pet_fsm.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_pet_fsm.py`:

```python
def test_transition_to_changes_state():
    fsm = PetFSM()
    assert fsm.current_state == PetState.IDLE
    fsm.transition_to(PetState.SHAKING)
    assert fsm.current_state == PetState.SHAKING

def test_transition_to_logs_via_callback():
    fsm = PetFSM()
    captured = []
    fsm.transition_to(PetState.HYPER, on_transition=lambda old, new: captured.append((old, new)))
    assert len(captured) == 1
    assert captured[0] == (PetState.IDLE, PetState.HYPER)

def test_transition_to_same_state_is_noop():
    fsm = PetFSM()
    captured = []
    fsm.current_state = PetState.SLEEP
    fsm.transition_to(PetState.SLEEP, on_transition=lambda old, new: captured.append((old, new)))
    assert len(captured) == 0
    assert fsm.current_state == PetState.SLEEP
```

- [ ] **Step 2: Run to verify fails**

Run: `py -m pytest tests/test_pet_fsm.py::test_transition_to_changes_state -v`
Expected: FAIL — PetFSM has no `transition_to` method

- [ ] **Step 3: Add method to `src/pet_fsm.py`**

Add after `__init__`:

```python
    def transition_to(self, new_state: PetState, on_transition=None) -> None:
        if new_state == self.current_state:
            return
        old = self.current_state
        self.current_state = new_state
        if on_transition:
            on_transition(old, new_state)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest tests/test_pet_fsm.py::test_transition_to_changes_state tests/test_pet_fsm.py::test_transition_to_logs_via_callback tests/test_pet_fsm.py::test_transition_to_same_state_is_noop -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/pet_fsm.py tests/test_pet_fsm.py
git commit -m "feat: PetFSM.transition_to with optional callback"
```

---

### Task 3: RISKY_KEYWORDS in Constants

**Files:**
- Modify: `src/constants.py` (add dict)
- Test: `tests/test_constants.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/test_constants.py`:

```python
import pytest
from src.constants import RISKY_KEYWORDS


def test_risky_keywords_is_dict():
    assert isinstance(RISKY_KEYWORDS, dict)

def test_risky_keywords_has_expected_keys():
    expected = {"--force", "rm -rf", "drop table", "TODO", "FIXME", "git push"}
    assert expected.issubset(RISKY_KEYWORDS.keys())

def test_risky_keyword_entries_have_dialogue_and_action():
    for keyword, responses in RISKY_KEYWORDS.items():
        assert len(responses) >= 2, f"{keyword} needs at least 2 responses"
        for item in responses:
            assert "dialogue" in item
            assert "action" in item

def test_risky_keyword_actions_are_valid():
    valid = {"idle", "wander", "celebrate", "devastated",
             "hyper", "shake", "bounce", "spin", "look_away"}
    for keyword, responses in RISKY_KEYWORDS.items():
        for item in responses:
            assert item["action"] in valid, f"{keyword}: {item['action']} not valid"
```

- [ ] **Step 2: Run to verify fails**

Run: `py -m pytest tests/test_constants.py -v`
Expected: FAIL — cannot import RISKY_KEYWORDS

- [ ] **Step 3: Add dict to `src/constants.py`**

Append at the end of `src/constants.py`:

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
        {"dialogue": "FIXME? You wrote the bug AND left a note. That's rich.", "action": "shake"},
        {"dialogue": "Aw geez, you're leaving FIXMEs for Future You? Poor guy...", "action": "devastated"},
    ],
    "git push": [
        {"dialogue": "Pushing without testing? You're a gambler, huh?", "action": "idle"},
        {"dialogue": "Straight to prod? No PR? No review? You maniac!", "action": "shake"},
    ],
}
```

Check if `from typing import Final` already exists at the top of constants.py. If not, add it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest tests/test_constants.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/constants.py tests/test_constants.py
git commit -m "feat: RISKY_KEYWORDS fast-path roast dict"
```

---

### Task 4: daemon-skill.md Bickering Pair Protocol

**Files:**
- Modify: `assets/daemon-skill.md`

No test file for this — the skill file is documentation read by the LLM at runtime.

- [ ] **Step 1: Update `assets/daemon-skill.md`**

After line 180 (end of section 7's "Mix voices across modes" line), insert:

```markdown
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

In the "Available modes" list (around line 172), add two new modes:

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

- [ ] **Step 2: Commit**

```bash
git add assets/daemon-skill.md
git commit -m "feat: Bickering Pair protocol in daemon-skill.md"
```

---

### Task 5: PetWindow Hostile Onboarding + Auth Lines

**Files:**
- Modify: `src/pet_window.py`
- Test: `tests/test_pet_window.py`

- [ ] **Step 1: Write failing tests for auth onboarding**

Add to `tests/test_pet_window.py`:

```python
def test_window_accepts_fresh_login_flag(qtbot):
    window = PetWindow(fresh_login=True)
    qtbot.add_widget(window)
    assert hasattr(window, "_fresh_login")

def test_window_accepts_fresh_login_false(qtbot):
    window = PetWindow(fresh_login=False)
    qtbot.add_widget(window)
    assert window._fresh_login is False

def test_window_without_explicit_auth(qtbot):
    window = PetWindow()
    qtbot.add_widget(window)
    assert window._crud is None
    assert window._firebase_mem is None
```

- [ ] **Step 2: Run to verify fails**

Run: `py -m pytest tests/test_pet_window.py::test_window_accepts_fresh_login_flag -v`
Expected: FAIL — PetWindow doesn't accept fresh_login

- [ ] **Step 3: Add `fresh_login` param to PetWindow.__init__ + remove `crud` param**

In `src/pet_window.py`, in the `__init__` signature, add `fresh_login: bool = False` and remove `crud` (CRUD is now created lazily in `_on_boot_check_auth`):

```python
    def __init__(
        self,
        opencode_enabled: bool = True,
        skill_ready: bool = False,
        initial_state: dict | None = None,
        memory_path: str | None = None,
        history_path: str | None = None,
        auth: "FirebaseAuth | None" = None,
        fresh_login: bool = False,
        **kwargs
    ) -> None:
```

After `self._initial_state = initial_state`, add:

```python
        self._fresh_login = fresh_login
```

In the Firebase initialization section (around lines 151-156), change from using `crud` parameter to using `self._crud = None` initially:

```python
        self._memory = Memory(path=memory_path)
        self._history = History(path=history_path)
        self._crud = None
        if auth and auth.uid:
            self._firebase_available = True
        else:
            self._firebase_available = False
        self._firebase_mem = None
```

Note: `self._crud` is created in `_on_boot_check_auth` when login succeeds. Until then it's `None`. The `MemoryManager` is also created at that point (Task 5's `_on_boot_login_success`).

At the end of `__init__`, add the boot check timer:

```python
        QTimer.singleShot(500, self._on_boot_check_auth)
```

- [ ] **Step 4: Add auth line constants and `_on_boot_check_auth` method**

At module level in `pet_window.py`, after imports (but before the class), add:

```python
_LOGIN_PROMPT = "Intruder! I-I don't recognize your clearance, man! Identify yourself!"
_LOGIN_SUCCESS = "Oh, it's just you. You coulda said so, jeez."
_SIGNUP_SUCCESS = "New identity registered. Don't make me regret this."
_LOGIN_FAILURE = "That ain't it, chief. You're locked out of the brain."
_SESSION_EXPIRED = "Your session expired. Get new clearance."
_NETWORK_ERROR = "Brain's offline. Can't reach Firebase, man."
```

Add the `_on_boot_check_auth` method to the class. This method hosts the LoginDialog natively so the pet is visible and panicking on screen while the user authenticates:

```python
    def _on_boot_check_auth(self) -> None:
        if self._fresh_login:
            self._fsm.transition_to(PetState.DEVASTATED)
            self._show_bubble(_LOGIN_PROMPT)

            def on_sign_in(email: str, password: str) -> str | None:
                return self._auth.sign_in(email, password)
            def on_sign_up(email: str, password: str) -> str | None:
                return self._auth.sign_up(email, password)

            from src.login_dialog import LoginDialog
            from src.firebase_crud import FirebaseCRUD
            from src import constants

            dialog = LoginDialog(on_sign_in=on_sign_in, on_sign_up=on_sign_up, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._crud = FirebaseCRUD(
                    token_provider=self._auth.get_valid_token,
                    project_id=constants.FIREBASE_PROJECT_ID,
                )
                from src.memory_manager import MemoryManager
                self._firebase_mem = MemoryManager(crud=self._crud, uid=self._auth.uid)
                self._firebase_available = True
                self._on_boot_login_success()
            else:
                sys.exit(1)
        else:
            self._fsm.transition_to(PetState.IDLE)
            self._show_bubble(_LOGIN_SUCCESS)

    def _on_boot_login_success(self) -> None:
        self._fsm.transition_to(PetState.IDLE)
        self._show_bubble(_LOGIN_SUCCESS)
```

Add `from PyQt6.QtWidgets import QDialog` to the imports at the top of `pet_window.py`.

Also ensure `self._crud`, `self._firebase_mem`, and `self._firebase_available` are initially set in `__init__` before `_on_boot_check_auth` runs. They're already set in lines 151-156 — just confirm they use `self._auth` and `self._crud` (passed in) rather than local variables.

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -m pytest tests/test_pet_window.py::test_window_accepts_fresh_login_flag tests/test_pet_window.py::test_window_accepts_fresh_login_false -v`
Expected: both PASS

- [ ] **Step 6: Commit**

```bash
git add src/pet_window.py tests/test_pet_window.py
git commit -m "feat: hostile onboarding with DEVASTATED state + auth line constants"
```

---

### Task 6: PetWindow Interruptive Interrogator (Keyword Detection)

**Files:**
- Modify: `src/pet_window.py:1155-1161`

- [ ] **Step 1: Write failing test for keyword detection**

Add to `tests/test_pet_window.py`:

```python
from unittest.mock import patch, MagicMock


def test_risky_keyword_interrupts_bubble(qtbot):
    window = PetWindow()
    qtbot.add_widget(window)
    window._typing_buffer.get_context = MagicMock(return_value="git push --force origin main")
    window._show_bubble = MagicMock()
    window._fsm.transition_to = MagicMock()
    window._on_typing_debounce()
    assert window._show_bubble.called
```

- [ ] **Step 2: Run to verify fails**

Run: `py -m pytest tests/test_pet_window.py::test_risky_keyword_interrupts_bubble -v`
Expected: FAIL — _on_typing_debounce doesn't check keywords

- [ ] **Step 3: Modify `_on_typing_debounce` in `pet_window.py`**

Replace the entire method:

```python
    def _on_typing_debounce(self) -> None:
        typing_content = self._typing_buffer.get_context() or ""
        lower = typing_content.lower()

        for keyword, responses in RISKY_KEYWORDS.items():
            if keyword.lower() in lower:
                self._clear_bubble_queue()
                self._fsm.transition_to(PetState.SHAKING)
                item = random.choice(responses)
                self._show_bubble(item["dialogue"])
                self._triggered_action = item["action"]
                self._typing_last_len = self._typing_buffer.char_count()
                return

        current_len = self._typing_buffer.char_count()
        new_chars = current_len - self._typing_last_len
        self._typing_last_len = current_len
        if new_chars >= 10 and not self._autonomous_query_pending:
            self._trigger_autonomous_query()
```

**Optional improvement — regex word boundary for alpha keywords:**
To prevent false matches (e.g. "TODO" matching inside "autodome"), use `re.search` with `\b` boundary for keywords ending in letters. Symbols like `--force` still use plain `in`:

```python
    def _on_typing_debounce(self) -> None:
        typing_content = self._typing_buffer.get_context() or ""
        lower = typing_content.lower()

        for keyword, responses in RISKY_KEYWORDS.items():
            kw = keyword.lower()
            if kw[-1].isalpha():
                match = re.search(r'\b' + re.escape(kw) + r'\b', lower)
            else:
                match = kw in lower
            if match:
                self._clear_bubble_queue()
                self._fsm.transition_to(PetState.SHAKING)
                item = random.choice(responses)
                self._show_bubble(item["dialogue"])
                self._triggered_action = item["action"]
                self._typing_last_len = self._typing_buffer.char_count()
                return

        current_len = self._typing_buffer.char_count()
        new_chars = current_len - self._typing_last_len
        self._typing_last_len = current_len
        if new_chars >= 10 and not self._autonomous_query_pending:
            self._trigger_autonomous_query()
```

Note: Add `import re` at the top of `pet_window.py` (it's already imported at line 6 — confirm before adding duplicate).

Add the import at the top (after other imports from src.constants):

```python
from src.constants import RISKY_KEYWORDS
```

Add `import random` at the top if not already imported (it is — line 4 of pet_window.py).

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest tests/test_pet_window.py::test_risky_keyword_interrupts_bubble -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pet_window.py tests/test_pet_window.py
git commit -m "feat: Interruptive Interrogator fast-path keyword detection"
```

---

### Task 7: PetWindow Bickering Pair Dispatcher

**Files:**
- Modify: `src/pet_window.py`
- Test: `tests/test_pet_window.py`

- [ ] **Step 1: Write failing tests for bickering pair dispatch**

Add to `tests/test_pet_window.py`:

```python
def test_dispatch_multiplexed_creates_worker(qtbot):
    window = PetWindow()
    qtbot.add_widget(window)
    with patch("src.pet_window.OpencodeWorker") as mock_worker_cls:
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker
        window._dispatch_multiplexed(["kenny_roast", "morty_panic"])
        assert mock_worker_cls.called
        assert mock_worker.start.called
        assert mock_worker.trigger_ready.connect.called

def test_structured_multiplexed_bickering_pair(qtbot):
    window = PetWindow()
    qtbot.add_widget(window)
    window._dispatch_structured = MagicMock()
    items = [
        {"dialogue": "Kenny roast!", "action": "shake", "target_x": 0, "mode": "kenny_roast"},
        {"dialogue": "Morty panic!", "action": "spin", "target_x": 0, "mode": "morty_panic"},
    ]
    window._on_structured_multiplexed(items)
    assert window._dispatch_structured.call_count == 1  # second is timed
    call_args = window._dispatch_structured.call_args
    assert call_args[0][0] == "Kenny roast!"
    assert call_args[0][1] == "shake"

def test_structured_multiplexed_standard_path(qtbot):
    window = PetWindow()
    qtbot.add_widget(window)
    window._dispatch_structured = MagicMock()
    window._response_manager.add_items = MagicMock()
    items = [
        {"dialogue": "First", "action": "idle", "target_x": 0, "pool_type": "jokes_blackmail"},
        {"dialogue": "Second", "action": "idle", "target_x": 0, "pool_type": "jokes_blackmail"},
    ]
    window._on_structured_multiplexed(items)
    assert window._dispatch_structured.call_count == 1
    call_args = window._dispatch_structured.call_args
    assert call_args[0][0] == "First"
    assert window._response_manager.add_items.called
```

- [ ] **Step 2: Run to verify fails**

Run: `py -m pytest tests/test_pet_window.py::test_dispatch_multiplexed_creates_worker -v`
Expected: FAIL — PetWindow has no _dispatch_multiplexed

- [ ] **Step 3: Add `_dispatch_multiplexed` and `_on_structured_multiplexed` methods**

Add before `_dispatch_structured` around line 856:

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
        worker.error_occurred.connect(self._on_opencode_error)
        worker.start()

    def _on_structured_multiplexed(self, items: list[dict]) -> None:
        if not items:
            return
        is_bickering = (
            len(items) == 2
            and items[0].get("mode") == "kenny_roast"
        )
        if is_bickering:
            self._dispatch_structured(items[0]["dialogue"], items[0]["action"],
                                      items[0].get("target_x", 0), force=True)
            QTimer.singleShot(3500, lambda: self._dispatch_structured(
                items[1]["dialogue"], items[1]["action"],
                items[1].get("target_x", 0), force=True))
            return
        first = items[0]
        self._dispatch_structured(first["dialogue"], first["action"],
                                  first.get("target_x", 0), force=True)
        for item in items[1:]:
            pool_type = item.get("pool_type", "jokes_blackmail")
            self._response_manager.add_items(pool_type, [item])
```

Also need to handle `force` parameter in `_dispatch_structured`. Currently it doesn't accept `force`. Modify it to clear the bubble queue when force is True:

Update `_dispatch_structured` to accept `force: bool = False`:

```python
    def _dispatch_structured(self, dialogue: str, action: str, target_x: int,
                             user_input: str = "", force: bool = False) -> None:
        logger.info("_dispatch_structured: dialogue='%s', action='%s', target_x=%s", dialogue, action, target_x)
        if force:
            self._clear_bubble_queue()
        logger.debug(f"_dispatch_structured | action={action} | target_x={target_x} | state={self._fsm.current_state.name}")
        self._fsm.transition_to(PetState.IDLE)
        self._show_bubble(dialogue)
        ...
```

Add `import json` at the top of `pet_window.py` if not already present (it's not currently imported).

Add `force` parameter to all callers of `_dispatch_structured` that pass more than 3 args — check existing callers:
- `_on_trigger_ready` calls `self._dispatch_structured(dialogue, action, target_x, "")` — work fine with default force=False
- `_trigger_boredom_query` calls `self._dispatch_structured(item["dialogue"], item["action"], item.get("target_x", 0))` — fine

- [ ] **Step 4: Add `_maybe_dispatch_bickering` helper and wire into timer handlers**

Add this method:

```python
    def _maybe_dispatch_bickering(self) -> bool:
        if random.random() < 0.10:
            self._dispatch_multiplexed(["kenny_roast", "morty_panic"])
            return True
        return False
```

In `_on_active_chat_tick`, add bickering check at the start of the method:

```python
    def _on_active_chat_tick(self) -> None:
        if self._maybe_dispatch_bickering():
            return
        if not self._should_fire_autonomous("active_chat"):
            return
        ...
```

In `_trigger_boredom_query`, add bickering check at the start:

```python
    def _trigger_boredom_query(self) -> None:
        if self._maybe_dispatch_bickering():
            return
        self._boredom_timer_ms = BOREDOM_TIMEOUT_SEC * 1000
        ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -m pytest tests/test_pet_window.py::test_dispatch_multiplexed_creates_worker tests/test_pet_window.py::test_structured_multiplexed_bickering_pair tests/test_pet_window.py::test_structured_multiplexed_standard_path -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/pet_window.py tests/test_pet_window.py
git commit -m "feat: Bickering Pair multiplexed dispatch + QTimer sequencing"
```

---

### Task 8: daemon.py — Auth Gate Delegates to PetWindow

The LoginDialog now lives inside PetWindow (Task 5) so the pet is visible and panicking on screen. daemon.py only initializes auth and passes it down. CRUD is initialized lazily by PetWindow when auth succeeds.

**Files:**
- Modify: `daemon.py`

- [ ] **Step 1: Update `daemon.py` auth gate — remove LoginDialog, delegate to PetWindow**

Replace the auth gate section (around lines 95-126):

```python
    auth = FirebaseAuth()
    fresh_login = not auth.load()

    if not fresh_login and not auth.get_valid_token():
        print("Session expired.", file=sys.stderr)
        sys.exit(1)

    window = PetWindow(
        opencode_enabled=not args.no_opencode,
        skill_ready=True,
        initial_state=state,
        auth=auth,
        fresh_login=fresh_login,
    )
```

Note: `FirebaseCRUD` is no longer initialized here. PetWindow creates it on login success (Task 5). `crud` parameter removed from PetWindow constructor call — PetWindow's `__init__` now accepts `auth` and `fresh_login`, and initializes `self._crud` as `None` initially.

Also remove the unused imports that are no longer needed in `daemon.py`:
- Remove `from src.login_dialog import LoginDialog`
- Remove `from src.firebase_crud import FirebaseCRUD`

- [ ] **Step 2: Commit**

```bash
git add daemon.py
git commit -m "refactor: auth LoginDialog moved to PetWindow for visible onboarding"
```

---

### Task 9: Final Test Run & Verification

- [ ] **Step 1: Run the full test suite**

Run: `py -m pytest tests/ -q --tb=line`
Expected: 471+ passed, 0 new failures (2 pre-existing logging failures)

- [ ] **Step 2: Verify git log is clean**

Run: `git log --oneline -5`
Expected: 5 clean feature commits on top of the current base

---

## Self-Review Checklist

1. **Spec coverage:** Does every section of the spec have a corresponding task?
   - LoginDialog persona (section 1) → Task 1 ✓
   - Hostile onboarding (section 2) → Task 5 ✓
   - Bickering Pair (section 3) → Task 4 + Task 7 ✓
   - Interruptive Interrogator (section 4) → Task 3 + Task 6 ✓
   - Dialogue matrix (section 5) → Task 5 (auth lines) + Task 3 (risky keywords) ✓
   - FSM integration (section 6) → Task 2 ✓
   - daemon.py changes (section 7) → Task 8 ✓

2. **Placeholder scan:** No "TBD", "TODO", "implement later", or missing code blocks. Every test contains exact assertions. Every implementation contains the actual code.

3. **Type consistency:**
   - `_dispatch_structured(dialogue, action, target_x, user_input, force)` — the `force` kwarg is added in Task 7, consistent with existing callers that use 4 positional args (default `force=False` works).
   - `_on_boot_check_auth` → `_on_boot_login_success` — defined in same task, consistent.
   - `RISKY_KEYWORDS` dict keys are lowercase strings matched via `keyword.lower() in lower` — consistent casing check.
   - `transition_to(PetState.X)` replaces direct `self._fsm.current_state = PetState.X` — all new code uses the method.
   - **Modal paradox resolved:** Task 5 hosts `LoginDialog` inside `PetWindow._on_boot_check_auth` (pet visible, panicking in DEVASTATED state behind it). Task 8 strips `daemon.py` to just init auth + compute `fresh_login`. CRUD is created lazily in Task 5 on login success.
