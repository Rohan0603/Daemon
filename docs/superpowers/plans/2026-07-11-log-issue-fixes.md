# Daemon Log-Issue Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three concrete defects found by analyzing `logs/daemon_2026-07-10_23-16-42.log` so autonomous behavior, the local-LLM path, and clean shutdown all work reliably.

**Architecture:** Three independent, single-file fixes. (1) Harden the autonomous debounce gate so a mismatched seed clock can never permanently block triggers. (2) Stop the OllamaWorker garbage-filter from discarding valid (nickname-only / terse) replies. (3) Replace the non-existent `FastMCP.shutdown()` call with a controllable `uvicorn.Server` handle so Ghost-Mode shutdown stops the MCP server cleanly.

**Tech Stack:** Python 3.14, PyQt6 (QThread), `mcp` (FastMCP), `uvicorn`, `pytest` (unittest style), `unittest.mock`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `src/autonomy/behavior_controller.py` | Pure-logic autonomous behavior (zero Qt imports). | `_should_fire_autonomous` debounce guard at lines 649-653. |
| `tests/test_behavior_controller.py` | Unit tests for `BehaviorController`. | New `TestDebounceClockSafety` class. |
| `src/llm/ollama_worker.py` | Stateless Ollama HTTP bridge + JSON parser. | `_filter_garbage_items` at lines 443-459. |
| `tests/test_ollama_worker.py` | Unit tests for `OllamaWorker`. | New `TestGarbageFilterNickname` class. |
| `src/mcp_server.py` | `MCPServerThread` (QThread) hosting the FastMCP SSE server. | `run()` (106-129) + `stop()` (131-140) + `__init__` (102). |
| `tests/test_mcp_server.py` | Unit tests for `MCPServerThread`. | New `TestMCPServerThreadStop` class. |

Existing test factories (`_make_controller` in `test_behavior_controller.py`, `OllamaWorker(prompt=..., pet_id=...)` in `test_ollama_worker.py`) and `Mock(spec=MCPServerThread)` patterns are reused — do not reinvent them.

---

## Task 1: Harden autonomous debounce against clock-seed mismatch

**Why:** The log shows 102 `[active_chat] Skipping: debounce (-1783684981.9s < 15s)` events. The seed value (`_last_autonomous_fire_time`) was an epoch (`time.time()` ≈ 1.78e9) while the comparison uses `time.monotonic()` (~2e4). `elapsed` becomes a huge negative, so `elapsed < 15.0` is *always* true and every autonomous trigger is blocked for the whole session. Current source already seeds with `time.monotonic()`, but a stale `.pyc` or any future regression can reintroduce a mismatched seed. The fix makes the gate clock-agnostic: only block when `elapsed` is genuinely in the positive 0–15s window.

**Files:**
- Modify: `src/autonomy/behavior_controller.py:649-653`
- Test: `tests/test_behavior_controller.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_behavior_controller.py`:

```python
class TestDebounceClockSafety(unittest.TestCase):
    """Regression: a mismatched/epoch seed must NOT permanently block firing."""

    def test_epoch_seed_does_not_permanently_block(self):
        controller = _make_controller(opencode_enabled=True)
        # Simulate the stale-.pyc bug: seed with an epoch (time.time()) value.
        controller._last_autonomous_fire_time = time.time()
        controller._autonomous_query_pending = False
        self.assertTrue(
            controller._should_fire_autonomous("active_chat"),
            "epoch seed must not permanently block firing",
        )

    def test_recent_monotonic_seed_blocks_within_window(self):
        controller = _make_controller(opencode_enabled=True)
        controller._last_autonomous_fire_time = time.monotonic()
        controller._autonomous_query_pending = False
        self.assertFalse(
            controller._should_fire_autonomous("active_chat"),
            "recent fire must still be debounced within 15s",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `py -m pytest tests/test_behavior_controller.py::TestDebounceClockSafety -v`
Expected: `test_epoch_seed_does_not_permanently_block` FAILS (returns `False` because `elapsed` is hugely negative and `< 15.0`). `test_recent_monotonic_seed_blocks_within_window` PASSES (already correct).

- [ ] **Step 3: Apply the minimal fix**

In `src/autonomy/behavior_controller.py`, replace lines 650-653:

```python
        elapsed = time.monotonic() - self._last_autonomous_fire_time
        if elapsed < 15.0:
            logger.debug("[%s] Skipping: debounce (%.1fs < 15s)", mode, elapsed)
            return False
```

with:

```python
        elapsed = time.monotonic() - self._last_autonomous_fire_time
        # Guard against a mismatched seed clock (e.g. an epoch value from
        # time.time() left by a stale .pyc). A hugely negative `elapsed` would
        # otherwise make `elapsed < 15.0` always true and permanently block all
        # autonomous triggers. Only block inside the genuine positive 0-15s window.
        if 0 <= elapsed < 15.0:
            logger.debug("[%s] Skipping: debounce (%.1fs < 15s)", mode, elapsed)
            return False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m pytest tests/test_behavior_controller.py::TestDebounceClockSafety -v`
Expected: Both tests PASS.

- [ ] **Step 5: Run the full behavior_controller suite (no regressions)**

Run: `py -m pytest tests/test_behavior_controller.py -v`
Expected: All tests PASS (the existing `test_should_fire_*` tests still expect `False` right after a fresh monotonic seed, which holds).

- [ ] **Step 6: Commit**

```bash
git add src/autonomy/behavior_controller.py tests/test_behavior_controller.py
git commit -m "fix: harden autonomous debounce against mismatched seed clock"
```

---

## Task 2: Stop OllamaWorker garbage-filter from discarding valid replies

**Why:** `ollama_worker.py:_filter_garbage_items` drops any item whose `dialogue` equals the user nickname (`"garbage meat"`) or is `"..."`. The weak local model (`llama3.2-1b-q8`) frequently returns `{"dialogue": "garbage meat", ...}` or `{"dialogue": "..."}`, so the filter discards a large fraction of otherwise-valid replies → refill failures → `ThoughtPool refill failed, pool has 0 items`. The persona is *supposed* to address the user by nickname, so nickname-only replies are legitimate. Pure-punctuation strings (which already cover `"..."`) should still be dropped.

**Files:**
- Modify: `src/llm/ollama_worker.py:443-459`
- Test: `tests/test_ollama_worker.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ollama_worker.py`:

```python
class TestGarbageFilterNickname(unittest.TestCase):
    def test_nickname_only_dialogue_is_kept(self):
        worker = OllamaWorker(prompt="hi", pet_id="kenny")
        items = [{"dialogue": "garbage meat", "thought": "finally talked to me"}]
        self.assertTrue(worker._filter_garbage_items(items))
        self.assertEqual(len(items), 1)

    def test_pure_punctuation_still_dropped(self):
        worker = OllamaWorker(prompt="hi", pet_id="kenny")
        items = [{"dialogue": "...", "thought": "x"}]
        self.assertFalse(worker._filter_garbage_items(items))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `py -m pytest tests/test_ollama_worker.py::TestGarbageFilterNickname -v`
Expected: `test_nickname_only_dialogue_is_kept` FAILS (`_filter_garbage_items` returns `False` because `"garbage meat" == nickname`). `test_pure_punctuation_still_dropped` PASSES.

- [ ] **Step 3: Apply the minimal fix**

In `src/llm/ollama_worker.py`, replace the body of `_filter_garbage_items` (lines 443-459):

```python
    def _filter_garbage_items(self, items: list[dict]) -> bool:
        nickname = self._get_user_nickname().lower().strip()
        valid = []
        for item in items:
            d = item.get("dialogue", "").strip()
            if not d or len(d) < 2:
                continue
            d_lower = d.lower()
            if d_lower in (".", "..", "...", "…", "?", "??", "!!!", "garbage meat"):
                continue
            if d_lower == nickname:
                continue
            if re.fullmatch(r'[\s.,!?…\-_]+', d):
                continue
            valid.append(item)
        items[:] = valid
        return len(valid) > 0
```

with:

```python
    def _filter_garbage_items(self, items: list[dict]) -> bool:
        valid = []
        for item in items:
            d = item.get("dialogue", "").strip()
            if not d or len(d) < 2:
                continue
            # Do NOT drop a reply merely because it equals the user's nickname
            # or reads as "...". The persona legitimately addresses the user by
            # nickname, and weak local models emit terse replies. Only drop
            # contentless punctuation-only strings.
            if re.fullmatch(r'[\s.,!?…\-_]+', d):
                continue
            valid.append(item)
        items[:] = valid
        return len(valid) > 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -m pytest tests/test_ollama_worker.py::TestGarbageFilterNickname -v`
Expected: Both tests PASS.

- [ ] **Step 5: Run the full ollama_worker suite (no regressions)**

Run: `py -m pytest tests/test_ollama_worker.py -v`
Expected: All tests PASS (confirm `_parse_response` / `test_parse_garbage_falls_back_to_freeform` still behave).

- [ ] **Step 6: Commit**

```bash
git add src/llm/ollama_worker.py tests/test_ollama_worker.py
git commit -m "fix: keep valid nickname/terse replies in OllamaWorker garbage filter"
```

---

## Task 3: Fix FastMCP server shutdown (`AttributeError`)

**Why:** `mcp_server.py:136` calls `self._server.shutdown()` on a `FastMCP` object, which has no `shutdown` method → `'FastMCP' object has no attribute 'shutdown'` at Ghost-Mode shutdown. The MCP SSE thread is then left dangling (only dies because it is a daemon thread). Fix: run the SSE app through a `uvicorn.Server` we control, and stop it by setting `should_exit = True`.

**Files:**
- Modify: `src/mcp_server.py:102` (`__init__`), `106-129` (`run`), `131-140` (`stop`)
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mcp_server.py` (reuse the `Mock(spec=MCPServerThread)` style already in the file):

```python
class TestMCPServerThreadStop(unittest.TestCase):
    def test_stop_exits_uvicorn_without_attributeerror(self):
        from src.mcp_server import MCPServerThread
        t = MCPServerThread()
        fake_uvicorn = unittest.mock.MagicMock()
        real_server = unittest.mock.MagicMock()  # stands in for FastMCP app
        t._uvicorn_server = fake_uvicorn
        t._server = real_server
        # Must not raise 'FastMCP' object has no attribute 'shutdown',
        # and must signal uvicorn to exit rather than calling .shutdown().
        t.stop()
        self.assertTrue(fake_uvicorn.should_exit)
        real_server.shutdown.assert_not_called()
        self.assertTrue(t._stop_event)
        self.assertIsNone(t._server)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -m pytest tests/test_mcp_server.py::TestMCPServerThreadStop -v`
Expected: FAILS — `real_server.shutdown.assert_not_called()` errors (old `stop()` calls `self._server.shutdown()`), and `fake_uvicorn.should_exit` is never set.

- [ ] **Step 3: Apply the fix**

In `src/mcp_server.py`:

(a) Add a handle in `__init__` (after line 102 `self._server = None`):

```python
        self._server = None
        self._uvicorn_server = None
```

(b) Replace `run()` (lines 106-129):

```python
    def run(self):
        """Start the FastMCP SSE server."""
        logger.info("Starting FastMCP SSE server thread")
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            logger.debug("pythoncom not available, continuing without CoInitialize")

        app = _create_fastmcp_app(self)
        self._server = app
        import uvicorn
        config = uvicorn.Config(
            app.sse_app(), host="127.0.0.1", port=4097, log_level="error"
        )
        self._uvicorn_server = uvicorn.Server(config)
        try:
            logger.info("Starting FastMCP SSE server on port 4097")
            self._uvicorn_server.run()
        except Exception as e:
            logger.error("FastMCP SSE server error: %s", e)
            raise
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except (AttributeError, ImportError):
                pass
```

(c) Replace `stop()` (lines 131-140):

```python
    def stop(self):
        """Stop the FastMCP SSE server."""
        logger.info("Stopping FastMCP SSE server")
        server = getattr(self, "_uvicorn_server", None)
        if server is not None:
            server.should_exit = True
        self._server = None
        self._stop_event = True
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -m pytest tests/test_mcp_server.py::TestMCPServerThreadStop -v`
Expected: PASS.

- [ ] **Step 5: Run the full mcp_server suite (no regressions)**

Run: `py -m pytest tests/test_mcp_server.py tests/test_mcp_server_fastmcp.py -v`
Expected: All tests PASS (tool registration, consent gating, path validation unaffected).

- [ ] **Step 6: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_server.py
git commit -m "fix: stop FastMCP SSE server via uvicorn should_exit"
```

---

## Self-Review

**1. Spec coverage** — Plan addresses the three highest-confidence, code-level defects from the log analysis: (1) debounce permanent-block, (2) Ollama garbage-filter over-rejection, (3) FastMCP shutdown `AttributeError`. The remaining findings (ThoughtPool starvation, Ollama 180s timeout, two-stage-vs-single-stage docs drift) are downstream/consequential or config/UX and are intentionally out of scope here — they are best addressed after Task 2 lands (which removes the primary cause of refill starvation).

**2. Placeholder scan** — No TBD/TODO/"add validation" placeholders. Every step has concrete code and exact commands.

**3. Type consistency** — `MCPServerThread._uvicorn_server` is declared in `__init__`, set in `run()`, read in `stop()`, asserted in the test. `_should_fire_autonomous` signature unchanged. `_filter_garbage_items` signature unchanged. Method/attribute names match across tasks.

**Note on verification:** The log defects were produced by a stale `.pyc` for the debounce case; after implementing Task 1, also delete `src/autonomy/__pycache__/behavior_controller.cpython-314.pyc` (or run a full clean test run) so no stale bytecode masks the change.
