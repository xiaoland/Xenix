# Runtime State

## When to Use

Developers and support operators use this runbook to locate active state, investigate a local failure, back up or restore a user environment, reset damaged state, or prepare support evidence. A wrong reset can remove conversations, settings, registered datasets, models, and artifacts.

## Locate and Inspect

`XENIX_APP_HOME` selects an explicit runtime home; otherwise Xenix uses its platform default. On Windows this is normally `%LOCALAPPDATA%\Xenix`. Resolve the active home before acting, especially when tests or isolated runs override it.

Treat its contents by ownership:

- config: application settings and persistent install identity;
- logs: local JSON diagnostic evidence;
- state: SQLite authority and app-owned dataset state;
- artifacts: generated reports, exports, models, and task work;
- cache and temp: rebuildable acceleration or transient support output;
- source import files outside the runtime home: user-owned inputs, not reset targets.

Inspect evidence by symptom:

| Symptom | Start with |
| --- | --- |
| startup or persistence failure | application log, active database, schema/migration error |
| provider behavior | Agent settings and application log; never copy credentials into a report |
| ML worker failure | worker settings, task log, local/remote validation result |
| missing dataset, model, or report | database registration plus referenced app-owned file |
| telemetry failure | [Observability](observability.md) and local exporter errors |
| packaged-only failure | [Packaging](packaging.md) and packaged smoke evidence |

## Backup and Restore

Stop Xenix before copying mutable state. For a consistent backup, preserve the entire runtime home, or at minimum the database, config, app-owned dataset state, and artifacts together. Record the source home and time. User-owned source files require their own backup policy.

To restore, stop Xenix, preserve the failed current home separately, restore the backup as one set, then start with the restored home. Verify that startup succeeds and that representative conversations, settings, datasets, artifacts, models, and worker configuration resolve. A successful launch alone is not restore proof.

## Recovery and Reset

Use this order:

1. Stop or quiesce Xenix and any local workers.
2. Identify the active home and forecast what the proposed action will remove.
3. Back up recoverable state.
4. Choose the smallest intervention.
5. Restart and verify the failed workflow plus representative retained state.

Prefer an empty isolated `XENIX_APP_HOME` for diagnosis; it changes no existing state. Database quarantine/rebuild loses SQLite-owned registrations and history from the active database but preserves the renamed database for investigation. A full runtime-home reset additionally removes settings, logs, app-owned datasets, artifacts, caches, and local task state. Never include user-owned source files in a runtime reset.

For migration-specific failure paths, use [Local State Evolution](local-state-evolution.md).

## Remote Workers and Support Bundles

After restoring or changing worker settings, revalidate the selected SSH worker before trusting it. Clear remote staged/cache data only after confirming the remote root and that no active task depends on it. Worker authority and local finalization are owned by [Product TDD](../20-product-tdd/README.md); known setup gaps remain recorded in [ADR 0005](../20-product-tdd/adr/0005-ssh-ml-worker-pool.md).

`pdm run diagnostic-bundle` creates a local support archive without the raw database. Treat it as sensitive: it contains logs, task logs, the persistent install id, and database summaries. Before manual sharing, review the archive, approve the recipient and retention period, and arrange deletion. The script and its tests own the exact manifest.
