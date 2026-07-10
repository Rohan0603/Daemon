#!/usr/bin/env bash
# sync-agent-skills.sh
#
# Single source of truth:  agent-skills/<name>/SKILL.md
# This script fans each skill out to every AI agent's skill directory and
# (re)generates CONVENTIONS.md for Aider. Run it after editing any skill.
#
#   bash scripts/sync-agent-skills.sh
#
# Targets:
#   .claude/skills/<name>/SKILL.md        -> Claude Code (project-local)
#   .opencode/skills/<name>/SKILL.md      -> OpenCode   (project-local)
#   ~/.hermes/skills/<name>/SKILL.md      -> Hermes     (default profile)
#   ~/.hermes/profiles/light/skills/...   -> Hermes     (active 'light' profile)
#   CONVENTIONS.md (repo root)            -> Aider      (auto-read; refers to skills)
#
# NOTE on Hermes: Hermes does NOT scan a project-local .hermes/skills/ dir.
# It scans ~/.hermes/profiles/<profile>/skills/ plus any dir listed under
# `skills.external_dirs` in ~/.hermes/config.yaml (see README.md for the
# zero-copy alternative). We copy into the profile dirs so it just works.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SRC="agent-skills"
CLAUDE_DIR=".claude/skills"
OPENCODE_DIR=".opencode/skills"
HERMES_DEFAULT="$HOME/.hermes/skills"
HERMES_LIGHT="$HOME/.hermes/profiles/light/skills"

# Collect skill names (directories that contain a SKILL.md)
declare -a SKILLS=()
for d in "$SRC"/*/; do
  [ -f "$d/SKILL.md" ] && SKILLS+=("$(basename "$d")")
done

if [ "${#SKILLS[@]}" -eq 0 ]; then
  echo "No skills found in $SRC/. Aborting." >&2
  exit 1
fi

echo "Syncing ${#SKILLS[@]} skill(s) from $SRC/ -> agent dirs..."

for name in "${SKILLS[@]}"; do
  src_file="$SRC/$name/SKILL.md"
  mkdir -p "$CLAUDE_DIR/$name" "$OPENCODE_DIR/$name" \
           "$HERMES_DEFAULT/$name" "$HERMES_LIGHT/$name"
  cp -f "$src_file" "$CLAUDE_DIR/$name/SKILL.md"
  cp -f "$src_file" "$OPENCODE_DIR/$name/SKILL.md"
  cp -f "$src_file" "$HERMES_DEFAULT/$name/SKILL.md"
  cp -f "$src_file" "$HERMES_LIGHT/$name/SKILL.md"
  echo "  -> $name"
done

# ---- Generate CONVENTIONS.md for Aider -------------------------------------
{
  echo "# Daemon - Conventions for Aider"
  echo
  echo "Full source of truth: **AGENTS.md** in this repo. Read it first."
  echo
  echo "## Reusable skills (procedures)"
  echo
  echo "Detailed, step-by-step procedures live in \`agent-skills/<name>/SKILL.md\`."
  echo "They are shared across Hermes, OpenCode, Claude Code, and Aider."
  echo "Load the relevant one for your current task, e.g.:"
  echo
  echo '```'
  echo 'aider --read agent-skills/run-tests/SKILL.md'
  echo '# or inside a session: /read agent-skills/add-mcp-tool/SKILL.md'
  echo '```'
  echo
  echo "| Skill | When to use it | Load with |"
  echo "|-------|---------------|-----------|"
  for name in "${SKILLS[@]}"; do
    desc="$(awk -F': ' '/^description:/{sub(/^description: /,""); print; exit}' "$SRC/$name/SKILL.md")"
    printf '| `%s` | %s | `aider --read agent-skills/%s/SKILL.md` |\n' "$name" "$desc" "$name"
  done
  echo
  echo "## Key conventions"
  echo
  echo "- **Python launcher:** use \`py\` (never \`python\` / \`python3\`)."
  echo "- **Pre-commit test gate:** \`py -m pytest tests/ -v\` must be green AND finish **under 50s**. Never instantiate \`PetWindow()\` directly - use the \`safe_pet_window\` / \`mock_background_workers\` fixtures."
  echo "- **Git:** work on \`task-<N>-<slug>\` branches, integrate via \`git merge --squash\`, then \`git branch -D\` it. Never commit to \`master\`. Never put an AI assistant name in a commit message. Use Conventional Commits."
  echo "- **Package boundaries:** \`ui -> autonomy -> {llm, system}\`. \`system\` must not import \`ui\`/\`llm\`; \`llm\` must not import \`ui\`; \`autonomy\` must not import \`ui\`."
  echo "- **Emotions are system-driven only.** The LLM may drive physical animations (\`change_visual_state\`) but never set emotions / colors / eye states."
} > CONVENTIONS.md

echo "Wrote CONVENTIONS.md ($(wc -l < CONVENTIONS.md) lines)."
echo "Done. Skills now available to:"
echo "  Claude Code : .claude/skills/"
echo "  OpenCode    : .opencode/skills/"
echo "  Hermes      : ~/.hermes/skills/ and ~/.hermes/profiles/light/skills/"
echo "  Aider       : CONVENTIONS.md (use --read agent-skills/<name>/SKILL.md)"
