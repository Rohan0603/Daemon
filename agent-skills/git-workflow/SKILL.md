---
name: git-workflow
description: Use when committing, branching, or integrating work on the Daemon project. Enforces the squash-merge feature-branch flow, the never-commit-to-master rule, the no-AI-assistant-names-in-commits convention, and the required pre-commit test gate.
version: 1.0.0
author: Daemon Project
license: MIT
metadata:
  hermes:
    tags: [git, workflow, branching, commits, daemon]
    related_skills: [run-tests]
---

# Daemon Git Workflow

## Overview

All work happens on throwaway feature branches and is integrated into `master`
via a **squash merge**. `master` is protected: nothing is ever committed
directly to it, and commit messages never name an AI assistant.

This workflow is a hard requirement from `AGENTS.md`. Pair it with the
`run-tests` skill — the test gate runs *before* the squash commit.

## When to Use

- Starting any non-trivial change (bug, feature, refactor, test)
- Integrating finished work into `master`
- Anything that will end in a `git commit`

Do NOT use for: hotfixes committed straight to `master` (not allowed here),
or amending published history.

## The Flow

```bash
# 1. Start from master
git checkout master
git pull --ff-only

# 2. Feature branch named by task number + slug
git checkout -b task-<N>-<slug>      # e.g. task-52-add-ide-slug

# 3. Implement, then commit on the branch (conventional style)
git add <files>
git commit -m "feat: add vim/emacs IDE slugs to active_window"

# 4. Run the pre-commit gate (see run-tests skill) — must be green & <50s
py -m pytest tests/ -v

# 5. Integrate via squash merge
git checkout master
git merge --squash task-<N>-<slug>
git commit -m "feat: add vim/emacs IDE slugs to active_window"

# 6. Delete the throwaway branch
git branch -D task-<N>-<slug>
```

## Commit Message Rules

- **Conventional Commits** style: `feat:`, `fix:`, `docs:`, `refactor:`,
  `test:`, `chore:`.
- **Never include AI assistant names** (no "Hermes", "OpenCode", "Claude",
  "Aider", etc.) in the message.
- Describe the *change*, not the conversation. Keep it scannable.

## Hard Rules

1. Never commit directly to `master`.
2. Never put an AI assistant name in a commit message.
3. Always squash-merge (single clean commit on `master`, branch deleted after).
4. Only commit after the `run-tests` gate passes (green + under 50s).

## Common Pitfalls

1. Committing to `master` because "it's just one line" → breaks the protection
   rule; rebase it onto a branch instead.
2. Leaving the feature branch around after merge → clutters the repo. Delete
   it (`git branch -D`).
3. Forgetting the squash → `master` gets N micro-commits and a messy history.
4. Naming an assistant in the message → trivially rejectable; rewrite before
   push.
5. Committing before running the test gate → red master / leaked timers.

## Verification Checklist

- [ ] Work is on a `task-<N>-<slug>` branch (or was squash-merged from one)
- [ ] No direct commits exist on `master` for this change
- [ ] Commit message uses Conventional Commits and contains no AI assistant name
- [ ] `py -m pytest tests/ -v` passed green and finished under 50s before merge
- [ ] Feature branch deleted after integration
