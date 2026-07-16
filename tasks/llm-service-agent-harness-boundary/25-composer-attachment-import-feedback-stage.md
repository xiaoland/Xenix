# Composer Attachment Import Feedback / Append-Ack Stage

## Objective

Make post-Send source attachment import visible and honest without inventing a
second conversation state:

1. a Composer attachment tag shows import progress while its source is being
   materialized as Dataset data;
2. the canonical UserMessage appears only after every required import succeeds
   and `LLMConversationService` acknowledges the append; and
3. Thinking begins only after a real pending sampling Message exists.

The same stage removes automatic thread-title provider I/O from the
append-ack critical path, so title latency/failure cannot hide an already
committed UserMessage or delay the start of primary sampling.

## Guardrails

- The Composer owns only transient selected-file and display state. It does not
  import a Dataset, write a canonical Message, construct a DatasetBlock, or
  project a fake UserMessage/Thinking bubble.
- Harness remains the import coordinator. `DatasetService` remains the
  materialization/provenance owner. `LLMConversationService` remains the sole
  canonical Thread/Message writer and Tool invoker.
- Attachment-import loading is Composer UI state, not a Chatbot Event and not
  Thinking. Thinking must retain its real pending Message identity and begin
  only after canonical append plus `begin_sampling`.
- UI updates occur only on the Qt thread. The Harness worker may emit typed,
  transient import progress, but must not mutate Composer widgets directly.
- A progress signal must identify an attachment by submission-local index or
  opaque local key, never by inserting a raw path into canonical data,
  provider input, generic Chatbot-event serialization, or observability.
- Do not introduce a persistent Turn, Run, execution ledger, optimistic
  canonical Message, SourceAttachmentBlock, or direct UI -> DatasetService
  dependency.
- Preserve the accepted domain-orphan trade for partial import/process loss;
  this stage does not add a cross-domain compensation transaction or tool
  idempotency system.

## Current Truth

Delivered on 2026-07-16:

- `ThreadDetailView` now has a distinct pre-append Composer state. It retains
  captured text/tags, marks submitted source tags `PENDING`, and locks edit,
  attach, remove, model selection, and resend without presenting `Stop`.
- Harness emits a path-free `attachment_import` stream envelope before each
  source materialization and on failure. The envelope owns the opaque client
  submission id; its typed progress payload owns only source index and status.
  It is neither a `ChatbotEvent` nor persistent state.
- A matching append acknowledgement snapshot clears only the captured Composer
  input. The subsequent real Thinking event supplies the pending Message id,
  enters `running`, and enables Stop. A pre-append error instead restores
  editable Composer state and leaves the failed tag visible.
- Automatic initial title work begins asynchronously only after the real
  Thinking event. It uses the immutable append snapshot as its eligibility
  witness, so a fast Assistant completion cannot suppress a valid first title.
  Its conditional title write remains LLM-owned; its late `title` stream event
  refreshes history metadata without replacing live Chatbot projection.

`ComposerAttachmentStatus` retains these concrete meanings:

- `READY`: selected/eligible source waiting for Send, not imported Dataset;
- `PENDING`: this submission is materializing that source; and
- `FAILED`: that source failed import and remains editable/retryable in the
  Composer.

## Settled Target Sequence

```mermaid
sequenceDiagram
    actor U as "User"
    participant UI as "Composer / Chatbot UI"
    participant H as "Agent Harness"
    participant DS as "DatasetService"
    participant C as "LLMConversationService"

    U->>UI: "click Send"
    UI->>UI: "retain submitted text/tags; mark tags importing"
    UI->>H: "transient submission with source inputs"
    H->>DS: "materialize Dataset(s)"
    DS-->>H: "bounded Dataset summaries"
    H->>C: "append UserMessage(TextBlock + DatasetBlock)"
    C-->>H: "append acknowledgement snapshot"
    H-->>UI: "clear submitted Composer state; render UserMessage"
    H->>C: "begin sampling"
    C-->>H: "pending Message identity"
    H-->>UI: "real Thinking event"
    H->>C: "asynchronous initial-title work from append snapshot"
    C-->>H: "late title-only metadata snapshot"
```

Automatic title work begins only after append acknowledgement and must not hold
up the UserMessage snapshot or `begin_sampling`. It may later conditionally
publish a title-only snapshot/update, while preserving the existing manual
rename-wins rule.

## Implementation Surface

- `src/xenix/ui/chatbot.py`
  - retain submitted Composer text/tags until append acknowledgement or a
    pre-append failure;
  - add a distinct preparing-import state, separate from sampling `running`;
  - lock Send and attachment removal while importer input is owned by the
    worker; display tag-local PENDING/FAILED state.
- `src/xenix/ui/main_window.py`
  - replace eager Composer clearing / attachment-record disposal with a
    submission-local transient payload;
  - apply typed import progress on the Qt thread;
  - distinguish pre-append failure (retain editable Composer state) from
    post-append failure (reload canonical snapshot; never offer resend);
  - clear the submitted Composer only at append acknowledgement;
  - schedule title work outside the append-ack/sampling-start path.
- `src/xenix/services/agent/harness_service.py`
  - retain source import before canonical append;
  - emit bounded, non-Chatbot import progress/failure events keyed by source
    index; and
  - yield append acknowledgement before title-model work.
- `src/xenix/services/llm/conversation.py`
  - preserve conditional title-write/manual-rename rules while exposing a
    post-ack-safe title operation if required by the selected scheduling seam.
- Focused Harness, LLM lifecycle/title, MainWindow, and Qt Composer tests;
  translation catalogs only if new user-visible copy is necessary.

## Failure and Race Rules

| Boundary | Required behavior |
| --- | --- |
| Import fails before append | No UserMessage/Thinking exists. Preserve text and tags; mark the failing tag `FAILED`; re-enable edit/retry. |
| One of several imports fails | Preserve the per-source result visibly; accepted earlier Dataset materialization may remain an orphan, but no canonical phantom Message is written. |
| Append acknowledged | Clear only the captured submission's Composer content/tags. The snapshot is canonical; subsequent errors never restore/retry that UserMessage. |
| Title work fails or is slow | UserMessage/sampling remain visible and proceed. Fall back or report title behavior without rolling back canonical conversation. |
| Sampling pending | Transition from preparing state to current `running`/Stop semantics only once a pending Message identity is available. |
| User attempts remove/send during import | Block the mutation rather than letting the visual Composer diverge from the worker's captured inputs. |
| Thread disappears/stale frontier during import | Surface a pre-append failure, preserve Composer input, and accept any already materialized domain orphan. |

## Verification

- Sending a large CSV/XLSX leaves the selected Composer tags visible with a
  spinner until import completes; no UserMessage or Thinking appears early.
- After successful import, the initial snapshot shows the canonical UserMessage
  and then real Thinking appears when sampling starts.
- Import failure marks the correct tag, retains text/other tags, writes no
  UserMessage, and permits user correction/retry.
- A first-message title-model delay/failure does not delay append acknowledgement
  or real Thinking; manual rename still wins any late automatic title write.
- No raw source path enters canonical Message blocks, provider history,
  Chatbot-event serialization, or generic observability through progress.
- Existing source projection/reopen, cancellation, title, lifecycle, and UI
  regressions remain green; full verification is selected after focused tests
  establish the new timing boundary.

Automated evidence on 2026-07-16:

- `pdm run test tests/test_agent_harness_streaming.py tests/test_llm_conversation_titles.py` — 22 passed.
- `pdm run test tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py tests/test_llm_conversation_lifecycle.py tests/test_llm_usage_observability.py` — 26 passed.
- `pdm run test tests/test_main.py -k "not smoke_test_bootstraps_runtime_in_fresh_app_home"` — 57 passed, 1 deselected because the desktop application's Windows single-instance mutex is already held.
- `pdm run check` — passed.

## Next Step

Manual acceptance only:

1. attach a noticeably slow CSV/XLSX, Send, and confirm the Composer tag spins
   while no UserMessage/Thinking/Stop is shown;
2. confirm the canonical UserMessage appears after import, then Thinking and
   Stop appear only when sampling actually begins;
3. force an import failure and confirm text/tags remain, the failed tag is
   removable, and no phantom UserMessage exists; and
4. send a first message with a slow title model and confirm the reply starts
   normally while the history title updates later.
