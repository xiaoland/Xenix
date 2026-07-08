# Docs, Skills, Fixtures, And I18n

## Objective & Hypothesis

The tool/storage contract only works if durable docs, skills, fixtures, tests, and translations stop teaching the old `data.peek` and artifact-link assumptions.

## Status

verified, ongoing

## Durable Owners / Blast Radius

- Product TDD and unit TDD docs.
- Agent skill Markdown and JSON assets.
- Dev fixtures and AIMock expectations.
- Translation catalogs.
- Task packet control surface.

## State Diff

From: docs and skills described source-file datasets, eager artifact links, and `data.peek`-first workflows.

To: docs and skills describe query-first probing, Parquet-backed app-owned datasets, `dataset://` activation, lazy workbook export, and compact tool results.

## Invariants

- Durable docs should describe stable contracts, not transient execution logs.
- Skills should tell the model what tools can do without over-prescribing brittle recipes.
- Task packet history belongs in archive/evidence, not the dashboard.
- i18n strings must be extracted and compiled when UI text changes.

## Decisions Consumed

- All decisions in `ledger/decisions.md`.

## Open Questions

- OQ-005: packaged runtime verification for new export/import dependencies.

## Verification Plan

- Search docs/skills/tests for stale `data.peek` guidance.
- Run i18n extract/compile after UI strings change.
- Keep task packet current after each sub-task.

## Verification Run Log

- Covered by `pdm run python -m pytest -q`: 304 passed, 3 warnings.

## Next Action

Use this packet for continuing documentation alignment, but create separate workstreams for runtime DB migration or packaging work.
