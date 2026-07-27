# V2 Implementation Slices

Status: **implemented through Slice 3; Slice 4 final verification in progress**.

## Slice 0 — Local Rules and Durable Contract

### Addresses

- `tests/agent_harness_benchmark/AGENTS.md` — new, narrow local guidance.
- `docs/30-unit-tdd/agent-harness-benchmark.md` — new durable benchmark
  ownership/semantic-evaluation document.
- `docs/30-unit-tdd/README.md` — link only.

### State Diff

From implicit benchmark rules split across task notes and tests, to one local
tripwire file plus one durable contract. The local file stays within physical
scope, hazards, forbidden shortcuts, and focused verification; it does not
duplicate product or cross-unit contracts.

### Invariants

No product behavior, provider settings, or test execution changes.

### Exit

Documentation review confirms case semantics, integrity, performance, and judge
roles are distinct and the default suite remains offline.

**Completed.**

## Slice 1 — Result and Case Contract Separation

### Addresses

- `tests/agent_harness_benchmark/contracts.py`
- `tests/agent_harness_benchmark/runner.py`
- `tests/test_agent_harness_benchmark.py`

### State Diff

From one `outcome_checks` conjunction that mixes task quality and infrastructure
facts, to versioned result channels for integrity, semantic verdict, subject
metrics, judge status, and judge metrics. Extend the case protocol only enough
to permit a case-owned bounded `JudgeInput`.

### Risks and Controls

- Preserve existing V1 JSON readers or intentionally bump `schema_version` with
  a documented compatibility policy.
- A no-judge case must still run with `judge=not_requested`; its deterministic
  semantic checks remain meaningful, so V2 does not force the April cleaning
  case into an uncalibrated rubric.
- No case id branching in the runner.

### Exit

Offline tests prove all status combinations, a result write failure, and that
integrity invalidation cannot appear as semantic failure.

**Completed.**

## Slice 2 — Independent Judge Runtime

### Addresses

- `tests/agent_harness_benchmark/judge.py` — new direct judge client.
- `tests/agent_harness_benchmark/runner.py`
- `scripts/run_agent_harness_benchmark.py`
- `tests/test_agent_harness_benchmark.py`

### State Diff

Load/freeze judge settings separately, then invoke `LLMService.complete()`
after a settled subject cell with `tools=[]`. Parse only strict, bounded JSON;
record judge usage/time/retries independently.

### Risks and Controls

- Do not construct a Harness/Conversation, canonical Message, or usage journal
  for the judge.
- Do not silently fall back to the subject model/settings.
- Treat provider error, invalid JSON, and missing configuration as judge status,
  not semantic verdict.
- Keep V2 inside current text-only provider capability; do not add max-token or
  vision support in this slice.

### Exit

Focused offline tests prove request isolation, no-Tools transport, strict JSON
validation, bounded serialization, and separate timing/token counters.

**Completed.**

## Slice 3 — Graph Case Evidence and Rubric Migration

### Addresses

- `tests/agent_harness_benchmark/chart_revenue.py`
- `tests/agent_harness_benchmark/fixtures/` — judge calibration evidence only.
- `tests/test_agent_harness_benchmark.py`
- V2 durable/task docs as needed.

### State Diff

From a prompt that prescribes bar/title/X/Y and an oracle that checks graph
metadata/bar count, to a normal business request plus case-owned final-SVG
semantic evidence and the regional-sales judge rubric.

### Risks and Controls

- Use only final Artifact evidence and independent fixture facts.
- No raw SVG, source rows, paths, ids, Tool arguments, metadata, or Assistant
  prose reaches the judge or report.
- Missing terminal visual is semantic failure; weak-but-real evidence is
  `inconclusive`, not a fabricated parser assertion.

### Exit

Offline cases cover good, misleading, unrelated, and insufficient-evidence
projections; no fixed chart implementation is required to pass the contract.

**Completed.**

## Slice 4 — Calibration and Explicit Live Acceptance

### Addresses

- `tasks/agent-harness-benchmark-semantic-evaluation/verification.md`
- explicit benchmark CLI/output only; no default-test provider call.

### State Diff

From uncalibrated semantic judging to recorded evidence that the configured
judge rubric produces the intended categories for safe calibration fixtures and
the live graph cell.

### Risks and Controls

- Record judge/model identity and same-model independence flag.
- Review judge variance before treating `partial` thresholds as regression
  gates; do not introduce a leaderboard or multi-judge ensemble prematurely.
- Live reports remain bounded and secret/data-free.

### Exit

One explicit Kimi K2.6 run has separate subject/judge metrics and a bounded
semantic verdict; focused tests, full tests, and static checks pass.

**Completed.**

## Impact Handshake for Authorization

| Element | Proposed change |
| --- | --- |
| Address/object | Benchmark contracts, runner, CLI, graph case, focused tests, local guidance, and Agent Harness durable docs only. |
| State diff | Structural/equality oracle → case-owned evidence plus independent rubric judge; mixed checks → separate execution/integrity/semantic/metrics channels. |
| Blast radius | Benchmark JSON consumers, explicit benchmark CLI, graph case tests, local contributor guidance. No UI, production settings, or default test network behavior. |
| Invariants | Real subject provider path, fresh temporary cell, public outcome boundary, no Tool-trace truth, privacy-bounded reports, offline default suite. |
| Verification | Focused offline tests, calibration fixtures, explicit live Kimi run, `pdm run test`, and `pdm run check`. |
