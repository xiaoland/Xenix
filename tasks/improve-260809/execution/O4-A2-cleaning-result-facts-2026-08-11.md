# O4-A2 Bounded Cleaning Result Facts — 2026-08-11

## Outcome

O4-A2 is implemented and objectively verified. `data.clean` still creates a complete derived Dataset and user-openable Artifact, but its canonical Agent/Provider Tool Result is metadata-only. It exposes the facts needed to understand one ordered cleaning pass without copying cleaned rows into the context window.

## Implemented State Diff

### Service authority

Each executed mean, median, mode, or constant fill now records one JSON-safe `resolved_fill_value` beside `operation`, `column`, and `cells_filled`. Forward-fill reports its operation and count but no fictional single value. Non-finite numeric scalars are normalized to bounded strings before report persistence.

The canonical staged order witness now proves:

- validation before median fill resolves `22`;
- median fill before validation resolves `14`.

### Agent compact projection

The existing bounds remain authoritative: 12 operation entries, 12 validation entries, 6 column names per collection, 96 characters per column/fill string, 5 warnings, and 240 characters per warning. The normal result now also carries the public `source_dataset_id`.

### Provider XTT

`data.clean` is routed to a dedicated renderer before generated-Dataset inspection is read. Its output contains:

- public source/result Dataset and Artifact IDs;
- row counts, whole-Dataset scope, and the holdout-safety boundary;
- ordered, allowlisted operation effects;
- bounded validation effects and omission counts;
- bounded warnings;
- an explicit note that rows and schema are omitted.

The XTT allowlist excludes inspection fields, preview rows, schema, paths, mappings, distributions, one-hot category-derived names, and arbitrary report extensions. The renderer always returns one bounded string, so malformed/missing inspection cannot fall back to the raw payload.

## Context Boundary Proof

The public Tool black box created and locally opened the complete seven-row Dataset/Artifact, while the canonical Tool Result:

- was under 4,096 characters for the five-operation case;
- contained no `shape`, `schema`, `data`, `records`, or `preview_rows` section;
- contained no fixture row identifier or date sentinel;
- retained median `135`, mode `North`, and the exact `validation.max` violation/removal facts.

This deliberately permits one bounded scalar because O4 identified the missing resolved fill value as a cause of follow-up queries. It does not permit any row or value collection. The independent audit's stricter numeric-only privacy proposal was not adopted because privacy was explicitly out of scope and would weaken the causal objective; its preview and allowlist findings were adopted.

## Verification

- focused service/Tool/canonical-XTT transport: `9 passed`;
- ordinary suite: `142 passed`, with 488 existing Joblib/NumPy deprecation warnings;
- `pdm run check`: passed;
- `pdm run smoke`: passed;
- `git diff --check`: passed before documentation closeout.

The first parallel full-test/smoke attempt exceeded the smoke command's 120-second orchestration window while both processes were contending. It produced no assertion failure and left no process running. Both commands then passed independently; this is execution scheduling evidence, not a product failure.

## Remaining Work

O4-A3 may now clarify left-to-right operation order and make atomic validation the canonical cleaning owner for supported row filters. It must keep `data.transform` available for predicates not represented by atomic cleaning operations and must remain separately attributable from this result-contract change.
