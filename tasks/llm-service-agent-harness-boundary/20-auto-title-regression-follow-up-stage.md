# Auto-Title Regression Follow-up Stage

## Status and Authority

Sir authorized implementation on 2026-07-15.  The coherent product-code change
is complete and verified; only manual acceptance remains.  No commit is
authorized.

## Purpose

Restore the established product contract: a pre-created, untitled Thread gains
an automatic title after its first durable UserMessage.  The regression was
introduced by the Thread/Message cutover, not by a provider, database, or UI
configuration failure.

## Confirmed Evidence

The normal desktop path is:

```text
MainWindow creates an empty Thread (title = NULL)
    -> first submit carries that existing Thread id
    -> Harness appends the UserMessage and samples the primary model
    -> no auto-title operation runs
    -> sidebar renders NULL as "Untitled conversation"
```

- `MainWindow._create_agent_thread()` creates the normal UI Thread with no
  title.  `_start_harness_submission()` then passes its existing id into
  `SubmitUserTurnInput`.
- `AgentHarnessService.submit_user_turn_stream()` uses its deterministic title
  fallback only when `thread_id is None`; its existing-Thread path has no
  equivalent trigger after a UserMessage append.
- `generate_thread_title()` currently returns a proposal only.  The sole live
  persistence path is the manually invoked UI context-menu flow followed by a
  user confirmation.
- The sidebar text `"Untitled conversation"` is a display fallback, not a
  stored title.
- The local runtime has `thread_title_fq_model_key=bailian/qwen-flash` set.
  A read-only query found the manually exercised Thread with a durable first
  UserMessage and `title=NULL`; this rules out a missing title-model setting
  and a stale UI cache as the cause.
- The prior implementation explicitly tested auto-titling a pre-created empty
  Thread, title-model use, deterministic fallback, and non-overwrite of a
  manual title.  Those tests disappeared with the cutover.

## Product Contract

1. The first successful UserMessage in an otherwise empty untitled Thread
   automatically assigns a concise Thread title.
2. A configured title model supplies the preferred title.  If it is absent,
   unavailable, or returns an unusable answer, the system assigns the bounded
   deterministic fallback derived from first text or attachment metadata.
3. Existing manual/non-empty titles and Threads that already have history are
   never automatically overwritten.
4. The title request is metadata work: it creates no canonical Conversation
   Message, pending sampling Message, Tool Call, Run, Thinking Event, or
   recovery obligation.
5. Previously persisted title-less Threads are not silently backfilled.  They
   remain manually renameable/generatable unless Sir separately authorizes a
   deliberate backfill policy.

## Target Topology

```text
Agent Harness
    -> append first canonical UserMessage through LLMConversationService
        -> LLMConversationService derives/proposes initial title from snapshot
        -> LLMConversationService conditionally writes Thread.title
    -> Harness continues the primary conversation sampling
    -> UI receives a snapshot and refreshes the history projection
```

- `LLMConversationService` remains the sole Thread/Message writer.  The
  initial-title operation belongs at this boundary because it reads canonical
  conversation state, uses the LLM backend, and persists Thread metadata.
- Harness owns only the trigger/orchestration around the successful first
  append.  It neither writes SQLite directly nor turns title generation into a
  Chatbot event.
- The provider call is outside the Thread write gate.  Its later persistence
  uses a conditional writer so a concurrent manual rename wins.
- No third owner, persistent Run/Turn, execution ledger, or Artifact relation
  is introduced.

## Required Interface and Concurrency Rules

- Capture the eligibility decision from the pre-append canonical snapshot:
  blank title and no final Messages.
- After the UserMessage commits, title generation must consume the canonical
  first-message snapshot rather than a second raw attachment convention.
- Add an LLMConversationService conditional title command that succeeds only
  while the Thread remains untitled.  It must return the current snapshot when
  a manual rename won the race rather than overwrite it.
- A title-model error is non-fatal to the primary conversation submission.  It
  logs through observability and uses the deterministic fallback; a fallback
  write race also resolves by preserving the current manual title.
- The auto-title request must use the configured independent title model, not
  the Thread's selected primary conversation model unless product settings
  explicitly select the same key.
- Do not encode auto-title status in Message payloads, title strings, or a
  persistent execution record.

## Implementation Slices

1. Move or expose initial-title proposal and conditional persistence at the
   LLMConversationService boundary; preserve the separate manual-title proposal
   workflow.
2. Have Harness invoke the operation only after a successful eligible first
   UserMessage append, then continue ordinary primary sampling.
3. Ensure the emitted snapshot carries the title so the existing sidebar
   refresh path updates without a second UI-specific title protocol.
4. Restore focused service/Harness and UI regressions for pre-created empty
   Threads; retain title-model, fallback, non-overwrite, and no-extra-message
   coverage.

## Implementation Result

- `LLMConversationService` now captures first-message eligibility from the
  pre-append snapshot, generates an initial title after the durable append, and
  conditionally persists it through a blank-title-only repository command.
- The title-model call occurs outside the per-Thread write gate.  A concurrent
  manual rename therefore wins the later conditional write without blocking on
  provider latency.
- Harness invokes that conversation-service operation only after the successful
  append and then samples normally.  It owns neither title persistence nor a
  title-provider dependency.
- The configured independent title model is used when available.  Unavailable,
  empty, or failed title-model responses fall back to bounded canonical typed
  block content, including Dataset and source-attachment metadata.
- Manual title generation remains a proposal-only operation.  No Message,
  pending sampling state, Chatbot Event, Run, Artifact edge, or historical
  backfill was added.

## Verification Result

- `tests/test_llm_conversation_titles.py` covers pre-created and implicit
  Threads, independent-model selection, canonical-block fallback, model
  failure, manual/history protection, no extra protocol state, and a manual
  rename race.
- `tests/test_main.py` verifies that the first submitted UI message refreshes
  the existing sidebar projection from `Untitled conversation` to the durable
  title.
- `pdm run check` passed.
- `pdm run test -k "not smoke_test_bootstraps_runtime_in_fresh_app_home"`
  passed: `289 passed, 1 deselected, 3 warnings`.  The excluded smoke test
  needs an isolated Windows single-instance mutex; a live desktop instance held
  that mutex during this verification and the exclusion is unrelated to the
  change.

## Verification Matrix

| Case | Required observation |
| --- | --- |
| New UI Thread + first text | Thread title becomes the title-model proposal; sidebar no longer shows `Untitled conversation`. |
| New UI Thread + first attachment only | A bounded attachment-derived fallback exists if the title model is unavailable/fails. |
| No configured title model | Primary conversation continues and deterministic title is persisted. |
| Title model error/empty output | Primary conversation continues; fallback title is persisted and error is observed only through logging. |
| Existing manual title | First/next message never overwrites it or calls the auto-title provider. |
| Manual rename races title result | Manual title wins; conditional auto-title write is a no-op. |
| First title operation | No added Conversation Message, pending sampling Message, Chatbot Event, Run, or Artifact edge. |
| Existing title-less historical Thread | Remains unchanged without an explicitly approved backfill. |

## Next Step

Manual acceptance only: create a new Thread and send its first message.  Verify
that its title is persisted and the sidebar changes from `Untitled conversation`
without a separate UI protocol.  Test a first attachment-only message and a
manual rename as desired.  The already title-less diagnostic Thread does not
self-heal by design; it remains manually renameable/generatable.
