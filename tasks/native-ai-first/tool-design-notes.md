# Tool Design Notes

## Status

- Mode: Explore.
- Scope: first-pass tool contract for Agent Harness discussion.
- Current LLM-facing tool inventory: `tasks/native-ai-first/llm-tool-inventory.md`.

## Tool Position

Tools are part of Agent Harness.

```text
Agent Harness
  -> StaticToolRegistry
  -> ToolExecutor
  -> CancellationController
  -> ToolArgumentValidator
  -> Xenix data/model tool handlers
```

The LLM provider sees tool definitions. The ToolExecutor sees executable Python handlers. The UI sees messages and artifacts produced from tool results.

Updated direction: start with a minimal bounded data/model tool registry. Generic LLM-authored script execution is deferred.

## Static Tool Definition

Candidate shape:

```text
AgentToolDefinition
  name
  title
  description
  input_model
  output_model
  input_json_schema
  output_json_schema
  side_effect_level
  idempotency_strategy
  artifact_output_contract
  render_hint
  handler
```

Notes:

- `input_model` and `output_model` should be Pydantic/SQLModel-compatible.
- JSON schema is generated from typed models.
- `handler` is Python code wired to Xenix services through dependency injection.
- `render_hint` helps the UI choose table, chart, artifact card, progress, or plain text rendering.

## Tool Call Contract

```text
ToolCallRequest
  id
  thread_id
  tool_name
  arguments
  requested_by_message_id

ToolCallResult
  id
  tool_call_id
  tool_name
  status: succeeded | failed | cancelled
  content_blocks
  artifact_refs
  usage
  error_summary
```

## Cancellation

First-slice user control is cancellation. While provider inference or a tool call is running, the Chatbot send button becomes a stop button.

Candidate side-effect labels help tests and logs:

```text
read_only
agent_record_write
dataset_artifact_write
ml_task_start
prediction_artifact_write
```

First-slice default:

- Dataset inspection: `read_only`
- Data integration and cleaning: `dataset_artifact_write` plus tool-result records.
- Feature selection: `agent_record_write`.
- Training start: `ml_task_start`
- Prediction start: `prediction_artifact_write`

## Idempotency

Tools that write local state or start ML tasks need an idempotency key.

Candidate key sources:

- thread id
- tool call id
- dataset file hash or canonical path
- input dataset id or artifact id
- model/training configuration hash

This borrows from LangGraph's durable execution warning: side effects must be replay-safe or recorded.

## First-Slice Tools

The current static registry is maintained in `tasks/native-ai-first/llm-tool-inventory.md`.

Provider-facing tool names should use snake_case. Namespaced labels such as `data.peek` can remain documentation aliases.

## Output Presentation

Tools can return markdown with artifact links. Chatbot previews linked images, tables, CSV/XLSX outputs, reports, and charts.

## Open Questions

- Whether tools should return UI-ready `content_blocks` directly or return domain outputs that a renderer maps into content blocks.
- Exact parameter schema for each data/model tool.
- Whether tool outputs should always include markdown summaries plus artifact links.
- Whether generic script runtime remains deferred until after the first AI-first acceptance.
