# Phase 49: Session Summarization & Hybrid Logging

## Overview
This spec outlines two new REST endpoints to be added to Daemon's internal HTTP server (`src/mcp_server.py`), alongside an architectural change to Daemon's shutdown sequence to seamlessly summarize the session in the background before fully exiting.

## Components

### 1. The `POST /log` Endpoint (Hybrid Logging)
- **Target:** `src/mcp_server.py`
- **Route:** Add `/log` to the `do_POST` handler.
- **Payload:** `{ "service": "str", "level": "str", "message": "str", "extra": "dict" }`
- **Logic:**
  - Map `level` to Python's `logging` module levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
  - Write **all** payloads to the standard rotating file logs (`logs/daemon_*.log`) using `logger.log()`, including the `extra` dictionary for debugging context.
  - If `level` is `INFO`, `WARNING`, or `ERROR`, format the output as `[{service}] {message}` and append it directly to `data/.daemon_thoughts.log`. This instantly projects the log onto the user-facing Matrix UI (`ThoughtLogDialog`).

### 2. The `POST /session/:id/summarize` Endpoint
- **Target:** `src/mcp_server.py`
- **Route:** Add `/session/:id/summarize` to the `do_POST` handler.
- **Payload:** `{ "providerID": "str", "modelID": "str" }`
- **Logic:**
  - Emit a PyQt signal (e.g., `fsm_bridge.emit_summarize_requested(provider, model)`) to jump from the HTTP server thread back to the main Qt thread.
  - In `PetWindow`, this triggers the generation of a background LLM prompt containing the current `History` queue.
  - Returns `{"success": true, "events": []}` to the caller immediately while the summarization happens asynchronously.

### 3. "Ghost Mode" On-Quit Summarization
- **Target:** `src/pet_window.py`
- **Trigger:** `_force_quit_app()`
- **Logic:**
  - **Hide the UI:** Immediately call `self.hide()` and `self._tray.hide()` so the pet vanishes from the user's screen instantly.
  - **Block Shutdown:** Prevent `QApplication.quit()` from firing immediately.
  - **Trigger Summary:** Instantiate an `OpencodeWorker` with a prompt to summarize the current conversation history. 
  - **Save & Terminate:** When the worker's `response_ready` signal fires, take the text, save it as a new entry into the `DiaryStore` (pushing to Firebase on sync), and *then* finally invoke `QApplication.quit()` to kill the Python process.
  - *Fallback:* Start a 15-second QTimer failsafe. If the LLM takes too long or fails, the failsafe forcefully terminates the app to prevent a zombie process.
