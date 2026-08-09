# B0 Offline Implementation — 2026-08-09

## Identity and Scope

- Run ID: `B0-OFFLINE-260809-01`.
- Base revision: housekeeping commit `3e29f5e`; verification was performed against the complete B0 implementation and task-record update before its implementation commit.
- Scope: Agent benchmark/evaluator infrastructure, five clean-room Agent cases, thin commands, development guidance, and one manual ordered CI workflow.
- Excluded: `src/xenix/` behavior, `tests/` service cases, paid provider calls, and branches/worktrees.

## Implemented State

- One subject model per invocation, defaulting to the external settings snapshot's `default_fq_model_key`, with one optional override.
- One killable spawn child per cell; 12 subject sampling rounds, 900 seconds, two attempts per round, 500,000 reported subject tokens per cell, and 4,000,000 per invocation.
- Usage, persistence, integrity, unexpected runner exceptions, and budget exhaustion fail closed and stop remaining paid cells.
- Privacy-bounded schema v5 report, non-gating characterization, formal `3 headless + 1 headed` policy, comparable Harness-variant cohorts, and explicit independent Judge calibration.
- Comparable runtime identity binds the full repository commit, Python/platform, dependency lock, case definition, and shared benchmark execution code.
- Five clean-room live Agent cases: data cleaning, two-segment clustering, explicit lag-four seasonal-naive transformation, item-similarity recommendation, and bilingual keyword frequency.
- Manual CI runs one explicit matching service selector plus the ordinary service portfolio before one separately selected paid Agent cell; only the job-success edge crosses between jobs.

## Verification Results

| Check | Result |
| --- | --- |
| Provider-free benchmark infrastructure, safety, report-policy, and Judge-calibration suite | 26 passed |
| Headless live catalog collect-only | 8 cases |
| Headed live catalog collect-only | same 8 cases |
| Explicit headless selector collect-only | 1 case |
| Explicit headed selector collect-only | 1 case |
| Ordinary service portfolio | 45 passed |
| Static/type/import/compile checks | passed |
| Isolated-runtime desktop smoke | passed in 82.2 seconds |
| Package and packaged smoke | not required; B0 changed no shipped runtime, dependency, or packaging input |
| Workflow YAML parse | passed |
| Cross-tree executable-import search | no service/Agent dependency found |
| Clean-room reverse scan | no full-file, data-row, or complete-row byte match found against the ignored corpus |

The first smoke attempt exceeded the command wrapper's 120-second observation limit and its verified process tree was terminated. A clean task-local runtime with a 300-second command ceiling completed in 82.2 seconds; no product-source change was needed.

## Verification Fixes Applied

- Explicit live selectors now replace the default benchmark root instead of unioning with all eight paid cases.
- The dedicated offline checker rejects extra selectors and live-provider options.
- Exact 500k-cell and 4m-invocation response boundaries remain valid measurements while blocking later work; reader and runner projections agree.
- Provider attempts are enforced in the budget controller rather than only through settings.
- Persistence failure, integrity failure, and unexpected runner exceptions halt the remaining invocation.
- Early invalid-setup reports preserve prior invocation token totals.
- Headed SQLite integrity checks require an existing database and open it read-only.
- Clustering verifies original feature values and non-empty labels; final-answer oracles were tightened against contradictory keyword co-occurrence.

## Deferred Evidence

No paid live baseline was run. The new cases represent workflows that later product slices must qualify through independently owned black-box service selectors first. The lag-four case proves only deterministic Agent orchestration through existing data transformation; it does not claim that native forecasting exists.

Next design target: `IH-F` (foundation: bounded profile/evaluation/result facts and split-aware preparation), followed by the `O-004` forecast-scope decision needed for `IH-CF` (clustering trustworthiness and the first native forecast workflow).
