# LLM Conversation / Agent Harness Unit Design

## Admission

The [LLM conversation boundary](../20-prd-tdd/llm-conversation-boundary.md)
is the sole cross-unit authority for topology, ownership, and primary
sequences. This document records only local seams that are expensive to
reconstruct while changing the LLM Conversation / Harness implementation; it
does not restate or supersede that contract.

Exact records, event shapes, Tool schemas, fields, registries, and method
signatures remain source and test truth. UI rendering contracts remain in typed
Chatbot events, UI code, and integration tests.

## Local Seams

- **UI feature ownership:** MainWindow owns conversation navigation/rendering,
  not Settings/Knowledge service composition. The auxiliary-window coordinator
  receives feature factories from the application and shuts update/dialog work
  down before application services. History receives summaries and action ports;
  opening a thread remains a shell command. Provider editing owns an in-memory
  draft, while SettingsDialog owns persistence; OCR owns its own generation and
  shutdown. Runtime/benchmark observers obtain application service handles from
  the composition callback, never through widget storage or service fields.
- **UI turn presentation:** A pure UI-local controller gates callbacks by the
  active submission generation, tracks append acknowledgement, and admits the
  final snapshot after Stop. It does not own canonical Message state. The
  injected execution adapter carries the originating generation on failures as
  well as events; selecting a Thread or closing the window invalidates old UI
  work. A closed gate suppresses UI delivery, not service I/O already in flight.
  Before append, a failure preserves Composer input; after append it reloads the
  canonical snapshot and never restores that input for resend.
- **Submission:** Harness validates UI input, coordinates source import through
  DatasetService, then asks `LLMConversationService` to append the User
  Message. Dataset blocks are canonical context; source attachments are
  presentation-only data derived later from Dataset provenance.
- **Sampling and Stop:** Harness owns the live loop and converts LLM
  Conversation live notifications into Thinking/activity/connection Events.
  User-facing Stop routes a `thread_id` pause command to
  `LLMConversationService`; Harness does not own its pause state. Its
  pending-Message cancellation maps are internal callback aids, cleared on
  finalization, abandonment, or cleanup; they are never another execution-state
  store or the meaning of Stop.
- **Pending completion:** LLMConversationService keeps private pending-exchange
  staging and performs Tool invocation/finalization. A Tool's direct returned
  value is the canonical ToolResult value: tabular Tools return XTT before the
  boundary receives it, and a typed ToolFailure remains that same value.
  Production Tool input is admitted through the Tool's strict Pydantic model;
  its provider schema is derived through the LLM-owned portable projector and
  is not a second schema authority.
  Harness must consume the resulting snapshot and decide only whether the new
  final frontier needs the next sample.
- **Projection:** First run the pure structural snapshot projection. Then, and
  only then, enrich Dataset blocks through DatasetService's read-only source
  presentation resolver. A failed resolver is a soft omission, not a Thread
  open failure. The Chatbot renderer determines displayability: reasoning-only
  Assistant events allocate no Bubble. The derived source-attachment
  presentation is neither a canonical block nor provider context; its
  originating DatasetBlock remains both.
- **Deletion and usage:** Route deletion through the LLM Conversation service
  so its writer gate and repository dependency order remain intact. Project
  usage only from LLM Conversation's observability-derived overview after the
  matching terminal Assistant event.

## Current Non-assumptions

There is no durable completion-guard, step-budget pause/resume, Turn, Run, or
cross-process pause recovery. The implemented runtime-only Thread pause blocks
later provider admission, not Tool cancellation. Once an admitted Tool exchange
has begun, it may converge its complete atomic result set; Harness then stops
at that ToolResult frontier. After it, only a new explicit UserMessage clears
pause; no stale-frontier replay occurs. Do not use legacy configuration or UI
remnants as a lifecycle contract.

## Change Guidance

Preserve the public command/snapshot seam. A new provider, Tool, stream path,
pause path, or source presentation must still converge on the canonical snapshot
specified by Product TDD. It must not make Chatbot UI infer protocol state from
storage or derive a second ToolResult from a raw Tool payload.

Read the nearest `src/xenix/services/agent/AGENTS.md` before changing this
loop. Source and tests decide exact method/field behavior; this document only
guards local ownership and sequence traps.

## Verification

- Harness coordination and direct ToolResult/XTT continuity:
  `tests/agent/test_agent_harness_first_slice.py`.
- Agent skill scope and AgentTool projection:
  `tests/agent/test_agent_skill_tool_scope.py`,
  `tests/agent/test_agent_ml_tool_projection.py`,
  `tests/agent/test_agent_ml_clustering_projection.py`,
  `tests/agent/test_agent_ml_forecast_projection.py`,
  `tests/agent/test_agent_ml_recommendation_projection.py`,
  `tests/agent/test_agent_ml_text_classification_projection.py`,
  `tests/agent/test_agent_ml_text_discovery_projection.py`, and
  `tests/agent/test_agent_data_cleaning_guidance.py`.
- Knowledge retrieval and the lookup Tool:
  `tests/knowledge/test_knowledge_retrieval.py` and
  `tests/knowledge/test_knowledge_lookup_tool.py`.
- Canonical storage, migration, and bootstrap:
  `tests/storage/test_migrations.py`,
  `tests/storage/test_storage_bootstrap.py`, and
  `tests/storage/test_storage_artifacts.py`.
- End-to-end Agent behavior (live, paid): `tests/e2e/agent_harness/`.

## Agent Harness Benchmark

[Agent Harness Benchmark](agent-harness-benchmark.md) records the local
evaluation boundary for real-provider benchmark cases, semantic judging,
integrity, measurements, and the offline/live policy.
