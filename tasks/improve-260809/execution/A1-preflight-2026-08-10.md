# A1 Formal ML Agent Acceptance Preflight — 2026-08-10

## Scope and Verdict

This was a provider-free admission audit. No Subject or Judge request and no
paid Agent cell ran.

**Verdict:** `blocked`; do not dispatch A1. The local desktop can host headed
execution. The initial preflight identified four apparent admission failures:

1. topic outcome closure is still in progress;
2. no independent Judge settings/model snapshot is available;
3. the five Judge-required cohort rubrics had no calibration suites;
4. the dispatch/report relationship was interpreted as requiring one shared
   `identity.invocation_id` across all four repetitions.

The later [A2 readiness audit](A2-harness-readiness-2026-08-10.md) corrected the
fourth item: it was not a real blocker. The report policy intentionally accepts
four distinct invocation IDs, and the existing formal-policy test already used
that topology. A2 also installed five exact-rubric calibration suites. Remaining
admission failures are topic closure/collection, a final clean immutable state,
and an external independent Judge snapshot plus five passing calibration runs.

## Repository Identity

The audit started from a fully clean index and tracked worktree at:

- commit `29138a77fc78b775bd50d484095c01b7f9fd83a5`;
- tree `d21814d3c1b58b800958a8e544f20fe7ec5a4211`;
- subject-settings SHA-256
  `578FB6960F5373A00CC77B815CAD41E9150760DCA8E61EE2DA0F60C9E744E026`;
- effective subject-settings SHA-256
  `e0fc36fec27a23343b89cdf36e5f5c78f2b95cdfce072a95cb46f5ef4a54987a`;
- selected Subject model-identity SHA-256
  `2271ef8fe957f49f55831a057c646e6d5335a6625b934e0eda65c686c390ea60`;
- embedding-settings SHA-256
  `84855E3EADB8F092BBE6E6E87D5ECAD071F1981359295FBA2826AEC4630F0397`.

The untracked/ignored Subject and Embedding snapshots both exist, parse through
the production schemas, select configured models, and have non-empty credential
and endpoint slots. This record deliberately retains neither credentials,
endpoints, provider/model names, nor filesystem paths.

During the audit, the topic case acquired concurrent uncommitted changes. The
preflight therefore does **not** freeze final repository, case, fixture,
evaluator, or runtime hashes. Re-run the complete admission block after topic
closure on the final clean commit.

## Exact Six-Case Cohort

| Capability | Exact selector | Judge |
| --- | --- | --- |
| Cleaning | `benchmarks/agent_harness/test_ml_cleaning.py::test_ml_cleaning` | not required |
| Clustering | `benchmarks/agent_harness/test_ml_cluster_selection.py::test_ml_cluster_selection` | required |
| Forecasting | `benchmarks/agent_harness/test_ml_forecast_validation.py::test_ml_forecast_validation` | required |
| Personalized recommendation | `benchmarks/agent_harness/test_ml_recommendation_ranking.py::test_ml_recommendation_ranking` | required |
| Grouped text classification | `benchmarks/agent_harness/test_ml_text_grouped_classification.py::test_ml_text_grouped_classification` | required |
| Topic discovery | `benchmarks/agent_harness/test_ml_text_topic_discovery.py::test_ml_text_topic_discovery` | required |

Each selector collected exactly one item. The combined command collected six
items in both modes:

```powershell
$selectors = @(
  'benchmarks/agent_harness/test_ml_cleaning.py::test_ml_cleaning'
  'benchmarks/agent_harness/test_ml_cluster_selection.py::test_ml_cluster_selection'
  'benchmarks/agent_harness/test_ml_forecast_validation.py::test_ml_forecast_validation'
  'benchmarks/agent_harness/test_ml_recommendation_ranking.py::test_ml_recommendation_ranking'
  'benchmarks/agent_harness/test_ml_text_grouped_classification.py::test_ml_text_grouped_classification'
  'benchmarks/agent_harness/test_ml_text_topic_discovery.py::test_ml_text_topic_discovery'
)
pdm run benchmark-agent-harness -- @selectors --collect-only -q
pdm run benchmark-agent-harness-headed -- @selectors --collect-only -q
```

Observed: `6 tests collected` headless and `6 tests collected` headed.

## Service and Offline Gates

The exact public service modules corresponding to the six business risks passed
together:

```powershell
pdm run pytest --direct `
  tests/test_ml_foundation_profile_cleaning.py `
  tests/test_ml_clustering_service.py `
  tests/test_ml_forecasting_service.py `
  tests/test_ml_recommendation_service.py `
  tests/test_ml_text_classification_service.py `
  tests/test_ml_text_discovery_service.py -q
```

Observed: `22 passed`; 156 existing Joblib/NumPy deprecation warnings.

Additional provider-free gates:

| Command | Result |
| --- | --- |
| `pdm run benchmark-agent-harness-check -q` | 30 passed |
| `pdm run check` | exit 0 |
| `pdm run smoke` | exit 0 |

The later [final current-worktree verification](final-verification-2026-08-10.md)
requalified `pdm run test -q`, Harness offline checks, repository checks, app
smoke, package creation, and a direct isolated packaged-executable smoke after
all retained O1/O2/A2/M1 changes and the O3 rollback. Official
`pdm run smoke-package` remains blocked before app launch by the missing locked
OCR golden image. These results qualify the current worktree, not a future
immutable commit; A1 must freeze and recheck hashes after that commit exists.

## Judge Admission

- No Judge settings environment path is configured and no ignored Judge settings
  snapshot was found.
- Subject/Judge model disjointness is therefore unknown, not passed.
- Five cases require a Judge. At initial preflight, repository search found
  calibration packets only for the unrelated revenue-chart case.
- `benchmark-agent-harness-calibrate-judge` correctly rejects a same-model Judge,
  uses at most four packets with three repetitions each, and binds the report to
  Judge settings, Judge model, Subject model, and exact rubric hash. Those facts
  do not substitute for the missing external snapshot.

A2 added a versioned, case-independent manifest whose five suites reference the
live cases' authoritative rubric symbols. Each suite contains one hand-labelled
`pass`, `partial`, `fail`, and empty-evidence `inconclusive` packet. The strict
loader rejects schema drift, duplicate identities, non-case symbols, and a
suite/rubric identity mismatch before provider dispatch. Once external Judge
settings exist, each rubric needs its own command of this shape and a passing
bounded report:

```powershell
pdm run benchmark-agent-harness-calibrate-judge -- `
  --manifest benchmarks/agent_harness/fixtures/ml_formal_judge_calibrations.json `
  --manifest-suite <exact-rubric-id> `
  --judge-llm-settings <external-judge-settings.json> `
  --judge-model <independent-judge-provider/model> `
  --subject-model <pinned-subject-provider/model> `
  --output <bounded-calibration-report.json>
```

## Headed Feasibility

The current Windows session is interactive, has Explorer in the same session,
uses the native Qt `windows` platform, and exposes one primary screen with
positive geometry. The six headed selectors also collect. Headed execution is
therefore locally feasible once the admission blockers clear; this observation
is not a headed acceptance run.

## Cell and Budget Preflight

The required matrix is exactly:

- 6 cases × 3 headless repetitions = 18 headless cells;
- 6 cases × 1 headed repetition = 6 headed cells;
- total = 24 Subject cells.

Installed worst-case bounds are:

| Bound | Per cell | Per six-cell pass | 24-cell cohort |
| --- | ---: | ---: | ---: |
| Subject sampling rounds | 12 | 72 | 288 |
| Provider attempts | 24 | 144 | 576 |
| Reported Subject tokens | 500,000 | 3,000,000 | 12,000,000 |
| Outer wall time | 900 s | 5,400 s | 21,600 s |

Four six-cell invocations—headless repetitions H1, H2, H3 and headed U1—would
each remain below the 4,000,000-token invocation ceiling even at the six-cell
worst case. Recent one-cell observations sum to 792,210 Subject tokens and
852.365 Subject-turn seconds for one six-case pass, implying a non-binding
planning estimate of 3,168,840 Subject tokens and 3,409.460 Subject-turn seconds
for four passes. This is not admission evidence: the topic observation failed
semantics, Judge requests are separate, provider variance is material, and no
versioned provider price table exists. Monetary cost therefore remains
uncomputed.

Five Judge calibrations add at most 5 × 4 packets × 3 repetitions = 60 Judge
requests, each with a 300-second outer limit. Judge usage, latency, and retries
must remain separate from Subject metrics.

## Dispatch Topology Correction

The intended cell IDs are `H1`, `H2`, `H3`, and `U1` for every selector above.
The natural supported topology would be three headless six-selector commands and
one headed six-selector command, all with the same Subject, Embedding, Judge,
model, variant, case definitions, and frozen hashes. Do **not** run those commands
yet.

Each command creates a new pytest invocation and therefore a new
`identity.invocation_id`; this is the intended topology. Formal acceptance
requires every report to carry a non-empty invocation ID but deliberately omits
that field from cohort-equality checks. The four dispatches independently own
their cumulative budget state, and each six-cell pass remains bounded by the
4,000,000-token invocation ceiling. A user-supplied shared ID would not provide
durable cross-process token accounting and is neither required nor exposed.

Each case is evaluated independently from exactly
three headless and one headed schema-v5 reports plus its exact calibration when
required:

```powershell
pdm run benchmark-agent-harness-evaluate -- formal `
  <case-H1.json> <case-H2.json> <case-H3.json> <case-U1.json> `
  --calibration <matching-calibration.json> `
  --output <case-formal-decision.json>
```

Cleaning omits `--calibration`. Every report, including semantic failures, must
be retained. Stop on settings/hash drift, repository mutation, missing usage,
infrastructure/integrity failure, uncalibrated Judge, or budget admission failure.

## Ready / Blocked Checklist

- [x] Exact six capability selectors identified.
- [x] Six selectors collect headless and headed.
- [x] Six matching service modules pass.
- [x] Offline benchmark checks, repository check, and app smoke pass on the
      observed preflight state.
- [x] Current desktop can host visible Qt execution.
- [x] Subject and Embedding snapshots exist and have safe frozen hashes.
- [ ] Topic product/outcome closure is complete.
- [ ] Final repository state is clean and immutable; all gates and hashes are
      frozen on that exact commit.
- [ ] Independent Judge settings and subject-disjoint model exist.
- [x] Five exact-rubric calibration suites exist and load provider-free.
- [ ] The five exact-rubric calibration runs pass with the frozen independent Judge.
- [x] Supported headless/headed commands produce the four independent,
      per-invocation-budgeted reports accepted by the formal policy.
- [x] Full test/package gates are repeated on the current worktree and the
      scoped package-smoke decision is explicit.
- [x] Sir authorized continuation through A1; dispatch remains forbidden until
      every objective admission item above is green.
