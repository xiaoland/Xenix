# Agent Harness Real-Provider Benchmark

Status: **V1 implemented and verified**. The deterministic suite remains
offline; the first real-provider matrix has been recorded in
[verification.md](verification.md).

## Objective

Build the smallest repeatable benchmark that answers:

> With this AgentHarness build, configured real models, and fixed tasks, what
> outcome quality, token cost, latency, message volume, Tool volume, and Tool
> failure behavior do we observe for each case × model cell?

This is not primarily a health check for whether AgentHarness is “broken”. Case
outcome checks remain necessary so a cheaper/faster run cannot score well after
producing unusable data.

Remove AIMock after the real-provider benchmark path works. Do not replace it
with Response Replay or another provider double.

## V1 Scope

1. Extract one shared non-Qt headless service composition used by `app.py` and
   benchmark setup.
2. Add one isolated real-provider benchmark runner through the public Harness
   boundary. Expand all provider/model entries from one external, untracked LLM
   settings file into a sequential benchmark matrix.
3. Add one historical case: the `清洗` turn from
   `bb5827f1c9794952b3490d869403c4cd` with its real/redacted April dine-in sales
   workbook.
4. Evaluate case-specific cleaning outcomes and collect performance metrics.
5. Persist one bounded JSON result per run before applying any optional outcome
   assertion.
6. Keep live benchmarking explicit and the default deterministic suite offline.
7. Remove AIMock while retaining deterministic lower-level protocol/fault tests.

## Guardrails

- The benchmark subject is one AgentHarness × model × case cell. Harness-version
  comparisons hold model/case fixed; model-adaptation comparisons hold Harness/
  case fixed.
- Token, time, message, request, Tool-call, retry, and Tool-failure counts are
  measurements in V1, not invented pass/fail ceilings.
- Outcome checks inspect the final public product state, not exact Tool names,
  order, arguments, or Assistant wording.
- A completed run always records metrics, including when its outcome checks
  fail. Invalid setup/provider execution is distinguished from a poor outcome.
- Production state and credentials receive no benchmark writes and never enter
  reports.
- The 116 MB workbook is an external, hash-pinned benchmark input. It is not a
  repository fixture and its absence makes a run invalid rather than skipped.
- Usage-reported responses, sampling rounds, and provider retries remain
  distinct measurements; V1 does not claim to reconstruct every HTTP attempt.
- Each matrix cell gets a fresh isolated runtime. One invalid provider/model
  cell is reported without aborting the remaining configured cells.
- Thread-title generation is outside the benchmark subject. The runner creates
  a non-empty deterministic benchmark title before submitting the first turn,
  preventing both model-generated and fallback title side tasks.
- Task-packet edits remain authorized during discussion. Sir authorized the V1
  source/test implementation on 2026-07-20.

## Verification

- One non-Qt builder is the sole owner of the production Agent service graph,
  and both `app.py` and the benchmark call it with caller-owned storage,
  settings, and lifecycle dependencies.
- Offline tests prove result serialization, privacy bounds, metric folding,
  terminal-output selection, and the cleaning oracle without network access.
- One explicit matrix run writes a bounded result for every configured model;
  at minimum the historical Kimi K2.6 cell completes, its outcome checks match
  the final isolated dataset, and its counters reconcile with canonical public
  Harness projections.
- The normal runtime database/config and source workbook retain their pre-run
  fingerprints; all generated product state is under the temporary app home.
- Default `pdm run test` remains offline; `pdm run check` and the affected UI,
  settings, Harness, storage, and preprocessing tests pass.
- Executable/configuration AIMock surfaces are absent, while generic provider,
  retry, HTTP/SSE, and deterministic Harness tests remain.

## Current Truth

- Production and the benchmark now call the same non-Qt
  `build_headless_agent_services()` composition root. Existing deterministic
  injected-provider tests remain lower-level evidence, not benchmark evidence.
- The real production path is Harness -> Conversation -> `LLMService.stream()`
  with `provider=None`. `provider=None` selects the real service path rather
  than one provider; the explicit Thread `fq_model_key` selects each matrix
  cell's configured provider/model.
- Public Harness projections expose canonical messages, Tool status/name, usage
  aggregates, and retry events. Usage `request_count` counts successful primary
  responses carrying valid usage, not every network attempt.
- The selected April workbook is external/ignored: 116,459,191 bytes, SHA-256
  `6B902DE50277E727FE936FFC4FE072B4D8B1C3D60A7D85413E114B72C4140E31`.
- The imported source has one source dataset and a single-chain historical
  cleaning result, but V1 no longer makes lineage a universal output locator.
  Each case owns output location; the April case selects the newest successful
  ToolResult reference to a readable run-created, non-source Dataset.
- `XENIX_AGENT_BENCHMARK_LLM_SETTINGS_PATH` (or the equivalent explicit CLI
  option) points to one external/untracked JSON file using the existing
  `LLMSettings` schema. The runner validates and freezes it in memory once per
  suite without copying credentials to product state. The shared builder
  receives the caller-owned real `LLMService` and never owns provider selection
  or settings persistence.
- `.gitignore` and unrelated task packets already contain user-owned changes;
  they are outside this task's mutation/commit scope. The ignored local
  `.vscode/tasks.json` is also outside scope even if it contains a stale AIMock
  task.

## Explicitly Deferred

Multiple cases, repetitions/statistics, leaderboards, weighted scores, LLM
judges, a general case DSL, benchmark-only `test.submit` Tool, automated
regression thresholds, and hosted result storage. Add them only after V1
produces useful runs or a case lacks an observable product output.

## Supporting Files

- [design.md](design.md) — minimal runner/result/report boundary.
- [case-contract.md](case-contract.md) — cleaning outcome oracle and metrics.
- [implementation-slices.md](implementation-slices.md) — ordered file-level
  implementation plan, slice gates, and return-to-discussion triggers.
- [verification.md](verification.md) — proof matrix, completion checklist, and
  run ledger.

## Next Step

Use the recorded baseline to choose a separate AgentHarness performance slice.
The first matrix found model-specific incomplete cleaning outcomes; V1 records
them rather than introducing a model-specific prompt, replay fixture, or
threshold after the fact.
