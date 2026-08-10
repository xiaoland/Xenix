# Impact Handshake O1 — Bounded Topic Final-Answer Diagnosis

**Status:** Proposed. Design review is required before mutation.

## Evidence Trigger

Paid run `d7ecbdf02fce4f899970818c341f1a10` completed normally with integrity pass and budget within limits. All FIT, EVALUATE, APPLY, identity, Dataset, and Artifact outcomes were correct. The bounded evaluator reported only missing final-answer grounding categories and one Windows-path disclosure. The persisted report deliberately contains no transcript or private value, so it cannot identify the path's provenance.

## Address and Object

- `benchmarks/agent_harness/test_ml_text_topic_discovery.py`: classify the path and grounding first divergence with bounded categories only;
- the case-owned ignored live runtime/report during one exact-selector diagnostic;
- `benchmarks/agent_harness/_infra_tests/` only if a reusable privacy-safe diagnostic invariant cannot be established statically.

No `src/xenix` product, Skill, Tool schema, orchestration, service, UI, or durable documentation change is authorized by this handshake.

## State Diff

- **From:** the evaluator reports `windows_path` and missing grounding dimensions but cannot distinguish attachment-path exposure, public-link rendering, Provider invention, or missing public evidence.
- **To:** one rerun reports only stable provenance categories such as `attachment_path`, `runtime_artifact_path`, `other_windows_path`, and whether every required public evidence family was available before finalization. No path, row, prompt, transcript, Tool payload, or private identifier is retained.

## Blast Radius

Only the topic case's evaluator-side diagnosis and its bounded report summary. Case success criteria, fixture, prompt, business oracle, service behavior, Tool trajectory freedom, report schema v5, and other live cases remain unchanged.

## Invariants

- A diagnostic category cannot turn a semantic failure into a pass.
- Subject and evaluator projections remain physically separate.
- No raw path or final answer is persisted in tracked evidence.
- The benchmark still evaluates public outcomes, not a prescribed Tool sequence.
- Any product optimization returns to Sir with a separate exact `IH-O2` naming the proven owner and state diff.

## Verification

1. Static/fixture privacy checks and focused evaluator helpers.
2. `pdm run benchmark-agent-harness-check -q`.
3. Exact headless/headed collect-only remains one item.
4. One bounded paid exact-selector diagnostic.
5. Promote only run identity, budgets, pass/fail channels, and bounded provenance categories.

## Return to Discussion

Return before product mutation, or immediately if classification needs raw transcript retention, broad observability, response rewriting, case-specific production behavior, or weakened grounding/privacy criteria.
