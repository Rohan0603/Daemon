# Daemon OpenCode SSE Integration Design

## 1. Overview
The Daemon currently relies on OS-level polling (`GetForegroundWindow`, UIAutomation) and APM hooks to drive the pet's behavioral states and triggers. To give Kenny deeper context about the user's coding workflow, we will integrate with OpenCode's Server-Sent Events (SSE) stream (`/event`). This allows Daemon to react in real-time to LSP syntax errors, completed terminal commands, and file edits.

## 2. Architecture & Components
### `EventStreamWorker(QThread)`
A new background thread in `src/event_worker.py` dedicated to the SSE connection.
- **Connection**: Makes a GET request to `http://127.0.0.1:4096/event` with `stream=True`.
- **Parsing**: Iterates over lines. When it detects an event of interest (`EventLspUpdated`, `EventCommandExecuted`, `EventFileEdited`), it parses the JSON payload.
- **Signals**:
  - `lsp_error_detected(diagnostics: dict)`
  - `lsp_error_cleared()`
  - `command_completed(command: str, exit_code: int)`
  - `file_edited(filepath: str)`

### `PetWindow` Integration
`PetWindow` manages the worker lifecycle and signal connections.
- Creates and starts `EventStreamWorker` on boot.
- Subscribes to the emitted signals.
- Maintains a 5-second `_lsp_debounce_timer` QTimer.

## 3. Data Flow
1. **File Edits**: Upon receiving `file_edited(filepath)`, the system silently updates the current `ContextManager` state so Kenny knows which file is in focus without relying entirely on OS screen-scraping.
2. **LSP Diagnostics**:
   - When an `EventLspUpdated` with an `ERROR` severity is parsed, `lsp_error_detected` is emitted.
   - `PetWindow` receives this and starts/resets the `_lsp_debounce_timer` (5000ms).
   - If the error is cleared before 5 seconds, the timer is canceled.
   - If the timer fires, Kenny transitions to `THINKING` and triggers an `lsp_roast` prompt, bypassing normal boredom timers.
3. **Commands**:
   - `EventCommandExecuted` bypasses timers.
   - If `exit_code == 0`, transition to `CELEBRATE` (or generic cheer).
   - If `exit_code != 0`, transition to `DEVASTATED` (or angry roast).

## 4. Error Handling & Reconnection
- **Disconnects**: If the HTTP stream breaks or the OpenCode server restarts, `EventStreamWorker` catches the exception and waits with an exponential backoff (starting at 3s, max 15s) before reconnecting.
- **JSON Errors**: Malformed chunks will log a warning and skip to the next chunk rather than crashing the thread.
- **Boot Safety**: If OpenCode is offline at startup, the worker enters the retry loop safely without blocking Daemon initialization.

## 5. Scope & Limitations
- **OS Context**: SSE only tracks the developer workspace. Existing OS-level polling remains for detecting applications like web browsers or Task Manager.
- **Debounce Constraint**: The 5-second LSP debounce is hardcoded. It prevents rapid-fire interruptions while actively typing.
