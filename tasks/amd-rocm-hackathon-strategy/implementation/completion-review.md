# Completion Architecture Review

## Verdict

The delivered topology preserves the intended complexity isolation: AMD is a
single optional composition leaf, capability services own inference semantics,
and storage/settings retain their pre-existing authorities. The completed
Private SSH product run and both package modes support that verdict.

## Ownership Review

| Concern | Owner | Result |
| --- | --- | --- |
| Desired installation and component generation lifecycle | AMD SQLite repository | Durable, monotonic, placement-immutable rows only |
| Compatibility and exact technical identity | Immutable manifest catalog | Admitted only after real-cell evidence; no model chooser or fallback |
| Physical target realization | Private SSH owns new realization; Local controller is composed cleanup-only for historical generations | Processes, paths, forwards, ports, secrets, and health remain live session facts |
| Provider catalog/selection | LLM, Embedding, OCR settings services | AMD contributes exact managed projections and never changes selection |
| Physical settings publication | App-lifetime `SettingsStore` | Per-document CAS and atomic publish; UI no longer bypasses it in regression coverage |
| Inference operation binding | Capability-owned factory/adapter plus AMD-private runtime directory | Exact generation is pinned without exposing a general endpoint resolver |
| Feature inclusion/removal | App/spec composition anchors | Default package includes AMD; AMD-absent package remains a working generic product |

## Issue Dispositions

| Earlier concern | Implemented disposition |
| --- | --- |
| Rollback across three settings domains | Removed the aggregate transaction premise. Registration is forward-only independent owner commands. |
| Lost UI settings update | One physical writer plus domain snapshots/revisions/CAS; tests use the production writer. |
| Dynamic SSH endpoint persisted as a `base_url` | No durable endpoint. Live binding is verified per operation through the private runtime directory. |
| AMD-specific OCR service abstraction | No `RocmOcrAdapter` in generic OCR. OCR remains KServe/PAGE; AMD maps only managed provenance and live binding. |
| Local Radeon presented as a desktop option | Corrected after product review: Xenix is Windows-only and no admitted native Windows ROCm cell exists. Guided/new-install policy exposes only Private SSH; the Local controller remains private solely so historical generations keep an exact cleanup owner. |
| Guided Install failed silently before enrollment | A new AMD-only guided command service owns validation and the SQLite/SettingsStore/reconcile sequence. The UI focuses invalid fields, renders localized typed reasons, and logs only redacted structured results. |
| Hidden IDs disappeared after restart | SQLite intent is now the first cross-authority checkpoint. The dialog discovers every non-removed installation, resumes the same hidden IDs, and offers a stable selector when multiple Private or historical Local identities exist. |
| Remove acknowledgement, inventory error, or a late Install result lied about current state | Remove waits off the UI thread for an exact terminal/blocked projection, maps `already_removed` to `removed`, and is a monotonic latest intent that older results or secondary SSH/profile read failures cannot overwrite. Unknown availability preserves the identity for retry. |
| An unreachable target appeared “Incompatible” | Target observation errors now have a separate status channel; only measured profile constraint failures produce `incompatible`. |
| Unsafe partial/remove cleanup | Desired absence, tombstone, identity/receipt/process fencing, and `REMOVAL_BLOCKED` preserve forward-only semantics. |
| Hard cut requires broad core surgery | AMD resources/services/UI/tests and bounded app/spec anchors form the removable inventory; generic contracts remain owner-neutral. |

## Residual Acceptance Boundary

The repair leaves no unresolved architecture or implementation decision.
Automated, headed validation, real SSH failure-path, hard cut-off, and default
package verification pass. The only remaining physical human acceptance is an
operational install plus Remove through the repaired Windows dialog against a
restored or fresh Private SSH Radeon target.
