# Workstream 11: Xenix Table Text Tool Results

Status: locally verified; uncommitted.

## Objective & Hypothesis

Replace Agent-facing tabular tool-result JSON with Xenix Table Text: YAML-style result metadata plus either a Markdown table or a records block.

Hypothesis: for LLM consumption, a bounded table preview is better represented as text with explicit shape, truncation, sampling, schema, null marker, and preview boundary than as JSON object arrays or compact `_schema`/`data` payloads.

Hard boundary: Xenix Table Text must live only inside AgentHarness as the agent-facing tool-result text projection. It is not a service-layer result type, not a tool implementation output format, not a persisted/provider-facing dual payload split, and not a `content_blocks` mechanism.

## Guardrails Touched

- Agent Harness tool-result boundary.
- `data.query` provider-facing result projection.
- Generated dataset tool-result preview projection for `data.integrate`, `data.transform`, `data.clean`, and `data.tokenize`.
- Durable docs/skills that teach the model how to read preprocessing tool results.
- Tests that currently parse provider tool-result JSON or assert compact `_schema`/`data` payloads.

## Current Understanding

- `DataQueryTransformService.query()` returns structured `DataQueryResult` with `rows`, `columns`, `returned_row_count`, `limit`, `truncated`, and validation metadata.
- `AgentToolRegistry._data_query()` currently projects that service result into a JSON payload shaped as:
  - `columns: {"_schema": ..., "data": ...}`
  - `rows: {"_schema": ..., "data": ...}`
  - `returned_row_count`
  - `truncated`
- `ConversationStore._tool_result_to_text()` currently wraps every tool call result as JSON:
  - `tool_name`
  - `status`
  - `result`
  - optional `error_summary`
- Therefore changing only `data.query` payload to a string would still leave the provider seeing a JSON wrapper. Xenix Table Text needs an AgentHarness-owned provider-facing result renderer. For tabular data results, provider replay must return the Xenix Table Text directly, with no surrounding JSON wrapper.
- `data.transform`, `data.clean`, `data.tokenize`, and `data.integrate` all use the generated-dataset registration helper. Its result includes `inspection.preview_columns`, `inspection.preview_rows`, `inspection.columns`, `inspection.row_count`, and `inspection.column_count`; that preview is tabular and should be rendered as Xenix Table Text in the agent-facing result.
- `data.clean.metadata` is a catalog/schema tool, not a tabular result. `data.feature.select` returns role-binding metadata, not tabular result data. They should remain structured.

## Target Format

Normal/narrow table:

```text
shape: 5 rows x 4 columns
returned_rows: 5
total_rows: 1280
truncated: true
sample: head(5)
null: ∅

schema:
  order_id: int64
  customer: string
  amount: decimal
  created_at: timestamp

data:
| # | order_id | customer | amount | created_at |
|---:|---:|---|---:|---|
| 1 | 1001 | Alice | 128.50 | 2026-07-01 10:15:00 |

notes:
  - If any
```

Wide rows or single-row detail:

```text
records:

[1]
user_id = 1001
profile = "enterprise customer, long text..."
last_login = 2026-07-01 09:20:00
lifetime_value = 18920.50
```

## Implementation Shape

- Added AgentHarness-owned formatter/renderer at `src/xenix/services/agent/xenix_table_text.py`.
- Kept `DataQueryResult` structured and added `total_row_count` for exact `total_rows` metadata.
- Keep tool `result_payload` canonical and structured. Do not make tools return Markdown strings and do not add `content_blocks`.
- Updated `ConversationStore._tool_result_to_text()` so recognized tabular payloads render as Xenix Table Text instead of JSON.
- Preserve structured ids and durable facts in result payloads where other Harness logic needs them; do not add `content_blocks`.
- Render errors as simple structured error payloads unless/until a separate error text format is defined.
- For `data.query`, render the query result table itself.
- For generated dataset-producing `data.*` tools, render the generated dataset preview from `inspection` as Xenix Table Text while keeping `dataset_id`, `artifact_id`, summary, row counts, input ids, and selected operation metadata available in the same agent-facing text as scalar metadata.

## Scope Control

Mandatory first implementation scope:

- `data.query`: full bounded query result.
- `data.integrate`: generated dataset preview from `inspection`.
- `data.transform`: generated dataset preview from `inspection`, plus scalar `dataset_id`, `artifact_id`, `row_count`, and summary.
- `data.clean`: generated dataset preview from `inspection` when operations produce a new dataset. No-op cleaning has no tabular result and should not use Xenix Table Text.
- `data.tokenize`: generated dataset preview from `inspection`.

Excluded from this slice:

- tabular previews inside `model.task.query` for apply results if they are currently returned inline;
- any future revived descriptive statistics/profile tool;
- non-tabular metadata catalogs such as `model.metadata` or `data.clean.metadata`;
- role-binding metadata such as `data.feature.select`.

## Resolved Design Points

- Xenix Table Text is only AgentHarness-owned agent-facing tool-result text. It must not become a service-layer return type or tool implementation output shape.
- Provider replay for tabular results returns the Xenix Table Text directly, not a JSON wrapper containing `tool_name`, `status`, and `result`.
- Persisted `result_payload` remains canonical structured data. The renderer projects it to Xenix Table Text on provider replay; this avoids reintroducing default persisted/provider-facing payload bifurcation.
- For `data.query`, `total_rows` means the query result cardinality before the preview limit. For generated dataset previews, `total_rows` means the generated dataset row count from inspection.
- Markdown table vs records block is selected by a simple renderer rule: records are used when there are more than 8 columns, a single row with more than 5 columns, or any rendered cell exceeds 80 characters.

## Verification

- `pdm run pytest tests/test_xenix_table_text.py -q`
  - Result: 4 passed.
- `pdm run pytest tests/test_data_transform.py -q`
  - Result: 14 passed.
- `pdm run pytest tests/test_agent_harness_foundation.py -q`
  - Result: 16 passed.
- `pdm run pytest tests/test_agent_harness_first_slice.py -q`
  - Result: 21 passed.
- `pdm run pytest tests/test_data_cleaning.py tests/test_data_tokenization.py -q`
  - Result: 18 passed.
- `pdm run pytest tests/test_agent_harness_streaming.py tests/test_agent_ai_observability.py -q`
  - Result: 31 passed.
- `pdm run python -m compileall -q src/xenix/services/agent/xenix_table_text.py src/xenix/services/agent/conversation_store.py src/xenix/services/data_transform.py src/xenix/services/agent/tools.py tests/test_xenix_table_text.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py tests/test_data_transform.py`
  - Result: passed.
- `pdm run pytest tests/test_xenix_table_text.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py tests/test_agent_harness_streaming.py tests/test_agent_ai_observability.py -q`
  - Result: 104 passed in 89.02s.
- `git diff --check`
  - Result: passed.
- Final guard after renderer edge-case cleanup:
  - `pdm run pytest tests/test_xenix_table_text.py tests/test_agent_harness_foundation.py -q`
  - Result: 20 passed.
  - `pdm run python -m compileall -q src/xenix/services/agent/xenix_table_text.py src/xenix/services/agent/conversation_store.py`
  - Result: passed.
  - `git diff --check`
  - Result: passed.
