# M1 Implementation Plan — Private-Material Service Characterization

**Status:** Completed, with a 2026-08-11 correction: clustering/forecasting remains qualified; Foundation cleaning is reclassified fail-closed after complete-result comparison; recommendation and text remain fail-closed. It authorized no product mutation or Provider upload.
**Execution record:** [M1 private-material service characterization — 2026-08-10](../execution/M1-private-material-service-characterization-2026-08-10.md).

## Outcome

Use selected complete supplied code/data cases to test realistic shape, format, leakage, runtime, and failure behavior after the clean-room service contracts are green. Clean-room tests remain acceptance authority; textbook outputs remain reference evidence only.

## Preconditions

- A clean repository checkpoint with all ordinary service tests green.
- The general, CF, and RT material-adoption guards remain in force.
- Every selected file is hash-bound and `internal_only`; Joblib/Pickle is never loaded.
- Reference, subject, and evaluator roots are physically disjoint.

## Independent Cells

1. **Foundation:** selected ch06/ch07/ch11 CSVs for profile, cleaning, schema/apply, and lineage characterization.
2. **Clustering/forecasting:** admitted ch12/ch15 CSVs for scale, temporal ordering, convergence, interval, and runtime characterization; reuse the completed ch15 algorithm spike only as planning evidence.
3. **Recommendation:** `M14-R-CONTENT` and `M14-R-CF` for scale, seen exclusion, and cold-user behavior; `M14-R-EVAL` is evaluator-only and never becomes subject truth.
4. **Text:** `M16-T-PREP`/`DICT` for deterministic preparation and process isolation; `M16-T-MODEL` only reproduces template leakage and cannot issue an acceptance verdict.

Each cell has its own G0 manifest, selected inputs, limits, command, output root, independent evaluator, and bounded evidence record. A failure in one cell does not block or rewrite another.

## Coherent Passes Per Cell

1. Bind canonical locators, hashes, sizes, runtime identity, license status, and admitted question.
2. Static-scan selected code; remove or block network, GUI, subprocess, package install, serialization, archive extraction, and writes outside one ignored output root.
3. Run the matching clean-room service selector first.
4. Execute only a reviewed reference projection when needed; independently recompute promoted facts.
5. Run Xenix through the public service boundary on the admitted private data.
6. Record bounded shape/runtime/metric/limitation evidence; retain all rows, labels, terms, memberships, predictions, and paths privately.

## Stop Conditions

Stop on hash/license mismatch, unexpected write, unsafe code tail, serialization, network attempt, answer contamination, irreproducible reference output, or a finding that changes product semantics. Any product change requires a new exact handshake and clean-room regression proof before the private cell is rerun.

## Acceptance

M1 is complete when every admitted cell has either a qualified bounded characterization or a stable fail-closed reason. It does not require or permit uploading supplied bytes to the paid Agent.

That condition remains met because a stable fail-closed result is valid characterization evidence. Current dispositions are: clustering/forecasting qualified; Foundation cleaning failed closed on `oracle_qualification_failed / cleaning_complete_result` after its earlier aggregate-only verdict was corrected; recommendation failed closed on `oracle_qualification_failed / recommendation_holdout`; text failed closed on `format_semantic_mismatch / text_resource_admission`. Supporting the newly exposed textbook cleaning semantics or two-column text normalization mappings requires separate exact handshakes.
