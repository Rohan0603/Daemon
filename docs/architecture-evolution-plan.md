# Daemon Architecture Evolution Plan

**Date:** 2026-09-04
**Status:** Proposed
**Scope:** Runtime architecture, model serving, training lifecycle, privacy,
and delivery plan

## Problem Statement

Daemon must feel continuously alive while keeping UI interactions responsive,
runtime memory bounded, behavior recoverable, and personal data private. It
needs autonomous behavior, local or remote LLM providers, explicit OS-action
consent, persistent memory, and a repeatable personality-model workflow.

## Decisions

### D1. Evolve current Python/PyQt6 runtime

Keep PyQt6, the current package direction, and existing provider/storage
implementations. Do not rewrite the renderer, behavior engine, or model
runtime in C++/Rust until profiling proves a measured budget violation.

Reason: current code already has tested FSM, renderer, provider gateway,
bounded MCP execution, cancellation, observability, atomic persistence, and
Firebase REST authentication. A rewrite would increase risk without proving
latency benefit.

### D2. Make orchestration the next ownership boundary

Extract an `LLMOrchestrator` from `PetWindow`. It owns request lifecycle,
deadlines, retries, provider selection, schema validation, fallback, and
correlation timing. OpenCode and Ollama workers remain transport adapters.

`PetWindow` remains composition root and UI adapter. Autonomous and refill
requests stay ephemeral; optional interactive session reuse remains explicit.

### D3. Use a deterministic fast path

Cached phrases, response-pool draws, TTS cache hits, and simple FSM changes
must not wait for model inference. The model supplies novelty and complex
planning, while action authorization and safety policy remain deterministic
runtime code.

### D4. Keep memory local-first

Local atomic stores are available during runtime and offline startup. Firebase
is an opt-in synchronization adapter, never a boot prerequisite. Cloud sync
must not receive data unless the user has enabled it and authenticated.

### D5. Centralize intrusive actions

Mouse, keyboard, clipboard, browser, window, UIA, and similar operations must
pass one typed action boundary with consent checks, parameter validation,
timeouts, cancellation, and audit logging. A model may request an action; it
may not authorize one.

### D6. Treat model artifacts as versioned releases

Every LoRA/GGUF artifact records its base model, dataset revision, training
configuration, evaluation results, quantization, and serving configuration.
Training and evaluation remain separate from the desktop runtime.

## Requirements and Success Criteria

| Area | Requirement | Verification |
|------|-------------|--------------|
| UI | Action-to-animation acknowledgement `<150 ms` | Automated event timing test |
| Speech | Cached short phrase starts `<300 ms` | TTS latency benchmark |
| Model | First-token and complete-response latency reported separately | Provider benchmark |
| Memory | Idle target `<200 MB` on representative hardware | Startup/idle memory measurement |
| Reliability | Provider failure falls back without freezing Qt | Failure-injection tests |
| Privacy | Sensors off and cloud sync opt-in by default | Configuration and boot tests |
| Safety | Intrusive actions require consent and bounded execution | Action-layer tests |
| Training | Held-out persona, JSON, safety, and generality evaluation exists | Artifact evaluation report |

## Build vs. Buy

| Area | Decision | Rationale |
|------|----------|-----------|
| UI/rendering | Keep PyQt6 | Existing behavior and test investment |
| FSM/behavior | Build on current modules | Core product differentiation |
| Local serving | Use Ollama or llama.cpp | Mature model lifecycle and quantization |
| Provider policy | Keep/build shared gateway | Product-specific fallback and budgets |
| TTS | Keep current fallback chain and cache | Existing Windows integration |
| Storage | Keep local stores plus Firebase adapter | Offline and privacy requirements |
| Plugin isolation | Defer WASM sandbox | Requirements are not stable enough yet |
| Native rewrite | Defer | Requires profiling evidence and hardware matrix |

## Dependency Plan

```text
Baseline metrics ───────────────┐
Training correctness ───────────┼──> Evaluation contract
Action boundary ────────────────┘             │
                                             v
Memory boundary ────────────────> LLM orchestrator
                                             │
                                             v
                              Performance optimization
                                             │
                                             v
                                      Release hardening
```

## Phased Execution

### Phase 0: Baseline and policy, S

- Measure UI, fast-path, provider, parsing, first-visible-bubble, TTS, and
  memory timings separately.
- Define evaluation prompts and telemetry fields before collecting new data.
- Confirm camera, microphone, cloud, and intrusive-action defaults.

**Done:** baseline report exists; budgets have explicit definitions.

**Risk:** a full uncached 3B response will not reliably fit the UI budget.

### Phase 1: Training pipeline correctness, S/M

- Ensure the notebook calls `trainer.train()` before saving adapters.
- Validate Alpaca records and maintain a held-out split.
- Add checkpoint retention and artifact manifest generation.
- Evaluate base versus tuned responses for persona, schema validity, safety,
  consent behavior, and general instruction retention.

**Done:** reproducible run produces an artifact and evaluation report.

**Risk:** repetitive synthetic data can overfit style while harming generality.

### Phase 2: LLM orchestration extraction, M

- Extract orchestration policy from `PetWindow`.
- Preserve `ProviderGateway`, request timing, cancellation, and fallbacks.
- Route fast-path and ThoughtPool hits before provider calls.
- Add contract tests for user, autonomous, refill, timeout, cancellation, and
  malformed output paths.

**Done:** UI coordinates typed signals; provider policy has one owner.

**Risk:** Qt worker lifecycle regressions; use `safe_pet_window` and
  `mock_background_workers` fixtures.

### Phase 3: Action and memory boundaries, M

- Route all intrusive operations through `ActionLayer`.
- Introduce a storage protocol over local and Firebase implementations.
- Test offline boot, crash recovery, account switching, and cloud-disabled
  operation.

**Done:** feature code cannot bypass authorization or storage contracts.

### Phase 4: Performance optimization, M

- Warm local models during idle where hardware permits.
- Bound context before provider calls.
- Cache common TTS and autonomous responses.
- Benchmark Ollama and OpenCode on representative hardware.
- Consider ONNX/TensorRT/native components only for measured bottlenecks.

**Done:** p50/p95 latency and idle memory are reported against agreed budgets.

### Phase 5: Release hardening, M

- Run package archive inspection and clean first-launch/restart tests.
- Run Firebase Emulator rules tests.
- Test provider failure, recovery, cancellation, and rollback.
- Run full test suite under the repository's 50-second gate.

**Done:** release checklist has reproducible evidence, not only qualitative QA.

## Governance Gaps

The proposed `AGENT_POLICY.yaml`, signed override tokens, and
`TELEMETRY_SCHEMA.json` are not current repository artifacts. They should not
be treated as enforced rules until designed, reviewed, and added deliberately.
Likewise, ADRs should document real decisions; they should not require an
ADR for every routine documentation or test change.

## Most Important Risk

Confusing model latency with UI latency can drive an unnecessary native rewrite.
Measure those paths independently before changing the runtime foundation.

## Next Actions

1. Run Phase 0 latency and memory baseline.
2. Correct and validate the Colab training pipeline.
3. Define the `LLMOrchestrator` contract from existing gateway timing and
   cancellation behavior.