# Impact Handshake O4-A2 — Bounded Cleaning Result Facts

**Status:** Consumed, implemented, and objectively verified on 2026-08-11 after Sir explicitly authorized O4-A2.

## Evidence Trigger

O4 proved that the authoritative cleaning report records operation names and aggregate counts but omits the value actually learned by mean, median, or mode imputation. The Provider-facing Xenix Table Text then omits validation effects while rendering generated Dataset preview rows. The Agent therefore sees the least useful part of the result at the highest context cost.

## Address and Object

- `DataCleaningService._apply_missing_operation`: retain the resolved scalar used by each fill operation;
- `AgentToolRegistry._compact_cleaning_report_operation`: project that scalar through the existing bounded cleaning report;
- `xenix_table_text._render_generated_dataset_preview` and `_append_cleaning_metadata`: make `data.clean` metadata-only at the Provider boundary and render bounded operation/validation effects;
- ordinary service and Agent-Tool black-box tests plus this task packet.

No cleaning input schema, operation semantics, Dataset contents, Artifact contents, ML preparation contract, paid benchmark oracle, or Provider budget changes are authorized.

## State Diff

- **From:** a fill reports only `cells_filled`; validation facts exist in the compact payload but disappear from Provider XTT; `data.clean` XTT includes generated Dataset preview rows.
- **To:** a fill also reports one JSON-safe `resolved_fill_value`; Provider XTT exposes public Dataset/Artifact IDs, row counts, bounded ordered operation effects, bounded validation effects, and warnings, while exposing no generated row, cell, schema preview, or local path.

## Bounds

- at most 12 operation effects and 12 validation effects;
- at most 6 column names per bounded collection;
- column names and string fill values are capped at 96 characters;
- at most 5 warnings of 240 characters;
- one scalar fill value per executed fill operation; no vectors, distributions, dictionaries, previews, or Dataset rows;
- omitted counts remain explicit when a bound is reached.

## Invariants

- The derived Dataset and user-openable Artifact remain the authorities for complete cleaned data.
- The Artifact's local metadata may retain the full execution report; the Provider receives only the compact projection.
- Operation order remains left-to-right and visible in the bounded operation sequence.
- Validation `violations`, `action`, and actual `rows_removed` remain distinct facts.
- `data.query` remains the explicit, purpose-limited path for values that are genuinely needed after cleaning.
- No source path, output path, `inspection.preview_rows`, raw row, or complete Dataset crosses the Agent boundary.

## Verification

1. The canonical staged nullable Dataset reports median `22` after validation and median `14` when the order is reversed.
2. A real `data.clean` Tool call returns Dataset/Artifact IDs, ordered effects, resolved fill values, and validation effects.
3. That same Tool result contains no row preview, schema preview, fixture row identifier, raw text value, source path, or output path.
4. Existing generated previews for other Tool families remain unchanged.
5. Focused tests, the ordinary suite, `pdm run check`, `pdm run smoke`, link checks, and `git diff --check` pass.
