# Daemon Log Analysis and Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve exponential prompt growth, fix LLM API empty responses, and address APM panic FSM state conflicts identified in the logs.

**Architecture:** We will fix the `OpencodeWorker` to prevent exponential prompt accumulation by separating the `original_prompt` from the context-injected `prompt`. We will also correct the FSM state used for low APM panics to avoid conflicting with the `DEVASTATED` state intended for critical errors.

**Tech Stack:** Python, PyQt6, Daemon architecture

---

### Task 1: Fix Exponential Prompt Growth in OpencodeWorker

**Files:**
- Modify: `src/opencode_worker.py:149-183`

- [ ] **Step 1: Write the failing test or verify manually**

(Assuming no explicit test exists for this specific bug, we will directly fix the prompt accumulation).

- [ ] **Step 2: Write minimal implementation**

Modify `src/opencode_worker.py` to preserve the `original_prompt` before prepending the `history_ctx`, and pass `original_prompt` to `_emit_turn_completed`.

```python
    def send(self, prompt: str) -> None:
        if self._abort:
            return
        from src.constants import STRUCTURED_SCHEMA
        llm_cfg = self._config.get("llm", {})
        provider = llm_cfg.get("provider", "")
        model_id = llm_cfg.get("model_id", "")

        # Preserve the original prompt to prevent exponential history growth
        original_prompt = prompt

        # Prepend previous conversation history as context if resuming
        history_ctx = ""
        if self._session_state and hasattr(self._session_state, "history_context"):
            history_ctx = self._session_state.history_context
        if history_ctx:
            prompt = f"{history_ctx}\n\n[Current message]\n{prompt}"

        payload = {
            "parts": [{"type": "text", "text": prompt}],
            "structured": STRUCTURED_SCHEMA,
        }
        # Note: We omit passing payload["model"] because OpenCode server 
        # crashes with HTTP 500 when overriding with OpenRouter models.
        # It automatically uses the primary agent defined in opencode.json.
        logger.debug("SEND payload prompt (first 500): %s", prompt[:500])
        logger.debug("SEND payload full: %s", json.dumps(payload, indent=2)[:2000])
        raw = self._post_message(payload, is_refill=self._is_autonomous)
        if self._abort:
            return
        if raw:
            logger.debug("RECV raw (first 1000): %s", raw[:1000])
            self._used_api = True
            self.path_used.emit("api")
            items = self._parse_json_response(raw)
            if items is not None:
                logger.debug("RECV parsed: %d items, first: %s", len(items), json.dumps(items[0] if items else {}))
                # Emit turn data for persistence using original_prompt
                self._emit_turn_completed(original_prompt, raw)
                self.response_ready.emit(items)
                return
            items = self._handle_schema_error(raw)
            self._emit_turn_completed(original_prompt, raw)
            self.response_ready.emit(items)
        else:
            logger.warning("send: API returned empty or None")
```

- [ ] **Step 3: Commit**

```bash
git add src/opencode_worker.py
git commit -m "fix(opencode_worker): prevent exponential prompt growth by using original prompt for session history"
```

### Task 2: Fix APM Panic FSM State Conflict

**Files:**
- Modify: `src/pet_window.py:488-499`

- [ ] **Step 1: Write minimal implementation**

Modify `_trigger_apm_panic` in `src/pet_window.py` to use a non-conflicting state for low APM panic, such as `LOOK_AWAY`, instead of `DEVASTATED`.

```python
    def _trigger_apm_panic(self, panic_type: str) -> None:
        """Trigger panic reaction to significant APM changes."""
        from src.pet_fsm import PetState
        if panic_type == "low":
            self._show_bubble("Why is my APM so low? I can't even think!")
            self._fsm.current_state = PetState.IDLE 
            self._fsm.transition_to(PetState.LOOK_AWAY)
        elif panic_type == "high":
            self._show_bubble("My APM just spiked! I'm hyperventilating!")
            self._fsm.current_state = PetState.IDLE
            self._fsm.transition_to(PetState.HYPER)
```

- [ ] **Step 2: Commit**

```bash
git add src/pet_window.py
git commit -m "fix(pet_window): change low APM panic state to LOOK_AWAY to avoid DEVASTATED conflict"
```
