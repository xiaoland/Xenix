# Agent Harness Unit TDD

## Purpose

Preserve the local invariants for `src/xenix/services/agent/`. Agent Harness is the service that turns Chatbot-first user interaction into persisted conversation records, LLM provider calls, tool execution, and artifact-producing service work.

## Unit Boundary

Agent Harness owns:

- Thread creation, rename, delete, listing, and snapshot loading
- Thread system prompt projection into provider messages
- Turn start, end, cancellation, and step-budget pause/resume
- Message persistence for user, assistant, system, tool-call, and tool-call-result records
- Provider boundary calls through a canonical provider contract
- Static tool registry exposure and tool execution
- Agent run recording and cancellation state

Storage owns persistence mechanics. Data, artifact, project, and ML services own domain operations. Qt UI owns rendering and user input collection.

## Records

- `Thread`: persisted conversation workspace with title and system prompt.
- `Turn`: ordered group of messages started by one user Message.
- `Message`: chronological content-block record with Harness kind and UI author.
- `ToolCall`: execution record linking a tool-call Message to its result Message.
- `AgentRun`: one provider/tool orchestration attempt for a turn.

## Provider Loop

One user submission follows this service flow:

```text
submit_user_turn
  -> create thread when needed
  -> start turn and persist user Message
  -> start AgentRun
  -> build provider messages from ThreadSnapshot
  -> call provider complete/stream
  -> persist assistant Message when provider returns assistant content
  -> end turn when provider returns zero tool calls
  -> for each tool call:
       persist tool-call Message and ToolCall row
       execute registered tool with ToolExecutionContext
       persist tool-result Message and ToolCall result status
       continue provider loop
```

A provider response with empty assistant content and zero tool calls ends the turn. A turn-end tool is outside the current contract.

## System Prompt

The system prompt is stored on `AgentThreadRow.system_prompt`.

`ThreadSnapshot.provider_messages()` prepends it as the first provider message with role `system`. It is metadata for provider calls and hidden from the Chatbot timeline.

## Step Budget And Cancellation

The initial step budget is enforced by Agent Harness. When the granted step budget is exhausted, Agent Harness pauses the run with `AgentRunStatus.AWAITING_CONFIRMATION` and emits a confirmation event. The user may grant more steps up to the configured total limit or stop the run.

Cancellation is user-driven from the Chatbot stop control. A cancel request stops provider/tool progression, attempts to cancel active ML tasks when available, records a system cancellation Message, cancels the Turn, and marks the AgentRun cancelled.

## Tool Registry

The first-slice tool registry is static for the current application capability set:

- `data.peek`
- `data.integrate`
- `data.clean`
- `data.feature.select`
- `model.metadata`
- `model.train`
- `model.hyper_train`
- `model.inference`

`model.metadata` exposes canonical model keys, model capabilities, and optional parameter schemas. `model.train` and `model.hyper_train` keep schemas lightweight and validate model keys through the model catalog at execution time.

## Provider Boundary

The provider contract is:

```text
complete(messages: list[ProviderMessage], tools: list[AgentToolSpec]) -> ProviderResponse
stream(messages: list[ProviderMessage], tools: list[AgentToolSpec]) -> ProviderStreamEvent*
```

`ProviderResponse` carries assistant content blocks, normalized tool calls, and raw provider payload. Provider adapters own OpenAI-compatible request assembly, streaming accumulation, provider tool-name mapping, and response parsing.

CopilotKit AIMock connects through the same OpenAI-compatible HTTP boundary during development testing.

## Test Obligations

Contract tests should cover:

- thread creation with default system prompt
- provider message projection with system prompt first
- user turn persistence and turn ending on zero tool calls
- empty-text zero-tool provider response ending a turn
- assistant streaming delta rendering events and final persisted assistant Message
- tool-call and tool-result persistence
- step-budget pause, resume, stop, and maximum total limit
- cancellation during provider and tool execution
- model metadata schema and model key normalization
- artifact link production for dataset, training, and prediction outputs
