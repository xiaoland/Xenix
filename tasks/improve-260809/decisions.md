# Decision Register

## Confirmed

### D-001 — Three interleaved verticals

**Status:** superseded by D-007 on 2026-08-09; the execution sequence remains, but the topology name was wrong.

Execute foundation + clustering/forecasting first, recommendation/text second, and use a benchmark-driven diagnosis vertical before and after both. The third vertical may improve preprocessing, Agent Skills, Tool schemas, orchestration, or observability only when evidence locates a failure there.

### D-007 — Two product verticals and Cross-cut 00

**Status:** confirmed by Sir on 2026-08-09.

Treat baseline, acceptance, diagnosis, and evidence-backed optimization as the first horizontal cross-cut. It starts before Vertical 01, brackets both product verticals, and remains active throughout the program. The underlying sequence from D-001 is preserved.

### D-002 — Three evidence layers

**Status:** confirmed by Sir on 2026-08-09.

Use private oracle qualification, ordinary public-boundary service integration tests, and live Agent Harness benchmarks. Each layer answers a different question and reports a separate verdict.

### D-003 — Service tests own service truth

**Status:** confirmed by Sir on 2026-08-09.

Material-derived cases must test ML/data services directly. Model training, apply, split semantics, preprocessing, evaluation, worker finalization, Dataset/Artifact registration, and reusable-model contracts are ordinary integration-test responsibilities. Agent benchmarks must not compensate for missing service coverage.

### D-004 — Agent benchmark owns workflow behavior

**Status:** confirmed by Sir on 2026-08-09.

The Agent benchmark evaluates business-language interpretation, Tool selection, typed argument construction, orchestration, waiting/recovery, public output use, final-answer grounding, and headed rendering. The earlier proposal to emit `blocked_by_service` is superseded by D-008: service failure prevents paid CI dispatch but is never read or translated by the Agent benchmark.

### D-005 — Evidence before optimization

**Status:** confirmed by Sir's non-binding hypothesis framing on 2026-08-09.

Preprocessing, Skills, Tool schemas, orchestration, logs, and traces are candidate causes, not assumed causes. Change the lowest responsible seam after reproducing a failure and finding the first divergence.

### D-006 — Private material boundary

**Status:** evidence-imposed guardrail.

The supplied corpus remains ignored and evaluator-private while licensing is unresolved. Subject and evaluator use separate filesystem projections. Serialized Joblib artifacts are never loaded; models are rebuilt from code/data where safe.

### D-008 — Physical and execution independence

**Status:** confirmed by Sir on 2026-08-09.

Service black-box integration tests and all executable support live under `tests/`. Agent Harness benchmark cases and all executable support live under `benchmarks/agent_harness/`. Neither side imports, invokes, or consumes reports from the other. Development guidance and CI dispatch order run service tests first solely to avoid paid measurement of an unqualified product path.

### D-009 — Paid live Agent evidence with hard safety limits

**Status:** confirmed by Sir on 2026-08-09.

Every Agent Harness baseline, improvement, ablation, or acceptance evidence run uses the real configured LLM/provider path and therefore incurs live cost. Record/replay, stubs, and offline infrastructure checks are never Agent benchmark evidence. Every cell is isolated and receives a hard sampling-round limit and hard wall-time limit before provider work begins; reported token ceilings add a secondary stop policy without pretending arbitrary OpenAI-compatible providers expose a portable hard token reservation.

### D-010 — One pinned subject model

**Status:** confirmed by Sir on 2026-08-09.

B0 benchmarks the Harness, not competing models. One settings hash and one explicit `provider/model` key remain fixed across a comparable baseline/improvement/ablation series. Omitting `--model` selects only `default_fq_model_key`; `--model` is a single override, not a repeatable matrix axis. Changing the model starts a separate evidence series.

## Approved B0 Details

### P-001 — Versioned acceptance-policy command

**Status:** approved by Sir on 2026-08-09.

Keep Agent benchmark execution as measurement and add a separate Agent-report command that fails on approved integrity, semantic, repetition, identity, and budget thresholds. It does not read service-test reports.

### P-005 — Dual fixture profiles

**Status:** approved by Sir on 2026-08-09.

Commit only independently designed `ci_synthetic` fixtures. Keep textbook bytes and every derivative of those bytes in ignored `external_full` / `private_derived` storage for internal realism and oracle qualification. Service and Agent executable fixtures remain owned by their separate trees even when they represent the same planning risk.

### P-006 — Honest proof-portfolio expansion

**Status:** approved by Sir on 2026-08-09.

Admit the material business-workflow service tests even though the current 45-case suite will cross the existing 50-case review trigger. Perform the required architecture review explicitly; do not merge unrelated cases or hide collection through parameterization merely to stay at 50.

### P-007 — Qualified live baseline and formal acceptance

**Status:** approved with D-008/D-009 corrections by Sir on 2026-08-09.

After the corresponding independently owned service black-box tests pass, run one bounded headless paid live baseline per new Agent workflow. Formal `3 × headless + 1 × headed` evidence follows for an accepted Harness/product state. The order is development guidance and CI dispatch control only; the Agent runner and evaluator do not check service status. Once an implementation handshake is explicitly started, these bounded live runs require no separate fee checkpoint.

## Later Product Proposals

### P-002 — Forecast v1 scope

Start with univariate seasonal forecasting and optional independent groups. Use chronological holdout or rolling origin, a seasonal-naive baseline, Holt-Winters, and bounded forecast intervals. Decide whether SARIMA belongs in the same implementation handshake after baseline cost/runtime evidence.

### P-003 — Recommendation v1 scope

Start with popularity/cold-start and personalized collaborative Top-K with seen-item exclusion. Defer matrix factorization and hybrid ranking until evaluation and apply contracts are proven.

### P-004 — Text benchmark scope

Use bilingual preprocessing plus a safe topic/text-insight case first. A classification benchmark requires grouped-template splitting or a new independent fixture; the supplied naïve random split is not accepted as generalization evidence.
