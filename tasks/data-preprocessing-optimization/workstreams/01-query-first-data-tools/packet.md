# Query-First Data Tools

## Objective & Hypothesis

Replace bundled `data.peek` behavior with smaller atomic tools. The model should use `data.query` for read-only evidence and `data.transform` only when it needs a durable derived dataset.

## Status

verified

## Durable Owners / Blast Radius

- Agent tool registry and tool schemas.
- Agent skills and dev fixtures.
- Agent Harness tests around provider-visible tools.
- Durable docs describing tool result shape.

## State Diff

From: `data.peek` bundled inspection, profile-like analysis, and structure evidence into one tool.

To: `data.peek` removed; `data.query` is the bounded probing surface with compact row/column output.

## Invariants

- Query calls are read-only and side-effect free.
- Query results do not echo inputs such as `bindings`, `dataset_id`, or `limit`.
- Query errors can return `{error: ...}` without success-side validation summaries.
- Provider schemas avoid unsupported `anyOf` / `oneOf` requirements.

## Decisions Consumed

- See `ledger/decisions.md`: `data.peek` removal, conservative provider schema subset, compact table pattern, `bindings` priority.

## Open Questions

- OQ-003: whether a future descriptive-statistics tool should replace useful old `data.peek.analysis` behavior.

## Verification Plan

- Ensure tool specs exclude `data.peek`.
- Ensure skills no longer tell the model to start with `data.peek`.
- Ensure `data.query` result shape is compact and ordered as `columns` before `rows`.
- Ensure `bindings` wins when both `bindings` and `dataset_id` are present.

## Verification Run Log

- Covered by `pdm run python -m pytest -q`: 304 passed, 3 warnings.
- Historical focused runs are in `ledger/verification.md`.

## Next Action

Watch new real-agent traces for whether query-first guidance is enough, then decide OQ-003 separately.
