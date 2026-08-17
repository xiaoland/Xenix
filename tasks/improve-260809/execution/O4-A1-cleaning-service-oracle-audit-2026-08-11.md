# O4-A1 Cleaning Service Oracle Audit — 2026-08-11

## Verdict

The existing Foundation cleaning test is a legitimate public-boundary integration test, not an implementation-mirror test. Its oracle is nevertheless incomplete for the textbook cleaning risk: it proves several operations in one workflow but does not make validation and imputation interact on the same nullable numeric column.

The Agent benchmark's final oracle does cover the correct business outcome, but it cannot substitute for service acceptance because it intentionally does not prescribe a Tool route. Its historical and retained successful runs can reach the exact result through `data.transform`, bypassing the defective `data.clean` validation path.

## 1. Why the Oracle Did Not Cover Nullable Validation Before Imputation

### Facts

- The service fixture `profile_cleaning_v1.csv` has missing `revenue`, but the operation list fills `revenue` before any validation.
- Its later `validation.max(action=drop_rows)` targets `discount_rate`, whose fixture values are all present. The nullable comparison mask therefore never contains an undecided missing element.
- The test registers the source and cleans the staged Dataset through `AgentToolRegistry`; canonical staging is already present. The missing axis is operation/data interaction, not absence of integration plumbing.
- The Agent fixture places a negative and a missing value in `parcel_count`, and its prompt orders negative-row rejection before median fill. Its evaluator accepts any run-descendant Dataset equal to the exact five-row oracle.
- The paid historical run and retained successful reproduction both used a transform. Thus an Agent semantic pass does not prove `validation.non_negative(drop_rows)` followed by `missing.fill_median` is correct.

### Inference

F1 mapped textbook chapters to a broad clean-room risk inventory—duplicates, missingness, range validation, outliers, typed profile, lineage, and immutability. Its acceptance language enumerated those facts but did not freeze a causal relation between operations. The clean-room redesign avoided copying textbook bytes correctly, yet changed the critical topology from “validate and later impute the same nullable field” to “impute one field and validate another.”

### Not the Cause

- The Agent oracle's expected five rows and median 21 are correct.
- The existing Foundation test does not read private helpers or mirror the mask implementation.
- CSV registration already stages the data; simply adding another raw-CSV direct-service check could falsely pass and would not close the canonical nullable-data gap.

## 2. Required Service Black-Box Acceptance

The new acceptance must derive from the business rule, not from the current mask code:

1. independently author service-owned rows with a duplicate, negative, missing, valid numeric values, and untidy text;
2. freeze their bytes but do not reuse benchmark rows, identifiers, expected-table helpers, or reports;
3. register through `DatasetService` and call only public `DataCleaningService.clean_dataset`;
4. issue the five business operations in the stated order;
5. compare the returned output with a literal independently calculated expected table;
6. assert public report arithmetic and source immutability;
7. add semantic controls that distinguish comparison validation, explicit not-null rejection, report-only behavior, and operation order.

This fails the current implementation because the missing-row identity disappears before imputation. It remains valid if Pandas/DuckDB internals, mask construction, or helper structure change.

## 3. Minimum Complete Matrix

The detailed matrix is owned by the [O4-A1 implementation plan](../implementation/O4-A1-cleaning-service-correctness.md). Its five cells are:

- G1 exact business workflow;
- C1 parameterized numeric comparison validators;
- C2 explicit `not_null` rejection;
- C3 `report_only` control;
- C4 reversed-order witness with a different expected median.

The matrix intentionally excludes unrelated allowed-values/regex/text/type/outlier/encoding/scaling behavior. Existing Foundation coverage remains responsible for broader Dataset/Artifact/profile/lineage integration.

## 4. Documentation Corrections

- F1's 2026-08-09 execution remains a true record of the workflow it ran; it must not be rewritten as if that run failed.
- Claims that Foundation fully qualifies the textbook cleaning semantics need narrowing: it qualifies bounded profile/general cleaning integration, but not nullable comparison validation before later imputation.
- O4-A1 must be a separate proposed mutation handshake because F1 explicitly excluded cleaning-operation semantic changes.
- A1 is service-first and Provider-free. Result projection and Tool/Skill efficiency remain later O4 slices.

## Files Reviewed

- `tasks/improve-260809/handshakes/IH-F1.md`
- `tasks/improve-260809/implementation/F1-dataset-profile-cleaning.md`
- `tasks/improve-260809/execution/foundations-2026-08-09.md`
- `tasks/improve-260809/cases/catalog.md`
- `tests/test_ml_foundation_profile_cleaning.py`
- `tests/fixtures/ml_foundation/profile_cleaning_v1.csv`
- `benchmarks/agent_harness/test_ml_cleaning.py`
- `benchmarks/agent_harness/fixtures/ml_capabilities/service_ticket_cleaning.csv`
- `src/xenix/services/data_cleaning.py`

No source, test, fixture, benchmark, or paid Provider was changed or executed during this audit.

## Concurrent Worktree Implementation Review

After the initial audit, another worker's uncommitted O4-A1 implementation became visible in the shared worktree. This audit remained read-only.

### Service change

The proposed change normalizes validation masks with missing entries as non-violations before row selection and computes `rows_removed` from the actual frame delta. This satisfies the intended public service semantics and fixes both the silent missing-row loss and validation/top-level report inconsistency. No issue was found in that narrow state diff from static inspection.

### Test/oracle blockers

The new raw fixture is not independently designed. It retains the Agent fixture's complete seven-row relation and numeric sequence—`12, missing, 18, 18, -3, 24, 30`—including the duplicate and median 21, while renaming columns and record identifiers. The packet explicitly states that renaming or transforming another fixture does not make it clean-room. This blocks acceptance even though the bytes and SHA-256 differ.

The new test also covers only G1. It lacks the C1 sibling-comparator, C2 `not_null`, C3 `report_only`, and C4 order-witness controls, and does not assert the public median-fill report entry. The current test is a useful regression demonstration, but it is not the minimum complete independent service qualification specified by this audit.

### Required correction before acceptance

1. Replace both raw/expected fixtures with independently selected identities, numeric values, text variants, and an independently calculated median.
2. Add C1–C4 without importing benchmark assets or private cleaning helpers.
3. Assert the fill report records one filled cell and all removal arithmetic reconciles.
4. Keep the narrow service change; do not broaden A1 into Tool/Skill/XTT work.

## Resolution

The audit blockers were closed later on 2026-08-11:

- the renamed seven-row fixture was discarded and replaced with an independently authored ten-row raw fixture plus a complete seven-row expected CSV;
- the new topology contains two missing values, two negative values, a separately placed duplicate, five valid numeric values, and independently calculated post-validation median 22;
- the public-service test now covers the golden ordered workflow, all three numeric comparison validators, explicit `not_null`, `report_only`, and a reverse-order witness whose pre-validation median is 14;
- the fill report, validation report, whole-report row arithmetic, complete output, original bytes, and canonical staged source are asserted;
- focused tests, all 142 ordinary tests, `pdm run check`, and `pdm run smoke` pass.

The audit therefore accepts O4-A1. The separate textbook full-result check remains fail-closed because the earlier private adapter's `223 × 13` aggregate result is not the supplied `218 × 18` expected result; that correction is recorded in the O4-A1 execution record.
