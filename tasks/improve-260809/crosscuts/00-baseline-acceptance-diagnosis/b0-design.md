# B0 Solution — Independent Capability Evidence Foundation

## Outcome

B0 establishes the Agent-evidence substrate before product behavior changes. It does not add forecasting, improve algorithms, edit Agent Skills, repair orchestration, or implement service black-box cases. It gives every later slice stable answers to:

1. What business risk and private evidence are being evaluated?
2. What does the independently owned typed public service test prove?
3. What does the independently owned paid live Agent case prove?
4. What changed in completion, correctness, latency, Tools, tokens, and cost?
5. At which layer did a failure first appear when the independent evidence is analyzed afterward?

## Recommended Repository Shape

```text
tests/
├─ ml_case_support.py                   # service-test-only helpers/oracles
├─ fixtures/ml_capabilities/            # service-test-only clean-room fixtures
├─ test_ml_service_preparation.py
├─ test_ml_service_clustering.py
├─ test_ml_service_forecasting.py
├─ test_ml_service_recommendation.py
└─ test_ml_service_text.py

benchmarks/agent_harness/
├─ _infra/                              # Agent-benchmark-only runtime/policy
├─ _infra_tests/                        # offline safety checks; not benchmark evidence
├─ fixtures/ml_capabilities/            # Agent-benchmark-only admitted/private assets
├─ test_ml_cleaning.py
├─ test_ml_clustering.py
├─ test_ml_forecasting.py
├─ test_ml_recommendation.py
└─ test_ml_text_insight.py

scripts/
├─ check_agent_harness_benchmark.py
├─ calibrate_agent_harness_judge.py
└─ evaluate_agent_harness_reports.py

.github/workflows/
└─ agent-harness-benchmark.yml          # manual paid CI: service job -> live Agent job
```

The service files land with their owning product vertical, not in `IH-B0`. Exact B0 files are fixed in [IH-B0](../../handshakes/IH-B0.md).

## Independent Executable Ownership

The task packet shares planning vocabulary only:

- a stable business-risk ID and description;
- the service fact that belongs under `tests/`;
- the Agent behavior that belongs under `benchmarks/agent_harness/`;
- the source/provenance and private-evidence restrictions that both implementations must independently honor.

There is no importable shared kernel, shared fixture directory, service prerequisite field, service-report join, workflow DSL, estimator catalog, second Tool registry, or case-id switchboard. Post-run diagnosis may relate independent results by the planning risk, repository revision, and bounded runtime facts, but no executable consumes the other's files or verdict.

## Dual Fixture Policy

`ci_synthetic` fixtures are small and independently designed from the business contract. Service copies/projections live only under `tests/` and run in default CI. Agent copies/projections live only under `benchmarks/agent_harness/`, collect offline, and execute only through the paid live command. `external_full`, `private_derived`, and `oracle_private` remain ignored and explicit. Material absence never affects `pdm run test`; an explicitly selected external evaluation fails closed on missing or hash-mismatched inputs.

The external full case may cover the same planning risk as CI, but it does not share raw bytes, executable manifests, thresholds, or reports across service and Agent trees. This preserves realistic internal evaluation without turning unresolved textbook material into a repository dependency.

## Service Acceptance Shape

Ordinary integration tests use public domain boundaries without an LLM:

```text
service-owned clean-room fixture
-> isolated XENIX_APP_HOME + production service graph
-> Dataset import/register
-> public data preparation / role binding / ML task command
-> real local worker execution and parent finalization
-> public Dataset / Artifact / trained-model / task inspection
-> service-test-owned private oracle
```

Tests assert user-costly outcomes: source immutability, split isolation, temporal order, metrics, output grain/schema, lineage, registered results, and honest reusable apply. They do not assert estimator classes, private branches, worker thread order, raw artifact paths, or exact Tool traces.

Missing capabilities are recorded in task evidence as `missing` or `partial`. They are not committed as `xfail` or permanently passing "unsupported" tests. Each final service workflow case lands green with its owning product slice and remains outside `IH-B0`.

## Proof-Portfolio Review

The current suite collects 45 cases. The intended high-value service additions across the product verticals are approximately:

- one cleaning and grouped-preparation workflow;
- one clustering workflow;
- one forecasting workflow;
- one recommendation workflow;
- one or two text workflows.

The likely final count is 52–55, triggering the documented review but remaining far below the hard ceiling of 100. These cases protect distinct product outcomes and pass the existing admission rule. They must not be collapsed or hidden merely to avoid the trigger. The review rejects resurrection of the former large branch-mirroring ML test matrix.

`IH-B0` does not add these ordinary cases; `IH-F`, `IH-CF`, and `IH-RT` own them with the behavior they prove.

## Agent Benchmark Shape

Agent cases independently own their business-language prompt, admitted fixture, public output locator, bounded evaluator projection, rubric, and report identity. The benchmark does not prescribe Tools, repeat service math, import test helpers, or read service reports.

Failure attribution happens after both independent commands have run. A service failure belongs to `service/data/worker`; a legal typed-call rejection belongs to `tool-boundary`; wrong selection/orchestration or a contradiction of correct public output belongs to the Agent; integrity failure belongs to evaluator/setup. This analysis is not an acceptance-aggregator dependency.

## Measurement, Safety, and Acceptance

The runner produces one privacy-bounded result for one `AgentHarness × one model × one benchmark-owned case × one mode × one repetition` cell. A separate versioned Agent-report evaluator owns pass/fail. It validates execution, persistence, integrity, benchmark case/settings/repository/variant identity, Judge status, repetitions, and budgets. It has no service-report input.

Qualified live baseline:

- run only after the corresponding independent service black-box cases pass through development guidance or CI order;
- use one subject model: the external settings snapshot's `default_fq_model_key`, or one single `--model` override;
- run one headless cell per newly qualified Agent workflow, with no headed run or repetition for the first baseline;
- reduce provider attempts to two and disable optional title/guard models in the snapshot;
- run one isolated process/cell with a hard maximum of 12 sampling rounds and a hard 900-second outer wall deadline;
- do not dispatch a thirteenth sampling request; terminate a timed-out process; persist either as `budget_exceeded` without semantic verdict;
- stop further sampling and remaining cells at 500,000 reported subject tokens per cell, 4,000,000 aggregate subject tokens, unreported usage, or infrastructure/integrity failure;
- treat token limits as response-boundary stops, not falsely advertised portable pre-request hard caps;
- retain the first baseline as characterization, never a regression gate.

Formal acceptance:

- three headless repetitions per case;
- one headed repetition only after the headless policy passes;
- critical integrity and deterministic facts pass every repetition;
- irreducible semantic judgment passes at least two of three headless samples, with no factual-contradiction failure;
- headed failure after headless success is classified as UI/E2E, not subject-model regression.

The subject model and settings hash remain fixed across comparable baseline/improvement/ablation runs. Model comparison requires separate invocations and produces a separate evidence series. A Judge uses a separate settings snapshot and must be independent for formal evidence. If unavailable, Judge-required outcomes remain provisional rather than using a weaker same-model substitution.

Reported tokens and requests are the portable cost facts. Dollar cost is derived only from an optional versioned price table because Xenix supports arbitrary OpenAI-compatible providers and settings do not carry trustworthy pricing.

## Development and CI Order

Local guidance states: run the focused service selector and `pdm run test`; only after they pass, invoke the independently executable paid Agent case. The Agent command does not inspect the earlier process or its output.

A new manually dispatched GitHub workflow expresses the same policy with two jobs:

```text
secretless service job (`pdm run test`)
-> `needs` dispatch edge only
-> secrets-bearing headless paid Agent job
```

No fixture, report, verdict, environment file, or status payload crosses the job edge. The existing required secretless `Native CI` remains unchanged. Headed acceptance remains an explicit interactive-desktop action.

## Judge Calibration

Each Judge rubric supplies bounded hand-labelled pass/fail/partial/inconclusive packets. The calibration command runs them against the exact Judge settings and rubric version before live scores are accepted. Raw Judge prompts/responses remain discarded; only expected/observed verdict, bounded reason codes, metrics, and hashes persist.

Uncalibrated, same-model, unavailable, malformed, or inconclusive Judge results remain measurements but cannot satisfy formal acceptance.

## B0 Delivery Slices

1. **B0.1 — Independent ownership and private qualification:** planning-only risk map, Agent fixture isolation/hash proof, and private manifest policy; service assets remain for product handshakes.
2. **B0.2 — Live runner safety:** exactly one model, isolated cell process, hard sampling/time limits, reported-token stops, and bounded result status.
3. **B0.3 — Agent cases and report policy:** five ML business cases, Agent-only acceptance evaluator, repetition/identity/budget policy.
4. **B0.4 — Judge calibration:** executable rubric qualification and retained bounded evidence.
5. **B0.5 — Guidance and ordered CI:** service stage first, independent paid Agent stage second, with no artifacts or verdicts passed between them.
6. **B0.6 — Qualified live baseline:** bounded paid calls after matching service tests land green; no additional fee checkpoint after an implementation handshake is explicitly started.

## Authorization Boundary

`IH-B0` may authorize Agent benchmark/evaluator assets, benchmark-only offline safety checks, thin scripts, development guidance, a manual ordered CI workflow, and qualified bounded live calls. It does not authorize changes under `src/xenix`, service black-box test implementations under `tests/`, product contracts, Git operations, or later production optimization. Those move with their product handshakes or require separate approval.
