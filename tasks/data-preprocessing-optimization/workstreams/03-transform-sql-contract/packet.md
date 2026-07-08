# Transform SQL Contract

## Objective & Hypothesis

Make `data.transform` a durable preprocessing tool that can express multi-step cleaning while preserving service-owned storage authority and atomic output registration.

## Status

verified

## Durable Owners / Blast Radius

- `DataQueryTransformService`
- DuckDB SQL validator
- generated dataset registration
- tests for failure atomicity and SQL validation

## State Diff

From: transform mostly behaved like a single SELECT materialized to CSV, with CSV validation failure able to leave half-success side effects.

To: transform supports bounded in-memory scripts, requires an `output` relation, materializes Parquet, validates output, and only then registers the derived dataset.

## Invariants

- User SQL cannot read or write direct filesystem paths.
- `CREATE` must be temporary.
- Extension/install/load/import/export/attach/copy authority remains rejected.
- Failed validation leaves no final output file and no derived dataset row.

## Decisions Consumed

- `data.transform` is the durable materializing tool.
- User SQL may mutate only in-memory temporary relations.
- Durable registration happens after output validation.

## Open Questions

None blocking for the current contract.

## Verification Plan

- Multi-statement script can create `output`.
- Missing `output` fails clearly.
- Validation failure is atomic.
- Derived output is Parquet.

## Verification Run Log

- Covered by `pdm run python -m pytest -q`: 304 passed, 3 warnings.

## Next Action

Use real traces to tune SQL repair hints, not the storage/output authority model.
