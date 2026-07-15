# Manual-Acceptance Follow-up Stage

## Purpose

Resolve the two confirmed manual-acceptance defects without reopening the
approved authority topology:

1. an attached Dataset block reaches canonical conversation persistence but is
   omitted from the current provider wire message; and
2. a reasoning-only Assistant Message produces an empty Chatbot bubble after
   the live Thinking event is removed.

Sir explicitly authorized implementation of this follow-up on 2026-07-15.  It
is now an Execute stage; the settled topology and the checks below remain the
scope boundary for the mutation.

## Preserved Topology

```text
LLMConversationService owns Thread and canonical Message state
    ├── provider adapter serializes canonical content for its backend
    └── Agent Harness projects a Thread/Message snapshot to Chatbot Events
            └── Chatbot UI renders Events
```

- There is no new conversation owner, persistent Run, Turn, execution ledger,
  Artifact provenance relation, or Harness dependency from the LLM boundary.
- Thinking remains a live Harness-owned Chatbot Event, never a persisted LLM
  Conversation concept.
- A reasoning value may remain canonical when provider continuation/replay
  requires it.  It is not automatically user-visible.

## Confirmed Evidence

For manual-acceptance thread `20bcb6e0648745a791518505f1ac3f13`:

> **Stage 23 supersession (2026-07-15).** The source Artifact/preview-column
> observations below describe the pre-reduction payload. New imports retain
> neither source Artifact provenance nor preview/schema metadata in canonical
> Dataset blocks. Historical rows remain readable under the Stage 23 decoder.

- The Dataset, DatasetImport, and DatasetWorkbook all exist. The historical
  User Message carries a Dataset block with dataset id, name, row/column
  counts, and preview columns.
- Harness correctly extracts that Dataset id for its current live ToolScope.
  The provider transcript nevertheless contains only the user's prose because
  the current Chat Completions path reads `block["text"]` and drops every
  non-text block.
- The first Assistant Message has reasoning but no user-facing text.  Harness
  projects it as an Assistant text event; the current Bubble does not render a
  reasoning block, so it allocates an empty visual card where Thinking had
  appeared.

## Settled Design

### Typed canonical blocks

Conversation Message payloads retain blocks.  A block is a typed class and
not an unbounded `dict[str, Any]` convention.  At minimum, the active types
cover text, dataset, and source attachment content used by the conversation.

Every block provides a safe, bounded textual fallback such as
`block.to_markdown()`.  It contains stable ids and bounded business facts but
never local absolute paths, diagnostic payloads, or secrets.  A Dataset block
therefore has one reusable fallback representation rather than a separately
invented rendering in each backend.

If a block retains a presentation hint, name it explicitly (for example
`chatbot_visible`), and define it as a Harness/UI concern only.  Provider
serialization must not treat that hint as an instruction to omit the block.

### Adapter-owned provider serialization

`LLMConversationService` supplies a provider-neutral transcript that retains
canonical blocks and protocol fields.  Each adapter chooses its history and
wire representation:

- a text-only Chat Completions adapter can concatenate the blocks'
  `to_markdown()` fallbacks;
- an adapter with native content items can use them where meaningful; and
- a remote-conversation adapter can elect not to resend historical content.

The adapter choice does not mutate canonical Messages.  Tool Call/Result
protocol fields remain structured rather than being flattened into generic
text.

### Snapshot-faithful Chatbot Events

Agent Harness projects a snapshot into Chatbot Events.  Assistant Chatbot
Message Events preserve the corresponding canonical message shape where it is
meaningful, including content blocks, `reasoning`, and `refusal`; they do not
run a second semantic assistant-message serializer.

The Chatbot Assistant Message Bubble decides only its displayability:

- render user-visible text content and a refusal when present;
- retain no visual card when neither exists; and
- never render `reasoning` under current product behavior.

Thus a reasoning-only Assistant Message remains available to protocol replay
and Event consumers but produces no empty UI bubble.  Tool Call and Tool
Result Messages remain independent canonical Messages.  The existing `TOOL`
Event intentionally projects one direct Call/Result pair into one UI card
through `source_message_ids`; it is a non-authoritative presentation grouping,
not a second lifecycle or Message type.

### Legacy compatibility boundary

The v14 production payload types that can become final canonical content are
`text`, `markdown`, `dataset`, and `source_attachment`.  They decode into the
closed typed algebra above; an unknown or malformed block fails closed instead
of being silently flattened into provider context.  `visible` remains a
read-only legacy spelling for `chatbot_visible`.

## Completed Design Checks

1. Define the typed block algebra, its JSON persistence representation, and
   its fallback-text bounds without creating a second block authority.
2. Trace every configured adapter's treatment of canonical blocks, including
   Chat Completions, streaming, and any Responses-style history strategy.
3. Define the exact Event fields shared with Assistant Messages and prove that
   a reasoning-only event does not allocate a bubble while a text/refusal event
   does.
4. Decide whether an existing generic `visible` field is renamed or eliminated
   in favor of a direct Harness projection rule.
5. Reassess the uncommitted, preemptive manual-acceptance patch against this
   stage.  It is not an approved implementation and must not be treated as the
   target design.

## Completed Verification

- A captured Chat Completions request includes the Dataset block's bounded
  textual fallback even when the Dataset is not shown as a separate UI card.
- Each adapter preserves its documented history behavior while receiving the
  same canonical block transcript.
- Reopening the affected thread preserves Dataset content for both provider
  serialization and Chatbot projection.
- A reasoning-only Assistant Message yields no visible bubble; text-only,
  refusal-only, text-plus-tool-call, and tool-only sequences retain their
  intended UI order.
- Provider replay still includes any reasoning required by the selected
  backend for a Tool Result continuation.

## Implementation Evidence

- `services.llm.messages` now defines the closed typed block algebra and its
  JSON conversion.  Dataset and source attachment ids reject path-shaped
  values before a textual fallback can expose a local path.
- `LLMConversationService` supplies typed blocks to provider messages.  The
  OpenAI-compatible Chat Completions adapter alone derives text with
  `block.to_markdown()`, including blocks hidden from the Chatbot UI.
- Chatbot Events retain Assistant `text`, `reasoning`, and `refusal` fields.
  The UI filters only presentation-hidden attachment blocks and allocates no
  card when a text event has no displayable content; it never displays
  reasoning.
- The v14-to-v15 migration now preserves a legacy provider tool name when it
  exists.  Older v15 rows that already lack it use the LLM-owned registry as a
  replay-only fallback; newly finalized Tool Calls persist it directly.
- The affected thread was read through SQLite in read-only mode.  Its legacy
  Dataset block (`visible: false`) decoded successfully, and a captured
  Chat-Completions request contained its user text, dataset id, and row count.
- Automated evidence: the focused service/migration/Harness suite passed 36
  tests; the Qt suite excluding the process-global single-instance smoke test
  passed 54 tests; the full repository suite passed 279 tests with that one
  smoke test explicitly deselected and three third-party ML warnings;
  `pdm run check` and `git diff --check` passed.

## Next Step

Manual acceptance only:

1. Reopen thread `20bcb6e0648745a791518505f1ac3f13`; the reasoning-only
   first Assistant Message must not leave a blank bubble.
2. Send a follow-up that relies on the attached churn Dataset; the model should
   receive the historical Dataset fallback and be able to identify it.
3. Attach/import another Dataset and confirm its hidden UI projection does not
   suppress its provider context.
