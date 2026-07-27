# Ecosystem Comparison — Conversation, Tools, Runs, and Persistence

## Method and Limits

This comparison was checked against official documentation and official source repositories on 2026-07-14. It uses external libraries as design evidence, not as architectural authority: they optimize for different deployment models, persistence guarantees, and extension surfaces than Xenix.

Facts reported by the libraries are separated below from the conclusions drawn for Xenix. Live documentation and repository `main` branches may move; implementation must not depend on an undocumented version-specific detail.

## Factual Comparison

| Ecosystem | Conversation/application state | Tool definition and execution | Persistence and recovery | Run / step / turn vocabulary |
| --- | --- | --- | --- | --- |
| [Vercel AI SDK](https://ai-sdk.dev/docs/reference/ai-sdk-core/ui-message) | `UIMessage` is described as the application's source of truth. It contains typed parts, metadata, and tool states; `convertToModelMessages` derives the model-facing representation. | A `Tool` carries schema and an optional `execute`; an application passes a ToolSet into `generateText`, `streamText`, or `ToolLoopAgent`. The agent/runtime executes tools when `execute` is present and reports unknown or invalid calls explicitly. | The chatbot guide recommends validating and storing `UIMessage`; application callbacks perform persistence. The basic persistence contract is not a durable side-effect transaction protocol. | Multi-call execution is described as steps controlled by `stopWhen`/`prepareStep`; the reviewed public state API does not introduce a persistent Turn entity. |
| [LangChain / LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence) | LangChain Messages are model-context units. LangGraph's authority is the graph's arbitrary State schema; `messages` is a common channel rather than the whole state. `AIMessage.tool_calls` and `ToolMessage` represent calls and results. | `ToolNode` owns an agent-local name-to-tool map and executes calls; `create_agent` builds the model-to-tools loop. Dynamic tool exposure and executable lookup must agree. | A checkpointer saves graph-state checkpoints by `thread_id` at graph steps and retains pending writes for recovery. Deployed Agent Server separates Threads from Runs. | Thread is persistent state across Runs; graph execution uses steps/super-steps. Turn is not a native LangGraph state entity. |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/running_agents/) | Sessions retain item history across Runs. `RunResult.new_items` contains typed message, tool-call, tool-output, handoff, and approval items; `RunState` represents an interrupted resumable execution. | Tools are attached to an Agent and the Runner performs the loop, local dispatch, result append, approval, error, and concurrency handling. | Built-in Session implementations include SQLite and other stores. Separate durable-execution integrations are offered for long-running crash recovery. | Documentation uses "logical turn" for one outer chat interaction, but `max_turns` counts inner AI invocations. The same word therefore spans two granularities and is not a safe storage concept. |
| [PydanticAI](https://pydantic.dev/docs/ai/core-concepts/message-history/) | Provider-neutral `ModelRequest`/`ModelResponse` values contain typed `ToolCallPart` and `ToolReturnPart`; tool parts remain in reusable message history. A Conversation may contain multiple Runs, and a Run may contain many messages. | An Agent owns functions/toolsets and its graph executes the model/tool loop. Toolsets can be composed and filtered dynamically. | Messages can be serialized by the application. [Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/) separately demonstrates provider-valid snapshots and an explicit `unknown_after_crash` tool-effect state. | Conversation, Run, and graph step are distinct identities; the reviewed API does not add a separate persistent Turn object. |
| [Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/function-calling/function-invocation) | `AgentThread` / `ChatHistory` holds `ChatMessageContent`; `FunctionCallContent` and `FunctionResultContent` preserve the call/result exchange. | Kernel plugins/functions form the registry. Auto mode owns the whole loop; manual mode lets a caller decide timing/order while dispatch still resolves through the Kernel. Function-choice filters control the advertised subset. | Thread implementations can be continued or rehydrated, with provider-specific variants. The public ChatCompletionAgent surface does not itself define Xenix's local SQLite transaction contract. | Invocation continues an AgentThread; no separate persistent Turn abstraction is required. |

Supporting official references:

- Vercel: [UIMessage](https://ai-sdk.dev/docs/reference/ai-sdk-core/ui-message), [message persistence](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-message-persistence), [tools and tool calling](https://ai-sdk.dev/docs/ai-sdk-core/tools-and-tool-calling), and [ToolLoopAgent](https://ai-sdk.dev/docs/reference/ai-sdk-core/tool-loop-agent).
- LangChain/LangGraph: [Messages](https://docs.langchain.com/oss/python/langchain/messages), [Tools / ToolNode](https://docs.langchain.com/oss/python/langchain/tools), [short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence), and [Threads and Runs](https://docs.langchain.com/langsmith/use-threads).
- OpenAI Agents SDK: [running agents](https://openai.github.io/openai-agents-python/running_agents/), [tools](https://openai.github.io/openai-agents-python/tools/), [sessions](https://openai.github.io/openai-agents-python/sessions/), and [results](https://openai.github.io/openai-agents-python/results/).
- PydanticAI: [Agents](https://pydantic.dev/docs/ai/core-concepts/agent/), [message history](https://pydantic.dev/docs/ai/core-concepts/message-history/), [toolsets](https://pydantic.dev/docs/ai/tools-toolsets/toolsets/), [typed Messages](https://pydantic.dev/docs/ai/api/pydantic-ai/messages/), and [Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/).
- Semantic Kernel: [Agent API](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-api), [function choice](https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/function-calling/function-choice-behaviors), and [auto/manual invocation](https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/function-calling/function-invocation).

## Recurring Topologies

The ecosystems expose three recurring shapes:

```text
Narrow model layer:
orchestrator -> ChatModel / LanguageModel -> provider adapter

Integrated agent runtime:
Agent / Runner -> model + local ToolSet + complete loop + state hooks

Kernel plus manual orchestration:
caller policy -> Kernel operation -> Kernel registry -> injected function
                              \-> chat/model adapter
```

Xenix deliberately uses the third shape with stronger canonical persistence:

```text
AgentHarnessService (policy and sequence)
        |
        v
LLM Conversation Kernel (state writer, provider operations, registry/dispatch)
        |                                      |
        v                                      v
ModelGateway / provider adapter           injected AgentTool -> domain service
```

The majority pattern of attaching both tools and the complete loop to one Agent does not refute the Xenix split. It does establish a condition: the target LLM boundary cannot remain a narrow chat-model wrapper. It must be a deep conversation/kernel boundary, and Harness must not duplicate its registry, lookup, dispatch, or persistence.

## What the Evidence Supports

### 1. Tool results belong in typed conversation history

All five ecosystems retain a typed tool result in conversation/application state: a Vercel tool part, LangChain `ToolMessage`, OpenAI tool-output item, Pydantic `ToolReturnPart`, or Semantic Kernel `FunctionResultContent`. This strongly supports the selected `ToolResultMessage` as Xenix's sole bounded canonical result.

Nothing in those shapes makes a second canonical result payload necessary. Xenix may derive provider wire and Chatbot values, but `AgentToolCallRow.result_payload`, a UI event, or provider-formatted payload must not become a competing authority.

### 2. Canonical application state must be distinct from provider input

Vercel makes this especially explicit with `UIMessage -> ModelMessage -> provider prompt`. LangGraph makes the broader point that model Messages need not contain all execution state. Xenix therefore needs both:

- canonical typed Message atoms for conversation truth; and
- a pure Context Compiler that derives provider input without mutating or replacing those atoms.

Trimming, summarizing, provider normalization, or applying a history processor must operate on a derived view. If canonical compaction is ever required, it needs an explicit state transition and retention contract rather than an in-place provider optimization.

### 3. Run is a capability choice, not a mandatory conversation entity

LangGraph Agent Server, OpenAI Agents, and PydanticAI distinguish conversation/thread, execution/run, and inner model/tool iterations because they offer resumable graph execution, approvals, checkpoints, or durable continuation. That proves Run can pay for those capabilities; it does not make persistent Run part of every conversation ontology.

Xenix now explicitly declines automatic continuation of an active Harness execution after process exit. Persisting Run would therefore retain the grouping cost without the recovery benefit. Xenix should use:

- Thread/Conversation for durable dialogue;
- a pending/final LLM Message for one model response identity;
- in-memory Harness state for step budget, cancellation, model lock, and completion policy;
- turn/run only as optional prose or observability vocabulary, not storage authorities.

### 4. Advertised scope and invocation authority must not diverge

Vercel's active tools, LangChain dynamic tools, Pydantic toolsets, and Semantic Kernel function filters all distinguish the available subset from the full registered surface. Xenix's immutable `ToolScope` is therefore well founded, but it needs two checks:

1. LLM Service resolves the advertised definitions from canonical registered tool IDs when compiling a provider request.
2. Live tool progress resolves staged call/tool identity through the LLM-owned registry and rejects missing or changed registrations before dispatch. It is not a post-restart replay command.

Harness may choose eligible IDs as policy. It never supplies a handler, tool definition, name/arguments copied from the provider, or a tool outcome.

### 5. Crash ambiguity is a product trade, not telemetry

PydanticAI Step Persistence calls a started-but-not-terminal tool effect `unknown_after_crash`; LangGraph persists step state and pending writes. Those designs are necessary for automatic durable continuation.

Xenix chooses a smaller and intentionally lossy contract: a tool-calling response remains provisional until its terminal Tool Results can commit with it. After process loss, the provisional sampling Message is discarded, no Result is manufactured, and no old Tool Call is resumed. A later explicit provider sample starts from the preceding finalized Client frontier and may issue a new call for similar work. This requires no Tool Call idempotency contract, but accepts orphaned domain effects and possible repeated semantic work. If automatic continuation or non-lossy recovery is added later, durable effect state or domain idempotence may again be necessary.

### 6. Provider message envelopes are not a canonical ontology

Official provider contracts themselves demonstrate the variation. OpenAI Chat Completions places `tool_calls` on an assistant message, while the Responses API returns separate `function_call` output items and accepts separate function-call outputs. Anthropic represents text and `tool_use` as ordered content blocks in an assistant response. Gemini can express function calls/results as separate interaction steps. See [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling), [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools), and [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling).

Vercel, LangChain, PydanticAI, and Semantic Kernel choose their own envelope/part models for their own APIs. That is useful evidence that typed call/result history is normal; it is not evidence that Xenix's canonical Thread must copy any provider's response container.

The corrected Xenix protocol therefore normalizes one provider response into an ordered sequence of independent `AssistantMessage` and `ToolCallMessage` atoms. `ToolResultMessage` directly references its Call. A Chat Completions-style adapter can synthesize a combined assistant envelope; a Responses- or Gemini-style adapter can project separate items; an Anthropic-style adapter can project ordered blocks. Provider grouping is a pure adapter concern, not a persistent `LLMMessage.parts`, parent-Assistant, or response-group relation.

### 7. Streaming deltas are not finalized conversation truth

The compared persistence examples generally add a complete message/result after stream completion, while deltas drive live UI/event surfaces. Xenix should likewise finalize a provider-valid final Message sequence and treat raw text/tool-input deltas as ephemeral projections or observability data.

This does not settle when the UI may display text or how retry-safe visible streaming should behave. It only prevents an incomplete delta stream from silently becoming a finalized canonical Message.

### 8. History transport is adapter capability, not conversation authority

OpenAI's official conversation-state contract sharpens Sir's adapter point:

- Chat Completions requires a client-managed provider-valid history projection; context windowing/compaction may reduce a derived view but cannot damage canonical history or tool call/result validity.
- Responses can send only the new frontier when it has a provider-resolvable stored `previous_response_id`. A same-process connection cache is a live optimization, not restart authority.
- Stateless operation, cursor loss, and `store:false`/ZDR after process loss require replaying locally retained required input/output. For reasoning models this can include every output item, assistant phase, tool item, and lossless `reasoning.encrypted_content`; a reasoning summary is not a substitute.
- Instructions should be sent explicitly rather than assumed to carry through a provider-side chain.

Therefore Xenix always owns the finalized local Message list. A response-ID cursor is committed with its finalized local LLM Message. Required opaque continuation fields are allowlisted adapter metadata on that Message and must be retained losslessly when a capability depends on them; they are not generally rebuildable. If they are missing, the adapter may fall back only when provider-valid replay is possible, otherwise it must fail with an explicit capability error.

A shared remote Conversation automatically appends response input/output, so a crash before the local commit can create split-brain; Xenix should not enable that mode without an explicit reconciliation contract. This consistency judgment is an inference from the official API behavior. `conversation` and `previous_response_id` also cannot be supplied together. See [OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state), [Responses create](https://developers.openai.com/api/reference/resources/responses/methods/create), and [Reasoning models](https://developers.openai.com/api/docs/guides/reasoning).

## What Xenix Should Not Copy

- Do not store a mutable UI object as the database schema merely because Vercel calls it an application source of truth. Chatbot events remain projections from Xenix domain Messages.
- Do not checkpoint arbitrary graph state or raw tool artifacts. Persist bounded conversation facts only; Artifact provenance stays in the Artifact domain rather than becoming a Message relationship.
- Do not let a context-window optimizer delete, replace, or summarize canonical history implicitly.
- Do not use provider `tool_call_id` as a domain idempotency identity. It is adapter correlation data. `ToolResultMessage.tool_call_message_id` enforces final call/result pairing, but grants no replay or recovery authority.
- Do not copy a persistent Run/checkpoint merely because a durable agent framework offers one. Its complexity is justified only if Xenix adopts durable continuation.
- Do not move the full agent loop into the LLM boundary merely because integrated SDKs do. That would erase the selected Harness policy boundary.
- Do not persist raw streaming deltas as finalized Messages or reconstruct abandoned Harness execution from UI stream state.

## Result for the Current Decision

The ecosystem review does not require a topology reversal. Combined with the no-auto-continuation product constraint, it strengthens the corrected two-service design while making five conditions explicit:

1. LLM Service is a Conversation Kernel, not a ChatModel wrapper.
2. Context compilation is a non-mutating projection.
3. Provider responses normalize into an ordered independent Message sequence; adapter containers are projections, while Tool Calls retain independent Message identities.
4. Provider history replay versus cursor continuation is an adapter decision, while local Messages remain authoritative.
5. Turn and persistent Run can both be removed only because Xenix accepts no cross-process execution continuation: it discards incomplete tool exchanges and permits explicit re-sampling to do new work.
