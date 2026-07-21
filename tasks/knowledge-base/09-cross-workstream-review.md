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

**Gate failed and reopened on 2026-07-21.** The integrated slice exposed unresolved
authority and convergence problems: Import publishes retrieval state directly,
execution is UI-thread-owned, canonical publication and import status are not atomic,
and the Tool result projects unnecessary internal identities. Packaged Knowledge
execution is also unproven. The earlier “reviewed” conclusion is withdrawn.

The active finding matrix and corrected Tool boundary are in the
[Knowledge Base follow-up packet](../knowledge-base-follow-up/README.md). This gate
must be rerun after repair; benchmark success alone cannot close it.
