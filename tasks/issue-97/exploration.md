# Issue 97 Data Preprocessing Optimization

## Objective & Hypothesis

- Objective: extract reusable data-preprocessing thinking from the provided scripts, then decide whether Xenix should improve existing `data.clean` operations, metadata guidance, or prompt-engineering behavior.
- Hypothesis: the scripts are mainly valuable as a diagnostic and decision sequence, not as implementation code to copy. Existing Xenix operations may already cover most concrete actions; the gap is likely in operation selection, risk communication, and progressive disclosure in prompts.

## Guardrails Touched

- Typed input: Intent plus Constraint.
  - Intent: improve non-technical data preprocessing workflow.
  - Constraint: do not turn the scripts directly into a monolithic tool unless a durable operation gap is proven.
- Durable owners under review:
  - `src/xenix/services/data_cleaning.py`: deterministic `data.clean` operation execution.
  - `src/xenix/services/agent/tools.py`: LLM-facing tool schemas and metadata guidance.
  - `src/xenix/services/storage/models.py`: default Agent thread system prompt, if prompt guidance is chosen.
  - `docs/20-product-tdd/runtime-boundaries.md` and `docs/30-unit-tdd/agent-harness.md`: only if durable contract changes are made.
- Invariants:
  - Source datasets remain unchanged.
  - `data.clean` remains explicit operation execution, not an opaque all-in-one cleaner.
  - High-risk preprocessing such as column deletion, outlier clipping, encoding, scaling, and target-driven grouping must not happen silently.
  - Progressive disclosure here means a prompt-engineering technique: reveal only the next relevant guidance/detail when context justifies it.

## Current Facts

- Issue #97 says to learn from the provided scripts; it explicitly does not require turning them into a tool.
- Provided scripts:
  - `tasks/issue-97/data-pre-process.py`
  - `tasks/issue-97/common-descriptive-analysis.py`
- Existing `data.clean` operation groups:
  - `duplicates`
  - `missing`
  - `types`
  - `text`
  - `validation`
- Existing `data.clean` behavior is explicit-execution only: when `operations` is absent or empty, it performs no cleaning, creates no derived dataset, and reports no-op.
- Current `data.clean.metadata` and adjacent tool/system text do not appear to instruct the LLM to apply a default cleaning suite whenever data is seen. The current gap is weaker: metadata exposes schemas but gives little operation-selection guidance.
- Existing concrete operations:
  - `duplicate.exact_rows`
  - `duplicate.key_columns`
  - `missing.fill_mean`
  - `missing.fill_median`
  - `missing.fill_mode`
  - `missing.fill_constant`
  - `missing.forward_fill`
  - `missing.drop_rows`
  - `type.convert`
  - `text.trim`
  - `text.lowercase`
  - `text.uppercase`
  - `text.collapse_whitespace`
  - `text.empty_to_null`
  - `text.map_values`
  - `validation.not_null`
  - `validation.non_negative`
  - `validation.min`
  - `validation.max`
  - `validation.allowed_values`
  - `validation.regex`

## Script Ideas Worth Considering

- Start with profiling before mutating data: row/column counts, field types, missingness, duplicate rows, unique value counts.
- Treat preprocessing as decisions over field kinds: numeric, categorical/text, binary, datetime, and possible target fields.
- Date conversion should be cautious: column-name signal, non-numeric guard, conversion success threshold, and reasonable year bounds.
- Descriptive analysis can guide cleaning decisions before execution: numeric distribution, category frequency, binary distribution, datetime ranges, and target-field grouping.
- Multi-output staging is useful conceptually: raw cleaned data, encoded data, and scaled data represent different downstream intents.

## Concrete Operation Gap Candidates

- Column-name normalization is not currently a `data.clean` operation.
  - Candidate operation: `schema.normalize_column_names`.
  - Proposed default strategy: preserve business-readable Unicode letters/numbers, including Chinese; trim leading/trailing whitespace; normalize full-width punctuation and common separators; replace whitespace and punctuation runs with `_`; collapse repeated `_`; trim surrounding `_`; lowercase ASCII letters only; fill empty results as `column_<1-based-index>`; resolve duplicates deterministically with suffixes like `_2`, `_3`; return an old-to-new mapping and collision report.
  - Non-goal: transliterate Chinese to pinyin or infer English business names.
  - Non-goal: accept an explicit old-to-new mapping, because that overlaps with `data.transform`/DuckDB projection aliases.
- Drop high-missing columns is not currently a `data.clean` operation.
- Outlier handling / clipping is not currently a `data.clean` operation.
- One-hot encoding and scaling are not currently `data.clean` operations.
- Dataset profiling / descriptive report is not currently a first-class `data.clean` operation. Existing `data.peek` gives inspection, and `data.query` can do analysis, but there is no dedicated profile/report operation.

## Initial Position

- Prefer improving operation-selection guidance before adding operations.
- `data.clean` may include high-impact operations when they are explicit, parameterized, auditable, and produce a derived dataset. This is compatible with current no-op semantics.
- If adding operations, favor auditable, narrow operations over presets:
  - column-name normalization is desirable, but explicit rename mapping may duplicate what `data.transform` with DuckDB SQL can already do well.
  - high-missing column handling can be an operation if columns or threshold behavior are explicit.
  - outlier clipping can be an operation if method, columns, and bounds/method parameters are explicit.
  - one-hot encoding and scaling can be operations if downstream intent is clear and output lineage is explicit.
  - avoid implicit presets that bundle unrelated changes without exposing parameters.
- Treat "progressive disclosure" as prompt-engineering structure:
  - first expose a short diagnostic checklist;
  - then expose only relevant operation groups;
  - then expose concrete operation schemas through `data.clean.metadata`;
  - then ask for confirmation before destructive or semantic-changing operations.

## Open Questions

- Should Issue 97 produce only prompt/tool-metadata guidance, or should it also add one or two new low-risk operations?
- Is a dedicated `data.profile` / descriptive report tool in scope, or should profiling remain composed from `data.peek` plus `data.query` for now?
- Should column-name normalization be considered cleaning, transform, or merely report-time presentation?

## Verification

- No implementation yet.
- Current task packet created to keep exploration synchronized with discussion.
