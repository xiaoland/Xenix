# Impact Handshake O4 — Cleaning Causal Diagnosis

**Status:** Consumed and completed on 2026-08-11. This handshake authorized diagnostic evidence only; no product source, ordinary test, or benchmark behavior was changed.

## Evidence Trigger

Historical paid run `d4fc5a8482a94c81a1909b1760345b24` passed the cleaning outcome in eight rounds, 69,863 subject tokens, and 102.266 seconds while using two queries, one transform, one cleaning-metadata call, one clean call, and two derived Datasets. Its schema-v5 report proved what happened in aggregate but retained neither the SQLite conversation nor ordered Tool arguments/results, so it could not establish why the route was chosen.

## Address and Object

- the historical ignored schema-v5 report under `build/agent-harness-benchmarks/`;
- two task-local ignored retained runtimes under `execution/raw/o4-cleaning-causal-diagnosis/`;
- read-only inspection of the cleaning case, preprocessing Skill, Tool schemas/projection, cleaning/transform services, SQLite conversation state, Dataset/Artifact lineage, and usage journal;
- tracked diagnosis, evidence, and ablation-plan records in this task packet.

No `src/xenix`, `tests/`, `benchmarks/`, durable documentation, provider settings, or benchmark acceptance contract mutation is authorized here.

## State Diff

- **From:** one successful bounded report showed two queries, a transform, two derived Datasets, and eight rounds but could not distinguish necessary work, planning ambiguity, service recovery, or redundant orchestration.
- **To:** retained-runtime reproductions identify exact per-round choices, the first divergence on each observed route, deterministic service/report defects, cost accumulation, alternative explanations, and a falsifiable ablation order. Historical facts remain separate from fresh reproduction evidence.

## Blast Radius

Task-local diagnostic evidence and planning only. The retained runs call the same paid subject model but are not formal acceptance reports. One diagnostic intentionally retains its isolated SQLite/runtime under the ignored task packet; it does not change normal Harness persistence.

## Invariants

- Do not infer an ordered historical trace from aggregate Tool counts.
- Do not treat a fresh reproduction as the original run.
- Do not classify a diagnostic-location failure as an old product-run failure.
- Service correctness, Agent orchestration, Tool projection, and Harness observability remain separate owners.
- Any product/test/Skill/Tool mutation requires a new exact Impact Handshake.

## Verification

1. Match historical and fresh case/settings/effective-settings identities.
2. Read retained SQLite conversation rows, Dataset/Artifact lineage, and usage journal directly.
3. Recompute the nullable validation mask from the canonical registered Parquet.
4. Reproduce the transform failure with the service directly and preserve its exact exception classification.
5. Check task-packet links and `git diff --check`.

## Return to Discussion

Return before implementing the proposed service, projection, Skill, orchestration, or diagnostic-retention changes. The next handshake must name the exact subset and its independently measurable expected improvement.
