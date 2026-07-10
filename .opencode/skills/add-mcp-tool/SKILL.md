---
name: add-mcp-tool
description: Use when adding a new MCP tool to Daemon's in-process JSON-RPC 2.0 server (port 4097). Covers FastMCP @app.tool() registration in src/mcp_server.py, the CONSENT_TOOL_MAP gating, the config.py consent key mapping, and the daemon_config_template.json default.
version: 1.0.0
author: Daemon Project
license: MIT
metadata:
  hermes:
    tags: [mcp, tools, consent, fastmcp, daemon]
    related_skills: [run-tests]
---

# Add an MCP Tool

## Overview

Daemon exposes a FastMCP server (`src/mcp_server.py`) on `127.0.0.1:4097` with
23 tools. Adding a tool means registering it with FastMCP, optionally gating it
behind a user **consent** key, and wiring that key through `config.py` and the
config template. Tools that only *read* local state are always allowed; tools
that touch the user's machine/clipboard/browser require explicit consent.

## When to Use

- You need the pet's LLM (or an external MCP client) to call a new capability
- Adding an introspection/read tool or an action tool
- Extending the MCP surface exposed to opencode serve

Do NOT use for: changing FSM states or emotions (those are internal — see
`add-emotion`); pure UI changes.

## Edit Sites (all in `src/`)

1. **Register the tool** — `src/mcp_server.py`, inside
   `_create_fastmcp_app()` (around line 143). Add an `@app.tool()` function
   that delegates to a `_handle_*` helper:

   ```python
   @app.tool()
   def my_new_tool(arg: str) -> dict:
       """One-line description of what the tool does."""
       return _handle_my_new_tool(server_thread, arg)
   ```

2. **(If consent-gated) Map the tool** — `src/mcp_server.py`,
   `CONSENT_TOOL_MAP` (around line 69). Add the entry:

   ```python
   "my_new_tool": "allow_my_new_tool",
   ```

   Omit this for always-allowed read tools (see tiers below).

3. **Implement the handler** — in `src/mcp_server.py`, add `_handle_my_new_tool`
   and guard it if gated:

   ```python
   def _handle_my_new_tool(server_thread, arg: str) -> dict:
       allowed, err = _is_tool_allowed(server_thread, "my_new_tool")
       if not allowed:
           return {"content": [{"type": "text", "text": err}]}
       # ... do the work, return {"content": [{"type": "text", "text": ...}]}
   ```

4. **Wire the consent key** — `src/config.py`. Add to BOTH
   `FLAT_TO_NESTED` (around line 50) and `NESTED_TO_FLAT` (around line 179):

   ```python
   "allow_my_new_tool": ("consent", "allow_my_new_tool"),
   ```
   (Skip if the tool needs no consent.)

5. **Add a default** — `assets/daemon_config_template.json`, under the
   `"consent"` block:

   ```json
   "allow_my_new_tool": false
   ```

6. **Tests + verify** — add/extend tests under `tests/` and run the gate
   (see `run-tests` skill). Never instantiate `PetWindow` directly; use
   `safe_pet_window` / `mock_background_workers`.

## Consent Tiers (Settings → Boundaries)

- **Tier 1 (Low, default True):** `allow_intrusive_animations`
- **Tier 2 (Medium, default False):** `allow_audio_disruptions`,
  `allow_browser_redirection`
- **Tier 3 (High, default False):** `allow_clipboard_hijacking`,
  `allow_mouse_interference`, `allow_window_management`,
  `allow_keyboard_injection`

**Always-allowed read tools (no consent key, never in `CONSENT_TOOL_MAP`):**
`list_directory`, `read_file`, `search_codebase`, `get_memory`, `get_diary`.

Pick the tier that matches the risk of your tool. High-risk actions must
default to `false`.

## Common Pitfalls

1. Forgetting the `CONSENT_TOOL_MAP` entry → a gated tool silently runs
   without consent, or `_is_tool_allowed` returns `True` for an unmapped name.
2. Forgetting BOTH config.py mappings → `validate_config()` rejects the key or
   it never round-trips env ↔ nested config.
3. Forgetting the `daemon_config_template.json` default → new configs lack the
   key and validation complains.
4. Returning a value instead of `{"content": [{"type": "text", "text": ...}]}`
   → FastMCP response shape mismatch.
5. Not guarding the handler with `_is_tool_allowed` for a consent-gated tool.

## Verification Checklist

- [ ] `@app.tool()` registered in `_create_fastmcp_app()`
- [ ] `CONSENT_TOOL_MAP` entry added iff the tool is consent-gated
- [ ] `_handle_*` implemented and guarded with `_is_tool_allowed` when gated
- [ ] `config.py` `FLAT_TO_NESTED` + `NESTED_TO_FLAT` both updated
- [ ] `daemon_config_template.json` has the default under `consent`
- [ ] `py -m pytest tests/ -v` green and under 50s
