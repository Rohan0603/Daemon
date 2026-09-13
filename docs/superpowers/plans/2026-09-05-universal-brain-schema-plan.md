# Universal Hierarchical Brain Schema Redesign Implementation Plan (continued)

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-09-05-universal-brain-schema-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**IF Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- I will dispatch fresh subagents for each of the 8 tasks above
- Between tasks, I review the subagent's output, fix any issues, and dispatch for the next task
- Fast iteration: typically 15-30 minutes per task
- At the end, all tests should pass and the full suite should run in <50s

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**IF Inline Execution chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:executing-plans
- I will execute tasks in this session, checking off each step
- Batch execution with review checkpoints after every 2 tasks
- May take longer in a single session but gives full context visibility

**Which approach do you choose?**

---
> **Self-review checklist** — run this against the completed plan before handing off:

> **1. Spec coverage:** Can every section/requirement in `docs/superpowers/specs/2026-08-22-universal-brain-schema-design.md` be traced to a task? List any gaps.

> **2. Placeholder scan:** Search the entire plan for "TBD", "TODO", "implement later", undefined types/functions. Fix any found.

> **3. Type consistency:** Do `BRAIN_SCHEMA` field types ("str"/"int"/"list"/"dict"/"float"/"bool") match across all tasks? Do `apply_brain_update()` type checks match? Do `MemoryManager` type validations match?

> **4. Test coverage:** Does each task have a corresponding test defined? Are the tests runnable (not just placeholders)?

> **5. No duplicate code:** Are any code blocks repeated across tasks? Should they be consolidated into a shared helper?

> **6. Task granularity:** Does each task produce an independently testable deliverable? Can a reviewer approve one task while rejecting its neighbor?

> **7. Global constraints honored:** Are all constraints from the "Global Constraints" section honored in every task (field types, locked flags, indexed flags, migration idempotency, no Rohan tokens)?

> If all 7 checks pass, the plan is ready for execution handoff.