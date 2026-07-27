# Agent Harness Real-Provider Benchmark

Status: **V1 implemented; V1.1 structural extension complete.** The graph
semantic-evaluation redesign now belongs to the separate
[Agent Harness Benchmark Infrastructure V2](../agent-harness-benchmark-semantic-evaluation/packet.md).
The deterministic suite remains offline; real-provider observations are
recorded in [verification.md](verification.md).

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

## V1.1 Extension: a Graph Artifact Case

Add one small, committed sales fixture and a regional-sales visualization
case. Its purpose is not to broaden product coverage for its own sake: it
tests whether a second, non-Dataset product outcome can join the benchmark
without putting case-specific behavior in the runner.

- The graph case owns its fixed input, user intent, source preservation check,
  canonical Artifact locator, SVG/product checks, and named outcomes.
- The runner receives an explicit narrow case contract rather than a default
  April source path. It may provide only public Dataset/Artifact access and
  isolated-cell facts through a case context.
- The CLI owns the small allow-listed case registry. Adding a case must mean
  adding its module, fixture/oracle, registry entry, and tests—not a
  `case_id` branch in the runner.
- The graph oracle resolves a successful canonical ToolResult's `artifact_id`
  through `ArtifactService`; it does not infer from Assistant prose or inspect
  Tool arguments/order. Artifact identifiers, paths, SVG content, and input
  rows remain outside persisted results.

### Candidate Correction: Semantic Goal, Not a Golden Graph

This is retained as V1 handoff context only. Do not implement the judge or
semantic-result redesign in this packet; its contract, slices, and verification
plan are owned by the V2 task packet linked above.

The first graph oracle was too structural: SVG parseability, Artifact metadata,
visible-bar count, source preservation, and state isolation do not establish
that the Agent produced the requested chart. They are respectively Tool/
renderer coverage or benchmark-run integrity evidence. The real Kimi graph
cell is therefore a structural baseline only, not a semantic quality pass.

The replacement prompt must state a business goal in ordinary language, for
example: “请用图表呈现各地区收入对比，选择最合适的图表形式并简述发现。” It
must not prescribe a mark, title, axis orientation, field syntax, or Tool
plan. A prompt with no business question at all would make a bounded outcome
oracle impossible; the task intent, rather than the implementation, is the
right minimum contract.

The replacement oracle should define an *acceptance set*, not one golden SVG.
Its primary semantic evaluator is a **rubric-based, pointwise
LLM-as-a-Judge** (also called model-graded evaluation), rather than a growing
set of host-language equality assertions:

- **Minimal deterministic eligibility:** a final, readable Artifact can be
  located and projected into bounded evidence. Fixture/configuration/isolation/
  privacy checks remain benchmark integrity, not model quality. No exact
  graph/data equality lives here.
- **Judge input:** each case owns a privacy-reviewed evidence projection:
  ordinary-language user intent, a compact independent set of source facts,
  and a normalized final-Artifact semantic extract. The graph case's facts
  include its four regions and their revenue ordering; the extract may contain
  visible text and SVG accessibility labels, never Artifact paths/IDs, Tool
  arguments/results, internal metadata, or Assistant prose.
- **Judge rubric and result:** a blinded judge returns only structured
  `pass` / `partial` / `fail` / `inconclusive`, per-dimension scores for task
  fulfilment, factual grounding, and semantic user comprehensibility, plus bounded
  reason codes. It decides whether the visual represents the requested
  regional-revenue comparison; it does not require a particular mark, title,
  axis, raw value display, or exact SVG shape.
- **Judge isolation:** use an explicit, independently recorded judge model and
  deterministic generation settings where supported. The judge runs after the
  Harness turn through the real `LLMService` with no Tools; its model identity,
  token usage, retries, elapsed time, rubric version, and availability are
  result metadata separate from the subject cell's token/time/tool metrics.
  A judge failure or insufficient final evidence is an evaluation-status result,
  never silently converted to a bad Agent outcome.
- **Calibration:** first prove the rubric against a small hand-labelled set of
  clearly good, materially misleading, irrelevant, and evidence-insufficient
  Artifacts. The runner must keep the subject model identity hidden from the
  judge and record a same-model judge as non-independent rather than pretending
  it is a neutral comparison.

The current provider boundary is text-only. V1 therefore judges the projected
semantic content of the final Artifact, not colors, pixel layout, or other
visual aesthetics; a future vision-capable evidence path must be a separate,
explicit extension.

The previous “four bars” check is useful only as a renderer-specific
observation. The business expectation—four regions and a meaningful revenue
comparison—is expressed to the judge as a rubric fact, so a valid non-bar
visual remains eligible. Exact title, X/Y, raw value, SVG DOM-order, and pixel
equality are not benchmark outcomes.

Case outcome checks are only final user-task semantics. Completion/artifact
location are assessment prerequisites; source/configuration fingerprint and
temporary-home confinement are runner integrity checks. Durable ownership and
implementation await an explicit correction slice.

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
- The second case proves extension behavior through a different terminal product
  type (registered SVG Artifact), while retaining one shared matrix, metric
  collector, JSON schema, isolation lifecycle, and real-provider path.
- A narrow `tests/agent_harness_benchmark/AGENTS.md` is planned for the next
  source slice. It will contain only this subtree's scope, live-run/isolation/
  privacy/oracle tripwires, and focused verification command; durable rationale
  belongs under `docs/30-unit-tdd/`, not in the local instruction file.
- The runner currently serializes integrity and semantic checks in one outcome
  list. The correction slice must give benchmark integrity a separate result
  channel before interpreting semantic quality, so a locator/privacy/isolation
  failure cannot be mistaken for a poor model outcome.
- Task-packet edits remain authorized during discussion. Sir authorized the V1
  source/test implementation on 2026-07-20.

## Verification

- One non-Qt builder is the sole owner of the production Agent service graph,
  and both `app.py` and the benchmark call it with caller-owned storage,
  settings, and lifecycle dependencies.
- Offline tests prove result serialization, privacy bounds, metric folding,
  Dataset/Artifact terminal-output selection, and both outcome oracles without
  network access.
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
- `BenchmarkCase`, `BenchmarkCaseServices`, and `BenchmarkCaseContext` make
  the runner's narrow extension seam explicit. Cases receive read-only public
  Dataset/Artifact access and isolated-cell facts, not the Harness, LLM, or
  Tool graph. The CLI selects allow-listed case factories outside the runner.
- The committed `analysis.revenue_by_region_chart` case currently validates a
  final SVG Artifact structurally. Its Kimi K2.6 cell completed in 21.5 s at
  15,884 tokens, but that historic result is not semantic outcome evidence;
  the correction rationale and exact evidence are in [verification.md](verification.md).
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

Repetitions/statistics, leaderboards, weighted cross-case scores, a general
case DSL, benchmark-only `test.submit` Tool, automated regression thresholds,
judge ensembles, and hosted result storage. The single-model LLM judge is in
scope because this case has an observable but intentionally non-golden product
output; multi-judge voting waits for calibration evidence.

## Supporting Files

- [design.md](design.md) — minimal runner/result/report boundary.
- [case-contract.md](case-contract.md) — cleaning outcome oracle and metrics.
- [chart-case.md](chart-case.md) — second-case graph Artifact contract.
- [implementation-slices.md](implementation-slices.md) — ordered file-level
  implementation plan, slice gates, and return-to-discussion triggers.
- [verification.md](verification.md) — proof matrix, completion checklist, and
  run ledger.

## Next Step

Treat V1 results as baseline evidence only. Continue the graph semantic work in
[the V2 task packet](../agent-harness-benchmark-semantic-evaluation/packet.md),
which owns the independent judge, result-channel separation, calibration, and
the next Kimi run. The first matrix's model-specific cleaning outcomes remain
observations; V2 does not introduce a model-specific prompt, replay fixture, or
threshold.
