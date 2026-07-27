# Cross-Workstream Review Gate

## Trigger

Workstream 01 (Import), Workstream 02 (Storage), and Workstream 03 (Agent Tool) now
have reviewable contracts and an integrated MVP slice. This cross-workstream review
is therefore active, not deferred.

## Review Matrix

| Cross-cutting concern | Import must provide | Storage must preserve | Tool must expose safely |
| --- | --- | --- | --- |
| Identity and scope | source hash, `document_id`, canonical generation, singleton library identity | document-to-retrieval-unit-to-anchor mapping | opaque IDs only; future library scope cannot weaken citation identity |
| Readiness and failure | canonical-ready plus explicit warnings | query projection/index availability and invalidation | clear unavailable/partial result, never pretend searchable means parsed |
| Provenance | Docling item/page/projection lineage | minimum source anchor needed to reopen/cite a result | bounded quote and page/section citation replay |
| Privacy | selected bytes only to configured document-AI services | no secrets, raw paths, or provider payloads in durable metadata | no paths, index data, credentials, or unbounded content to provider |
| Refresh and invalidation | source/current canonical output | source change to unit/projection update policy | lookup never serves stale text as current without disclosure |
| Removal and source availability | import removal/cancel behavior | document/unit removal or stale marking policy | historical citations stay resolvable or report an honest unavailable state |
| Evolution | parser/OCR/projection descriptor | unit/embedding/index compatibility descriptor | mode negotiation and deterministic result shape |
| Product/UI | one global library, secondary workspace, queue state | durable document/index status DTOs | enabled/off control, typed citation presentation |

## Required Outputs

1. One end-to-end sequence from file selection to a persisted `knowledge.lookup`
   replay, including source refresh/invalidation and unavailable-source behavior.
2. A single ID/locator vocabulary with no duplicate authority or raw-path escape.
3. A consistency decision for canonical source, retrieval unit, embedding, and index
   projections.
4. A removal/staleness story that does not make a cited answer misleading.
5. A narrow, ordered implementation plan with explicit migration and package
   boundaries.

## Current Status

**Implementation rerun complete on 2026-07-23; final product review pending.** The
2026-07-21 authority failures have executable closure evidence: Import stops at
canonical-ready, derivation alone publishes Units, the Tool has one minimal
canonical result, and repository/package/native/live acceptance passes. This review
then found six cross-boundary gaps. Sir admitted them as one structural Phase F
repair rather than six independent patches; all six now have local executable
closure evidence. The resumed final review then found two import-entry omissions,
which Phase G repaired as one cohort. A real post-Phase-G Workspace import then
exposed a production-only nested-process gap; Phase H is now locally accepted.

| ID | Finding | Structural resolution | Local closure evidence |
| --- | --- | --- | --- |
| KB-X01 | PDF page trust was an extracted-alphanumeric threshold. | A bounded `PdfPageEvidence` model now classifies `credible`, `suspect`, and `absent`; suspect pages take the hybrid OCR route. Generic complex-layout understanding remains outside the claim. | Generated born-digital, scanned, mixed, suspect OCR-layer, and broken-font evidence fixtures pass. |
| KB-X02 | Format routing was only partly registry-driven. | One validated capability graph binds probe, normalizer, route-planner, and parser providers; execution dispatches through provider ports. | Every MVP format resolves a complete provider graph and the pipeline boundary suite passes. |
| KB-X03 | Vector build input and corpus identity were not frozen together. | Projection v3 uses deterministic Unit identities and one SQLite metadata-plus-body snapshot, then rechecks the exact identity before publication and task success. | Same-count replacement and superseded-generation regressions pass; fast status and strict search agree. |
| KB-X04 | OCR fast readiness and canonical OCR identity were incomplete. | READY depends on freshness-bound full hash/self-test evidence refreshed off the UI thread; canonical provenance records the actual runtime generation and model descriptor. | Deployment/status/provenance tests and the real native import chain pass. |
| KB-X05 | Forced import cancellation had no process-tree proof. | Each spawned import worker owns a Windows kill-on-close Job Object after cooperative cancellation is exhausted. | A stubborn worker-grandchild acceptance proves no orphan remains. |
| KB-X06 | The final corpus exercise was narrower than the route/runtime promise. | Route-labelled PDF fixtures cover the claimed page states, and source plus frozen-package acceptance execute native OCR through Import, Canonical, Derivation, and lookup. | Full source suite, real OCR integration, package smoke, and live final-answer benchmark pass. |
| KB-X07 | PPT/PPTX were missing from the intended product format set. | PPTX is a direct Docling capability and PPT is an explicit LibreOffice-to-PPTX normalization capability in the same provider graph. | Real/encrypted/generated PPT/PPTX, named 53 MB public retrieval, full suite, and frozen-worker smoke pass. |
| KB-X08 | Workspace import was picker-only. | One Workspace-local drop adapter feeds the same ordered/deduplicated submission operation as the picker while the Import Service retains admission authority. | Picker/drop parity and mixed-input UI tests pass. |
| KB-X09 | Phase G acceptance bypassed the production `spawned Import worker -> nested Docling process` topology, whose opaque failure lost the leaf stage. | The spawned Import worker is now the sole Docling isolation boundary; result schema v2 preserves a safe stage/diagnostic while the parent distinguishes launch, timeout, crash, and invalid result. Runner selection is explicit. | Named 53 MB spawned Import→Derivation→lookup, failure-stage/process-tree, full suite, fresh package/frozen spawned smoke, and bilingual queue-name acceptance pass. |

The strict Tool path, single ToolResult, keyword fallback, current-generation Unit
filter, library scoping, task-owner separation, and final-answer benchmark contract
remain coherent. Source refresh/removal UX stays explicitly out of MVP; immutable
app-owned source snapshots keep current citations available in the present no-removal
product surface.

The detailed disposition ledger and commands are in the
[Knowledge Base follow-up packet](../knowledge-base-follow-up/README.md). Phase H
implementation and local delivery acceptance are complete. This gate closes only
after one resumed coupled review with Sir confirms that the resulting Import,
Storage, Tool, UI, OCR runtime, release, and index-generation topology is the
accepted product boundary.
