# Agent-First Replatform Phase 1 Design

## Goal

Replatform the Daemon repo for agent-first development by decomposing the codebase into domain-owned packages that are smaller, more isolated, and easier for Codex, Hermes, and Antigravity to modify safely with less ambient context.

## Scope

This spec covers phase 1 only: codebase decomposition. It does not cover the later automation-rails or multi-agent-workflow subprojects except where this phase intentionally creates cleaner boundaries for them.

## Architecture

The repo will move from a `pet_window.py`-centered structure to a domain-first structure where `PetWindow` becomes a thin composition shell rather than the center of application behavior.

Target top-level domains:

- `src/system/`
- `src/llm/`
- `src/autonomy/`
- `src/ui/`

Extraction order:

1. `system`
2. `llm`
3. `autonomy`
4. `ui`

This order minimizes refactor blast radius by extracting leaf integrations first, then model/session orchestration, then application coordination, and finally the Qt shell.

## Target Package Responsibilities

### `src/system/`

Owns platform-facing and background integrations only.

Examples:

- APM and input monitors
- typing capture
- screen reading
- TTS playback
- active window lookup
- click-through behavior
- event-stream clients
- other OS/runtime adapters

Rules:

- exposes service-style APIs, events, or signals
- does not own behavior policy
- does not know Kenny persona, FSM priority decisions, or prompt strategy
- must not import `ui`
- must not import `llm`

### `src/llm/`

Owns all model/session/prompt orchestration.

Examples:

- `StrandsSession`
- `OpencodeWorker`
- prompt/context assembly
- skill loading
- response parsing
- session persistence

Rules:

- produces structured outputs and streamed updates
- does not directly mutate UI or FSM state
- becomes the only domain that knows Strands/opencode details
- must not import `ui`

### `src/autonomy/`

Owns application coordination and behavior policy.

Examples:

- behavior loop coordination
- trigger policy
- reminder reactions
- risky-typing reactions
- action dispatch
- translation of system inputs and LLM outputs into app actions

Rules:

- consumes `system` signals and `llm` outputs
- emits domain actions for the UI layer
- becomes the main owner of behavior currently scattered through `pet_window.py`

### `src/ui/`

Owns widgets, dialogs, renderer-facing composition, and presentation-only wiring.

Examples:

- windows and dialogs
- tray/menu presentation
- user-input presentation
- rendering composition
- signal wiring that is purely visual or interaction-facing

Rules:

- renders and relays user intent
- does not own core application policy
- is the final thin shell composed on top of other domains

## Dependency Rules

Primary dependency direction:

- `ui -> autonomy -> {llm, system}`

Additional rules:

- `autonomy` may coordinate `llm` and `system`
- `llm` must not import `ui`
- `system` must not import `ui`
- `system` must not import `llm`
- shared cross-domain types should live in small neutral modules rather than importing back upward

## Migration Strategy

This replatform should be staged rather than rewritten in one pass.

### Stage 1: Extract `system`

- create `src/system/` package
- move leaf integrations first
- add compatibility shims only where needed to keep behavior stable during the move
- reduce import sprawl before deeper coordination refactors

### Stage 2: Extract `llm`

- create `src/llm/` package
- move session/workers/prompts/parsing under one ownership boundary
- make existing callers depend on a narrower LLM-facing interface
- centralize all Strands/opencode knowledge here

### Stage 3: Extract `autonomy`

- create `src/autonomy/` package
- move reminder logic, risky-typing reactions, autonomous trigger coordination, and similar behavior-selection code out of `pet_window.py`
- make `pet_window.py` stop making application behavior decisions

### Stage 4: Extract `ui`

- create `src/ui/` package
- collapse the remaining Qt-heavy shell into smaller presentation-owned modules
- leave the final UI layer mainly responsible for composition, event relay, and rendering

## Migration Constraints

- each stage must be independently test-backed and shippable
- temporary compatibility wrappers are allowed only as migration scaffolding
- tests should migrate with ownership, so domain tests live near the domain they validate
- docs and agent instructions must be updated in the same stage as the code move

## Verification Strategy

- every extraction step starts with a failing ownership or regression test before code moves
- behavior-preserving moves must keep the full suite green
- stage-specific tests must be runnable in isolation
- weak runtime paths, especially reminder actions and risky-typing reactions, get explicit regression coverage
- import boundaries should be checked after each stage so the moved domain no longer depends on higher layers

## Success Criteria

- `pet_window.py` is no longer the dominant owner of system, LLM, autonomy, and UI behavior at once
- `src/system/`, `src/llm/`, `src/autonomy/`, and `src/ui/` exist as real ownership boundaries with production code inside them
- model/session changes live in `llm`
- platform hooks live in `system`
- behavior policy lives in `autonomy`
- widgets and presentation live in `ui`
- a fresh agent can infer where to work from repo structure without reading a giant central file first
- repo docs and agent instructions reflect the new boundaries

## Risks

- temporary compatibility glue can linger after extraction
- Qt signal wiring may hide coupling until code is moved
- apparent progress can be fake if files shrink but ownership boundaries remain cross-wired

## Risk Controls

- enforce per-stage ownership boundaries
- move tests with the code they validate
- update docs in the same stage
- verify each stage with full test evidence rather than import success alone

## Explicit Non-Goals

- phase 1 does not attempt to solve the full automation-rails project
- phase 1 does not attempt to solve the full multi-agent-workflow project
- phase 1 is not a UI redesign
- phase 1 is not a feature expansion

## Recommended Immediate Execution Order

1. extract `system`
2. extract `llm`
3. extract `autonomy`
4. extract `ui`

This order is the default unless a stage uncovers hidden coupling severe enough to justify reordering.
