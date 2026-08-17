# IH-A2 — Formal Agent Harness Readiness

**Status:** consumed and provider-free verified on 2026-08-10. No Subject or
Judge provider call was authorized or made by this slice.

## Evidence

- A1 preflight claimed formal acceptance required one invocation ID shared by
  three headless and one headed report.
- `report_policy._cohort_identity_reasons` requires a non-empty invocation ID
  per report but does not compare it across a cohort.
- The existing formal-policy test constructed four different invocation IDs and
  accepted the cohort.
- Each pytest invocation owns in-memory cumulative token state and passes it
  between its selected cells; the runner refuses a later cell at 4,000,000 and
  invalidates a response-boundary overrun.
- Five A1 cases require a Judge, while only the unrelated revenue chart exposed
  calibration packets before A2.

## Address and Object

- `benchmarks/agent_harness/_infra/calibration_manifest.py`: add a strict,
  case-agnostic loader for versioned hand-labelled calibration inputs that
  resolve authoritative live-case rubric symbols.
- `benchmarks/agent_harness/_infra/report_policy.py`: document the existing
  dispatch-local invocation identity contract without changing policy logic.
- `benchmarks/agent_harness/_infra_tests/test_calibration_manifest.py` and
  `test_report_policy.py`: prove exact-rubric binding, fail-closed manifest
  loading, and acceptance of four independently budgeted invocation IDs.
- `benchmarks/agent_harness/fixtures/ml_formal_judge_calibrations.json`: add one
  bounded four-packet suite for each of the five Judge-required A1 rubrics.
- `scripts/calibrate_agent_harness_judge.py`: accept either the existing
  `module:symbol` suite or an explicit `--manifest/--manifest-suite` pair.
- A1/A2 task implementation, execution, handshake, and index records: correct
  the preflight claim and retain exact provider-free evidence.

## State Diff

`From`:

- A1 records treat four distinct pytest invocation IDs as a formal-policy
  incompatibility and propose a shared-ID interface;
- five exact A1 rubrics have no runnable calibration inputs;
- exposing an ID alone would allow no reliable cross-process 4m aggregate state.

`To`:

- invocation ID is explicitly dispatch-local; formal acceptance consumes three
  headless and one headed report from four independent, budget-owning
  invocations;
- no user-supplied shared-ID or cross-process state replica is added;
- a versioned manifest supplies bounded `pass`, `partial`, `fail`, and
  `inconclusive` packets for each authoritative rubric;
- the existing calibration engine remains the sole owner of repetitions,
  independence, provider dispatch, report projection, and exact rubric hash.

## Blast Radius

- Calibration CLI callers gain one additive input mode. Existing
  `module:symbol` commands remain valid.
- Loading the formal manifest imports the referenced live case modules to obtain
  their rubric objects and fails closed if a case cannot import or its rubric ID
  drifts.
- Formal acceptance behavior and report schema do not change; only its existing
  invocation semantics become explicit and regression-protected.

## Invariants

- One subject cell remains one pinned model, case, mode, and repetition.
- The installed 12-round, 900-second, two-attempt, 500k-cell, and 4m-invocation
  limits are not raised or bypassed.
- Invocation token state has one owner per pytest process; no caller-authored ID
  is treated as budget authority.
- Judge settings/model remain independent from Subject settings/model. No
  same-model, unavailable, malformed, or uncalibrated result can satisfy formal
  acceptance.
- Case prompts, semantic checks, rubrics, private fixtures, and Judge report
  evidence are not changed by A2.
- Calibration manifests are labelled test inputs, never fabricated Judge
  observations or formal evidence. A passing live calibration report still
  requires the external Judge.

## Verification

1. `pdm run benchmark-agent-harness-check -q` passes without a provider.
2. The manifest loader resolves exactly five authoritative rubric identities,
   with four distinct expected verdicts per suite, and rejects identity drift or
   non-case symbol references.
3. The formal-policy test proves four distinct invocation IDs remain accepted
   only when every other identity, execution, integrity, budget, semantic, and
   calibration condition passes.
4. Headless and headed collect-only commands discover the same exact six A1
   selectors without provider access.
5. `pdm run check` and `git diff --check` pass.

## External Boundary

A2 does not run a calibration or Subject cell. Formal A1 remains blocked until
an external, subject-disjoint Judge snapshot is frozen and all five exact-rubric
calibrations pass. Topic closure and final clean-state qualification remain
separate A1 admission conditions.
