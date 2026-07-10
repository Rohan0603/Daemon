# Daemon Agent Skills

A single, DRY library of reusable procedures ("skills") that any AI coding
agent working on this project can use. One authored copy per skill fans out to
every agent via `scripts/sync-agent-skills.sh`.

## Why

Hermes, OpenCode, Claude Code, and Aider all need the same project knowledge
(the strict 50s test gate, the squash-merge git flow, how to add an MCP tool,
how to add an emotion). Maintaining that in four places drifts. So we author
once in `agent-skills/<name>/SKILL.md` and sync.

## Directory layout

```
agent-skills/
  run-tests/      SKILL.md     # strict pre-commit test gate + Qt fixtures
  git-workflow/   SKILL.md     # squash-merge branch flow, no-AI-names rule
  add-mcp-tool/   SKILL.md     # FastMCP registration + consent gating
  add-emotion/    SKILL.md     # Emotion enum + EMOTION_PROFILES registry
scripts/
  sync-agent-skills.sh         # fan-out + CONVENTIONS.md generator
```

## Skill format

Each `SKILL.md` is plain markdown with a YAML frontmatter block:

```yaml
---
name: run-tests
description: Use when running or verifying the Daemon test suite...
version: 1.0.0
author: Daemon Project
license: MIT
metadata:
  hermes:
    tags: [testing, pytest, daemon]
    related_skills: [git-workflow]
---
```

This single format satisfies all four agents:

| Agent    | How it picks the skill up                                  |
|----------|------------------------------------------------------------|
| Claude Code | `.claude/skills/<name>/SKILL.md` (project-local)        |
| OpenCode    | `.opencode/skills/<name>/SKILL.md` (project-local)      |
| Hermes      | `~/.hermes/profiles/<profile>/skills/<name>/SKILL.md`   |
| Aider       | `CONVENTIONS.md` at repo root; load a skill with `--read agent-skills/<name>/SKILL.md` |

## Syncing

After editing any `agent-skills/<name>/SKILL.md`, run:

```bash
bash scripts/sync-agent-skills.sh
```

It copies each skill into `.claude/skills/`, `.opencode/skills/`, and the
Hermes profile skill dirs, then regenerates `CONVENTIONS.md`.

## Hermes zero-copy alternative (optional)

Instead of copying, you can point Hermes directly at this folder so it reads
the source of truth with no duplication. Add to `~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - "C:/Users/ponna/Project/Daemon/agent-skills"
```

Hermes scans every `*/SKILL.md` under that path. (The sync script copies into
the profile dirs by default, which works without touching config.yaml.)

## Adding a new skill

1. `mkdir agent-skills/<my-skill>`
2. Write `agent-skills/<my-skill>/SKILL.md` with the frontmatter above.
3. `bash scripts/sync-agent-skills.sh`
4. Commit `agent-skills/`, `scripts/`, and the regenerated `.claude/`,
   `.opencode/`, `CONVENTIONS.md` (see the `git-workflow` skill).
