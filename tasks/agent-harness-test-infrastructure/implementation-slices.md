# Agent Harness Benchmark Implementation Slices

The control surface is [packet.md](packet.md). Design decisions live in
[design.md](design.md), the first case contract in
[case-contract.md](case-contract.md), and proof/commands in
[verification.md](verification.md).

Status: **all four V1 slices complete**. Exact deterministic and live evidence
is recorded in [verification.md](verification.md).

## Execution Order

Implementation and verification followed this order. The real-provider matrix
ran only after the shared composition, offline runner branches, privacy
serializer, and AIMock removal had deterministic proof.

```text
shared composition
        ↓
offline matrix kernel + April case
        ↓
AIMock removal
        ↓
live provider/model matrix + full regression
```

## Slice 1 — One Headless Composition Authority

### Objective

Make the desktop application and benchmark construct the same non-Qt Agent
service graph without moving storage, provider-settings, worker, logging, or Qt
lifecycle ownership into the builder.

### Planned Addresses

- `src/xenix/services/agent/composition.py` — new builder, return bundle, and
  pure Agent Skill context/scope helpers.
- `src/xenix/services/agent/__init__.py` — narrow public exports if callers need
  them.
- `src/xenix/app.py` — replace the in-function graph construction after storage
  bootstrap; retain lazy runtime loading and thin compatibility wrappers for
  existing helper imports.
- `tests/test_agent_composition.py` — headless import and graph-parity proof.

### State Change

- From: `build_main_window()` is the only production graph owner, while the old
  scripted replay independently assembles a smaller graph.
- To: one builder owns Dataset/Clean/Transform/ML/Artifact/Tool/Skill/
  Conversation/Harness wiring; app and benchmark supply their own paths,
  session factory, real `LLMService`, worker settings, and usage sink.

### Risk Controls

- Do not import `xenix.app` or PySide from the headless module.
- Do not move `StorageBootstrapService.initialize()`, engine disposal,
  `LinkRouter`, `UpdateService`, `MainWindow`, observability flushing, or
  provider settings persistence into the builder.
- Keep production `AgentHarnessService.provider` unset so Conversation remains
  the real provider gateway.
- Preserve startup lazy-import timing; do not import the composition module at
  `xenix.app` module import time before the splash/runtime loading boundary.
- Preserve current Windows preprocessing-worker defaults and serialized
  `AppPaths` behavior.

### Slice Exit

- The builder imports in a process with no Qt application and no PySide import.
- App and a headless test both call the same builder.
- Existing focused Harness/Skill/Tool and startup tests pass.

## Slice 2 — Offline Matrix Kernel and April Case

### Objective

Build the smallest reusable benchmark mechanism: external provider/model
configuration, sequential isolated cells, bounded metrics/results, one
case-owned output locator, and one data oracle. No live provider call belongs in
the default test suite.

### Planned Addresses

- `tests/agent_harness_benchmark/contracts.py` — result/status/metric values and
  the narrow case callable contract.
- `tests/agent_harness_benchmark/runner.py` — external settings load/freeze,
  matrix expansion, isolated cell lifecycle, stream folding, persistence, and
  suite exit status.
- `tests/agent_harness_benchmark/cleaning_april.py` — fixed input contract,
  ToolResult-reference locator, normalization, fingerprints, and named outcome
  checks.
- `tests/agent_harness_benchmark/__init__.py` — only intentional exports.
- `scripts/run_agent_harness_benchmark.py` — explicit command-line entry.
- `pyproject.toml` — opt-in `benchmark-agent-harness` command only.
- `tests/test_agent_harness_benchmark.py` — deterministic kernel, locator,
  oracle, isolation, branch, and privacy tests.
- `src/xenix/services/llm/service.py` — only the minimal settings-source seam
  needed for the real `LLMService` to consume one frozen, read-only
  `LLMSettings` snapshot; do not add a provider adapter.

Exact module splits may collapse if a file would be trivial, but the runner and
case must remain separate owners.

### Cell Sequence

1. Resolve `--llm-settings`, else
   `XENIX_AGENT_BENCHMARK_LLM_SETTINGS_PATH`.
2. Parse the external/untracked JSON once with the existing `LLMSettings`
   schema; freeze it in memory and enumerate every `providers[].models` fully
   qualified key. An optional `--model` narrows diagnosis only.
3. Validate the case input hash once.
4. For every model, create a new temporary app home/storage context and call the
   shared composition with the real `LLMService`.
5. Pre-create a Thread titled from case id, model, UTC start, and run id. Submit
   to that Thread so automatic model/fallback title work is ineligible.
6. Consume `submit_user_turn_stream(provider=None)` to completion while folding
   sampling/retry counters and retaining only the latest public snapshot.
7. Derive canonical message, Tool name/status, and nullable usage/token
   aggregates from public Harness projections.
8. Let `cleaning_april` locate the newest successful ToolResult reference to a
   readable run-created, non-source Dataset; do not use a global lineage or
   timestamp heuristic.
9. Run the oracle outside Agent timing, whitelist the result schema, and write
   the cell JSON atomically under ignored
   `build/agent-harness-benchmarks/` (or an explicit output directory).
10. Dispose cell storage and continue after invalid, failed-outcome, runtime, or
    measurement errors. Compute suite exit status after all cells.

### Required Offline Branch Proof

- completed/pass and completed/outcome-fail;
- missing config/fixture, fixture mismatch, invalid model, and unavailable
  credential;
- provider/runtime failure with partial metrics;
- missing/malformed usage remains `null`, not zero;
- retry and sampling-round counters remain distinct;
- one model cell failure does not abort later cells;
- synthetic title prevents title provider/fallback work and late title events;
- missing, source-only, stale, malformed, and unreadable Dataset references;
- oracle header/report/header-row/duplicate/corruption cases;
- result-write failure never claims persistence;
- serialized results exclude secrets, endpoints, absolute paths, prompt/data,
  Tool payloads, raw errors, and Thread/Message/Dataset identities.

### Slice Exit

- All kernel/case tests pass without network access or production runtime state.
- The live command exists but is not collected or invoked by `pdm run test`.
- A dry run can enumerate configured model keys without printing credentials.

## Slice 3 — Remove AIMock Without a Replacement

### Objective

Delete AIMock's product/configuration surface after the real-provider benchmark
path exists, while keeping general provider and deterministic fault coverage.

### Planned Addresses

- `src/xenix/services/llm/service.py` — remove `AimockSettings`, settings field,
  development override, and legacy migration copy.
- `src/xenix/services/llm/__init__.py`,
  `src/xenix/services/agent/settings.py`, and
  `src/xenix/services/agent/__init__.py` — remove compatibility exports.
- `src/xenix/ui/settings_dialog.py` — remove the AIMock card/load/save behavior.
- `src/xenix/translations/xenix_en_US.ts` and `xenix_zh_CN.ts` — synchronize UI
  strings through the normal translation workflow.
- `tests/test_agent_settings.py`, `tests/test_main.py`, and affected settings/UI
  tests — remove AIMock-specific expectations and add historical-extra-field
  compatibility proof.
- Delete tracked `aimock.json` and
  `fixtures/aimock/10-xenix-streaming.json`.

### Risk Controls

- Historical `agent_settings.json` containing an extra `aimock` key must still
  load; the next normal save omits it without changing providers.
- Keep `XENIX_ENV` because development-only Agent Skill projection still owns
  an independent use.
- Keep generic OpenAI-compatible provider, HTTP/SSE, retry, malformed-response,
  and injected-provider unit tests.
- Do not add Response Replay, a Kimi-specific adapter, or another provider
  double.
- Do not edit ignored local `.vscode/tasks.json`, historical task notes,
  `.gitignore`, or unrelated dirty task packets.

### Slice Exit

- Scoped executable/configuration search has no AIMock surface.
- Translation extraction/compile and affected settings/UI/provider tests pass.
- The default provider path remains `LLMService` with no hidden development
  override.

## Slice 4 — Live Matrix and Completion Evidence

### Objective

Run the real April cleaning case for every configured model, confirm result
truthfulness and isolation, then execute repository verification.

### Run Order

1. Preflight external settings path, model enumeration, workbook size/hash,
   output directory, repository identity, and absence of printed secrets.
2. Run the Kimi K2.6 cell first as the historical reference and diagnose any
   Harness/infrastructure defect before spending the rest of the matrix.
3. Continue the remaining configured cells sequentially, including cells whose
   outcome fails; do not repair model-specific behavior inside the benchmark.
4. Reconcile each cell's canonical messages, Tool calls/statuses, usage, retry,
   output locator, terminal shape, and named oracle checks.
5. Confirm the workbook and external settings identities are unchanged and all
   generated product state stayed under the cell's temporary home.
6. Record only safe result paths and aggregate evidence in the task ledger.
7. Run targeted tests, `pdm run check`, and default `pdm run test`.

### Slice Exit

- Every configured model has a persisted cell result or an explicit safe
  persistence failure.
- The Kimi reference cell is a valid completed run; its outcome result agrees
  with direct inspection of the terminal Dataset.
- Default tests remain offline and the full deterministic regression passes.
- The task packet records commands, results, remaining model-specific failures,
  and any follow-up recommendation without inventing V1 thresholds.

## Return-to-Discussion Triggers

Stop source execution and return to Sir if evidence requires any of these state
changes:

- the builder would need to own storage/provider/process/UI lifecycle;
- freezing external settings requires a second provider schema or provider
  adapter rather than a narrow settings source;
- the April case cannot locate output from canonical public results and would
  require a benchmark-only Tool or production schema change;
- the real workbook identity differs from the pinned case contract;
- privacy-safe reporting cannot explain a failure without exposing source,
  credential, endpoint, or raw Tool/provider payloads;
- a newly discovered change crosses an owner or blast radius not covered by the
  approved Impact Handshake.

Provider/model outcome failures, high token use, slow latency, or unsupported
Tool behavior are benchmark findings, not automatic reasons to expand V1.
