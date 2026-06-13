# Phase 49 Session Summary and Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/log` endpoint for external process logging and a `/session/:id/summarize` endpoint alongside a "Ghost Mode" shutdown mechanic that silently generates and saves a session summary before the process exits.

**Architecture:** We will extend the internal `mcp_server.py` with two new REST endpoints under the existing `do_POST` handler. `POST /log` will write to rotating logs and optionally inject into the user's `ThoughtLogDialog` by writing to `data/.daemon_thoughts.log`. `POST /session/:id/summarize` will emit a Qt signal to `PetWindow`. When `PetWindow` handles the signal (or when the app shuts down), it will spawn a background LLM task, hide the UI, save the resulting summary to the `DiaryStore`, and then fully exit.

**Tech Stack:** Python 3.11+, PyQt6, `http.server`

---

### Task 1: Hybrid Logging Endpoint (`POST /log`)

**Files:**
- Modify: `src/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_mcp_server.py
import json
import logging
import urllib.request
from src.constants import THOUGHTS_LOG_PATH
from pathlib import Path

def test_post_log_writes_to_thoughts_and_logger(mcp_server):
    host, port = mcp_server.server_address
    url = f"http://{host}:{port}/log"
    
    payload = {
        "service": "opencode",
        "level": "ERROR",
        "message": "Connection reset",
        "extra": {"retries": 3}
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        res_body = json.loads(response.read().decode("utf-8"))
        assert res_body.get("success") is True
        
    # Verify thoughts log was written
    content = Path(THOUGHTS_LOG_PATH).read_text(encoding="utf-8")
    assert "[opencode] Connection reset" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_mcp_server.py::test_post_log_writes_to_thoughts_and_logger -v`
Expected: FAIL (404 error since `/log` route doesn't exist)

- [ ] **Step 3: Write minimal implementation**

```python
# In src/mcp_server.py
# Inside do_POST, add handling for /log:
    def do_POST(self):
        if self.path == "/log":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            msg = json.loads(body)
            
            service = msg.get("service", "unknown")
            level_str = msg.get("level", "INFO").upper()
            message = msg.get("message", "")
            extra = msg.get("extra", {})
            
            # Map level to logging module
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR
            }
            level = level_map.get(level_str, logging.INFO)
            
            logger.log(level, f"[{service}] {message} - Extra: {extra}")
            
            # Write to thoughts log for visual output if INFO or above
            if level >= logging.INFO:
                from src.constants import THOUGHTS_LOG_PATH
                from pathlib import Path
                try:
                    with open(THOUGHTS_LOG_PATH, "a", encoding="utf-8") as f:
                        f.write(f"[{service}] {message}\n")
                except Exception as e:
                    logger.error(f"Failed to write to thoughts log: {e}")
            
            self._send_json({"success": True})
            return

        # existing code:
        if self.path in ("/message", "/"):
            # ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_mcp_server.py::test_post_log_writes_to_thoughts_and_logger -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(mcp): add POST /log endpoint for hybrid logging"
```

---

### Task 2: Session Summarization Endpoint & Signal (`POST /session/:id/summarize`)

**Files:**
- Modify: `src/fsm_bridge.py`
- Modify: `src/mcp_server.py`
- Modify: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_mcp_server.py
from unittest.mock import MagicMock

def test_post_session_summarize(mcp_server):
    host, port = mcp_server.server_address
    url = f"http://{host}:{port}/session/1234/summarize"
    
    # Mock the signal emit
    mcp_server.server.fsm_bridge.emit_summarize_requested = MagicMock()
    
    payload = {
        "providerID": "openai",
        "modelID": "gpt-4"
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        res_body = json.loads(response.read().decode("utf-8"))
        assert res_body.get("success") is True
        assert "events" in res_body
        
    mcp_server.server.fsm_bridge.emit_summarize_requested.assert_called_once_with("openai", "gpt-4")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_mcp_server.py::test_post_session_summarize -v`
Expected: FAIL (404 error)

- [ ] **Step 3: Write minimal implementation**

```python
# In src/fsm_bridge.py, add the signal:
    summarize_requested = pyqtSignal(str, str) # providerID, modelID

    def emit_summarize_requested(self, provider_id: str, model_id: str) -> None:
        self.summarize_requested.emit(provider_id, model_id)

# In src/mcp_server.py
# Inside do_POST, add handling for /session/:id/summarize (use regex or startswith):
    def do_POST(self):
        if self.path == "/log":
            # ... existing log handling ...
            return

        import re
        match = re.match(r"^/session/([^/]+)/summarize$", self.path)
        if match:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            msg = json.loads(body)
            
            provider_id = msg.get("providerID", "")
            model_id = msg.get("modelID", "")
            
            if hasattr(self.server, "fsm_bridge") and self.server.fsm_bridge:
                self.server.fsm_bridge.emit_summarize_requested(provider_id, model_id)
                
            self._send_json({"success": True, "events": []})
            return

        # existing code:
        if self.path in ("/message", "/"):
            # ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_mcp_server.py::test_post_session_summarize -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fsm_bridge.py src/mcp_server.py tests/test_mcp_server.py
git commit -m "feat(mcp): add POST /session/:id/summarize endpoint and signal"
```

---

### Task 3: Ghost Mode On-Quit Summarization

**Files:**
- Modify: `src/pet_window.py`
- Modify: `tests/test_pet_window.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_pet_window.py
from unittest.mock import patch, MagicMock
from src.pet_window import PetWindow

@patch("src.pet_window.QApplication.quit")
def test_ghost_mode_on_quit_triggers_summary(mock_quit, qtbot):
    window = PetWindow()
    qtbot.addWidget(window)
    
    with patch.object(window, "hide") as mock_hide, \
         patch.object(window._tray, "hide") as mock_tray_hide, \
         patch("src.pet_window.OpencodeWorker") as mock_worker_class:
             
        mock_worker_instance = MagicMock()
        mock_worker_class.return_value = mock_worker_instance
        
        window._force_quit_app()
        
        # Verify UI is hidden instantly
        mock_hide.assert_called_once()
        mock_tray_hide.assert_called_once()
        
        # Verify quit is NOT called yet
        mock_quit.assert_not_called()
        
        # Verify worker is started
        mock_worker_instance.start.assert_called_once()
        
        # Simulate worker finishing
        window._on_summary_ready([{"type": "observation", "content": "Rohan was coding"}])
        
        # Now quit should be called
        mock_quit.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_pet_window.py::test_ghost_mode_on_quit_triggers_summary -v`
Expected: FAIL (`QApplication.quit()` is called immediately in the current `_force_quit_app`)

- [ ] **Step 3: Write minimal implementation**

```python
# In src/pet_window.py
# Modify _setup_window (or __init__) to connect the new signal:
        if self._mcp_server and self._mcp_server.fsm_bridge:
            self._mcp_server.fsm_bridge.summarize_requested.connect(self._handle_summarize_request)

# Add handler:
    def _handle_summarize_request(self, provider_id: str, model_id: str) -> None:
        self._trigger_ghost_summarization()

# Modify _force_quit_app:
    def _force_quit_app(self) -> None:
        if self._force_quit:
            return
        self._force_quit = True
        logger.info("Initiating Ghost Mode shutdown sequence...")
        
        # Hide UI immediately
        self.hide()
        if self._tray:
            self._tray.hide()
            
        # Trigger summarization
        self._trigger_ghost_summarization(on_complete=self._finalize_quit)

    def _trigger_ghost_summarization(self, on_complete=None) -> None:
        self._summary_on_complete = on_complete
        
        # Failsafe timer (15 seconds)
        from PyQt6.QtCore import QTimer
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setSingleShot(True)
        if on_complete:
            self._shutdown_timer.timeout.connect(on_complete)
        self._shutdown_timer.start(15000)
        
        history_text = "\n".join([f"{item['role']}: {item['content']}" for item in self._history.get_recent(50)])
        prompt = f"Summarize this session strictly into a single observation about the user's habits:\n{history_text}"
        
        from src.opencode_worker import OpencodeWorker
        from src.brain_schema import STRUCTURED_SCHEMA
        self._summary_worker = OpencodeWorker(
            prompt=prompt,
            session_id=self._session_id,
            schema=STRUCTURED_SCHEMA,
            is_autonomous=True
        )
        self._summary_worker.response_ready.connect(self._on_summary_ready)
        self._summary_worker.start()

    def _on_summary_ready(self, items: list[dict]) -> None:
        if items and "content" in items[0]:
            summary = items[0]["content"]
            # Save to DiaryStore
            self._diary_store.add_diary_entry(summary, int(time.time()))
            # Push to Firebase
            self._memory_manager.push_pending_diaries(self._diary_store)
            logger.info("Session summarized and saved.")
            
        if hasattr(self, "_summary_on_complete") and self._summary_on_complete:
            if self._shutdown_timer.isActive():
                self._shutdown_timer.stop()
            self._summary_on_complete()

    def _finalize_quit(self) -> None:
        # Existing cleanup logic from _force_quit_app goes here:
        if self._mcp_server:
            self._mcp_server.stop()
        self._fsm_timer.stop()
        self._behavior_timer.stop()
        if self._response_manager:
            self._response_manager.stop()
        if self._write_coalescer:
            self._write_coalescer.stop()
            self._write_coalescer.flush()
        if self._typing_buffer:
            self._typing_buffer.stop()
        if self._tts:
            self._tts.stop()
        if self._apm_worker:
            self._apm_worker.stop()
        
        if self._thought_log_dialog:
            self._thought_log_dialog.close()

        from src.screen_reader import _cleanup_uia
        _cleanup_uia()

        import sys
        from PyQt6.QtWidgets import QApplication
        from src.persistence import save_state
        save_state({"mood": self.mood_score, "interactions": self.interaction_count})
        QApplication.quit()
```

*(Note: Depending on how `_force_quit_app` is structured originally, carefully migrate its cleanup code into `_finalize_quit` without losing any components. The failsafe ensures `_finalize_quit` is always called).*

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_pet_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pet_window.py tests/test_pet_window.py
git commit -m "feat(daemon): implement ghost mode session summarization on quit"
```

---

## Spec Self-Review Checklist
- [x] Spec coverage: Tasks cover both `/log` endpoint, `/session/:id/summarize`, and Ghost Mode on quit. Failsafe timer is included.
- [x] Placeholder scan: No "TBD" or generic "handle edge cases". Actual python code is provided.
- [x] Type consistency: The mapping to logging levels and PyQt signal matches the described architecture.
