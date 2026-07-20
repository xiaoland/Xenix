# Agent Harness Benchmark

## Admission

This document owns the local evaluation boundary for the Agent Harness
benchmark. The [LLM conversation boundary](../20-product-tdd/llm-conversation-boundary.md)
continues to own product conversation topology, authority, and sequences;
benchmark code observes public outcomes and does not alter that contract.

## Subject and Case Boundary

A subject is one isolated `AgentHarness × configured subject model × case`
cell. It uses the real provider path and ordinary public Harness submission,
then observes the settled public product state. The runner is case-agnostic.

`benchmarks/agent_harness/` is the benchmark home. Each `test_*.py` case
module is both the case definition and its explicitly collected pytest item;
pytest selects and controls the case matrix. Shared runner, contracts, judge,
and the deliberately small pytest fixture live in `_infra/`. There is no case
registry and no second case-specific test implementation.

A case owns its business intent, fixture validation, submission, terminal
output location, privacy-reviewed evidence projection, and rubric identity.
It must not require a prescribed Tool trace, Assistant prose, chart grammar,
or golden output. The regional-sales graph case, for example, accepts an
appropriate presentation form rather than bars, a title, or a particular axis
layout.

## Evidence and Judge Boundary

Each judge-enabled case supplies only a bounded packet of user intent,
independent fixture facts, and final public Dataset/Artifact semantics. For a
text-only judge, graph evidence is a semantic projection such as visible text
and accessibility labels, not pixels or raw SVG. It may assess task fulfilment,
factual grounding, and semantic comprehensibility, but not visual aesthetics.

Evidence is untrusted content. It must be delimited and treated as data, and
must exclude transcripts, Tool arguments/results, Assistant prose, raw fixture
rows, raw artifacts, internal identifiers, paths, provider metadata, and
credentials. Persist only bounded verdict scores and reason codes; discard raw
judge prompts, responses, and errors.

The judge is a rubric-based, pointwise evaluator after the subject cell has
settled. Its configuration is explicit and separate from the subject matrix;
same-model judging is allowed only when recorded as non-independent. A judge
uses no Tools and is not another participant in the Agent turn.

## Result Interpretation

Execution, integrity, semantic verdict, judge status, subject metrics, and
judge metrics are independent result channels. Integrity covers fixture and
settings fingerprints, isolated-runtime confinement, and safe serialization.
An integrity breach invalidates the measurement instead of becoming a model
quality result.

A semantic `fail` is a valid subject outcome. Missing terminal output may be
such a failure; insufficient final evidence is `inconclusive`. An evaluator
uses `fail` only for positive evidence of an irrelevant or materially
contradictory outcome, not merely because another score dimension is weak.
Missing judge configuration, provider failure, or malformed judgement is a
judge-status state and must not be collapsed into a semantic failure or
success.

Subject measurements include the Harness turn's latency, token usage, messages,
Tool calls/results, retries, and derived outputs. Judge latency, usage, and
retries are evaluation metadata and never contribute to subject performance.

## Offline and Live Policy

The default test suite is deterministic and offline. It does not collect the
benchmark case directory or call a provider. Its small
`tests/test_agent_harness_benchmark_infra.py` coverage is reserved for dynamic
shared-boundary behavior—such as privacy-safe judge dispatch, persistence,
matrix continuation, metrics folding, and the explicit pytest live gate—not
for duplicating case logic, schemas, types, or component-level Tool checks.

Use `pdm run benchmark-agent-harness -- --collect-only` to prove discovery
without provider access. A live run is an explicit
`pdm run benchmark-agent-harness -- [pytest options]` action with external,
untracked subject and judge settings; normal pytest selection (`-k` or a node
id) selects its case. A live report must retain the separate channels above
without secrets or raw evidence. Calibrate a configured judge before using
scores for comparison; disagreement with clear fixtures is a signal to refine
the case evidence or rubric, not to add Tool-trajectory assertions.

## Change Guidance

Read `benchmarks/agent_harness/AGENTS.md` before changing the benchmark.
Source and focused dynamic-infrastructure tests own exact fields, request
shapes, and pytest options.
