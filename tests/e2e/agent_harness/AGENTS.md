# Agent Harness Benchmark Local Guidance

## Scope

This subtree owns real-provider benchmark cases, privacy-safe fixtures, and
the small shared runtime in `_infra/`. It evaluates a public Agent Harness
outcome; it does not redefine product behavior, the LLM Conversation boundary,
provider adapters, or production settings.

## Tripwires

- A subject is exactly one isolated `AgentHarness × one pinned subject model ×
  case × mode × repetition` cell. Omitting `--model` selects only the settings
  snapshot's `default_fq_model_key`; one `--model` may override it, while model
  comparison uses separate evidence series. Pytest owns case selection and lifecycle; keep `_infra` case-
  agnostic, while a case owns its submission,
  terminal public-state locator, safe evidence projection, and rubric.
- A judge is an evaluator after the subject settles, never a second Agent turn.
  Give it explicit, independent settings and no Tools; do not silently reuse a
  subject default or include its cost, latency, or retries in subject metrics.
- Preserve separate execution, integrity, semantic-verdict, judge-status,
  subject-metric, and judge-metric channels. A semantic `fail` is a measured
  subject outcome; unavailable or malformed judgement is an evaluation state.
- Deterministic semantic checks must stay structural: exact public Dataset,
  linked public Artifact, and integrity facts. Do not regex-match free
  natural-language prose for number or word grounding; explanation-quality
  grounding is irreducible semantic judgment and belongs to the Judge, never a
  deterministic regex.
- Judge evidence and persisted reports are bounded. Never pass or retain a
  transcript, Tool payload, raw source row, raw Artifact/SVG, identifier, path,
  credential, endpoint, raw provider error, or raw judge request/response.
- Default tests stay offline. Do not add replay/mocks to the product path or a
  network call to ordinary test verification.
- Every paid cell runs in a killable child process with at most 12 subject
  sampling rounds, 900 seconds, two provider attempts per sampling round, and
  500,000 reported subject tokens. An invocation stops at 4,000,000 reported
  subject tokens.
  Token limits are response-boundary stops; unreported usage invalidates the
  cell. Installed limits may be lowered for infrastructure checks, never raised.
- Service black-box tests under `tests/` outside `tests/e2e/` and Agent cases in
  this subtree share no executable helpers, fixtures, reports, or runtime
  prerequisite. Run the service portfolio first through development guidance or
  CI `needs` ordering only; the Agent evaluator never reads a service result.
- A case is its own `test_*.py` benchmark module. Do not create a second
  case-specific test file or restate static/schema guarantees. Ordinary tests
  may prove only dynamic `_infra` boundaries that cannot be established by
  types, schemas, or component tests.

## Focused Verification

- Run `pdm run check` for imports and result-shape continuity. Do not recreate an
  ordinary pytest mirror for benchmark schemas, options, case logic, or private
  runner branches.
- Run `pdm run benchmark-agent-harness-check` for the dedicated offline safety,
  report-policy, and Judge-calibration checks. These checks are not live Agent
  evidence and are not part of `pdm run test`.
- Use `pdm run benchmark-agent-harness -- --collect-only` to verify discovery
  without a provider; use `pdm run benchmark-agent-harness-headed --
  --collect-only` to prove the visible mode discovers that same case catalog.
  Use either live command only for explicit acceptance with externally supplied,
  untracked subject, Embedding, and optional Judge settings.
- Inspect a persisted result for bounded serialization and separate subject and
  judge measurements before treating a live score as evidence.
- Use `pdm run benchmark-agent-harness-evaluate` to characterize or formally
  evaluate v5 Agent reports. A v4 report is diagnostic-only and never silently
  upgraded. Use `pdm run benchmark-agent-harness-calibrate-judge` before a
  Judge-required formal series.
