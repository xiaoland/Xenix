# Naming Assessment — Public LLM Boundary

## Recommendation

`LLMChatService` is more specific than `LLMService`, but it is not the recommended final name. Use **`LLMConversationService`** for the public deep-module facade, subject to the implementation slice's Impact Handshake.

Continue to use **LLM Service** as the neutral owner label in this task packet until Sir explicitly settles the code name. No product rename is authorized by this assessment.

## Why `Chat` Is Risky Here

The target object owns more than a chat-model call:

- canonical Thread and typed Message state;
- pending/final LLM Message lifecycle and conversation-frontier validation;
- conversation persistence and context compilation;
- provider selection, transport, retry, and normalization;
- AgentTool protocol, registry, exposed scope, invocation, and call/result commits.

Across the compared ecosystems, `ChatModel`, `ChatCompletionService`, and `useChat` usually identify one of two narrower layers:

- a model adapter that accepts and returns Messages; or
- a UI/chat interaction helper.

In Xenix, `ChatbotEvent` already names the UI projection, while the PRD consistently calls the primary work surface a **Conversation**. Naming the deep state owner `LLMChatService` would therefore make three meanings compete: provider Chat Completions, Chatbot UI, and canonical Conversation.

That ambiguity is structural, not cosmetic. A future maintainer who reads `LLMChatService` as a model wrapper is more likely to move persistence or tool authority back into Harness, recreate the boundary this task is removing, or expose low-level `complete/stream` methods instead of the intended deep operations.

## Candidate Comparison

| Name | Strength | Main problem | Judgment |
| --- | --- | --- | --- |
| `LLMService` | Short, stable, and broad enough to cover all owned capabilities | Says almost nothing about its authority; the current class is already understood as a provider facade | Credible fallback, but its ambiguity remains |
| `LLMChatService` | Signals message-oriented LLM use | Collides with provider ChatModel and Chatbot UI meanings; under-describes persistence and tool authority | Viable but not recommended |
| `LLMConversationService` | Matches the product term and canonical Thread/Message ownership; still distinguishes the LLM-backed boundary | Long, and requires internal decomposition to avoid a god class | Recommended public facade |
| `LLMInteractionService` | Covers messages and tools | `Interaction` is not established product vocabulary and is less concrete than Conversation | Possible, weakly anchored alternative |
| `LLMConversationRuntime` | Accurately suggests stateful execution | `Runtime` implies ownership of the complete agent loop and blurs the Harness boundary | Do not use for the public service |

## Intended Name Topology

```text
AgentHarnessService
        |
        v
LLMConversationService                 public deep-module facade
├─ ConversationRepository port         canonical Thread / typed Message
├─ ContextCompiler                     immutable state -> provider input
├─ ModelGateway                        provider transport / normalization
└─ AgentToolRegistry                   LLM-owned protocol / scope / dispatch
```

`Chat` remains appropriate where it has a narrow meaning:

- a provider-specific `ChatModel` / Chat Completions adapter where that protocol is genuinely used;
- Chatbot UI and `ChatbotEvent` projection.

`Conversation` names the persisted product interaction. `Harness` names policy/orchestration. This makes the dependency graph legible from names alone.

## Rename Constraints

- Do not perform a standalone global rename before the ownership move. Renaming the current provider/settings wrapper would claim a boundary it does not yet implement.
- Apply the new name when the Thread/Message port and AgentTool registry become part of the public facade.
- Keep provider-level completion operations internal or behind a narrow gateway; the facade should expose deep commands such as `append_user_message`, `sample`, and `invoke_tool`.
- A temporary import alias is acceptable only for a bounded migration. Do not preserve both names indefinitely.
- The public facade may delegate to multiple internal modules. `LLMConversationService` must not become one monolithic `service.py` merely because it has one public owner.

## Strong Alternative — Keep `LLMService`

An adversarial naming review preferred retaining `LLMService`: it covers Conversation, provider, and tools without implying UI Chat, remote provider conversations, or ownership of the whole agent runtime. That is a credible second choice if its public contract is made explicit and the low-level `complete/stream` entry points are removed from normal callers.

The reason this packet still recommends `LLMConversationService` is that the current `LLMService` is already a provider/settings facade. Reusing the same broad name for a materially different state owner would hide the semantic migration. In the proposed public model, Conversation is the durable product abstraction and provider/tool mechanics are subordinate capabilities. If that premise is rejected and Thread/Message are intentionally exposed without a public Conversation abstraction, retaining `LLMService` is equally credible.

This is a maintainability judgment, not an invariant. Retaining `LLMService` would not invalidate the selected topology. Renaming it to `LLMChatService` would make the topology harder to infer.

## Decision Test

The name is correct if a caller can infer all three facts without reading implementation:

1. it owns a persisted LLM-backed Conversation rather than a single model request;
2. it is below Agent Harness policy rather than replacing Harness;
3. provider ChatModel mechanics and Chatbot UI remain subordinate projections/adapters.

`LLMConversationService` passes this test more clearly than `LLMChatService`.
