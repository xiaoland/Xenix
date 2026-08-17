# IH-B0 — Independent Paid-Live Agent Evidence Foundation

**Status:** consumed for implementation and offline-verified on 2026-08-09. Paid live characterization is deferred until matching service black-box selectors land green.

## Evidence and Decisions

- Evidence: `E-001`, `E-004`, `E-005`, `E-007`, `E-008`, `E-009`, `E-010`.
- Decisions: `D-002` through `D-010`; approved details `P-001`, `P-005`, `P-006`, revised `P-007`.

## Address and Object

This handshake authorizes the following exact repository scope.

Existing Agent benchmark infrastructure:

- `benchmarks/agent_harness/_infra/contracts.py`: add explicit budget-exhaustion status, budget/variant identity, and bounded persisted measurements.
- `benchmarks/agent_harness/_infra/runner.py`: replace the configured-model matrix with one selected model; run one isolated cell process; enforce the 12-round and 900-second limits; stop on reported-token/integrity conditions.
- `benchmarks/agent_harness/_infra/pytest_plugin.py`: make `--model` single-valued, expose bounded policy options only where lowering a limit is safe, and report one cell rather than a model tuple.
- `benchmarks/agent_harness/_infra/headed.py`: propagate the same cell identity, wall deadline, and terminal budget status through headed execution.
- `benchmarks/agent_harness/_infra/case_support.py` and `benchmarks/agent_harness/conftest.py`: only the small case-agnostic fixture/evidence support needed by the new Agent cases.
- New `benchmarks/agent_harness/_infra/budgets.py`: one deep benchmark-only safety controller; no product imports from benchmark code.
- New `benchmarks/agent_harness/_infra/report_policy.py`: versioned Agent-report acceptance and baseline/improvement/ablation comparison; no service-report input.
- New `benchmarks/agent_harness/_infra/judge_calibration.py`: bounded hand-labelled Judge qualification.

Benchmark-only offline safety checks:

- New `benchmarks/agent_harness/_infra_tests/test_budgets.py`.
- New `benchmarks/agent_harness/_infra_tests/test_model_selection.py`.
- New `benchmarks/agent_harness/_infra_tests/test_report_policy.py`.
- New `benchmarks/agent_harness/_infra_tests/test_judge_calibration.py`.

These checks use no provider and are not Agent benchmark evidence. They are selected only by the dedicated infrastructure-check command, never by `pdm run test` and never as live benchmark cases.

Paid live Agent cases and their independently owned fixtures:

- New `benchmarks/agent_harness/test_ml_cleaning.py`.
- New `benchmarks/agent_harness/test_ml_clustering.py`.
- New `benchmarks/agent_harness/test_ml_forecasting.py`.
- New `benchmarks/agent_harness/test_ml_recommendation.py`.
- New `benchmarks/agent_harness/test_ml_text_insight.py`.
- New safe committed assets below `benchmarks/agent_harness/fixtures/ml_capabilities/`; ignored source/private projections remain in the task packet and are never mounted together with admitted subject inputs.

Commands, guidance, and CI:

- `scripts/run_agent_harness_benchmark.py` and `scripts/run_agent_harness_headed_benchmark.py`: thin single-model/cell-process orchestration only.
- New `scripts/check_agent_harness_benchmark.py`, `scripts/evaluate_agent_harness_reports.py`, and `scripts/calibrate_agent_harness_judge.py`.
- `pyproject.toml`: add the offline infrastructure-check, report-evaluation, and Judge-calibration commands; preserve `pdm run test` as the independent service portfolio.
- New `.github/workflows/agent-harness-benchmark.yml`: manually dispatched paid workflow with a secretless service job first and a secrets-bearing headless Agent job using `needs`; no service artifact or verdict is passed to the Agent job.
- `CONTRIBUTING.md`, `benchmarks/agent_harness/AGENTS.md`, and `docs/30-unit-tdd/agent-harness-benchmark.md`: own the independent-tree rule, service-first development/CI order, live-only evidence definition, single-model semantics, hard safety limits, and command sequence.
- This task packet's evidence/execution records: record bounded qualification and live result identities without credentials, raw rows, transcripts, Tool payloads, or private answers.

Explicitly outside this handshake:

- every file under `src/xenix/`;
- service black-box helpers, fixtures, and cases under `tests/`—they land with `IH-F`, `IH-CF`, and `IH-RT`;
- product PRD/TDD contracts other than the benchmark-owned unit guidance named above;
- changes to Agent Skills, Tool schemas, orchestration, ML services, preprocessing, storage, UI, or observability;
- branches, worktrees, commits, pushes, or publication.

## State Diff

`From`:

- omitting `--model` runs every configured subject model;
- a cell has no hard sampling-round or outer process deadline;
- live benchmark pytest produces measurements but semantic/integrity failure is not a versioned acceptance result;
- three existing cases cover no ML business workflow;
- service qualification is not expressed as development/CI ordering;
- no executable Judge calibration or Harness ablation identity exists.

`To`:

- every invocation runs exactly one pinned subject model, defaulting to `default_fq_model_key`;
- every cell is an isolated process with at most 12 sampling rounds, at most 900 seconds, and two provider attempts per sampling round;
- 500k reported subject tokens per cell and 4,000k per invocation stop future work at response boundaries; missing usage invalidates the cell;
- five independently owned paid live ML Agent cases produce privacy-bounded reports;
- an Agent-only versioned evaluator gates identity, execution, integrity, semantic repetitions, Judge status, and budgets;
- development guidance and manual CI order `pdm run test` before paid live dispatch without creating a runtime dependency;
- comparable baseline/improvement/ablation evidence pins model/settings and records the Harness variant.

## Blast Radius

- Agent benchmark CLI compatibility: repeated `--model` matrices disappear; callers run separate commands for separate models.
- Report schema and consumers: a new schema version records budget exhaustion and variant identity; old reports remain readable or fail with an explicit unsupported-policy reason.
- Live execution lifecycle: each cell moves behind a child-process boundary, including headed cleanup and timeout termination.
- GitHub Actions: a new manual paid workflow requires protected external settings/secrets, while the existing required secretless `Native CI` remains unchanged.
- Benchmark collection grows from 3 to 8 live cases; ordinary `pdm run test` collection is unchanged by IH-B0.

## Invariants

- `tests/` service cases and `benchmarks/agent_harness/` Agent cases never import, invoke, or consume reports from each other.
- `pdm run test` remains deterministic, offline, and provider-free.
- A benchmark evidence run always uses the real LLM/provider path; replay, stub, or recorded-provider output is not baseline or acceptance evidence.
- One cell remains one `AgentHarness × one model × one benchmark-owned case × one execution mode × one repetition` with a fresh runtime home.
- The runner remains case-agnostic; cases own intent, admitted fixture, public outcome locator, bounded evaluator projection, and rubric without prescribing Tool traces.
- Canonical SQLite state, Datasets, Artifacts, and trained-model/task records remain product authority; reports and traces are evidence only.
- Subject and evaluator paths/bytes remain physically isolated. Hidden labels, recommendation truth, future windows, exact answers, reference code, credentials, and raw logs never enter subject inputs or persisted reports.
- Judge measurements remain separate from subject latency/tokens/cost and require an independent calibrated model for formal acceptance.
- No benchmark change creates a production branch, alternate Tool registry, shared service/Agent case kernel, or product behavior change.

## Verification

Offline and structural:

1. Dedicated benchmark infrastructure checks prove one-model selection, refusal of a thirteenth sampling request, child-process timeout classification, response-boundary token stops, old/new report handling, and Judge calibration policy.
2. `pdm run benchmark-agent-harness -- --collect-only -q` and the headed variant each collect exactly the same 8 live cases without provider access.
3. A no-`--model` dry run selects only `default_fq_model_key`; one explicit `--model` selects only that key; a repeated/multi-value form is rejected.
4. Repository search proves no imports between `tests/` service-case support and `benchmarks/agent_harness/`, and the Agent evaluator accepts no service-report argument.
5. `pdm run test`, `pdm run check`, and `pdm run smoke` pass. Packaging gates run only if implementation evidence shows the new benchmark subprocess path affects shipped dependencies or packaging inputs.

Live and paid:

6. A corresponding service black-box selector must already pass before development guidance or CI dispatches its Agent case. This is checked by the caller/workflow, not by benchmark code.
7. The first qualified baseline is one headless live repetition with the pinned model. Formal evidence is three headless repetitions, followed by one headed repetition after headless acceptance.
8. The first retained live result records the installed round/time/token policies and stays within them. Round exhaustion and the 900-second watchdog are proven offline rather than intentionally burning live calls or wall time.
9. Every retained result is inspected for separate execution, integrity, semantic, subject metrics, Judge status/metrics, settings/fixture/repository/variant identity, and privacy-bounded serialization.

## Live Execution Authority

When Sir explicitly starts this handshake, qualified live baseline and acceptance calls within these fixed limits are authorized without a second fee confirmation. A live case still waits until its independent service selector is green and external untracked settings are available. Headed execution additionally waits for an interactive desktop.

## Return to Discussion

Return before mutation or further live calls if:

- enforcing the 12-round or 900-second hard limit requires a change under `src/xenix/`;
- a service test or report must be imported or read by benchmark code to make the workflow function;
- a safe Agent fixture cannot be built without copying unresolved source/private bytes into tracked files;
- provider usage cannot be observed and the runner cannot stop safely after the first response;
- the benchmark child-process boundary changes product runtime or packaging behavior;
- implementation needs any file outside the Address and Object list;
- a branch, worktree, commit, push, publication, or new external authority is required.
