# Implementation Record

## Delivered

- Replaced the legacy `agent_*` storage model with `conversation_thread` and immutable `conversation_message` rows. The v14-to-v15 migration converts only complete exchanges, removes incomplete legacy calls, breaks the old FK cycle before drop, and removes every Artifact-to-conversation relation.
- Added `LLMConversationService` as the sole public conversation writer. A persisted `pending_llm_sampling` placeholder exists before provider I/O; it is deleted and replaced atomically by independent Assistant, ToolCall, and ToolResult Messages. Tool Results directly reference the canonical ToolCall Message.
- Moved the Agent Tool protocol, registration, scoped validation and invocation into `services.llm.tooling`. Domain-backed tools are injected at composition time; no LLM module imports Harness or a concrete tool module.
- Preserved built-in Agent Skills through the same composition seam: their concrete catalog operations and finalized-message-derived system context are injected into the LLM boundary without restoring Harness ownership of tool dispatch.
- Replaced the persisted Turn/Run/ConversationStore loop with a thin live `AgentHarnessService`: attachment import, sampling continuation after a committed Tool Result, cancellation, and Chatbot-event projection only. Thinking/activity/connection are non-persistent events keyed by a pending Message.
- Removed Artifact conversation provenance (`thread_id`, tool/message identities and result artifact references) without adding a lineage replacement.
- Moved the single-instance guard from the packaged wrapper to the common GUI entry point, so development and packaged GUI startup share the one-writer boundary while workers remain outside it.
- Restored provider token observability through a bounded, hashed, local
  observability journal and metrics. `LLMConversationService` exposes only
  read-only completed User-to-terminal-LLM usage overviews; Harness projects
  their transient `USAGE` events. Usage never enters canonical Messages or
  SQLite and cannot restore conversation/execution state.
- Corrected Thread deletion with direct ToolResult-to-ToolCall edges by
  flushing dependent Results before their Calls, and reject deletion while a
  canonical pending sampling Message exists.
- Hardened the pending capability lifecycle: generator abandonment, cancelled
  tool callbacks, result-budget/finalization failures, and invalid tool scopes
  cannot silently leave a durable or in-memory pending tombstone. Tool
  exceptions now persist only a bounded generic failure summary.

## Verified

- `pdm run test`: 212 non-UI tests and 52 Qt/UI tests passed in separate clean processes (3 third-party ML warnings only).
- `pdm run check`, `pdm run smoke`, and `git diff --check`: passed.
- `pdm run check` and `git diff --check`: passed.
- The default PDM test runner now isolates the Qt window suite from the native ML/multiprocessing suite in a second clean process. This eliminates the Windows-native Qt access violation previously observed when both domains shared one Python process.
- Stage 21/22 focused regression suite: `37 passed`.
- Full current suite excluding the single-instance smoke while a real desktop
  Xenix process owns the Windows mutex: `309 passed, 1 deselected, 3`
  third-party ML warnings. `pdm run check` and `git diff --check` also passed.

## Manual Acceptance Focus

1. Send a normal text message; confirm Thinking appears only while provider sampling and the final assistant response remains after reopening the thread.
2. Execute a tool-backed request; confirm the UI shows its Tool event, the following assistant response sees the Tool Result, and reopening retains the call/result history.
3. Cancel during provider sampling; restart the app and verify no pending indicator or resumable execution appears.
4. Attach a source file; confirm it imports as a Dataset, its canonical
   Message contains only the Dataset summary, and reopening projects the
   original source attachment without creating an Artifact relation. If the
   original file has moved, the Thread must still open and the source open
   action must be unavailable rather than substituted with app-owned Parquet.
5. Complete a normal and a tool-backed conversation; confirm token usage
   appears after the terminal assistant answer, including after reopening the
   Thread, while no usage appears for unknown provider counts.
6. Delete a Thread containing at least one visible tool result; confirm it
   disappears without a foreign-key error. Attempt deletion while Thinking is
   active; confirm it is rejected without cancelling the sampling.
