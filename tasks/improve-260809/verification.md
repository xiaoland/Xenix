# Verification Architecture

## Responsibility Contract

> Given a valid typed command, service tests prove the machine-learning facts are correct. Given business language and admitted files, Agent benchmarks prove the Harness selects, orchestrates, and explains the correct workflow.

| Layer | Owns | Does not own |
| --- | --- | --- |
| Oracle qualification | Fixture identity, split, hidden truth, expected result, tolerance, runtime compatibility, contamination checks | Product behavior or Agent quality |
| Service integration | Data import/preparation, leakage rules, model fit/evaluate/apply, worker/finalizer, registered outputs, reusable contracts | Business-language planning or prose quality |
| Agent Harness benchmark | Task interpretation, Tool routing, legal typed calls, orchestration, public Dataset/Artifact use, grounded explanation, headed rendering | Re-proving estimator math when service qualification is red |

Service tests and Agent benchmarks share no executable code, fixtures, reports, or runtime prerequisite. Their common business-risk names live only in planning guidance. A service failure prevents CI from dispatching a paid Agent job; it does not suppress, rewrite, or classify the verdict of a benchmark started independently.

## Qualification Order

1. Validate fixture hash, runtime identity, oracle version, subject/evaluator path disjointness, content-hash disjointness, and answer-string contamination checks.
2. Run the independently owned service black-box suite under `tests/`.
3. In development guidance or CI, dispatch the paid benchmark command only after step 2 passes; pass no service artifact or verdict into it.
4. Run the independently owned headless Agent case and inspect public Dataset/Artifact/final-answer outcomes.
5. Run headed mode for the same benchmark-owned case definition when UI delivery is in scope.
6. Apply the separately versioned Agent-report policy.

## Proposed Acceptance Policy

This is the recommended B0 policy. Sir reviews its material cost/evidence trade-off through `O-003`; detailed thresholds remain implementation policy:

- Every cell requires completed execution, persisted canonical state, all critical integrity checks, and deterministic public-output prerequisites.
- Leakage, temporal ordering, source immutability, and seen-item exclusion must pass every repetition; aggregate scores cannot mask them.
- If a Judge is required, unavailable, malformed, or inconclusive judging is not acceptance.
- Formal acceptance requires deterministic/integrity conditions `3/3`; irreducible semantic judgment passes at least `2/3`, with every verdict retained. The first qualified headless live baseline is deliberately single-sample and never a regression gate.
- Comparable Agent runs bind the same benchmark case ID, fixture/evaluator version, repository/runtime identity, single subject model/settings hash, Judge settings, and repetition policy. Service identifiers are not part of the Agent report contract.
- Preflight computes `one pinned subject model × cases × Harness variants × execution modes × repetitions`.
- Every subject cell has a hard maximum of 12 provider sampling rounds, a hard 900-second outer process deadline, and two provider attempts per sampling round. A thirteenth round is not dispatched; a timed-out process is terminated; either outcome is `budget_exceeded` with no semantic verdict.
- Reported subject tokens have a 500,000-token per-cell stop and a 4,000,000-token aggregate run stop. Because arbitrary OpenAI-compatible providers do not expose a portable tokenizer or output reservation, this is enforced at response boundaries and is not represented as a strict pre-request token cap. Missing usage invalidates the cell and stops remaining cells.
- Monetary cost is derived only when a versioned provider price table is supplied; tokens, requests, and wall time remain the portable facts.

## Failure Attribution

| First failing evidence | Owner classification |
| --- | --- |
| Independent service black-box case fails for the corresponding business risk | `service` / `data` / `worker` |
| Legal typed call rejected by schema/adapter | `tool-boundary` |
| Agent chooses wrong Tool or emits schema-invalid arguments | `agent` |
| Public Dataset/Artifact is correct but final answer contradicts it | `agent-grounding` |
| Headless passes and headed fails | `ui` |
| Judge unavailable, malformed, or inconsistent with calibration | `evaluator` |
| Setup/hash/isolation failure | `setup` |

Attribution is a post-run diagnostic activity over independent evidence; the Agent evaluator never reads a service report. Each real defect gets a regression test at the lowest responsible layer. Change a benchmark only when the user-visible outcome or evaluator contract changed.

## Repository Gates

For each approved slice:

1. Focused direct service/public-boundary integration tests under `tests/`.
2. `pdm run test`; this is the service-stage CI gate.
3. Focused offline benchmark infrastructure/policy checks under `benchmarks/agent_harness/`; these are not benchmark evidence.
4. Independently invoked qualified paid live Agent cases under `benchmarks/agent_harness/`; CI expresses step 2 -> step 4 only through job ordering.
5. `pdm run check`.
6. `pdm run smoke`.
7. `pdm run package` and `pdm run smoke-package` when shipped runtime or dependencies change.

The current benchmark pytest exit code remains measurement-only until proposed `P-001` is approved and implemented.
