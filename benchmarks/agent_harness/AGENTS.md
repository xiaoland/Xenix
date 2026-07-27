# Agent Harness Benchmark Local Guidance

## Scope

This subtree owns real-provider benchmark cases, privacy-safe fixtures, and
the small shared runtime in `_infra/`. It evaluates a public Agent Harness
outcome; it does not redefine product behavior, the LLM Conversation boundary,
provider adapters, or production settings.

## Tripwires

- A subject is exactly one isolated `AgentHarness × configured subject model ×
  case` cell. Pytest owns case selection and lifecycle; keep `_infra` case-
  agnostic, while a case owns its submission,
  terminal public-state locator, safe evidence projection, and rubric.
- A judge is an evaluator after the subject settles, never a second Agent turn.
  Give it explicit, independent settings and no Tools; do not silently reuse a
  subject default or include its cost, latency, or retries in subject metrics.
- Preserve separate execution, integrity, semantic-verdict, judge-status,
  subject-metric, and judge-metric channels. A semantic `fail` is a measured
  subject outcome; unavailable or malformed judgement is an evaluation state.
- Judge evidence and persisted reports are bounded. Never pass or retain a
  transcript, Tool payload, raw source row, raw Artifact/SVG, identifier, path,
  credential, endpoint, raw provider error, or raw judge request/response.
- Default tests stay offline. Do not add replay/mocks to the product path or a
  network call to ordinary test verification.
- A case is its own `test_*.py` benchmark module. Do not create a second
  case-specific test file or restate static/schema guarantees. Ordinary tests
  may prove only dynamic `_infra` boundaries that cannot be established by
  types, schemas, or component tests.

## Focused Verification

- Run `pdm run check` for imports and result-shape continuity. Do not recreate an
  ordinary pytest mirror for benchmark schemas, options, case logic, or private
  runner branches.
- Use `pdm run benchmark-agent-harness -- --collect-only` to verify discovery
  without a provider; use `pdm run benchmark-agent-harness-headed --
  --collect-only` to prove the visible mode discovers that same case catalog.
  Use either live command only for explicit acceptance with externally supplied,
  untracked subject, Embedding, and optional Judge settings.
- Inspect a persisted result for bounded serialization and separate subject and
  judge measurements before treating a live score as evidence.
