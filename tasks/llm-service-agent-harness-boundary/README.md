# LLM Conversation / Agent Harness Boundary

## Objective

Establish an evidence-backed boundary between LLM Service, canonical interaction state, observability, and Agent Harness that improves maintainability and readability, corrects confirmed defects, and settles whether conversation persistence needs either a `Turn` or persistent `Run` abstraction.

## Guardrails

- Sir authorized investigation and task-packet restructuring on 2026-07-14. Product mutations remain whole-task-specific: the complete cross-owner cutover needs one approved Impact Handshake before it is applied.
- Do not treat an architecture preference as a defect without a reproduced failure or a violated invariant.
- Preserve only complete canonical conversation protocol units: a final LLM emission containing Tool Call Messages commits together with its Tool Result Messages. Domain side effects remain outside that SQLite transaction and may be orphaned by an accepted process-loss trade; preserve final-history convergence and typed Chatbot projection. Legacy completion-guard artifacts are not current connected lifecycle behavior.
- Keep provider configuration, transport, retry, response normalization, the Thread/Message interface, typed Message algebra, context projection, pending/final LLM Message lifecycle, AgentTool abstraction/registry/invocation, and canonical conversation state at the LLM boundary. Keep import coordination, live sampling/cancellation policy, and Chatbot-event projection at the Harness boundary. No third top-level conversation service is in scope.
- Observability is cross-cutting, not a third conversation owner: logs, traces, metrics, retry timing, and raw diagnostic wire data may be persisted by observability, but are never a source for conversation replay, tool-outcome reconstruction, or state repair.
- Tool interface and implementation are different things, but `AgentTool` is LLM-owned. LLM Service owns the Tool protocol, registry, exposed-scope validation, and invocation operation. Concrete adapters implement the LLM protocol and are wired by composition; Harness bootstrap may call the registration interface but never owns registry/lookup/dispatch/lifecycle. LLM Service never imports Harness or concrete/domain tool modules.
- SQLite remains the authority for bounded local application state. Forward migrations, fresh bootstrap, upgrade, ORM readability, and focused repository behavior must be proven for any schema change.
- Do not commit, publish, or change external state without separate explicit authority.

## Verification

- Complete the fact checks in [01-boundary-map.md](01-boundary-map.md), including history replay, state ownership, the observability firewall, the tool contract, and whether `Turn`/persistent `Run` earn independent authority.
- Maintain evidence, severity, owner, and disposition for every issue in [02-finding-register.md](02-finding-register.md).
- Agree on an architecture decision and a bounded implementation sequence in [03-slice-plan.md](03-slice-plan.md) before changing product code.
- For the approved whole cutover, prove adapter correctness, normal/stream convergence, retry/cancellation, persistence/migration safety, and UI projection with focused PDM tests.

## Current Truth

- The whole cutover is implemented; [18-implementation-record.md](18-implementation-record.md) records its source/schema/runtime delivery. Stages 19–22 are implemented and have passed automated verification; they await Sir's combined manual acceptance. Their scopes and evidence are recorded in [19-manual-acceptance-follow-up-stage.md](19-manual-acceptance-follow-up-stage.md) through [22-thread-deletion-integrity-follow-up-stage.md](22-thread-deletion-integrity-follow-up-stage.md).
- Production authority is `UI -> Agent Harness -> LLMConversationService -> provider adapter -> provider`.  `LLMConversationService` is the sole canonical Thread/Message writer; no `ConversationStore`, persistent `Turn`, persistent `Run`, or execution ledger remains.
- Finalized Client/LLM Messages are durable.  A pending sampling placeholder is provisional; an Assistant emission and its independent ToolCall/ToolResult Messages commit atomically.  ToolResult directly references ToolCall, and no Artifact owns a conversation provenance edge.
- The LLM boundary owns the provider/tool protocol, tool registry, scoped validation, invocation, typed blocks, and adapter-specific history serialization.  Harness imports attachments, controls live sampling/cancellation, and projects snapshots to Chatbot Events; it is never an LLM invocation dependency.
- Typed canonical blocks currently cover text, markdown, dataset, and legacy
  source attachment. New writes retain only Dataset identity plus its bounded
  summary; source attachments are a Harness-to-Chatbot projection derived from
  DatasetImport provenance. Provider adapters receive canonical Dataset blocks
  through bounded `to_markdown()` fallbacks, while the compatibility decoder
  keeps historical wide Dataset/source-attachment payloads readable.
- Thinking/activity/connection are live Harness events.  Assistant Event projection preserves `text`, `reasoning`, and `refusal`; the UI suppresses reasoning and creates no empty Bubble for a reasoning-only Message.
- No automatic cross-process execution recovery or tool idempotency promise is provided.  Process loss may discard an unfinished exchange and a later user-driven sample may repeat semantic tool work; observability remains non-authoritative.
- The v14-to-v15 migration converts complete history, removes the legacy aggregate tables and Artifact provenance, and preserves legacy provider tool names when present.  Older v15 rows without that field have an LLM-registry replay fallback.
- [05-two-service-boundary-options.md](05-two-service-boundary-options.md) through [17-whole-task-implementation-rehearsal.md](17-whole-task-implementation-rehearsal.md) retain the evidence and decision history behind the delivered topology; read [18-implementation-record.md](18-implementation-record.md) and stage 19 before treating any earlier "current" or "target" wording as live state.
- Automatic naming of a pre-created empty Thread now runs after its first durable UserMessage through `LLMConversationService`, using the independent title model or bounded canonical fallback.  It conditionally writes only a still-blank title, adds no conversation protocol state, and does not silently backfill existing title-less Threads.
- Stage 21 restores token usage through an injected, bounded observability journal that stores only normalized counts and hashed correlation keys. `LLMConversationService` derives closed User-to-terminal-LLM units from canonical Messages, queries that non-authoritative journal, and Harness projects `USAGE` after the terminal Assistant. Usage never enters canonical Messages or SQLite and never repairs/replays conversation state. See [21-token-usage-observability-follow-up-stage.md](21-token-usage-observability-follow-up-stage.md).
- Stage 22 fixes Thread deletion with direct ToolResult-to-ToolCall edges by deleting dependent Results in one flush before their Calls/other Messages. Deletion now rejects a pending sampling Message under the Thread writer gate rather than discarding it first. See [22-thread-deletion-integrity-follow-up-stage.md](22-thread-deletion-integrity-follow-up-stage.md).
- Stage 23 implements the DatasetBlock contract and source-projection
  topology: new canonical blocks retain only `dataset_id`, `name`,
  `row_count`, and `column_count`; DatasetService remains the
  source-provenance authority; Harness derives an ephemeral Chatbot source
  attachment. `data.list` remains explicitly deferred. See
  [23-dataset-block-contract-reduction-stage.md](23-dataset-block-contract-reduction-stage.md).
- Stage 24 has reconciled durable owners with the delivered boundary: a Product
  TDD topology/sequence contract and ADR, a corrected Unit TDD, and minimal
  PRD/observability guidance. It deliberately leaves unresolved
  Dataset-disposal, legacy guard/step-budget, Artifact-URI, and ToolResult
  local-path decisions out of the documentation mutation. See
  [24-durable-documentation-reconciliation-stage.md](24-durable-documentation-reconciliation-stage.md).
- Stage 25 implements Composer attachment-import feedback without optimistic
  conversation state: path-free Harness progress drives Composer tags,
  canonical append acknowledgement clears captured input, and automatic title
  work begins only after real sampling starts. See
  [25-composer-attachment-import-feedback-stage.md](25-composer-attachment-import-feedback-stage.md).

## Next Step

Stage 25 is ready for Sir's manual acceptance alongside the earlier follow-up
stages: Dataset context and reasoning-only bubbles, automatic initial title,
token usage projection, Thread deletion/pending rejection, source attachment
projection/reopen, and Composer import feedback. `data.list` remains out of
scope. No commit is authorized until Sir explicitly requests one.
