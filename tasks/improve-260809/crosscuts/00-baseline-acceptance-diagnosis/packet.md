# Cross-cut 00 — Baseline, Acceptance, Diagnosis

## Objective & Hypothesis

Create a repeatable evidence-and-diagnosis layer that separates service defects from Agent Harness defects, compares task completion/performance/cost, and authorizes only the smallest evidence-backed optimization.

Hypothesis: preparation, Skill guidance, Tool schemas, orchestration, result grounding, or observability may cause real failures, but private oracle qualification and canonical runtime evidence must locate the first divergence before any of them changes.

## Status

`IH-B0 implemented and offline-verified`; the B0 Agent Harness baseline, acceptance, and diagnosis infrastructure is complete. Detailed design is in [b0-design.md](b0-design.md), the exact mutation boundary is in [IH-B0](../../handshakes/IH-B0.md), and bounded results are in the [offline execution record](../../execution/B0-offline-implementation-260809.md).

## Scope and Non-Goals

In scope:

- dual clean-room/private fixture profiles and physical subject/evaluator isolation;
- information-only capability baseline for missing and partial workflows;
- direct public-boundary service acceptance owned by ordinary tests;
- headless/headed Agent profiles, before/after/ablation runs, and a report-level policy;
- safe correlation across case, conversation, Tool call, ML task, Dataset, Artifact, final answer, and headed render;
- exact optimizations justified by reproduced first-divergence evidence.

Non-goals:

- using the Agent benchmark to test estimator math;
- committing expected-failure tests for capabilities that do not exist yet;
- broad observability, prompt, Skill, schema, or orchestration rewrites without a failing case;
- case-specific prompts, Tool-trace oracles, or benchmark-only production branches;
- treating record/replay as live-provider acceptance.

## Dependencies

B0 begins first. The cross-cut then brackets Verticals 01 and 02. Service tests and Agent benchmarks remain independently executable; development guidance and CI dispatch paid Agent work only after the service job passes.

## Durable Owners / Blast Radius

B0 is limited to Agent benchmark/evaluator infrastructure, Agent-owned clean-room fixtures, thin scripts, development guidance, and ordered paid CI. It must not change `tests/` service cases or `src/xenix` product behavior. Later product handshakes own service cases and behavior; exact optimization handshakes may touch production seams only when a diagnosed case names that owner.

## Candidate State Diff

- `From`: three live cases, an all-configured-model default, no ML workflow coverage, no hard cell budget, and measurement-only semantic/integrity outcomes.
- `To`: independently owned service and Agent cases, a single pinned-model live baseline, hard step/time safety, guidance/CI-only ordering, safe post-run attribution, versioned Agent acceptance, and bounded cost evidence.

Only B0 receives the first handshake; later production optimizations require separate `IH-O<n>` handshakes.

## Invariants

- Benchmark runner remains a measurement producer; acceptance policy is a separate consumer.
- Service failure prevents paid CI dispatch and remains service evidence; the Agent runner never reads or translates it.
- Existing canonical DB and Artifacts remain state authority; traces are correlation evidence only.
- Planning risks may have independent service and Agent fixtures, but the executable trees and their reports never overlap.
- Once an approved implementation handshake is explicitly started, its qualified bounded live runs need no additional fee checkpoint.

## Decisions Consumed

`D-002` through `D-010`; `P-001`, `P-005`, `P-006`, and revised `P-007` are approved B0 details.

## Cases Consumed

All business risks in [Case catalog](../../cases/catalog.md). A live Agent baseline is admitted only after the corresponding independent service black-box cases are green; therefore missing product capabilities do not receive speculative pre-service Agent runs.

## Verification Plan

1. Qualify separately owned service and Agent fixtures, private projections, and oracle bindings offline.
2. Record `available`, `partial`, or `missing` service capability without committing red tests.
3. Make each implemented domain's public-boundary service acceptance green in its product vertical.
4. After the service CI stage passes, run one bounded paid live headless Agent baseline without passing service artifacts into the runner.
5. Run formal repeated headless and one headed acceptance cell for an accepted state.
6. Attribute failures by the first failing layer and add regression proof at the lowest owner.

## Current Evidence

- Report schema v5 and the Agent-only evaluator now separate execution, integrity, semantic, Judge, subject metrics, Judge metrics, budget status, and comparison identity. Characterization remains non-gating; formal acceptance is a separate policy decision.
- Historical live runs show normal cases around 18–24k subject tokens and under 70 seconds, while a difficult cleaning failure consumed about 240k tokens and 18 minutes. B0 therefore needs a hard 12-round limit, a hard 900-second process deadline, and secondary reported-token stops.
- The live runner now selects exactly the settings snapshot's `default_fq_model_key`, with one optional single-value override. Every cell is process-isolated and enforces the approved round/time/token/attempt limits.
- Five clean-room ML Agent cases extend the catalog from 3 to 8 without copying supplied-corpus bytes. Headless/headed collection match, and an explicit selector collects one paid cell rather than the whole catalog.
- The ordinary suite has 45 collected tests; six distinct capability workflow tests cross the documented 50-case architecture-review trigger.

## Next Action

Review the two proposed foundation handshakes and their independent implementation plans: Dataset profile/cleaning evidence first, then group-safe preparation/evaluation/lifecycle facts. Resolve `O-004` only before the later clustering/forecasting handshake. Paid live characterization remains deferred until the corresponding service selector is implemented and green.
