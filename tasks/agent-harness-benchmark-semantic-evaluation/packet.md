# Agent Harness Benchmark Infrastructure V2

Status: **completed on 2026-07-20**.

## Objective

Upgrade the real-provider Agent Harness benchmark from case-specific structural
or exact-equality outcomes to repeatable, privacy-bounded, rubric-based
semantic evaluation.

For every `case × subject model` cell, V2 must answer independently:

1. Did the Harness execution complete and produce the intended user-visible
   product outcome?
2. What quality verdict does a configured, independent LLM judge assign to
   that final outcome against the case's business rubric?
3. What subject-Harness resources were consumed: token usage, latency,
   messages, Tool calls/results, retries, and derived outputs?

The judge's own resource use and failures are evaluation metadata, not subject
model measurements.

## Scope

- Keep the existing public AgentHarness boundary and real-provider execution
  path. Do not reintroduce AIMock, response replay, or a benchmark-only
  provider adapter.
- Add one generic, direct `LLMService` judge path outside Harness/Conversation.
- Define a narrow case-owned judge-evidence contract and use it first for the
  regional-sales graph case.
- Separate execution status, benchmark integrity, semantic verdict, subject
  performance metrics, and judge metrics in the persisted result schema.
- Add a narrow local `AGENTS.md` for the benchmark subtree and durable local
  Agent Harness benchmark guidance.
- Keep default tests offline. Live subject/judge runs remain an explicit CLI
  action using external, untracked settings.

## Guardrails

- The subject is always one AgentHarness × configured subject model × case.
  The judge is an evaluator, never a second participant in the Agent turn.
- A case specifies a business intent and rubric, not a golden chart, Tool
  trace, Assistant prose, title, axis orientation, or exact SVG geometry.
- Case evidence is derived only from final public Dataset/Artifact state and
  independently supplied fixture facts. It excludes transcript, Tool payload,
  Artifact/Dataset identifiers, paths, provider metadata, raw errors, and
  credentials.
- The runner remains case-agnostic. Cases own input validation, submission,
  terminal-output location, privacy-reviewed evidence projection, and rubric
  identity; the runner never branches on `case_id`.
- Judge provider/model configuration is explicit and separate from the subject
  matrix. A same-model judge is permitted for early local runs but must be
  recorded as non-independent.
- A semantic `fail` is a subject outcome; judge unavailability, malformed
  judgement, or insufficient evidence is an evaluation state, not a silent
  subject failure.
- Persist only bounded structured scores/reason codes. Never persist raw judge
  prompts/responses, raw Artifact/SVG, fixture rows, credentials, endpoints,
  paths, or internal identities.
- V2's current provider boundary is text-only. It evaluates projected Artifact
  semantics, not pixel-level visual aesthetics; multimodal judging is deferred.

## Verification

- Focused offline tests prove schema separation, judge request construction,
  bounded JSON parsing, error classification, configuration isolation, privacy
  deny-lists, and subject-versus-judge metric separation without a network call.
- Fixture-based calibration proves that the rubric distinguishes clearly good,
  misleading, irrelevant, and evidence-insufficient graph outcomes.
- A live Kimi K2.6 subject/judge run persists an auditable bounded result with
  separate subject and judge metrics; a judge configuration failure persists an
  evaluation status without losing the subject measurements.
- `pdm run test` and `pdm run check` remain green and offline by default.

## Current Truth

- V1 already has a real-provider matrix, isolated temporary app homes, a
  public Harness submission boundary, a bounded result report, and two case
  shapes: terminal Dataset and terminal SVG Artifact.
- The current graph case hard-codes bar/title/X/Y/metadata checks, so it is
  structural coverage rather than a credible open-ended outcome benchmark.
- Current `outcome_checks` mix product semantics with locator/source/isolation
  facts. V2 must split those channels before semantic quality is interpreted.
- `LLMService.complete()` can call a configured provider directly with no Tools,
  which is the appropriate transport for a judge. Its settings can be frozen
  independently. It currently has no per-call output-token cap and accepts
  text-only provider messages; V2 must not enlarge that core boundary without
  a separate justified slice.
- LLM-as-a-Judge is the intended method: rubric-based, pointwise,
  reference-guided by independent task facts but not by a golden output.

## Next Step

V2 implementation is underway under the approved scope. The active evidence
ledger is [verification.md](verification.md); preserve the result-channel and
privacy boundaries when completing final regression or live acceptance.

## Supporting Files

- [design.md](design.md) — topology, ownership, statuses, and configuration.
- [judge-contract.md](judge-contract.md) — case evidence, rubric, safety, and
  structured judge response contract.
- [implementation-slices.md](implementation-slices.md) — ordered mutation plan
  and impact handshakes.
- [verification.md](verification.md) — offline, calibration, and live proof
  plan.
