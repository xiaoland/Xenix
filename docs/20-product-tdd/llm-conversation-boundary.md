# LLM Conversation Boundary

## Admission

Chatbot UI, Agent Harness, `LLMConversationService`, provider adapters, and
AgentTool implementations share one authority and ordering boundary. Losing it
can recreate a second conversation writer, make a UI event authoritative, or
couple the LLM boundary back to Harness/domain code.

This contract owns cross-unit topology and sequence. Source, schemas, and tests
own exact records, payload fields, methods, limits, and adapter mechanics.

## Dependency and Authority Topology

```mermaid
flowchart LR
    UI["Chatbot UI"]
    H["Agent Harness<br/>live coordination and projection"]
    C["LLMConversationService<br/>canonical state and LLM protocol"]
    DS["DatasetService<br/>materialization and source provenance"]
    DB[("Conversation SQLite")]
    P["Provider adapter"]
    L["External LLM"]
    I["Concrete AgentTool implementations"]
    D["Dataset / ML / Artifact domains"]

    UI --> H
    H --> C
    H --> DS
    C --> DB
    C --> P
    P --> L
    I -. "implements LLM-owned AgentTool interface;<br/>registered by composition" .-> C
    I --> D
```

The dotted line is dependency inversion, not a reverse LLM dependency: concrete
Tool implementations depend on the interface defined by the LLM boundary and
are registered at composition. `LLMConversationService` invokes registered
Tools through that interface; it does not import Harness or concrete/domain
Tool modules.

## Authority Rules

- `LLMConversationService` is the sole canonical Thread/Message writer. It
  owns the provider-facing transcript, pending/final Message lifecycle, and
  the `AgentTool` protocol, registry, scope validation, and invocation.
- Agent Harness owns transient application coordination only: source import,
  the decision to sample or cancel, and snapshot-to-Chatbot-event projection.
  It does not directly write or mutate canonical Messages, dispatch a Tool, or
  serialize provider history.
- Chatbot UI submits intent and renders Chatbot Events. It neither accesses a
  conversation repository nor infers protocol state from storage rows or raw
  Tool payloads.
- Final Messages are durable. A pending sampling Message is the sole
  provisional canonical state. There is no persistent `Turn`, `Run`,
  `ConversationStore`, execution ledger, or automatic cross-process recovery.
- Finalization atomically commits independent ToolCall/ToolResult Messages and
  an Assistant Message when the provider emitted one. A ToolResult directly
  identifies its ToolCall; neither Artifact nor observability becomes
  conversation provenance.
- DatasetService owns materialized data and original-source provenance. After a
  snapshot is loaded, Harness may derive an ephemeral source attachment for
  Chatbot display. That presentation is not canonical content, provider input,
  or a recovery record; a missing original source is a soft display result.
- Thinking, activity, connection, and usage are Chatbot Events. Observability
  may retain bounded diagnostics/usage but never restores, repairs, or replays
  conversation or Tool state.

## Live Submission and Sampling Sequence

```mermaid
sequenceDiagram
    actor U as "User"
    participant UI as "Chatbot UI"
    participant H as "Agent Harness"
    participant DS as "DatasetService"
    participant C as "LLMConversationService"
    participant P as "Provider adapter / LLM"
    participant T as "LLM-owned Tool registry"
    participant I as "Registered Tool implementation"

    U->>UI: "submit text and optional source files"
    UI->>H: "submission intent"
    opt "source attachment"
        H->>DS: "materialize Dataset and record provenance"
        DS-->>H: "bounded Dataset summary"
    end
    H->>C: "append immutable UserMessage"
    C-->>H: "canonical snapshot"

    loop "while Harness elects to sample the final frontier"
        H->>C: "begin sampling"
        C-->>H: "pending Message identity"
        H-->>UI: "Thinking Chatbot Event"
        C->>P: "serialize history and sample"
        P-->>C: "normalized Assistant / ToolCall candidate"
        alt "Tool Calls proposed"
            C->>T: "validate and invoke registered Tool"
            T->>I: "execute through LLM-owned interface"
            I-->>T: "bounded outcome"
            T-->>C: "terminal ToolResult"
            C->>C: "atomically finalize ToolCall/ToolResult and Assistant when present"
        else "terminal Assistant"
            C->>C: "finalize Assistant"
        end
        C-->>H: "final snapshot"
        H-->>UI: "project snapshot to Chatbot Events"
    end
```

The pending Message gives Harness a stable identity for Thinking and
cancellation without making either a canonical conversation concept. When a
ToolResult leaves the final frontier requiring another LLM sample, Harness
chooses the next loop iteration; Tool invocation itself remains inside the LLM
boundary.

## History Reopen and Source-Presentation Sequence

```mermaid
sequenceDiagram
    actor U as "User"
    participant UI as "Chatbot UI"
    participant H as "Agent Harness"
    participant C as "LLMConversationService"
    participant DB as "Conversation SQLite"
    participant DS as "DatasetService"

    U->>UI: "open retained Thread"
    UI->>H: "request Thread view"
    H->>C: "get canonical snapshot"
    C->>DB: "load Thread and Messages"
    DB-->>C: "read snapshot"
    C-->>H: "snapshot"
    H->>H: "pure structural Chatbot projection"
    loop "each canonical DatasetBlock"
        H->>DS: "resolve source presentation by dataset_id"
        DS-->>H: "bounded metadata, openability, or no result"
    end
    H-->>UI: "enriched Chatbot Events"
```

The UI opening target is a short-lived desktop capability, not ordinary event
content. A missing/malformed source therefore cannot prevent the snapshot from
opening or cause provider/canonical data to gain a local path.

## Safety and Change Rules

- Application/runtime Thread deletion goes through `LLMConversationService`.
  It rejects deletion while sampling is pending; its storage path deletes
  dependent ToolResults before their ToolCalls and remaining Messages.
- Changes to a provider, Tool, pending lifecycle, source presentation, or
  Chatbot event must preserve the topology above. Do not add a convenience
  callback from LLM to Harness or a second state holder for presentation or
  execution recovery.
- The boundary intentionally accepts process loss of an incomplete exchange
  and possible domain side-effect orphans. A later user-driven sample may
  repeat semantic work; it must not infer a ToolResult from logs, Artifacts, or
  domain rows.

## Verification Routes

- Conversation lifecycle, pending/cancellation, titles, usage, message algebra,
  and retry: `tests/test_llm_conversation_lifecycle.py`,
  `tests/test_llm_conversation_titles.py`, `tests/test_llm_message_blocks.py`,
  `tests/test_llm_usage_observability.py`, and `tests/test_llm_service_retry.py`.
- Harness projection, Tool sequencing, Dataset source presentation, and UI
  convergence: `tests/test_agent_harness_foundation.py`,
  `tests/test_agent_harness_first_slice.py`,
  `tests/test_agent_harness_streaming.py`,
  `tests/test_dataset_service_source_presentation.py`, and `tests/test_main.py`.
- Canonical storage, deletion ordering, and migration/bootstrap:
  `tests/test_repositories.py`, `tests/test_migrations.py`, and
  `tests/test_storage_bootstrap.py`.
