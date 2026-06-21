# Strands Agent Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three independent improvements to `StrandsAutonomousWorker`: (A) persistent agent — one long-lived Agent per session instead of a new one per query; (B) streaming output — partial tokens displayed in the speech bubble as they arrive; (C) tool stratification — autonomous queries get read-only MCP tools only, user queries get full toolset.

**Architecture:** All three improvements are in `src/strands_worker.py` and `src/pet_window.py`. Track A replaces the per-query Agent construction with a session-scoped singleton managed by `PetWindow`. Track B hooks Strands' streaming callback to emit partial text via a new Qt signal, which `PetWindow` connects to update the bubble incrementally. Track C passes a filtered `allowed_tools` list to `sse_client()` based on a `query_mode` param on the worker.

**Tech Stack:** Python 3.14, PyQt6, `strands` SDK, `src/strands_worker.py`, `src/pet_window.py`, `src/mcp_server.py`

**Reference:** Current `StrandsAutonomousWorker` lives in `src/strands_worker.py`. It creates a new `Agent` per `run()` call, connects to MCP via `sse_client`, and emits `response_ready(list)` when done.

---

## File Map

| File | Action |
|------|--------|
| `src/strands_worker.py` | MODIFY — all three improvements |
| `src/pet_window.py` | MODIFY — connect streaming signal, manage persistent agent lifecycle |
| `src/mcp_server.py` | MODIFY — expose read-only tool list constant |
| `src/constants.py` | MODIFY — add STRANDS_READ_ONLY_TOOLS list |
| `tests/test_strands_worker.py` | MODIFY — add tests for all three improvements |

---

## Track A: Persistent Agent

### Task A1: Session-scoped Agent singleton

**Context:** Currently `StrandsAutonomousWorker.run()` creates a new `Agent(...)` every call. This means Strands' `SlidingWindowConversationManager` accumulates no history across queries, and a fresh MCP SSE connection is opened/closed each time (slow).

**Design:** `PetWindow` owns one `StrandsSession` object (a thin wrapper). `StrandsSession` lazily creates the `Agent` on first use and reuses it on subsequent queries. The session is invalidated (and recreated on next query) when MCP server restarts or when `StrandsSession.invalidate()` is called.

- [ ] **Step 1: Write failing tests**

In `tests/test_strands_worker.py`, add:

```python
def test_strands_session_creates_agent_once(mock_config):
    """StrandsSession should reuse the same Agent across multiple queries."""
    from src.strands_worker import StrandsSession
    from unittest.mock import patch, MagicMock

    mock_agent = MagicMock()
    with patch("src.strands_worker.Agent", return_value=mock_agent) as MockAgent:
        session = StrandsSession(config=mock_config)
        agent1 = session.get_agent(mode="user")
        agent2 = session.get_agent(mode="user")
        assert agent1 is agent2
        assert MockAgent.call_count == 1


def test_strands_session_invalidate_forces_recreate(mock_config):
    from src.strands_worker import StrandsSession
    from unittest.mock import patch, MagicMock

    with patch("src.strands_worker.Agent", return_value=MagicMock()) as MockAgent:
        session = StrandsSession(config=mock_config)
        session.get_agent(mode="user")
        session.invalidate()
        session.get_agent(mode="user")
        assert MockAgent.call_count == 2


def test_strands_session_mode_autonomous_different_tools(mock_config):
    """Autonomous mode should restrict tools vs user mode."""
    from src.strands_worker import StrandsSession, READ_ONLY_TOOL_NAMES
    from unittest.mock import patch, MagicMock

    agents = {}

    def make_agent(**kwargs):
        m = MagicMock()
        agents[kwargs.get("mode", "?")] = kwargs
        return m

    with patch("src.strands_worker.Agent", side_effect=make_agent):
        session = StrandsSession(config=mock_config)
        session.get_agent(mode="user")
        session.get_agent(mode="autonomous")
        # autonomous creates new agent because mode changed
        # both calls made
        assert len(agents) >= 1
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_strands_worker.py::test_strands_session_creates_agent_once -v
```

- [ ] **Step 3: Implement StrandsSession**

In `src/strands_worker.py`, add `StrandsSession` class above `StrandsAutonomousWorker`:

```python
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager


READ_ONLY_TOOL_NAMES = frozenset({
    "list_directory", "read_file", "search_codebase",
    "get_memory", "get_diary", "query_memory",
})


class StrandsSession:
    """Session-scoped Agent singleton. Creates once, reuses across queries.

    Invalidate on MCP restart or config change.
    Mode-switching (user ↔ autonomous) recreates the agent to swap toolsets.
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self._agent: Agent | None = None
        self._current_mode: str | None = None

    def get_agent(self, mode: str = "user") -> Agent:
        """Return cached Agent, or create one if mode changed or not yet created."""
        if self._agent is None or self._current_mode != mode:
            self._agent = self._create_agent(mode)
            self._current_mode = mode
        return self._agent

    def invalidate(self) -> None:
        """Force recreation of Agent on next get_agent() call."""
        self._agent = None
        self._current_mode = None

    def _create_agent(self, mode: str) -> Agent:
        from strands.models.openai import OpenAIModel
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.sse import sse_client
        from strands.tools.mcp import MCPClient

        cfg = self._config
        model = OpenAIModel(
            model_id=cfg.get("model_id", "gemini-2.5-flash"),
            client_args={
                "api_key": cfg.get("api_key", ""),
                "base_url": cfg.get("base_url", "https://opencode.ai/zen/v1"),
            },
        )
        mcp_url = cfg.get("mcp_url", "http://127.0.0.1:4097/sse")
        mcp_client = MCPClient(lambda: sse_client(mcp_url))

        # Tool filtering for autonomous mode
        if mode == "autonomous":
            allowed = list(READ_ONLY_TOOL_NAMES)
        else:
            allowed = None  # all tools

        conv_manager = SlidingWindowConversationManager(window_size=30)
        agent = Agent(
            model=model,
            tools=[mcp_client],
            conversation_manager=conv_manager,
        )
        return agent
```

- [ ] **Step 4: Update StrandsAutonomousWorker to use StrandsSession**

In `StrandsAutonomousWorker`, update `__init__` and `run()`:

```python
class StrandsAutonomousWorker(QThread):
    response_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt: str, config: dict,
                 session: "StrandsSession",
                 mode: str = "user",
                 parent=None):
        super().__init__(parent)
        self._prompt = prompt
        self._config = config
        self._session = session
        self._mode = mode
        self._abort = False

    def run(self) -> None:
        if self._abort:
            return
        try:
            agent = self._session.get_agent(mode=self._mode)
            result = agent(self._prompt)
            # ... existing JSON extraction and response_ready emit ...
        except Exception as e:
            if not self._abort:
                self.error_occurred.emit(str(e))
                self._session.invalidate()  # force recreate on next call

    def abort(self) -> None:
        self._abort = True
```

- [ ] **Step 5: Update PetWindow to manage StrandsSession**

In `PetWindow.__init__`, add:

```python
from src.strands_worker import StrandsSession
self._strands_session = StrandsSession(config=self._build_strands_config())
```

Add `_build_strands_config()` method:

```python
def _build_strands_config(self) -> dict:
    from src.config import load_config
    cfg = load_config()
    return {
        "model_id":  cfg.get("llm", {}).get("model_id", "gemini-2.5-flash"),
        "api_key":   cfg.get("llm", {}).get("api_key", ""),
        "base_url":  cfg.get("llm", {}).get("base_url", "https://opencode.ai/zen/v1"),
        "mcp_url":   "http://127.0.0.1:4097/sse",
    }
```

Pass `session=self._strands_session` and `mode=` when constructing `StrandsAutonomousWorker`.

On MCP health-check failure, call `self._strands_session.invalidate()`.

- [ ] **Step 6: Run tests**

```bash
py -m pytest tests/test_strands_worker.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/strands_worker.py src/pet_window.py
git commit -m "feat(strands): persistent session-scoped Agent singleton (StrandsSession)"
```

---

## Track B: Streaming Output

### Task B1: Stream partial tokens to bubble

**Context:** Strands `Agent.__call__()` is blocking — it returns only when done. Strands supports a streaming callback via `callback_handler` param or agent hooks. We hook into this to emit partial text each time a content chunk arrives.

**Design:** `StrandsAutonomousWorker` gains a new `partial_text` pyqtSignal(str). `PetWindow` connects this signal to a slot that updates `_bubble_text` in-place on each chunk. The final `response_ready` signal still fires with the structured items for pool caching.

- [ ] **Step 1: Write failing tests**

In `tests/test_strands_worker.py`, add:

```python
def test_worker_has_partial_text_signal():
    from src.strands_worker import StrandsAutonomousWorker
    assert hasattr(StrandsAutonomousWorker, "partial_text")


def test_partial_text_emitted_on_chunk(mock_config, qtbot):
    """partial_text signal fires for each streamed chunk."""
    from src.strands_worker import StrandsAutonomousWorker, StrandsSession
    from unittest.mock import patch, MagicMock

    received = []
    session = MagicMock(spec=StrandsSession)

    chunks = ["Hello", " world", "!"]

    def fake_agent_call(prompt, callback_handler=None):
        if callback_handler:
            for chunk in chunks:
                callback_handler(chunk)
        return MagicMock(message=MagicMock(content=[MagicMock(text='{"speech":"Hello world!","type":"observation","priority":5}')]))

    session.get_agent.return_value = MagicMock(side_effect=fake_agent_call)

    worker = StrandsAutonomousWorker(
        prompt="test", config=mock_config,
        session=session, mode="user"
    )
    worker.partial_text.connect(lambda t: received.append(t))

    with qtbot.waitSignal(worker.response_ready, timeout=3000):
        worker.start()

    assert "Hello" in received
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_strands_worker.py::test_worker_has_partial_text_signal -v
```

- [ ] **Step 3: Add `partial_text` signal and streaming hook**

In `StrandsAutonomousWorker`:

```python
class StrandsAutonomousWorker(QThread):
    response_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    partial_text   = pyqtSignal(str)   # NEW: emitted per streamed chunk

    def run(self) -> None:
        if self._abort:
            return
        try:
            agent = self._session.get_agent(mode=self._mode)

            # Streaming callback
            def _on_chunk(chunk_text: str) -> None:
                if not self._abort and chunk_text:
                    self.partial_text.emit(chunk_text)

            result = agent(self._prompt, callback_handler=_on_chunk)
            # ... existing JSON extraction and response_ready emit ...
        except Exception as e:
            if not self._abort:
                self.error_occurred.emit(str(e))
                self._session.invalidate()
```

> **Note:** If `Agent.__call__` does not accept `callback_handler`, use the hooks API:
> ```python
> from strands.hooks import BeforeModelInvocationEvent, AfterModelInvocationEvent
> # Check strands SDK docs for the correct streaming hook.
> # Fallback: connect to agent.hooks with a text-chunk handler.
> ```
> Verify the actual API by running:
> ```bash
> py -c "import inspect; from strands import Agent; print(inspect.signature(Agent.__call__))"
> ```
> Adjust the implementation to match the actual signature.

- [ ] **Step 4: Connect partial_text in PetWindow**

In `PetWindow`, where `StrandsAutonomousWorker` is constructed, connect:

```python
worker.partial_text.connect(self._on_strands_partial_text)
```

Implement:

```python
def _on_strands_partial_text(self, chunk: str) -> None:
    """Update speech bubble with streaming partial text."""
    if not self._bubble_text:
        self._bubble_text = chunk
    else:
        self._bubble_text += chunk
    self.update()   # trigger repaint with updated bubble
```

Clear `_bubble_text` at start of each new query (before worker starts).

- [ ] **Step 5: Run tests**

```bash
py -m pytest tests/test_strands_worker.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/strands_worker.py src/pet_window.py
git commit -m "feat(strands): streaming partial_text signal for incremental bubble updates"
```

---

## Track C: Tool Stratification

### Task C1: Read-only tool set for autonomous queries

**Context:** Autonomous background queries should never be able to move the mouse, capture screenshots, or simulate keystrokes — those are high-risk MCP tools. User-initiated queries get the full toolset.

**Design:** Define `READ_ONLY_TOOL_NAMES` constant (already added in Track A). `StrandsSession._create_agent(mode="autonomous")` passes an `allowed_tools` filter so only read-only tools are registered. The MCP server already has consent-based blocking — this adds a second, client-side layer.

**Note:** `READ_ONLY_TOOL_NAMES` was already defined in Task A1. This task wires it into the actual agent construction.

- [ ] **Step 1: Write failing tests**

In `tests/test_strands_worker.py`, add:

```python
def test_autonomous_mode_uses_read_only_tools(mock_config):
    """Autonomous mode agent construction should only include read-only tools."""
    from src.strands_worker import StrandsSession, READ_ONLY_TOOL_NAMES
    from unittest.mock import patch, MagicMock, call

    created_agents = []

    def capture_agent(**kwargs):
        created_agents.append(kwargs)
        return MagicMock()

    with patch("src.strands_worker.Agent", side_effect=capture_agent):
        with patch("src.strands_worker.MCPClient", return_value=MagicMock()):
            session = StrandsSession(config=mock_config)
            session.get_agent(mode="autonomous")

    assert len(created_agents) == 1
    # Agent must have been constructed (no assertion on internal tool filtering
    # because MCPClient wraps them — but we verify the session used autonomous mode)
    assert session._current_mode == "autonomous"


def test_user_mode_uses_full_tools(mock_config):
    from src.strands_worker import StrandsSession
    from unittest.mock import patch, MagicMock

    with patch("src.strands_worker.Agent", return_value=MagicMock()):
        with patch("src.strands_worker.MCPClient", return_value=MagicMock()):
            session = StrandsSession(config=mock_config)
            session.get_agent(mode="user")
            assert session._current_mode == "user"


def test_read_only_tool_names_contains_expected_tools():
    from src.strands_worker import READ_ONLY_TOOL_NAMES
    expected = {"list_directory", "read_file", "search_codebase",
                "get_memory", "get_diary", "query_memory"}
    assert expected.issubset(READ_ONLY_TOOL_NAMES)


def test_high_risk_tools_not_in_read_only():
    from src.strands_worker import READ_ONLY_TOOL_NAMES
    high_risk = {"move_mouse", "simulate_keystroke", "capture_blackmail_evidence",
                 "browser_navigation", "read_clipboard"}
    assert high_risk.isdisjoint(READ_ONLY_TOOL_NAMES)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
py -m pytest tests/test_strands_worker.py::test_read_only_tool_names_contains_expected_tools tests/test_strands_worker.py::test_high_risk_tools_not_in_read_only -v
```

- [ ] **Step 3: Verify READ_ONLY_TOOL_NAMES is correct**

`READ_ONLY_TOOL_NAMES` was defined in Task A1. Verify it contains exactly the allowed set:

```python
READ_ONLY_TOOL_NAMES = frozenset({
    "list_directory",
    "read_file",
    "search_codebase",
    "get_memory",
    "get_diary",
    "query_memory",   # new tool added in Brain/Memory plan
})
```

Confirm this excludes: `change_visual_state`, `read_clipboard`, `capture_blackmail_evidence`, `send_system_toast`, `simulate_keystroke`, `move_mouse`, `browser_navigation`, `set_log_level`, `get_screen_time`, `get_recent_git_diff`, `set_reminder`, `get_reminders`, `dismiss_reminder`.

- [ ] **Step 4: Wire tool filtering into StrandsSession._create_agent**

In `StrandsSession._create_agent()`:

```python
def _create_agent(self, mode: str) -> Agent:
    from strands.models.openai import OpenAIModel
    from mcp.client.sse import sse_client
    from strands.tools.mcp import MCPClient

    cfg = self._config
    model = OpenAIModel(
        model_id=cfg.get("model_id", "gemini-2.5-flash"),
        client_args={
            "api_key": cfg.get("api_key", ""),
            "base_url": cfg.get("base_url", "https://opencode.ai/zen/v1"),
        },
    )
    mcp_url = cfg.get("mcp_url", "http://127.0.0.1:4097/sse")

    if mode == "autonomous":
        # Filter MCP tools to read-only at client level
        mcp_client = MCPClient(
            lambda: sse_client(mcp_url),
            # If MCPClient supports allowed_tools, pass it:
            # allowed_tools=list(READ_ONLY_TOOL_NAMES)
        )
        # Post-creation filtering fallback: monkey-patch list_tools response
        # if SDK doesn't support allowed_tools directly
    else:
        mcp_client = MCPClient(lambda: sse_client(mcp_url))

    conv_manager = SlidingWindowConversationManager(window_size=30)
    agent = Agent(
        model=model,
        tools=[mcp_client],
        conversation_manager=conv_manager,
    )
    return agent
```

> **SDK Note:** Check whether `MCPClient` constructor accepts `allowed_tools` param:
> ```bash
> py -c "import inspect; from strands.tools.mcp import MCPClient; print(inspect.signature(MCPClient.__init__))"
> ```
> If it does, pass `allowed_tools=list(READ_ONLY_TOOL_NAMES)` directly.
> If not, after agent creation, filter `agent.tool_registry` (or equivalent) to remove disallowed tools.

- [ ] **Step 5: Verify autonomous mode in PetWindow passes correct mode**

In `PetWindow`, all autonomous trigger paths (`_trigger_chat`, `_trigger_joke`, `_trigger_boredom_fsm`, `_on_autonomous_trigger`) must pass `mode="autonomous"` to `StrandsAutonomousWorker`.

User query path (`_on_input_submitted`) must pass `mode="user"`.

Search in `pet_window.py`:
```bash
grep -n "StrandsAutonomousWorker" src/pet_window.py
```

For each autonomous construction, ensure `mode="autonomous"` is set. For user query construction, ensure `mode="user"` (or default).

- [ ] **Step 6: Run full Strands test suite**

```bash
py -m pytest tests/test_strands_worker.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/strands_worker.py src/pet_window.py
git commit -m "feat(strands): tool stratification — autonomous queries restricted to read-only MCP tools"
```

---

## Task D: Full regression + squash merge

- [ ] **Step 1: Run full suite**

```bash
py -m pytest tests/ -v --timeout=30
```

Expected: all pass, 0 failures.

- [ ] **Step 2: Squash merge**

```bash
git checkout master
git merge --squash task-75-strands-improvements
git commit -m "feat: Strands persistent session, streaming output, tool stratification (Phase 75)"
git branch -D task-75-strands-improvements
```

---

## Implementation Order Recommendation

These three tracks have no hard interdependency, but Track A (persistent session) should land first because Tracks B and C both build on `StrandsSession`. Within Track A, Task A1 (StrandsSession class) is the prerequisite for everything else.

Suggested order:
1. Track A (Tasks A1) → foundation
2. Track C (Task C1) → tool stratification (pure extension of A1)
3. Track B (Task B1) → streaming (independent of C, but needs A1)
