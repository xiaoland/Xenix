# Thread Deletion Integrity Follow-up Stage

## Status and Authority

Sir approved implementation on 2026-07-15. The bounded repository repair and
pending-thread rejection contract are implemented and automated verification is
complete; they await Sir's manual acceptance.

## Objective

Make deletion of a Thread containing canonical Tool Call/Tool Result Messages
reliably succeed while preserving the direct ToolResult-to-ToolCall invariant,
the Thread writer gate, and SQLite referential integrity.

## Confirmed Evidence

```text
conversation_message ToolResult --tool_call_message_id--> ToolCall
                                  FK NO ACTION

repository deletes every Message in one ORM flush
    -> ORM may DELETE ToolCall before ToolResult
    -> SQLite rejects the parent delete with FOREIGN KEY constraint failed
```

- The reported traceback fails at
  `ConversationRepository.delete_thread()` while deleting
  `conversation_message`, not in the UI confirmation flow.
- `ConversationMessageRow.tool_call_message_id` references
  `conversation_message.id`; both the ORM model and v15 DDL use the default
  `NO ACTION` delete behavior.  The actual runtime database confirms that
  foreign-key shape and has no pre-existing `foreign_key_check` violation.
- The repository fetches every Thread Message, calls `session.delete()` for all
  of them, then performs one flush.  It declares no ORM self-relationship, so
  SQLAlchemy has no dependency ordering to apply.
- The order is not safely determined by canonical sequence.  SQLAlchemy may
  batch deletes by identity/primary key; fixed ids such as `a-call` and
  `z-result` reproduce deletion of the referenced ToolCall first.
- Existing UI deletion coverage exercises an empty Thread only.  It misses the
  direct ToolResult dependency introduced by the v15 canonical Message model.

## Implemented Repair

Keep the existing schema and delete in dependency order inside the repository:

1. delete final Tool Result Messages (`tool_call_message_id IS NOT NULL`) and
   flush;
2. delete all remaining Messages and flush;
3. delete the Thread and flush/commit.

This is a bounded repository correction.  It preserves the direct foreign key
and avoids a new migration.  Merely sorting Python rows before one flush is not
safe because ORM delete batching can reorder them.  Changing the self-FK to
`ON DELETE CASCADE` would require a forward migration and is unnecessary for
the desired aggregate-delete semantics.

## Pending-Deletion Contract

The attachment's FK failure is independent of pending sampling, but the audit
found a second issue that must not be hidden:

- The accepted protocol says Thread deletion is rejected while a pending
  sampling Message exists.
- Current `LLMConversationService.delete_thread()` first commits pending
  discard, then begins the separate Thread/message deletion transaction.  If
  the latter fails, the Thread remains while its pending placeholder is already
  gone.

The implemented service now reads pending state under the same per-Thread writer
gate and rejects the deletion before any row is discarded. This restores the
accepted contract and removes the prior two-transaction partial-change path;
atomic cancel-and-delete remains deliberately out of scope.

## Required Verification

| Case | Required observation |
| --- | --- |
| Empty Thread | Deletion still succeeds. |
| Assistant-only history | Deletion succeeds. |
| Tool Call + directly linked Tool Result | Deletion succeeds with no FK error. |
| Multiple Calls/Results | All dependent Results delete before their Calls; Thread and all Messages disappear. |
| Fixed adversarial ids | `a-call` / `z-result` proves correctness does not depend on ORM batch order. |
| Foreign-key integrity | `PRAGMA foreign_key_check` stays clean after deletion. |
| Pending Thread | Chosen pending-deletion contract is explicit and tested; no partial canonical change occurs on rejection/failure. |

## Automated Verification

- Repository regression covers multiple direct dependencies, fixed adversarial
  ids, and `PRAGMA foreign_key_check` after deletion.
- Focused Stage 21/22 suite: `37 passed`.
- Full suite excluding the already-running desktop instance's single-instance
  smoke: `309 passed, 1 deselected, 3` third-party ML warnings.
- `pdm run check` and `git diff --check`: passed.

## Next Step

Return the stage for Sir's manual acceptance. No commit is authorized by this
stage.
