# Local State Evolution

Application operators and storage developers use this runbook when startup migration or persisted-state recovery is involved.

## Runtime Contract

Xenix migrates known supported SQLite versions forward in place during startup. Source and migration tests own the current version and exact supported edges; do not copy those mechanical facts into documentation.

Automatic migration does not create a pre-migration backup and has no rollback path. Back up the active runtime state before a risky migration, release transition, manual repair, or destructive recovery. A migration failure can prevent startup and must not be hidden by accepting ambiguous data.

## Developer Contract

- Add a new forward edge; never rewrite an edge that may exist in a deployed database.
- Advance the source-owned current version only with the edge that reaches it.
- Prove both fresh bootstrap and upgrade from the prior supported state.
- Repair known bad app-owned values in a forward data migration. Do not weaken ORM reads to tolerate them indefinitely.
- Before raw SQL touches an enum-backed field, inspect the model's configured persisted representation and prove the migrated row loads through the current ORM.

The nearest `src/xenix/services/storage/AGENTS.md` owns migration-author tripwires. Migration functions, models, and tests own SQL, table/field shape, version values, and edge composition.

## Failure and Recovery

Distinguish these cases before acting:

- **Unsupported version:** preserve the database, confirm that no supported edge applies, then restore a compatible backup or quarantine it and bootstrap fresh.
- **Corrupt database:** stop the app, back it up if readable, quarantine it, bootstrap fresh, and retain the quarantined file for analysis.
- **Migration failure:** preserve the original and logs; fix the forward edge or restore the pre-migration backup before retrying.
- **Fresh bootstrap:** creates empty current state. It is not recovery of conversations, registrations, or artifacts.
- **Restore:** replaces the active state with a consistent backup and requires post-startup data checks.

Use [Runtime State](runtime-state.md) for backup sets, reset blast radius, restore order, and verification. Do not delete or overwrite the only failing database while diagnosing it.
