# O4-A2 Cleaning Result Projection Audit — 2026-08-11

**Status:** Independent stricter-boundary recommendation, partially adopted. It is not the accepted O4-A2 contract or final execution verdict.

## Integration Resolution

The audit correctly located the canonical projection owner and caused the implementation to use a dedicated metadata-only renderer, a narrow operation allowlist, zero inspection/schema/row preview, and no raw-payload fallback. Its proposed zero-string privacy posture was not adopted: Sir explicitly removed privacy as a constraint for this diagnosis and separately constrained context size, while O4's reproduced cause requires the actual bounded mean/median/mode result to avoid another value query. O4-A2 therefore permits one scalar per executed non-forward fill, caps strings at 96 characters, and still prohibits rows, lists, distributions, generated category columns, paths, or complete Dataset content.

The bounded warning text and validation name are also retained because both are code/caller-authored facts already known to the Agent and have hard entry/length limits. This choice is a context contract, not a privacy contract. The accepted result and verification are recorded in [O4-A2 execution](O4-A2-cleaning-result-facts-2026-08-11.md).

## Verdict

The current cleaning path has one canonical Provider value, but that value exposes the wrong facts. `data.clean` creates a compact report containing bounded validation effects, then Xenix Table Text discards those effects and renders up to five cleaned rows from the generated-Dataset inspection. The service report records only `cells_filled`, so the Provider cannot learn the resolved median/mean that the user requested.

O4-A2 should use a dedicated, fail-closed `data.clean` projection. It may expose public Dataset/Artifact identity, aggregate row/effect counts, controlled operation names, bounded validation effects, and finite numeric mean/median fill facts. It must not expose a cleaned-row preview, inspection schema, raw value/list/map, category-derived generated name, local path, arbitrary warning text, mode value, or echoed constant value.

The consumed A2 handshake currently permits string fill values and free-form warnings. Those two permissions conflict with the requested privacy contract and should be corrected before acceptance.

## Current End-to-End Shape

### 1. Service report generation

`DataCleaningService.clean_dataset` returns `CleanDatasetResult`:

```text
output_path: str
report:
  row_count_before: int
  row_count_after: int
  rows_removed: int
  no_op: bool
  operations: list[dict]
  validation_rules: list[dict]
  warnings: list[str]
```

The report remains a `dict[str, Any]`; its detailed entries are operation-specific rather than schema-validated as one union.

`DataCleaningService._apply_missing_operation` currently appends, for each affected fill column:

```text
operation: missing.fill_mean | missing.fill_median | missing.fill_mode | missing.fill_constant | missing.forward_fill
column: str
cells_filled: int
```

`DataCleaningService._resolve_fill_value` computes the mean, median, mode, or constant, but returns it only to the dataframe mutation. No resolved value enters the report.

`DataCleaningService._apply_validation_operation` appends:

```text
name: str
column: str
operation: validation.*
action: report_only | drop_rows
violations: int
rows_removed: int                 # only when drop_rows removed rows
```

The full report is also retained in local Dataset-export Artifact metadata by `AgentToolRegistry._data_clean` through `_register_generated_dataset_result`. That local audit is not the Provider contract.

The complete report cannot be projected wholesale. For example, one-hot encoding retains raw categories in `columns_summary.category_columns`; generated column names can also embed those values. Warning text is currently implementation-authored, but the report type does not mechanically prevent a future warning from containing a raw value.

### 2. Agent Tool payload before rendering

`AgentToolRegistry._data_clean` calls the service, then `preprocessing_worker._register_generated_dataset` returns:

```text
dataset_id: public result Dataset ID
artifact_id: public Dataset-export Artifact ID
summary: fixed-template aggregate summary
inspection:
  source_format
  file_name
  row_count
  column_count
  columns
  preview_columns
  preview_rows                       # up to five cleaned rows
```

`_data_clean` adds:

```text
row_count_before
row_count_after
scope: whole_dataset
holdout_safe_model_preparation: false
cleaning_report: _compact_cleaning_report(full_report)
```

The normal non-no-op result currently does not add `source_dataset_id`; the no-op branch does.

`AgentToolRegistry._compact_cleaning_report` already caps operation and validation entries at 12, warnings at 5, column collections at 6, column names at 96 characters, and warnings at 240 characters. It retains validation rules, but it also has broader operation-detail projection, including category-derived `generated_columns`. Bounds prevent unbounded context; they do not make a raw value safe.

### 3. XTT and canonical Tool Result

`AgentToolRegistry._tabular_tool_success` calls `render_xenix_table_tool_result`. For `data.clean`, `xenix_table_text._render_generated_dataset_preview` currently emits:

- `dataset_id`, `artifact_id`, summary, and row counts;
- `rows_removed`, operation names, and warning text from `_append_cleaning_metadata`;
- inspection schema plus up to five cleaned rows.

It does not render the compact report's `validation_rules`, `violations`, `action`, actual validation removals, or any resolved fill value.

The renderer's `None` result falls back to the raw payload in `_tabular_tool_success`. A dedicated privacy projection therefore must not merely “usually omit” inspection. Malformed/missing A2 fields must produce a bounded typed failure, never a raw-payload fallback.

### 4. Storage and Provider wire

After rendering, `ToolSuccess.value` is the XTT string. `LLMConversationService` persists that exact string as `conversation_message.value_payload`; the Provider adapter's `_tool_result_wire_content` returns a string unchanged. No later component creates a second cleaning projection.

Therefore the correct owner is the Tool/XTT projection before `ToolSuccess`, and a Tool-level privacy assertion proves the storage and Provider shape when combined with the existing canonical-XTT transport test.

## Target Provider Contract

The following is the maximum allowed semantic shape. Formatting may be XTT/YAML, but it must preserve these types and omission rules.

```text
tool: data.clean
dataset_id: PublicId
artifact_id: PublicId | omitted_on_no_op
source_dataset_id: PublicId
scope: whole_dataset
holdout_safe_model_preparation: false
row_count_before: NonNegativeInt | unavailable_on_no_op
row_count_after: NonNegativeInt | unavailable_on_no_op
rows_removed: NonNegativeInt
no_op: bool

operation_count: NonNegativeInt
operations: up to 12 controlled operation/effect records
omitted_operation_entries: NonNegativeInt | omitted

validation_rule_count: NonNegativeInt
validation_effects: up to 12 records of
  operation: controlled validation operation
  column: bounded schema name
  action: report_only | drop_rows
  violations: NonNegativeInt
  rows_removed: NonNegativeInt | omitted
omitted_validation_rules: NonNegativeInt | omitted

fill_effects: up to 12 records of
  operation: missing.fill_mean | missing.fill_median | missing.fill_mode |
             missing.fill_constant | missing.forward_fill
  column: bounded schema name
  cells_filled: NonNegativeInt
  resolved_fill_kind: finite_numeric_aggregate | dataset_mode_redacted |
                      caller_constant_redacted | row_predecessor_redacted
  resolved_fill_value: finite JSON number | omitted
```

`resolved_fill_value` is allowed only for `missing.fill_mean` and `missing.fill_median`, only when it is a finite JSON number, and only when at least one cell was filled. Mean/median are explicitly admitted derived aggregates even when an odd-cardinality aggregate happens to equal one source value.

Mode remains a member of the source value domain and may be text, an identifier, or a sensitive category. Constant values are already supplied in Tool arguments and need not be echoed. Forward fill has no single resolved scalar. Those three strategies expose a controlled kind and count only.

The Provider projection may retain controlled operation names and numeric effect counts such as `cells_changed` or `rows_removed`. It must drop operation-specific maps/lists, category labels, mappings, generated names derived from categories, distributions, bounds unrelated to imputation, and arbitrary extra fields.

## Mechanical Bounds

| Field family | Bound | Failure/omission behavior |
| --- | ---: | --- |
| result/source Dataset ID, Artifact ID | 1–128 ASCII `[A-Za-z0-9_-]` | required normal-result ID invalid → typed projection failure; no raw fallback |
| operation effects | 12 | publish total and omitted count |
| validation effects | 12 | publish total and omitted count |
| fill effects | 12 | publish total and omitted count |
| schema column names per collection | 6 | 96 characters each; publish omitted count where a collection exists |
| resolved fill value | one finite JSON number per admitted mean/median effect | non-finite, boolean, string, list, map, or unsupported scalar → omit value and use controlled redacted/unavailable kind |
| warning information | count plus at most 5 controlled warning codes | no free-form warning text in Provider projection |
| preview rows/cells/raw value collections | 0 | presence in the pre-render payload is ignored; presence in canonical Tool Result fails privacy test |
| summary | fixed template, at most 512 characters | no user name, path, row value, or arbitrary report text |
| complete canonical Tool Result | existing 64 KiB limit remains | size limit is defense-in-depth, not a privacy control |

Counts must be integers in `0..2^63-1`; booleans do not qualify as integers. Controlled operation/action/kind strings must come from code-owned enums/allowlists. Projection code must not call `str()` on an arbitrary report value and then treat truncation as privacy.

## Fail-Closed Rules

1. Route `data.clean` to a dedicated metadata-only renderer before the generic generated-Dataset preview branch.
2. Ignore the entire `inspection` object for `data.clean`; do not render `columns`, `preview_columns`, `preview_rows`, file name, or format.
3. Project from an explicit allowlist. Unknown fields, nested values, raw maps/lists, and unsupported scalar types are omitted, not stringified.
4. Never expose `name` from a validation rule; it is caller-controlled and unnecessary when operation, column, action, and effects are present.
5. Do not render free-form warnings. Retain only a count and future code-owned warning codes.
6. If required result IDs or the compact report cannot be safely rendered, return a bounded typed projection failure. `_tabular_tool_success` must not return the original payload for `data.clean`.
7. Persist and send exactly the resulting XTT string; no downstream consumer may rehydrate Artifact metadata or inspection into the Provider message.

## Existing Test Coverage and Gaps

### Ordinary service tests

`tests/test_data_cleaning_service.py` proves nullable validation semantics, ordered median behavior, final rows, and report counts. It currently asserts `cells_filled` but not a resolved fill fact. It is the correct owner for service-report generation and should add:

- post-validation median 22;
- reversed-order median 14;
- JSON-safe finite numeric type;
- mode/constant/forward-fill redaction shape rather than a raw scalar.

### Public Tool integration

`tests/test_ml_foundation_profile_cleaning.py` executes a real `data.clean` Tool and extracts public Dataset/Artifact IDs, but it does not assert validation/fill facts or prohibit raw preview/value/path disclosure. It should retain its Dataset/Artifact/lineage checks and add a provider-projection assertion, or a focused new `tests/test_agent_data_cleaning_projection.py` should own the privacy seam.

The projection proof should use private sentinels in row IDs, text/category cells, a mode, a caller constant, a source path, and one-hot category-derived names. The canonical Tool Result must contain none of them while retaining the admitted numeric median and bounded validation effects.

At least one mechanical test must exceed 12 validation/effect entries and assert total/omitted counts. Another must inject a malformed generated-registration payload and prove `data.clean` fails closed instead of returning raw `inspection`.

### Canonical storage/Provider transport

`tests/test_agent_harness_first_slice.py::test_direct_xtt_tool_result_has_one_value_across_storage_provider_and_chatbot` already proves that one XTT string is preserved across storage, Provider request, and chatbot projection. A data-cleaning variant or reuse of the new canonical string should assert the same identity plus sentinel absence.

### Agent benchmark

`benchmarks/agent_harness/test_ml_cleaning.py` correctly evaluates the exact user-visible Dataset, public Artifact linkage, and grounded final answer without prescribing a Tool route. It does not inspect Provider Tool-result privacy and should remain route-agnostic. O4-A2 acceptance belongs to provider-free ordinary projection tests; a later paid ablation measures whether the new facts remove queries, but must not become the privacy oracle.

## Required Documentation Corrections

Before O4-A2 is accepted, its handshake/plan should be narrowed in three places:

- replace “string fill values capped at 96” with finite numeric mean/median only plus controlled redaction kinds for mode/constant/forward-fill;
- replace bounded free-form warnings with counts/controlled codes only;
- state explicitly that category-derived generated column names and renderer raw-payload fallback are forbidden.

## Fact / Inference / Unknown

- **Fact:** the current service does not retain a resolved fill value.
- **Fact:** compact validation effects exist but current XTT does not render them.
- **Fact:** current `data.clean` XTT renders up to five cleaned rows.
- **Fact:** the XTT string is the one persisted and Provider-sent Tool Result.
- **Fact:** existing ordinary/Agent tests do not assert the full A2 privacy contract.
- **Inference:** numeric resolved fill facts should remove a follow-up query whose only purpose is grounding the median/mean.
- **Unknown until later live ablation:** whether the model consistently uses the new facts and whether total rounds/tokens fall.

No product source, ordinary test, benchmark, or Provider was changed or executed by this audit.

## Concurrent Worktree Implementation Review

Another worker's uncommitted A2 implementation became visible after the source audit. This review remained read-only.

### Correct direction

- `xenix_table_text._render_generated_dataset_preview` now routes `data.clean` to a dedicated renderer before reading `inspection`.
- The dedicated renderer emits metadata plus an omission note and never emits the cleaned schema/table/records.
- It always returns a string, so this specific path no longer reaches `_tabular_tool_success`'s raw-payload fallback.
- The XTT operation-effect allowlist does not include category-derived `generated_columns` even though the intermediate compact report may contain them.
- Numeric medians 22 and 14 are now present in service tests, and bounded validation effects reach XTT.

### Stricter-profile findings not adopted as O4-A2 blockers

The current implementation violates the strict raw-value boundary:

1. `DataCleaningService._report_scalar` accepts strings and booleans, converts datetime-like values to strings, and finally calls `str()` on arbitrary objects.
2. `AgentToolRegistry._compact_cleaning_scalar` accepts strings/booleans and truncates arbitrary values to 96 characters. Truncation is a size bound, not redaction.
3. `tests/test_ml_foundation_profile_cleaning.py` explicitly requires the raw mode category `"North"` in the canonical Provider Tool Result.
4. `_append_cleaning_metadata` still emits bounded free-form warning strings.
5. `_cleaning_validation_effect` still emits caller-controlled validation `name`.
6. The normal result still lacks explicit `source_dataset_id`, and public IDs are not mechanically shape-validated before rendering.

The preview-removal portion is acceptable, but the result-fact portion must be revised before A2 can pass this audit. Only finite numeric mean/median aggregates may carry a value; mode, caller constant, and forward-fill must use controlled redaction kinds. Warning text and validation name must not cross the Provider boundary.
