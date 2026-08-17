# O4-A1 Cleaning Service Correctness — 2026-08-11

## Outcome

O4-A1 is complete. Numeric comparison validation now preserves nullable values for later ordered missing-value operations, and validation `rows_removed` records the actual output delta. The new ordinary service acceptance is independent of the Agent benchmark and compares the entire returned table with a frozen expected CSV after canonical Dataset staging.

## Red Evidence

The valid regression registers its CSV through `DatasetService`, then calls `DataCleaningService.clean_dataset`. Before the service change the returned table lost the missing numeric row during `validation.non_negative(action="drop_rows")` even though the report counted only negative rows as violations. A raw-CSV-only call had passed, proving canonical nullable staging is a necessary part of this black-box boundary.

The first drafted fixture was rejected by independent review because it preserved the Agent benchmark's seven-row/numeric topology under renamed fields. It was discarded rather than accepted by hash difference alone.

## Accepted Service Oracle

The replacement fixture is independently authored:

- ten source rows and one separately placed exact duplicate;
- two negative values and two missing values in the same numeric field;
- five retained observed values with post-validation median 22;
- text values requiring trim and lowercase;
- a complete seven-row expected CSV rather than selected-row or aggregate assertions.

The proof matrix covers:

1. dedupe → non-negative/drop → text trim/lowercase → median fill;
2. nullable behavior for non-negative, minimum, and maximum comparisons;
3. explicit `validation.not_null(action="drop_rows")`;
4. numeric validation with `action="report_only"`;
5. fill-before-validation order witness, which produces median 14 rather than 22.

## Textbook Oracle Correction

The earlier ignored Foundation material adapter did not compare with the supplied expected result. It derived a generic exact-dedupe/all-column-fill plan from the source schema and promoted only aggregate facts. That produced `223 × 13` with zero missing cells and was incorrectly described as qualified cleaning evidence.

O4-A1 admitted the supplied `customer_sample_keep_extremes.csv` as evaluator-only expected output and reran the private service cell through adapter `private_runner.foundation.v2`:

- logical source-manifest digest: `e0bd80f73151c93bb5574c889b4f03887c4bb4903bbd999210dc62e0c681c3f5`;
- result: stable fail-closed `oracle_qualification_failed / cleaning_complete_result`;
- observed Xenix shape: `223 × 13`;
- supplied expected shape: `218 × 18`;
- failure record SHA-256: `f3aef9083d404c28c582d0f42275f50dc05b4cf54abf910c18ed7d5bf4643926`;
- Provider attempts and reference-code executions: zero.

The difference is not caused by the nullable-mask defect alone. The textbook result also applies business-key latest-record selection, required-field and high-missing-row rules, per-field missing strategies, missing indicators, invalid-to-null treatment, and outlier facts that the old adapter never attempted. The prior Foundation cleaning qualification is retracted; this private cell is now truthful diagnostic evidence for later cleaning-capability work.

## Verification

| Gate | Result |
| --- | --- |
| Focused service/Foundation selectors | 7 passed |
| Ordinary suite | 142 passed; 488 existing Joblib/NumPy deprecation warnings |
| `pdm run check` | passed |
| `pdm run smoke` | passed |
| Private textbook complete-result cell | expected fail-closed at `cleaning_complete_result` |
| `git diff --check` and task links | passed |

No Agent Tool, XTT projection, Skill, transform service, benchmark asset, or paid Provider behavior changed in O4-A1.
