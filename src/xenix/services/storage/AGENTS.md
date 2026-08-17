# Storage Guidance

## Scope

Applies to SQLite models, repositories, bootstrap, migrations, and storage layout under `src/xenix/services/storage/`.

## Tripwires

- Add a forward migration edge; never rewrite an edge that may exist in a deployed database.
- Advance the source-owned current version with the new edge and prove both fresh bootstrap and upgrade from the prior supported state.
- Inspect the ORM's configured enum representation before raw SQL or data migration. Prove migrated rows load through the current ORM.
- Repair known bad app-owned persisted values through a forward data migration. Do not weaken model reads to conceal them.
- Keep operational backup, unsupported-state handling, quarantine, restore, and reset guidance in [Deployment](../../../../docs/40-deployment/README.md). Do not copy version numbers or table inventories here.

Verify migration composition and ORM readability in `tests/storage/test_migrations.py` and `tests/storage/test_storage_bootstrap.py`; use focused repository tests for changed persistence behavior.
