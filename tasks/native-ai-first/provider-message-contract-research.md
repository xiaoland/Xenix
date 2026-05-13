# Provider Message Contract Research

## Status

- Mode: Explore.
- Purpose: constrain Xenix Agent Harness message design from provider API contracts.
- Sources checked on 2026-05-11.

## Design Pressure

Xenix needs one persisted `Message` model that supports:

- UI projection: whether the visible message is from user or assistant, and what content it contains.
- Harness projection: provider-facing role or item type such as `system`, `user`, `assistant`, tool call, and tool result.
- LLM providers: OpenAI Responses, OpenAI Chat Completions, legacy OpenAI Completions, Anthropic Messages, and Google Gemini Generative API.

The design should keep one UI Message corresponding to one Harness Message whenever that message is visible. Hidden system/developer messages can still be stored as Messages with `visibility = hidden`.

## OpenAI Responses API

Relevant official facts:

- Responses supports stateful model responses, text and image inputs, tools, function calling, and built-in tools. Source: https://platform.openai.com/docs/api-reference/responses
- OpenAI describes function calling as a multi-step conversation where the app sends tool definitions, receives tool calls, executes app-side code, sends tool outputs back, then receives final model output. Source: https://platform.openai.com/docs/guides/function-calling
- Responses output items can include `function_call` with `id`, `call_id`, `name`, and JSON-encoded `arguments`. Tool results are appended as input items with `type = function_call_output`, `call_id`, and `output`. Source: https://platform.openai.com/docs/guides/function-calling

Implication for Xenix:

- Harness Message needs an internal content block for provider output item `function_call`.
- Tool result needs to retain provider call correlation id, normalized tool name, structured result payload, and provider-specific serialization.
- OpenAI Responses maps cleanly to a block-oriented message model because model output is an array of typed items.

## OpenAI Chat Completions API

Relevant official facts:

- Chat Completions generates a response from a list of messages comprising a conversation. Source: https://platform.openai.com/docs/api-reference/chat
- Message roles include `developer`, `system`, `user`, `assistant`, and `tool`; older `function` role exists for deprecated function calling compatibility. Source: https://platform.openai.com/docs/api-reference/chat
- Assistant messages can contain `tool_calls`; `function_call` is deprecated and replaced by `tool_calls`. Tool messages respond to a tool call via `tool_call_id`. Source: https://platform.openai.com/docs/api-reference/chat
- OpenAI recommends Responses for new projects in its current Chat Completions docs. Source: https://platform.openai.com/docs/api-reference/chat

Implication for Xenix:

- Harness Message role enum should include at least `developer`, `system`, `user`, `assistant`, `tool`.
- Tool calls can be assistant-message content blocks in Xenix even though Chat Completions exposes them as assistant message fields.
- Tool results can be stored as Messages with harness role `tool` and content blocks carrying the structured result.

## OpenAI Legacy Completions API

Relevant official facts:

- OpenAI marks Completions API as legacy.
- The endpoint uses a freeform `prompt` string, not a list of messages. Source: https://platform.openai.com/docs/guides/completions

Implication for Xenix:

- Legacy Completions should be treated as a low-priority adapter requiring prompt flattening from stored Messages.
- It should not drive the canonical Message model because it lacks native role and tool-call structure.

## Anthropic Messages API

Relevant official facts:

- The Messages API accepts `messages` with roles such as `user` and `assistant`; the response is an assistant `message` with a `content` array of typed content blocks. Source: https://docs.anthropic.com/en/api/messages-examples
- Anthropic Messages is stateless, so the application sends full conversational history each request. Source: https://docs.anthropic.com/en/api/messages-examples
- For tool use, Anthropic integrates tools directly into user and assistant message structure. Assistant content can include `tool_use`; user content can include `tool_result`. Source: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use
- Anthropic tool definitions include `name`, `description`, and `input_schema`. Source: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use

Implication for Xenix:

- A Message with role `assistant` can contain both text blocks and tool-call blocks.
- A Message with role `user` can contain tool-result blocks that represent app-side tool execution output.
- Xenix content blocks should support mixed content in one message.

## Google Gemini Generative API

Relevant official facts:

- Gemini function calling connects models to external tools and APIs; the model returns a `functionCall` object and the app returns a `functionResponse`. Source: https://ai.google.dev/gemini-api/docs/function-calling
- Gemini examples keep conversation as `contents`, where function call content from the model is appended, then a `Content(role="user", parts=[function_response_part])` is appended for the function response. Source: https://ai.google.dev/gemini-api/docs/function-calling
- Gemini function calling modes include `AUTO`, `ANY`, and `NONE`. Source: https://ai.google.dev/gemini-api/docs/function-calling
- Gemini 3 can include multimodal content in function response parts, including images and documents, under documented MIME type constraints. Source: https://ai.google.dev/gemini-api/docs/function-calling

Implication for Xenix:

- Xenix content blocks should map to Gemini `parts`.
- Tool calls map to `functionCall` parts.
- Tool results map to `functionResponse` parts, usually on a provider role `user` content item.
- Multimodal tool results support the need for artifact-bearing message content.

## Canonical Xenix Message Shape

Candidate canonical model:

```text
ConversationThread
  id
  title
  created_at
  updated_at

Message
  id
  thread_id
  sequence_index
  harness_kind:
    developer_instruction
    system_instruction
    user_message
    assistant_message
    tool_call
    tool_call_result
  provider_role:
    developer | system | user | assistant | tool | none
  ui_author:
    user | assistant | hidden
  visibility:
    visible | hidden
  content_blocks:
    - text
    - file_attachment
    - tool_call
    - tool_result
    - table
    - chart
    - artifact_ref
    - turn_end
    - cancellation
    - error
  provider_refs:
    response_id
    output_item_id
    call_id
    tool_call_id
    provider_message_id
  status
  created_at
```

## Invariants

- `Message` is the durable unit.
- Visible UI messages map 1:1 to Harness Messages.
- `content_blocks` are not standalone user-visible messages.
- System and developer instructions are persisted as hidden Messages.
- LLM providers translate canonical Messages into provider-specific request shapes.
- LLM providers translate provider responses back into canonical Messages before UI rendering.
- Tool calls and tool results are Agent Harness messages, and Xenix service tools live inside Agent Harness.
- A valid `turn_end` tool result becomes a durable tool-call-result Message whose `turn_end` content block lets ChatBox render the turn divider.

## Open Questions

- Whether `tool_call` and `tool_call_result` should be separate `harness_kind` values or assistant/user messages with corresponding content blocks.
- Whether a visible assistant message with text plus a tool call should persist as one Message, matching Anthropic, or split into two Messages for easier UI progress rendering.
- Whether provider roles should be stored durably or derived by adapter from `harness_kind`.
