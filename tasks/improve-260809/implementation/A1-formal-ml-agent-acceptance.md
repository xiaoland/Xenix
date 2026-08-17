# A1 Implementation Plan — Formal ML Agent Acceptance

**Status:** Admission-blocked on topic outcome closure, a clean immutable state,
and an independent Judge settings/model snapshot plus five passing calibration
runs. All provider-free readiness work and current-worktree regression/package
gates are complete.
The A2 audit removed the earlier cross-mode invocation blocker and installed
the exact-rubric calibration inputs. See the
[provider-free preflight](../execution/A1-preflight-2026-08-10.md) and
[A2 execution record](../execution/A2-harness-readiness-2026-08-10.md).

## Outcome

Apply the approved report policy to a comparable six-case ML cohort: cleaning, clustering, forecasting, personalized recommendation, grouped text classification, and topic discovery. This converts single-run characterization into formal Agent Harness evidence without using service reports as benchmark inputs.

## Preconditions

- All corresponding service selectors, `pdm run test`, `pdm run check`, app smoke, and relevant package smoke pass on one clean commit.
- O1 and any exact topic product optimization are complete; one fresh topic characterization passes deterministic semantics/integrity.
- One pinned subject model/settings snapshot and an independent Judge model/settings snapshot are frozen.
- Judge calibration passes the exact rubric identities used by the cohort.
- Case, fixture, evaluator, runtime, settings, and repository hashes are recorded before dispatch.

## Cohort

For each of the six named cases:

- three independent headless cells;
- one headed UI cell;
- the same subject model, settings, case definition, fixture, evaluator, and Harness variant;
- existing 12-round, 900-second, two-attempt, 500k-token cell limits;
- four independent pytest invocations—`H1`, `H2`, `H3`, and `U1`—each owning
  its own ID, cumulative token state, stop conditions, and 4m-token invocation
  limit. Formal acceptance does not use invocation ID as a cohort key.

Run service qualification and offline Harness checks first through workflow ordering only. Paid cells remain independently executable and never read service results.

## Coherent Passes

1. Calibrate the independent Judge against each suite in
   `benchmarks/agent_harness/fixtures/ml_formal_judge_calibrations.json` and
   freeze the five resulting rubric hashes.
2. Run a cost/token/time preflight and enumerate the exact 24 cells.
3. Execute three headless repetitions per case; persist every verdict, including failures.
4. Execute one headed cell per case on an interactive desktop and verify the same public Dataset/Artifact/final-answer outcome.
5. Apply the versioned report policy and publish only bounded aggregate completion, latency, token, Tool-count, Judge, integrity, and semantic facts.

## Stop Conditions

Stop the active invocation on settings/hash drift, missing usage,
infrastructure/integrity failure, repository mutation, or its aggregate budget
admission failure. Do not start the formal cohort until all five Judge
calibrations pass. A semantic failure is retained as evidence and returns to a
new diagnosis plan; it is not retried until it passes.

## Acceptance

- Critical deterministic and integrity conditions pass `3/3` headless and the headed cell.
- Irreducible semantic/Judge conditions pass at least `2/3` headless and the headed cell under the approved policy.
- No unavailable, malformed, same-model, or uncalibrated Judge result is counted as acceptance.
- Costs are reported as tokens/requests/time unless a versioned provider price table is supplied.
