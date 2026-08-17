# Final Current-Worktree Verification — 2026-08-10

## Scope and Verdict

This record verifies the retained O1 evaluator correction, O2 Modeling Skill
audit, A2 calibration readiness, M1 task evidence, and complete rollback of the
rejected O3 product experiment. It contains no Provider call and does not claim
formal A1 acceptance.

**Verdict:** all internally executable repository and package gates passed on
the current worktree. A1 remains admission-blocked by the missing independent
Judge settings/model and five live calibration reports, the lack of a clean
immutable final commit, and the still-open topic final-answer outcome.

## Verification Results

| Gate | Result |
| --- | --- |
| `pdm run test -q` | 136 passed; only existing Joblib/NumPy deprecation warnings |
| `pdm run benchmark-agent-harness-check -q` | 33 passed |
| `pdm run check` | exit 0 |
| `pdm run smoke` | exit 0 |
| six A1 selectors, headless collect-only | exactly 6 collected |
| six A1 selectors, headed collect-only | exactly 6 collected |
| `pdm run package` | exit 0 in 833.4 seconds |
| rebuilt `xenix.exe --smoke-test` with isolated runtime | exit 0 in 78.3 seconds |
| `pdm run smoke-package` | blocked before app launch: locked Native OCR golden image absent |
| `git diff --check` | passed after task-packet synchronization |

The packaged executable embeds commit `29138a77fc78b775bd50d484095c01b7f9fd83a5`
because the retained work is intentionally uncommitted. That build identity is
not suitable for the formal A1 cohort; a new explicitly approved commit and
fresh frozen hashes are required first.

## Boundary of the Result

- O1 is complete: the `artifact://` path false positive is fixed and the first
  remaining divergence is final Provider synthesis.
- O2 is retained: its canonical pre-finalization audit is structurally sound,
  but paid samples did not reliably include every isolation/offline fact.
- O3 is rejected: its source and ordinary-test changes were rolled back after a
  valid paid no-improvement result.
- M1 is complete: two private material cells qualified and two stopped at stable
  semantic admission failures without substitution.
- A2 is complete provider-free: five strict exact-rubric calibration suites are
  ready for an external subject-disjoint Judge.
- A1 did not run. No uncalibrated or same-model Judge result can be promoted to
  formal acceptance.

Two isolated packaged-smoke runtime directories were retained for manual
cleanup. Their local paths are intentionally omitted from this tracked record.
