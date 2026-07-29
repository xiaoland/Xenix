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
| Physical target realization | Local or Private SSH placement/session | Processes, paths, forwards, ports, secrets, and health remain live session facts |
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
| Local Radeon excluded because development lacks hardware | Local and Private placements are peers. Only the physical Local acceptance cell remains outstanding. |
| Unsafe partial/remove cleanup | Desired absence, tombstone, identity/receipt/process fencing, and `REMOVAL_BLOCKED` preserve forward-only semantics. |
| Hard cut requires broad core surgery | AMD resources/services/UI/tests and bounded app/spec anchors form the removable inventory; generic contracts remain owner-neutral. |

## Residual Acceptance Boundary

The code has no unresolved architecture decision. The remaining work is physical
manual acceptance on a fresh Private SSH target and a fresh compatible Local
Linux Radeon host, as recorded in the task control surface.
