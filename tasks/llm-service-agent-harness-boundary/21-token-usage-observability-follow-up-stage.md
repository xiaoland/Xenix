# Token-Usage Observability Follow-up Stage

## Status and Authority

Sir approved implementation on 2026-07-15. The queryable observability variant
is implemented and automated verification is complete; it awaits Sir's manual
acceptance.

## Objective

Restore actual provider token observability and the Chatbot usage overview
without reintroducing `Turn`, persistent `Run`, provider-request storage, a
Message usage field, or a recovery dependency on observability data.

## Confirmed Root Cause

```text
Provider adapter normalizes ProviderResponse.usage_payload
    -> LLMConversationService retained only output_items       [break]
    -> no observability record and no usage projection existed
```

Adapters still normalize normal and terminal-stream usage, but the conversation
cutover discarded it before telemetry and UI projection. The no-`Turn` decision
is correct; treating observability-only data as disposable everywhere was not.

## Implemented Topology

```text
Provider response
    -> LLMConversationService normalizes safe token counts
    -> best-effort LocalLLMUsageObservability journal + metrics
       (hashed Thread/User/frontier/pending correlation keys only)
    -> canonical snapshot establishes closed User-to-terminal-LLM units
    -> LLMConversationService read-only usage_overviews(snapshot)
    -> Agent Harness interleaves USAGE after its terminal Assistant event
    -> existing UsageOverviewItem
```

- The journal is an explicit, bounded observability read model, not generic log,
  OTLP, metric, conversation, or execution storage. It retains normalized
  counts and hashed correlation keys only; no prompt, raw provider payload/SSE,
  secret, local path, Tool/domain result, raw Thread id, or raw Message id.
- `LLMConversationService` captures the root User, sampling frontier, and
  pending identity when it receives a primary provider response. It never
  derives correlation later from timestamps, log text, or adjacency.
- Canonical Message grammar decides only whether an interaction is closed. The
  injected observability reader contributes independent token facts. Missing,
  malformed, rotated, or unwritable telemetry yields no overview and changes no
  replay, Tool Result, frontier, cancellation, or commit behavior.
- A displayed total is actual observed provider-request usage associated with a
  User interaction, not token attribution for a Message text range: provider
  input includes system/history/tool schemas and may repeat across Tool loops.
- Title-model responses are recorded as `thread_title` observability operations
  and are excluded from primary conversation totals.
- The pure canonical `project_chatbot_events()` remains pure. Harness alone
  combines it with the service's typed overview, so the final snapshot already
  contains the `USAGE` event rather than being cleared by a later snapshot.
- Retained journal files allow re-projection after a Thread reopen/process
  restart. They never reconstruct conversation/execution state, and retention
  loss merely hides usage.

## Required Contract

1. Normal and streaming primary sampling record equivalent normalized usage
   when the provider supplies usable counts; explicit zero is valid, unknown is
   absent rather than fabricated.
2. The service exposes only completed canonical User-to-terminal-LLM overviews,
   aggregated by explicit root-user correlation with `request_count`, input,
   cached-input, output, and total counts.
3. Harness places one derived `USAGE` event directly after the terminal
   Assistant event. It creates no Message, Chatbot persistence row, Run,
   provider-request row, or hidden response group.
4. Observability writing/reading is bounded, redacted, best-effort, and cannot
   influence canonical state. A provider response's actual usage may be kept
   even if later canonical-output validation fails; it becomes displayable only
   if a canonical interaction later closes.
5. No Message payload/schema or SQLite execution record receives usage.

## Implemented Slices

1. Safe typed observation/aggregate, injected reader/writer port, and bounded
   hashed local journal in the observability layer.
2. Normal, stream, and title-model response capture at the LLM boundary, plus
   best-effort token metrics.
3. Closed-interaction derivation in `LLMConversationService` and Harness event
   interleaving after terminal Assistant projection.
4. Focused regression coverage for journal reopening/redaction/deduplication,
   normal/stream parity, Tool-loop aggregation, title exclusion, writer/reader
   failures, no-canonical-persistence, and event order.
5. Strict journal ingress: only bounded non-negative integer counts and the
   `primary`/`thread_title` operations are recorded. Malformed, negative,
   oversized, boolean, or unknown-operation data is absent rather than coerced
   into a false zero-usage overview.
6. Pending-capability hardening discovered during final review: abandoned live
   streams, tool callbacks racing cancellation, result-budget/finalization
   errors, and invalid tool-scope serialization all revoke or avoid a pending
   placeholder. They never create a recoverable Run or use observability to
   repair canonical state.

## Verification Matrix

| Case | Required observation |
| --- | --- |
| Single normal response | One overview has normalized provider counts. |
| Terminal stream usage | Same counts as normal. |
| Two-round Tool loop | One final overview sums both primary samples. |
| Unknown usage | Conversation finalizes normally without a false overview. |
| Title model | Its usage is observed but excluded from conversation total. |
| Journal failure | Canonical finalization succeeds; overview is absent. |
| Reopen | Retained journal data reprojects without becoming Message state. |
| Redaction | Raw provider payload and raw canonical ids never enter journal. |
| No-message invariant | No Message/schema/SQLite execution usage field exists. |
| Malformed counts/operations | No false zero total or unbounded journal entry is emitted. |
| Live-stream abandonment | Closing after Thinking removes the pending placeholder. |
| Invalid tool scope | Validation happens before any pending Message is durable. |

## Automated Verification

- Focused Stage 21/22 suite: `37 passed`.
- Full suite excluding the already-running desktop instance's single-instance
  smoke: `309 passed, 1 deselected, 3` third-party ML warnings.
- `pdm run check` and `git diff --check`: passed.

## Next Step

Return the stage for Sir's manual acceptance. No commit is authorized by this
stage.
