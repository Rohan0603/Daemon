# Fix: LLM brain now uses MCP tools to perform actions

## Problem

When the user said e.g. "jump", the pet only *spoke* — it never performed the
action. Root causes (all in `src/`):

1. `llm.engine == "opencode"` (the default in `data/daemon_config.json`) routes
   to `OpencodeWorker`, which had **no tool wiring at all** — it posts the
   prompt and returns plain text. The brain could only ever produce dialogue.
2. `OllamaWorker`'s `change_visual_state` tool schema enum was **stale**: it was
   missing valid actions (e.g. `"jump"`) and included invalid ones
   (`"perimeter"`, `"thinking"`, `"sleep"` — none of which exist in
   `mcp_server.VALID_ACTIONS`).
3. `PetWindow._on_ollama_tool_call` routed **every** `change_visual_state` call
   to the FSM-only handler (`emit_request` → `_on_mcp_fsm_action`), so
   expression actions like `"jump"` were silently dropped. The FSM branch also
   called `emit_request("triggered_action", action, target_x, target_y)` — a
   wrong argument count that would *always* raise — so the Ollama FSM-action
   path was broken too.

The MCP server itself was correct: `"jump"` is a valid `EXPRESSION_ACTION`
(`mcp_server.py`, `action_layer.py`) and `_handle_change_visual_state` routes
it to the ActionLayer. The gap was purely on the LLM-brain side.

## Fix

- **`src/llm/mcp_client.py`** (new): an in-process MCP SSE client. `list_tools()`
  and `call_tool()` with synchronous wrappers. The LLM tool schema is generated
  *live* from the running Daemon MCP server, so it can never drift from
  `mcp_server.py`.
- **`src/llm/ollama_worker.py`**: builds its tool schema from the MCP catalog
  (falling back to a `VALID_ACTIONS`-derived schema when the MCP server is
  unreachable) and executes tool calls **through the MCP server** — consent
  gating, validation, and FSM/expression routing all happen server-side.
- **`src/ui/pet_window.py` `_on_ollama_tool_call`**: routes expression actions
  (`jump`, `float`, …) to the ActionLayer and FSM actions to the FSM handler;
  fixes the `emit_request` argument bug.
- **`src/llm/opencode_worker.py`**: advertises the MCP tool catalog to opencode
  and forwards any `tool_calls` opencode emits to the Daemon MCP server.
  Automatically disabled if the MCP server is unreachable, or via
  `llm.opencode_forward_tools=false`.

## How to verify

1. Run the pet and say "jump" → the pet **jumps** (and still speaks). Logs should
   show the MCP tool call and the ActionLayer trigger.
2. Tests added (all green):
   - `tests/test_mcp_client.py`
   - `tests/test_ollama_worker_tools.py`
   - `tests/test_opencode_worker_toolcalls.py`
   - `tests/test_pet_window_tool_routing.py`
3. Full suite: `842 passed, 3 failed, 1 skipped`. The 3 failures are the
   pre-existing `tests/test_diary_store_compaction.py` day-merge tests (out of
   scope for this fix).

## OpenCode engine — guaranteed-correct alternative (Phase 3B)

The in-Daemon forwarding (above) works when opencode serve returns `tool_calls`
over `/session/{id}/message`. If your opencode serve does not, the robust path
is to let **opencode** call the Daemon MCP server itself. Register it in your
opencode config (`opencode.json`):

```json
{
  "mcp": {
    "daemon": {
      "type": "remote",
      "url": "http://127.0.0.1:4097/sse"
    }
  }
}
```

Then set `llm.opencode_forward_tools: false` in `data/daemon_config.json` so the
Daemon does **not** also execute the tool (avoids double execution). This is the
recommended production setup for the opencode engine; the in-Daemon forwarding
is the fallback for when opencode serve can't be reconfigured.
