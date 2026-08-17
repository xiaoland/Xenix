# O4-A1 Implementation Plan — Cleaning Service Oracle

**Status:** Completed and objectively verified on 2026-08-11. The initial inadmissible fixture was replaced, the full control matrix landed, and the independent audit blockers are closed.
**Execution record:** [O4-A1 cleaning service correctness — 2026-08-11](../execution/O4-A1-cleaning-service-correctness-2026-08-11.md).

## Outcome

Turn the cleaning textbook risk into an independent ordinary service acceptance case that fails on the current nullable validation-before-imputation defect without prescribing how the service implements validation.

## Why the Existing Proof Missed It

The two existing executable cases prove different things:

- `tests/test_ml_foundation_profile_cleaning.py` is a public-boundary service workflow, but its missing-value and validation operations do not interact. It fills missing `revenue`, then validates a different `discount_rate` column with no missing values.
- `benchmarks/agent_harness/test_ml_cleaning.py` has the exact five-row/median-21 outcome oracle, but it is Tool-route agnostic by design. Any run descendant matching the final table passes, including the observed clean → transform → clean route that never invokes nullable comparison validation.

The gap is relational: neither ordinary service acceptance nor its fixture says that a missing value on the same numeric field must survive comparison validation so that a later operation can impute it. A raw-CSV-only spot check is also insufficient because the defect is exposed by the canonical registered Parquet's nullable integer representation.

## Public Black-Box Shape

Use a new service-owned fixture with distinct bytes and business identifiers. It should contain:

- one exact duplicate;
- two negative numeric values;
- two missing values in that same numeric field;
- five other non-missing valid values whose post-dedup/post-validation median is independently obvious;
- text values needing trim and lowercase.

The test flow is:

```text
service-owned CSV + frozen hash
→ isolated XENIX_APP_HOME
→ DatasetService registration/canonical staging
→ public DataCleaningService.clean_dataset
→ load returned output
→ compare exact business oracle and public report
→ prove source bytes and registered source remain unchanged
```

Do not call `_clean_dataset_in_process`, `_validation_mask`, `_apply_validation_operation`, or inspect a Pandas dtype/mask. Do not import the benchmark fixture or its `_EXPECTED_ROWS`. The oracle is a literal independent expected table calculated from the fixture's business rules.

## Minimal Complete Case Matrix

| Cell | Operations / condition | Observable oracle | Purpose |
| --- | --- | --- | --- |
| G1 golden workflow | exact dedupe → non-negative/drop → trim → lowercase → median fill | exact seven-row/four-column result; negatives and duplicate absent; two missing records retained and filled with independently calculated median 22; normalized text | reproduces the user-level service contract and current defect |
| C1 sibling numeric comparisons | parameterized `non_negative`, `min`, and `max`, each with one violation plus one missing value before later fill | only the actual comparison violation is dropped; missing identity remains and is filled; report removal arithmetic matches output | prevents a one-operation special case while staying at the shared public semantics |
| C2 explicit missing rejection | `validation.not_null(action=drop_rows)` before fill | missing row is removed; later fill does not recreate it | proves missing preservation is not applied to the rule whose purpose is rejecting missingness |
| C3 report-only | numeric violation with `action=report_only` before fill | no row is removed; violation is reported; missing row is filled | protects action semantics and report/output agreement |
| C4 order witness | same clean-room data with fill before numeric validation | output differs from G1 by the independently calculated pre-validation median | proves the public left-to-right contract without asserting the loop implementation |

G1 is the required regression. C1 may be one parameterized test; C2–C4 are compact semantic controls. Do not expand A1 into exhaustive coverage of unrelated cleaning operations.

## Acceptance Assertions

- exact output columns, row identities, values, and row count;
- no duplicate, negative, or unresolved missing value in G1;
- public report `row_count_before`, `row_count_after`, and `rows_removed` reconcile;
- validation entry's `violations` and `rows_removed` equal the actual rejected rows;
- median-fill entry records two filled cells, while the output values independently prove the median;
- input fixture bytes and registered source content are unchanged;
- no assertion names a private helper, `<NA>`, `fillna(False)`, or a concrete dataframe implementation.

## Verification Order

1. Demonstrate G1 fails on the pre-change service for the expected wrong-output/report reason.
2. Implement only the numeric comparison-mask semantic correction.
3. Run G1 and C1–C4.
4. Re-run the existing Foundation workflow to protect its broader lineage/Artifact/profile contract.
5. Run `pdm run pytest --direct tests/test_ml_foundation_profile_cleaning.py -q`, `pdm run test`, and `pdm run check`.

No Agent Harness or paid Provider run is part of O4-A1. O4-A2/A3 may only start from a green, trustworthy service boundary.

## Independent Review of the Concurrent Worktree

The observed service change makes comparison masks total with missing values treated as non-violations and records actual row-count delta. That matches the proposed service state diff.

The initially observed test was not an admissible independent oracle:

- its seven-row topology and numeric sequence `12, missing, 18, 18, -3, 24, 30` are identical to the Agent fixture, including duplicate placement and median 21; changing field/record labels is exactly the renamed-derivative pattern rejected by the packet's fixture policy;
- it implements G1 only; C1–C4 are absent;
- it proves the final filled value through the expected table but does not assert the public median-fill report entry and `cells_filled=1`.

That fixture was discarded. The accepted replacement uses ten rows, two missing values, two invalid values, a different valid-value distribution, median 22, different duplicate placement, and distinct business identities. G1, the three numeric-comparison variants, explicit not-null/report-only semantics, and the reverse-order witness all execute through canonical Dataset staging and the public cleaning service.
