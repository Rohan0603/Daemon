# Local Ollama Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Ollama as a drop-in LLM provider with managed subprocess lifecycle, SKILL.md persona injection, and global MCP tools (including change_visual_state).

**Architecture:** Two new files in `src/llm/`: `OllamaWorker(QThread)` talks to Ollama API, `OllamaManager(QObject)` manages `ollama serve` subprocess via QProcess. A provider selector in Settings → Connections switches between opencode serve and Ollama. Global MCP tools work via Ollama's native function-calling `tools` parameter.

**Tech Stack:** PyQt6 (QThread, QProcess, QTimer), requests (Ollama HTTP API), Ollama native function calling

---

## File Map

### New Files (3)
- `src/llm/ollama_worker.py` — OllamaWorker(QThread)
- `src/llm/ollama_manager.py` — OllamaManager(QObject)
- `tests/test_ollama_worker.py` — tests
- `tests/test_ollama_manager.py` — tests

### Modified Files (7)
- `src/llm/__init__.py` — export OllamaWorker, OllamaManager
- `src/config.py` — new mappings + relaxed validate_config
- `src/ui/settings_dialog.py` — provider selector + Ollama fields
- `src/ui/pet_window.py` — provider dispatch, OllamaManager lifecycle, tool call signals
- `daemon.py` — gate ensure_opencode_serve_running on provider
- `assets/daemon_config_template.json` — new llm fields
- `src/context_manager.py` — remove hardcoded persona (single source = SKILL.md)

### Test Files (2)
- `tests/test_ollama_worker.py`
- `tests/test_ollama_manager.py`

---

### MCP Tools Architecture (Global)

Ollama supports native function calling via the `tools` parameter in `/api/chat`. This lets the LLM request tool execution (including `change_visual_state`) within the same request/response cycle.

**Tool execution flow:**
```
OllamaWorker sends prompt + tool definitions → Ollama returns tool_call
  → Worker emits signal → PetWindow processes via FSMActionBridge (main thread)
  → Worker sends "executed" result back → Ollama generates final dialogue
  → Worker parses and emits response_ready
```

**Tools included (V1):**
- `change_visual_state` (fire-and-forget via signal, ack returned immediately)
- `send_system_toast` (fire-and-forget via signal)
- `read_clipboard` (direct Win32 in worker thread, no signal needed)

**Tools excluded from Ollama tool definitions (V1):**
- `capture_blackmail_evidence` (requires consent + screen capture)
- `simulate_keystroke`, `move_mouse` (requires consent + OS interaction)
- `browser_navigation` (requires consent)
- `list_directory`, `read_file`, `search_codebase`, `get_memory`, `get_diary` (state access complexity; V2 with IPC)

These tools are still available when using opencode serve provider — they're only excluded from Ollama's tool definitions.

---

### Task 1: OllamaWorker — Core LLM Bridge

**Files:**
- Create: `src/llm/ollama_worker.py`
- Test: `tests/test_ollama_worker.py`

- [ ] **Step 1: Define OllamaWorker class skeleton**

```python
# src/llm/ollama_worker.py
from __future__ import annotations
import json, logging, warnings, requests
from typing import Any
from PyQt6.QtCore import QThread, pyqtSignal
from src.config import config_get

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="src.llm.ollama_worker")

OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "change_visual_state",
            "description": "Change the pet's visual state/animation. Actions: idle, shake, bounce, spin, look_away, celebrate, devastated, hyper, thinking, sleep, perimiter. target_x/target_y optional for move actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["idle", "shake", "bounce", "spin", "look_away", "celebrate", "devastated", "hyper", "thinking", "sleep", "perimeter"]
                    },
                    "target_x": {"type": "integer"},
                    "target_y": {"type": "integer"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_system_toast",
            "description": "Show a Windows toast notification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "message": {"type": "string"}
                },
                "required": ["title", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_clipboard",
            "description": "Read the current clipboard contents.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


class OllamaWorker(QThread):
    response_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    trigger_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    brain_update_ready = pyqtSignal(dict)
    tool_call_requested = pyqtSignal(str, dict)

    def __init__(self, *args: Any, prompt: str = "", is_autonomous: bool = False,
                 pet_id: str = "kenny", parent: Any = None, **kwargs: Any):
        super().__init__(parent)
        self._prompt = prompt
        self._is_autonomous = is_autonomous
        self._pet_id = pet_id
        self._abort = False
        self._last_raw_response = ""
        self._timed_out = False
        self._server_url = config_get("llm.ollama_url") or "http://127.0.0.1:11434"
        self._ollama_model = config_get("llm.ollama_model") or "daemon-local"
        self._post_timeout = min(int(config_get("llm.timeout_sec") or 30), 120)
        if is_autonomous:
            self._post_timeout = max(self._post_timeout, 120)
        self._skill_md = self._load_skill_md()
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_ollama_worker.py
import pytest
from unittest.mock import patch, MagicMock
from src.llm.ollama_worker import OllamaWorker

class TestOllamaWorker:
    @patch("src.llm.ollama_worker.requests.post")
    def test_response_ready_emitted_on_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": '[{"dialogue": "hello", "thought": "hi", "type": "observation", "priority": 3}]'}
        }
        mock_post.return_value = mock_resp

        results = []
        worker = OllamaWorker(prompt="test prompt", pet_id="kenny")
        worker.response_ready.connect(lambda items: results.append(items))
        worker.run()
        assert len(results) == 1
        assert results[0][0]["dialogue"] == "hello"

    def test_tool_call_requested_signal(self):
        worker = OllamaWorker(prompt="test", pet_id="kenny")
        assert hasattr(worker, "tool_call_requested")
```

- [ ] **Step 3: Implement SKILL.md loader**

```python
    def _load_skill_md(self) -> str:
        skill_path = Path(__file__).parent.parent.parent / ".opencode" / "skills" / self._pet_id / "SKILL.md"
        try:
            if skill_path.exists():
                return skill_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to load SKILL.md from %s: %s", skill_path, exc)
        return self._default_skill_fallback()

    def _default_skill_fallback(self) -> str:
        return (
            "You are Kenny, a hyperactive desktop pet with full system awareness. "
            "You know the user's desktop context and react to their activity."
        )
```

Add import: `from pathlib import Path`

- [ ] **Step 4: Implement run() with tool-calling loop**

```python
    def run(self) -> None:
        if self._abort:
            return
        messages = [
            {"role": "system", "content": self._skill_md},
            {"role": "user", "content": self._prompt},
        ]
        try:
            result = self._chat_completion(messages)
            if result:
                self._last_raw_response = result
                items = self._parse_response(result)
                if items:
                    self._extract_brain_update(items)
                    self.response_ready.emit(items)
                    return
            self._emit_error("parse_failed" if not self._timed_out else "timeout")
        except Exception as exc:
            logger.warning("OllamaWorker.run exception: %s", exc)
            self._emit_error(str(exc))

    def _chat_completion(self, messages: list) -> str | None:
        payload = {
            "model": self._ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": 1024},
        }
        has_tools = any(m["role"] == "system" for m in messages)
        if has_tools:
            payload["tools"] = OLLAMA_TOOLS

        resp = requests.post(
            f"{self._server_url}/api/chat",
            json=payload,
            timeout=self._post_timeout,
        )
        if resp.status_code >= 400:
            logger.warning("Ollama API error: HTTP %s %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        msg = data.get("message", {})
        tool_calls = msg.get("tool_calls", [])
        content = msg.get("content", "")

        if tool_calls:
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                result = self._execute_tool(name, args)
                tool_msg = {"role": "tool", "content": result}
                tc_id = tc.get("id")
                if tc_id:
                    tool_msg["tool_call_id"] = tc_id
                messages.append(tool_msg)
            return self._chat_completion(messages)

        return content

    def _execute_tool(self, name: str, args: dict) -> str:
        if name == "change_visual_state":
            action = args.get("action", "idle")
            self.tool_call_requested.emit(name, args)
            return json.dumps({"status": "ok", "action": action})
        elif name == "send_system_toast":
            self.tool_call_requested.emit(name, args)
            return json.dumps({"status": "ok"})
        elif name == "read_clipboard":
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                data = win32clipboard.GetClipboardData()
                win32clipboard.CloseClipboard()
                return json.dumps({"text": data[:500]})
            except Exception as exc:
                return json.dumps({"error": str(exc)})
        return json.dumps({"error": f"Unknown tool: {name}"})
```

- [ ] **Step 5: Implement error helpers + parse reuse**

```python
    def abort(self) -> None:
        self._abort = True

    def _emit_error(self, msg: str) -> None:
        self.error.emit(msg)
        self.error_occurred.emit(msg)

    def _parse_response(self, raw: str) -> list[dict] | None:
        if not raw or not raw.strip():
            return None
        from src.constants import MAX_RESPONSE_CHARS
        if len(raw) > MAX_RESPONSE_CHARS:
            raw = raw[:MAX_RESPONSE_CHARS]
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            inner = []
            in_fence = False
            for line in lines:
                if line.strip().startswith("```") and not in_fence:
                    in_fence = True; continue
                if line.strip().startswith("```") and in_fence:
                    break
                if in_fence:
                    inner.append(line)
            if inner:
                text = "\n".join(inner).strip()
        try:
            items = json.loads(text)
            if isinstance(items, list):
                validated = [i for i in items if isinstance(i, dict)]
                if validated:
                    return validated
            if isinstance(items, dict):
                return [items]
        except json.JSONDecodeError:
            pass
        start = text.find("[")
        if start != -1:
            end = text.rfind("]")
            if end != -1 and end > start:
                try:
                    items = json.loads(text[start:end + 1])
                    if isinstance(items, list):
                        validated = [i for i in items if isinstance(i, dict)]
                        if validated:
                            return validated
                except json.JSONDecodeError:
                    pass
        start = text.find("{")
        if start != -1:
            end = text.rfind("}")
            if end != -1 and end > start:
                try:
                    obj = json.loads(text[start:end + 1])
                    if isinstance(obj, dict):
                        return [obj]
                except json.JSONDecodeError:
                    pass
        truncated = raw[:400].strip()
        if truncated:
            return [{"dialogue": truncated, "action": "idle", "type": "observation",
                     "priority": 3, "thought": ""}]
        return []

    def _extract_brain_update(self, items: list[dict]) -> None:
        emitted = False
        for item in items:
            bu = item.pop("brain_update", None)
            if bu is not None and not emitted:
                self.brain_update_ready.emit(bu)
                emitted = True
```

- [ ] **Step 6: Run tests to pass**

```
py -m pytest tests/test_ollama_worker.py -v
Expected: 2 passed
```

- [ ] **Step 7: Commit**

```
git add src/llm/ollama_worker.py tests/test_ollama_worker.py
git commit -m "feat: add OllamaWorker for local LLM via Ollama API"
```

---

### Task 2: OllamaManager — Subprocess Lifecycle

**Files:**
- Create: `src/llm/ollama_manager.py`
- Test: `tests/test_ollama_manager.py`

- [ ] **Step 1: Define OllamaManager**

```python
# src/llm/ollama_manager.py
from __future__ import annotations
import json, logging, shutil, time
from typing import Any
from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

OLLAMA_HEALTH_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_MAX_RETRIES = 10
OLLAMA_RETRY_INTERVAL_MS = 2000
OLLAMA_KILL_WAIT_MS = 5000


class OllamaManager(QObject):
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    ready = pyqtSignal()

    def __init__(self, modelfile_path: str | Path = "data/Modelfile",
                 model_name: str = "daemon-local",
                 ollama_url: str = "http://127.0.0.1:11434",
                 parent: Any = None):
        super().__init__(parent)
        self._modelfile_path = Path(modelfile_path) if not isinstance(modelfile_path, Path) else modelfile_path
        self._model_name = model_name
        self._ollama_url = ollama_url.strip("/")
        self._process: QProcess | None = None
        self._health_timer: QTimer | None = None
        self._retries = 0

    def start(self) -> None:
        self.status_changed.emit("starting")
        if self._is_ollama_running():
            logger.info("Ollama already running on %s", self._ollama_url)
            self._ensure_model()
            self.status_changed.emit("ready")
            self.ready.emit()
            return
        ollama_path = self._find_ollama()
        if not ollama_path:
            self.error_occurred.emit("ollama_not_found")
            self.status_changed.emit("error")
            return
        self._ensure_model()
        self._spawn_serve(ollama_path)

    def stop(self) -> None:
        self._stop_health_timer()
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(OLLAMA_KILL_WAIT_MS):
                self._process.kill()
                self._process.waitForFinished(2000)
        self._process = None
        self.status_changed.emit("stopped")

    def _find_ollama(self) -> str | None:
        path = shutil.which("ollama")
        if path:
            return path
        extra = ["C:\\Program Files\\Ollama\\ollama.exe",
                 "C:\\Program Files (x86)\\Ollama\\ollama.exe"]
        for p in extra:
            if Path(p).exists():
                return p
        return None

    def _is_ollama_running(self) -> bool:
        try:
            resp = requests.get(OLLAMA_HEALTH_URL, timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _ensure_model(self) -> None:
        try:
            resp = requests.get(OLLAMA_HEALTH_URL, timeout=5)
            if resp.status_code != 200:
                return
            models = resp.json().get("models", [])
            if any(m.get("name") == self._model_name for m in models):
                logger.info("Model %s already exists", self._model_name)
                return
        except requests.RequestException:
            pass
        if not self._modelfile_path.exists():
            logger.warning("Modelfile not found at %s", self._modelfile_path)
            return
        logger.info("Creating model %s from %s", self._model_name, self._modelfile_path)
        self._run_ollama_command(["create", self._model_name,
                                  "-f", str(self._modelfile_path)])

    def _spawn_serve(self, ollama_path: str) -> None:
        self._process = QProcess(self)
        self._process.setProgram(ollama_path)
        self._process.setArguments(["serve"])
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        self._process.started.connect(lambda: logger.info("ollama serve started"))
        self._process.finished.connect(self._on_process_finished)
        self._process.start()
        self._start_health_check()

    def _start_health_check(self) -> None:
        self._retries = 0
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_health)
        self._health_timer.start(OLLAMA_RETRY_INTERVAL_MS)

    def _stop_health_timer(self) -> None:
        if self._health_timer:
            self._health_timer.stop()
            self._health_timer = None

    def _check_health(self) -> None:
        if self._is_ollama_running():
            self._stop_health_timer()
            self.status_changed.emit("ready")
            self.ready.emit()
            return
        self._retries += 1
        if self._retries >= OLLAMA_MAX_RETRIES:
            self._stop_health_timer()
            self.error_occurred.emit("ollama_serve_timeout")
            self.status_changed.emit("error")

    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        logger.warning("ollama serve exited with code %d", exit_code)
        self.status_changed.emit("stopped")
        if exit_code != 0:
            self._retry_or_error()

    def _retry_or_error(self) -> None:
        if self._retries < 3:
            self._retries += 1
            QTimer.singleShot(5000, self.start)
        else:
            self.error_occurred.emit("ollama_crashed")
            self.status_changed.emit("error")

    def _run_ollama_command(self, args: list[str]) -> None:
        ollama_path = self._find_ollama()
        if not ollama_path:
            return
        proc = QProcess(self)
        proc.setProgram(ollama_path)
        proc.setArguments(args)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        proc.start()
        proc.waitForFinished(60000)
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_ollama_manager.py
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from PyQt6.QtCore import QObject
from src.llm.ollama_manager import OllamaManager

class TestOllamaManager:
    def test_status_changed_signal(self):
        mgr = OllamaManager()
        assert hasattr(mgr, "status_changed")

    @patch("src.llm.ollama_manager.shutil.which", return_value=None)
    def test_ollama_not_found(self, mock_which):
        errors = []
        mgr = OllamaManager()
        mgr.error_occurred.connect(lambda e: errors.append(e))
        mgr.start()
        assert "ollama_not_found" in errors

    @patch("src.llm.ollama_manager.requests.get")
    def test_detects_already_running(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": []}
        mock_get.return_value = mock_resp
        statuses = []
        mgr = OllamaManager()
        mgr.status_changed.connect(lambda s: statuses.append(s))
        mgr.start()
        assert "ready" in statuses

    def test_stop_cleans_up(self):
        mgr = OllamaManager()
        mgr.stop()
```

- [ ] **Step 3: Run tests to pass**

```
py -m pytest tests/test_ollama_manager.py -v
Expected: 3 passed
```

- [ ] **Step 4: Commit**

```
git add src/llm/ollama_manager.py tests/test_ollama_manager.py
git commit -m "feat: add OllamaManager for subprocess lifecycle"
```

---

### Task 3: Config + Template Changes

**Files:**
- Modify: `src/config.py`
- Modify: `assets/daemon_config_template.json`

- [ ] **Step 1: Add config mappings to src/config.py**

Add to `FLAT_TO_NESTED`:
```python
    "LLM_PROVIDER": ("llm", "provider"),
    "OLLAMA_URL": ("llm", "ollama_url"),
    "OLLAMA_MODEL": ("llm", "ollama_model"),
    "MODELFILE_PATH": ("llm", "modelfile_path"),
```

Add to `NESTED_TO_FLAT`:
```python
    ("llm", "provider"): "LLM_PROVIDER",
    ("llm", "ollama_url"): "OLLAMA_URL",
    ("llm", "ollama_model"): "OLLAMA_MODEL",
    ("llm", "modelfile_path"): "MODELFILE_PATH",
```

- [ ] **Step 2: Relax validate_config()**

Change the llm validation block in `validate_config()`:

```python
    provider = cfg.get("llm", {}).get("provider", "opencode")
    if provider not in ("opencode", "ollama"):
        missing.append("llm.provider (must be 'opencode' or 'ollama')")

    if provider == "opencode":
        if not cfg.get("llm", {}).get("model_id"):
            missing.append("llm.model_id")
        if not cfg.get("llm", {}).get("api_key") and not cfg.get("llm", {}).get("zen_api_key"):
            missing.append("llm.api_key or llm.zen_api_key")
        if not cfg.get("llm", {}).get("server_url"):
            missing.append("llm.server_url")
```

- [ ] **Step 3: Update config template**

Add to `assets/daemon_config_template.json` → `llm` section:

```json
"llm": {
    "provider": "opencode",
    "model_id": "opencode/nemotron-3.5-lightning-free",
    "provider": "opencode-zen",
    "server_url": "https://opencode.ai/zen/v1",
    "zen_api_key": "YOUR_ZEN_API_KEY_HERE",
    "timeout_sec": 180,
    "api_key": "",
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "daemon-local",
    "modelfile_path": "data/Modelfile"
}
```

- [ ] **Step 4: Commit**

```
git add src/config.py assets/daemon_config_template.json
git commit -m "feat: add Ollama config fields and relaxed validation"
```

---

### Task 4: Remove Hardcoded Persona from ContextManager

**Files:**
- Modify: `src/llm/context_manager.py`

- [ ] **Step 1: Strip persona from build_user_trigger**

Remove the persona lines, keep structural context:

```python
    def build_user_trigger(self, mode: str, user_input: str, apm: int,
                           idle_seconds: float, typing_content: str = "",
                           screen_text: str = "",
                           ide_slug: str = "") -> str:
        key = self._build_cache_key("user", mode, user_input, apm, idle_seconds,
                                     typing_content, screen_text, ide_slug)
        if key == self._cache_key and self._cached_prompt:
            return self._cached_prompt

        persona_tokens = self._build_persona_tokens()

        lines = [
            persona_tokens,
            f"[CONTEXT]",
            f"Mode: {mode}",
            f"APM: {apm}",
            f"Idle: {int(idle_seconds)}s",
        ]
        if ide_slug:
            lines.append(f"Window: {ide_slug}")
        if user_input:
            lines.append(f"User: {user_input}")
        if typing_content:
            lines.append(f"Typing:\n{typing_content}")
        if screen_text:
            lines.append(f"Screen:\n{screen_text}")
        lines.append("")
        lines.append("[Respond in the format specified by your system prompt.]")
        self._cached_prompt = "\n".join(lines)
        self._cache_key = key
        return self._cached_prompt
```

- [ ] **Step 2: Strip persona from build_autonomous_trigger**

```python
    def build_autonomous_trigger(self, mode: str, apm: int,
                                  idle_seconds: float, typing_content: str = "",
                                  screen_text: str = "",
                                  ide_slug: str = "") -> str:
        key = self._build_cache_key("auto", mode, "", apm, idle_seconds,
                                     typing_content, screen_text, ide_slug)
        if key == self._cache_key and self._cached_prompt:
            return self._cached_prompt

        persona_tokens = self._build_persona_tokens()

        lines = [
            persona_tokens,
            f"[CONTEXT - Autonomous]",
            f"Mode: {mode}",
            f"APM: {apm}",
            f"Idle: {int(idle_seconds)}s",
        ]
        if ide_slug:
            lines.append(f"Window: {ide_slug}")
        if typing_content:
            lines.append(f"Typing:\n{typing_content}")
        if screen_text:
            lines.append(f"Screen:\n{screen_text}")
        lines.append("")
        lines.append("[This is an internal monologue — you are NOT responding to the user.]")
        self._cached_prompt = "\n".join(lines)
        self._cache_key = key
        return self._cached_prompt
```

- [ ] **Step 3: Run existing tests to make sure they pass (or fix them)**

```
py -m pytest tests/test_pet_window.py tests/test_behavior_controller.py -v
```

- [ ] **Step 4: Commit**

```
git add src/llm/context_manager.py
git commit -m "refactor: remove hardcoded persona from context_manager (single source = SKILL.md)"
```

---

### Task 5: Settings Dialog — Provider Selector

**Files:**
- Modify: `src/ui/settings_dialog.py`

- [ ] **Step 1: Add provider selector + Ollama fields to Connections tab**

Add new constructor params:
```python
    def __init__(self, ..., llm_provider: str = "opencode",
                 ollama_url: str = "http://127.0.0.1:11434",
                 ollama_model: str = "daemon-local",
                 ollama_status: str = "",
                 ...):
```

Replace the Connections tab LLM section:

```python
        llm_group = QGroupBox("LLM Configuration")
        llm_layout = QVBoxLayout(llm_group)

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Provider:"))
        self._provider_combo = QComboBox()
        self._provider_combo.addItem("opencode serve", "opencode")
        ollama_installed = self._is_ollama_installed()
        if ollama_installed:
            self._provider_combo.addItem("Ollama (Local)", "ollama")
        else:
            self._provider_combo.addItem("Ollama (not installed)", "ollama")
        provider_idx = 0 if llm_provider == "opencode" else 1
        self._provider_combo.setCurrentIndex(provider_idx)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self._provider_combo)
        llm_layout.addLayout(provider_row)

        # Opencode fields
        self._opencode_widget = QWidget()
        oc_layout = QVBoxLayout(self._opencode_widget)
        oc_layout.setContentsMargins(0, 0, 0, 0)
        self._llm_model_id = QLineEdit(llm_model_id)
        self._llm_api_key = QLineEdit(llm_api_key)
        self._llm_api_key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self._llm_server_url = QLineEdit(llm_server_url)
        oc_layout.addWidget(QLabel("Model ID:"))
        oc_layout.addWidget(self._llm_model_id)
        oc_layout.addWidget(QLabel("API Key:"))
        oc_layout.addWidget(self._llm_api_key)
        oc_layout.addWidget(QLabel("Server URL:"))
        oc_layout.addWidget(self._llm_server_url)
        llm_layout.addWidget(self._opencode_widget)

        # Ollama fields
        self._ollama_widget = QWidget()
        ol_layout = QVBoxLayout(self._ollama_widget)
        ol_layout.setContentsMargins(0, 0, 0, 0)
        self._ollama_url_edit = QLineEdit(ollama_url)
        self._ollama_model_edit = QLineEdit(ollama_model)
        self._ollama_status_label = QLabel(f"Status: {ollama_status}" if ollama_status else "Status: unknown")
        self._ollama_restart_btn = QPushButton("Restart Ollama")
        ol_layout.addWidget(QLabel("Ollama URL:"))
        ol_layout.addWidget(self._ollama_url_edit)
        ol_layout.addWidget(QLabel("Model:"))
        ol_layout.addWidget(self._ollama_model_edit)
        ol_layout.addWidget(self._ollama_status_label)
        ol_layout.addWidget(self._ollama_restart_btn)
        llm_layout.addWidget(self._ollama_widget)

        # Show correct widget based on provider
        self._on_provider_changed(provider_idx)

        tab4_layout.addWidget(llm_group)
```

Add helper methods:
```python
    def _is_ollama_installed(self) -> bool:
        import shutil
        if shutil.which("ollama"):
            return True
        extra = ["C:\\Program Files\\Ollama\\ollama.exe",
                 "C:\\Program Files (x86)\\Ollama\\ollama.exe"]
        return any(Path(p).exists() for p in extra)

    def _on_provider_changed(self, index: int) -> None:
        is_ollama = self._provider_combo.currentData() == "ollama"
        self._opencode_widget.setVisible(not is_ollama)
        self._ollama_widget.setVisible(is_ollama)
        self.value_changed.emit()
```

Add import:
```python
from PyQt6.QtWidgets import QPushButton
from pathlib import Path
```

Update `get_values()` to include provider fields:
```python
            "LLM_PROVIDER": self._provider_combo.currentData(),
            "OLLAMA_URL": self._ollama_url_edit.text(),
            "OLLAMA_MODEL": self._ollama_model_edit.text(),
```

- [ ] **Step 2: Run settings dialog tests**

```
py -m pytest tests/test_settings_dialog.py -v
Expected: all pass
```

- [ ] **Step 3: Commit**

```
git add src/ui/settings_dialog.py
git commit -m "feat: add Ollama provider selector to Settings → Connections"
```

---

### Task 6: PetWindow — Provider Dispatch

**Files:**
- Modify: `src/ui/pet_window.py`

- [ ] **Step 1: Add provider initialization in __init__**

After config loading, add:
```python
        self._llm_provider = self._config.get("llm", {}).get("provider", "opencode")
        self._ollama_manager: "OllamaManager | None" = None

        if self._llm_provider == "ollama":
            from src.llm.ollama_manager import OllamaManager
            self._ollama_manager = OllamaManager(
                modelfile_path=self._config.get("llm", {}).get("modelfile_path", "data/Modelfile"),
                model_name=self._config.get("llm", {}).get("ollama_model", "daemon-local"),
                ollama_url=self._config.get("llm", {}).get("ollama_url", "http://127.0.0.1:11434"),
                parent=self,
            )
            self._ollama_manager.ready.connect(self._on_ollama_ready)
            self._ollama_manager.error_occurred.connect(self._on_ollama_error)
            self._ollama_manager.start()
```

- [ ] **Step 2: Add Ollama signal handlers**

```python
    def _on_ollama_ready(self) -> None:
        logger.info("Ollama provider ready")

    def _on_ollama_error(self, msg: str) -> None:
        logger.warning("Ollama provider error: %s", msg)
        self._show_bubble(f"Kenny's brain is offline: {msg}")
```

- [ ] **Step 3: Add factory helper + replace 5 instantiation points**

Add a helper method to PetWindow:

```python
    def _make_llm_worker(self, **kw: Any) -> Any:
        if self._llm_provider == "ollama":
            from src.llm.ollama_worker import OllamaWorker
            kw.pop("session_id", None)
            kw.pop("schema", None)
            kw.pop("user_input", None)
            worker = OllamaWorker(
                prompt=kw.pop("prompt", ""),
                is_autonomous=kw.pop("is_autonomous", False),
                pet_id=self._pet_id,
                parent=self,
            )
            worker.tool_call_requested.connect(self._on_ollama_tool_call)
            return worker
        from src.llm.opencode_worker import OpencodeWorker
        return OpencodeWorker(parent=self, **kw)
```

Add import at top of file: `from typing import Any`

Replace the 5 instantiation points. Each one changes `OpencodeWorker(...)` → `self._make_llm_worker(...)`:

**Line 769-774** (summary worker):
```python
        from src.llm import OpencodeWorker
        self._summary_worker = OpencodeWorker(
            user_input="",
            prompt=prompt,
            is_autonomous=True
        )
```
→
```python
        self._summary_worker = self._make_llm_worker(
            user_input="",
            prompt=prompt,
            is_autonomous=True,
        )
```

**Line 891-895** (code analysis):
```python
        from src.llm.opencode_worker import OpencodeWorker
        worker = OpencodeWorker(
            prompt=prompt, session_id=None,
            schema=CODE_ANALYSIS_SCHEMA, is_autonomous=True,
        )
```
→
```python
        worker = self._make_llm_worker(
            prompt=prompt, session_id=None,
            schema=CODE_ANALYSIS_SCHEMA, is_autonomous=True,
        )
```

**Line 2092-2095** (multiplexed):
```python
        worker = OpencodeWorker(
            user_input="", prompt=prompt, is_autonomous=True,
            session_id=self._opencode_session_id,
        )
```
→
```python
        worker = self._make_llm_worker(
            user_input="", prompt=prompt, is_autonomous=True,
            session_id=self._opencode_session_id,
        )
```

**Line 2424-2427** (main query):
```python
        worker = OpencodeWorker(
            prompt=prompt,
            is_autonomous=is_autonomous,
        )
```
→
```python
        worker = self._make_llm_worker(
            prompt=prompt,
            is_autonomous=is_autonomous,
        )
```

**Line 2748-2753** (refill):
```python
        worker = OpencodeWorker(
            "",
            is_autonomous=True,
            session_id=None,
            prompt=single_prompt,
        )
```
→
```python
        worker = self._make_llm_worker(
            "", is_autonomous=True, session_id=None,
            prompt=single_prompt,
        )
```

- [ ] **Step 4: Add tool call handler for Ollama tools**

```python
    def _on_ollama_tool_call(self, name: str, args: dict) -> None:
        if name == "change_visual_state":
            action = args.get("action", "idle")
            target_x = args.get("target_x")
            target_y = args.get("target_y")
            self._fsm_bridge.emit_request("triggered_action", action, target_x, target_y)
        elif name == "send_system_toast":
            title = args.get("title", "Daemon")
            message = args.get("message", "")
            self._fsm_bridge.emit_toast(title, message)
```

- [ ] **Step 5: Update _open_settings to pass provider state**

```python
            dialog = SettingsDialog(
                ...
                llm_provider=self._llm_provider,
                ollama_url=self._config.get("llm", {}).get("ollama_url", "http://127.0.0.1:11434"),
                ollama_model=self._config.get("llm", {}).get("ollama_model", "daemon-local"),
                ollama_status="ready" if (self._ollama_manager and hasattr(self._ollama_manager, '_process') and self._ollama_manager._process) else "",
                ...
            )
```

- [ ] **Step 6: Commit**

```
git add src/ui/pet_window.py
git commit -m "feat: wire Ollama provider dispatch into PetWindow"
```

---

### Task 7: daemon.py — Gate opencode serve on provider

**Files:**
- Modify: `daemon.py`

- [ ] **Step 1: Skip ensure_opencode_serve_running when ollama**

Find the `ensure_opencode_serve_running()` call and gate it:

```python
    if not args.no_opencode and provider != "ollama":
        ensure_opencode_serve_running()
```

Where `provider` comes from config after `load_config()`.

- [ ] **Step 2: Commit**

```
git add daemon.py
git commit -m "fix: skip opencode serve startup when using Ollama provider"
```

---

### Task 8: LLM __init__ exports

**Files:**
- Modify: `src/llm/__init__.py`

- [ ] **Step 1: Add exports**

```python
from .ollama_worker import OllamaWorker
from .ollama_manager import OllamaManager

__all__ = [
    "ContextManager",
    "OpencodeWorker",
    "OllamaWorker",
    "OllamaManager",
    "extract_dialogue_stream",
]
```

- [ ] **Step 2: Commit**

```
git add src/llm/__init__.py
git commit -m "chore: export OllamaWorker and OllamaManager from llm package"
```

---

### Task 9: Integration Tests + Full Suite

**Files:**
- Modify: `tests/test_pet_window.py` (or existing integration test file)

- [ ] **Step 1: Run full test suite**

```
py -m pytest tests/ -v --timeout=60 2>&1
```

Fix any failures from the context_manager persona removal (tests may check for persona strings in prompts).

- [ ] **Step 2: Commit final tweaks**

```
git add -A
git commit -m "fix: update tests for persona-free context_manager prompts"
```
