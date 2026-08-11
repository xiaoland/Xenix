# Impact Handshake O4-A1 — Nullable Cleaning Service Correctness

**Status:** Consumed and completed on 2026-08-11 after Sir explicitly approved A1 implementation.

## Evidence Trigger

[O4](IH-O4-cleaning-causal-diagnosis.md) reproduced a deterministic service defect on the canonical registered Parquet: a nullable numeric comparison produces a mask containing `<NA>`, while `drop_rows` indexes with the inverted mask. The missing row is excluded even though it is not counted as a violation, so a later median-imputation operation cannot fill it.

The existing Foundation service case does not exercise this interaction. It fills missing `revenue` before applying `validation.max` to a different, non-missing `discount_rate` field. The independent Agent benchmark has the right final business oracle, but deliberately accepts any correct descendant Dataset and therefore can pass through a SQL-transform route without qualifying the one-call cleaning service route.

## Address and Object

- `src/xenix/services/data_cleaning.py`: numeric comparison-validation row-selection semantics at the public `DataCleaningService.clean_dataset` boundary;
- `tests/test_data_cleaning_service.py`: independently designed complete-result black-box regression and semantic controls;
- `tests/fixtures/ml_foundation/ordered_validation_raw_v1.csv` and `ordered_validation_expected_v1.csv`: service-owned raw/expected oracle pair;
- the existing Foundation workflow as a non-regression selector;
- the ignored private-material Foundation adapter for a corrected complete textbook-result check.

No Skill, Tool input schema, Tool result/XTT projection, Agent orchestration, benchmark fixture/evaluator, transform service, storage schema, UI, or paid Provider run belongs to O4-A1.

## State Diff

- **From:** `validation.non_negative`, `validation.min`, and `validation.max` may treat a nullable numeric missing value as neither a counted violation nor a retained row when `action=drop_rows`; report removals can disagree with actual row loss and later imputation cannot act on the missing row.
- **To:** numeric comparison validation has a total boolean violation decision. Missing values are retained unless an explicit missing-value rule rejects them; dropped-row count equals the number of rows actually rejected; subsequent ordered operations observe the retained rows.

## Blast Radius

Only numeric comparison-validation row rejection in whole-Dataset cleaning and its public report. The service continues to execute the caller's operation list left-to-right and to create a new output rather than overwrite the source.

## Invariants

- `validation.not_null(action=drop_rows)` still removes missing rows.
- `action=report_only` never removes rows.
- A missing value is not silently reclassified as a passing or failing business value; it remains missing for a later explicit missing-data operation.
- `validation.allowed_values`, `validation.regex`, duplicate, text, type, outlier, encoding, scaling, and transform semantics do not change.
- The regression uses independently owned service bytes and oracle; it does not import or copy the Agent benchmark fixture, evaluator, or report.
- The test asserts public output membership/values, source immutability, and report arithmetic, never a private helper, Pandas mask representation, or implementation branch.

## Verification

1. Register the service fixture through `DatasetService` so cleaning consumes the canonical staged representation.
2. Call public `DataCleaningService.clean_dataset` with duplicate removal, numeric validation/drop, text normalization, and later median fill in the business-specified order.
3. Assert the exact independently calculated output, preserved/finally filled missing-row identity, source immutability, and reconciled report counts.
4. Run semantic controls for `validation.not_null`, `report_only`, sibling numeric comparators, and reversed operation order.
5. Run the focused Foundation selector, the complete ordinary suite, `pdm run check`, and `pdm run smoke`. No paid run is required for A1.

All five proof cells passed. The ordinary suite finished with 142 tests, and both repository checks passed.

## Return to Discussion

Result projection, resolved fill values, Skill/Tool authority, and live Agent measurements remain outside this completed slice and require their later O4 handshakes.
