# April Dine-In Sales Cleaning Benchmark Case

Case ID: `cleaning.april_dine_in_sales`

Historical source: thread `bb5827f1c9794952b3490d869403c4cd`, user goal
`清洗`, historical model `kimi/kimi-k2.6`.

## Why This Is a Benchmark Case

The user gives a real business file and a minimal goal rather than a Tool plan.
The Agent must discover the malformed spreadsheet structure, decide how to
materialize a useful dataset, and converge through real Tool feedback. Static
tests can prove individual SQL/index/cleaning operations; they cannot measure
the real Agent's planning cost, detours, failure/recovery behavior, or whether
the final leaf dataset fixes the observed defects.

The source workbook's imported shape is `486,122 x 50`:

- imported columns are `品项销售明细`, `column_2`, ..., `column_50`;
- row 0 is a report-filter description, not business data;
- row 1 contains the actual 50 business headers (`城市`, `机构编码`, ...,
  `单品备注`);
- rows 2 onward contain 486,120 business rows;
- the business section contains 330 exact duplicate rows.

These facts create an objective oracle without prescribing how the Agent must
reach it.

## Input

- Fresh isolated Thread.
- External real/redacted `4月堂食销售数据.xlsx` input, 116,459,191 bytes,
  SHA-256
  `6B902DE50277E727FE936FFC4FE072B4D8B1C3D60A7D85413E114B72C4140E31`.
- One user turn: `清洗`.
- One explicit fully qualified model key supplied by the matrix cell.

No cleaning instructions, expected Tool calls, column indexes, or target schema
are injected into the prompt. The workbook is ignored and not committed; the
explicit benchmark command accepts its path and rejects a missing or mismatched
input as `invalid_setup`.

## Selecting the Output

Output location belongs to this case rather than a universal runner heuristic.
The case records attached source Dataset ids, scans successful canonical Tool
Results from newest to oldest, and selects the first referenced Dataset id that
is readable, was created during this isolated cell, and is not a source input.
Intermediate header-fix or cleaning datasets are allowed and counted. No
matching reference produces a failed `terminal_output_resolved` check, not an
infrastructure-invalid run. The locator does not inspect Tool names/arguments,
traverse lineage, sort timestamps, or infer from Assistant prose.

## Required Outcome Checks

Each check is recorded independently; `outcome_passed` is their conjunction.

1. **`canonical_completion`** — final Assistant frontier, no pending sampling,
   cancellation, refusal, or unhandled runtime error.
2. **`terminal_output_resolved`** — the case locator resolves one readable,
   run-created, non-source Dataset under the isolated runtime.
3. **`header_promoted`** — final 50 column names equal the source's row-1 header
   values; placeholder `column_N` names are gone.
4. **`report_row_removed`** — the report-filter description is not a data row.
5. **`header_row_removed`** — the 50 header labels are not retained as a data
   row.
6. **`exact_duplicates_removed`** — the terminal dataset contains no exact
   duplicate business rows after the oracle's canonical value normalization.
7. **`expected_shape`** — terminal shape is `485,790 x 50` (486,120 business
   rows minus 330 exact duplicates).
8. **`business_rows_preserved`** — after both source and output trim surrounding
   text whitespace and map only `null`, empty text, and the observed exact `--`
   sentinel to one blank value, their unique full-row fingerprints match. This
   detects arbitrary deletion or corruption without broadly treating values
   such as `N/A`, zero, or `false` as missing.
9. **`source_unchanged`** — the external workbook and registered source retain
   their pre-run hashes/shape/content.
10. **`state_isolated`** — all generated datasets/artifacts/logs remain inside
    the temporary app home; provider configuration and normal runtime are
    unchanged.

The oracle loads data through public Dataset rows and the shared Polars tabular
reader. It does not inspect Tool arguments or invoke cleaning services itself.
It hashes the external workbook before/after and the app-owned imported Parquet
from its first snapshot to the final snapshot. Oracle loading/fingerprinting is
timed separately from Agent execution.

## Non-Gating Quality Observations

V1 may also record remaining blank-string/sentinel counts, parse rates for known
date/numeric columns, nullable counts, and intermediate dataset count. These
help explain outcome quality but are not silently folded into a weighted score.
They can become required checks only after the intended cleaning contract is
made explicit.

## Performance Metrics

Measure the complete user turn without changing production instrumentation:

- attachment-inclusive turn time and separate oracle time; automatic Thread
  title work is absent because the matrix cell pre-creates a non-empty title;
- unique sampling rounds;
- usage-reported successful primary response count (nullable when usage is not
  available; not mislabeled as every HTTP attempt);
- input, cached-input, output, and total tokens;
- canonical messages, broken down into User/Assistant/ToolCall/ToolResult;
- Tool calls, succeeded/failed/cancelled results, and calls by Tool name;
- provider retry count;
- derived/intermediate dataset count;
- terminal output rows/columns.

These values are benchmark output, not V1 assertions. A run with ten failed
Tools may still produce correct data, but the report makes its poor performance
visible rather than misclassifying it as equivalent to a direct run.

## Historical Reference, Not Threshold

The original thread produced a correct terminal shape. Its canonical message
timestamps span approximately:

```text
canonical message span 1,474.1 s
canonical messages          41
assistant messages          14
Tool calls                  13
failed Tool results          3
primary requests            14
primary total tokens   208,013
```

This is not an equivalent end-to-end wall-clock baseline because attachment
import precedes the first canonical User Message. Each configured model receives
the same case. The Kimi K2.6 cell may be compared with this historical reference;
cross-model cells measure adaptation/performance under the same Harness and
case. V1 declares no arbitrary threshold. Repeated runs and statistical
comparison remain deferred.

## Intentionally Not Asserted

- exact Tool names, order, arguments, or index/name references;
- exact Assistant prose or reasoning;
- whether the Agent uses `data.clean`, `data.transform`, or an intermediate
  header-repair dataset;
- a fixed number of messages, Tool calls, requests, failures, tokens, or seconds.

Those facts explain performance; the terminal data oracle determines whether
the task was actually accomplished.
