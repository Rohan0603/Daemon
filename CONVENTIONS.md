# Daemon - Conventions for Aider

Full source of truth: **AGENTS.md** in this repo. Read it first.

## Reusable skills (procedures)

Detailed, step-by-step procedures live in `agent-skills/<name>/SKILL.md`.
They are shared across Hermes, OpenCode, Claude Code, and Aider.
Load the relevant one for your current task, e.g.:

```
aider --read agent-skills/run-tests/SKILL.md
# or inside a session: /read agent-skills/add-mcp-tool/SKILL.md
```

| Skill | When to use it | Load with |
|-------|---------------|-----------|
| `add-emotion` | Use when adding a new emotion to Daemon's visual layer. Covers adding the Emotion enum member in src/animator.py, registering it in the EMOTION_PROFILES registry, the EmotionProfile field set, and the system-driven (never LLM-driven) trigger boundary. | `aider --read agent-skills/add-emotion/SKILL.md` |
| `add-mcp-tool` | Use when adding a new MCP tool to Daemon's in-process JSON-RPC 2.0 server (port 4097). Covers FastMCP @app.tool() registration in src/mcp_server.py, the CONSENT_TOOL_MAP gating, the config.py consent key mapping, and the daemon_config_template.json default. | `aider --read agent-skills/add-mcp-tool/SKILL.md` |
| `git-workflow` | Use when committing, branching, or integrating work on the Daemon project. Enforces the squash-merge feature-branch flow, the never-commit-to-master rule, the no-AI-assistant-names-in-commits convention, and the required pre-commit test gate. | `aider --read agent-skills/git-workflow/SKILL.md` |
| `run-tests` | Use when running, debugging, or verifying the Daemon pytest suite before a commit. Enforces the strict pre-commit gate (full suite green + under 50s) and the safe_pet_window / mock_background_workers fixtures that prevent Qt event-loop pollution and zombie timers. | `aider --read agent-skills/run-tests/SKILL.md` |

## Key conventions

- **Python launcher:** use `py` (never `python` / `python3`).
- **Pre-commit test gate:** `py -m pytest tests/ -v` must be green AND finish **under 50s**. Never instantiate `PetWindow()` directly - use the `safe_pet_window` / `mock_background_workers` fixtures.
- **Git:** work on `task-<N>-<slug>` branches, integrate via `git merge --squash`, then `git branch -D` it. Never commit to `master`. Never put an AI assistant name in a commit message. Use Conventional Commits.
- **Package boundaries:** `ui -> autonomy -> {llm, system}`. `system` must not import `ui`/`llm`; `llm` must not import `ui`; `autonomy` must not import `ui`.
- **Emotions are system-driven only.** The LLM may drive physical animations (`change_visual_state`) but never set emotions / colors / eye states.
