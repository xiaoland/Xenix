# A1 Implementation Plan — Formal ML Agent Acceptance

**Status:** Blocked on topic outcome closure, a clean immutable state, and independent Judge settings/calibration.

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
- existing 12-round, 900-second, two-attempt, 500k-token cell limits and 4m-token invocation limit.

Run service qualification and offline Harness checks first through workflow ordering only. Paid cells remain independently executable and never read service results.

## Coherent Passes

1. Calibrate the independent Judge and freeze rubric hashes.
2. Run a cost/token/time preflight and enumerate the exact 24 cells.
3. Execute three headless repetitions per case; persist every verdict, including failures.
4. Execute one headed cell per case on an interactive desktop and verify the same public Dataset/Artifact/final-answer outcome.
5. Apply the versioned report policy and publish only bounded aggregate completion, latency, token, Tool-count, Judge, integrity, and semantic facts.

## Stop Conditions

Stop the cohort on settings/hash drift, missing usage, infrastructure/integrity failure, uncalibrated Judge, repository mutation, or aggregate budget admission failure. A semantic failure is retained as evidence and returns to a new diagnosis plan; it is not retried until it passes.

## Acceptance

- Critical deterministic and integrity conditions pass `3/3` headless and the headed cell.
- Irreducible semantic/Judge conditions pass at least `2/3` headless and the headed cell under the approved policy.
- No unavailable, malformed, same-model, or uncalibrated Judge result is counted as acceptance.
- Costs are reported as tokens/requests/time unless a versioned provider price table is supplied.
