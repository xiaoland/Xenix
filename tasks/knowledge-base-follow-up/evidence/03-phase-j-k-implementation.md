# Slice 03 Phases J/K — Workspace Loading and Document Removal

**Date:** 2026-07-23
**State:** implemented, accepted, and closed by Sir on 2026-07-24

## Phase J Outcome

The Workspace no longer waits for one aggregate snapshot before rendering
documents. `KnowledgeWorkspaceService` exposes independent document and status
projections. The dialog owns explicit `cold`, `loading`, `ready`, `empty`, and
`unavailable` viewport states, retains the last successful rows during refresh, and
uses request plus lifecycle generations to reject hidden or superseded results.

The footer remains strict and truthful, but cold LanceDB/PyArrow verification can
complete later without withholding the document list. Initial paint uses translated
loading copy; only a completed empty document query displays the empty-Library
message.

## Phase K Outcome

`KnowledgeService` remains retrieval-only. The new
`KnowledgeDocumentLifecycleService` owns destructive document commands. One guarded
SQLite writer transaction:

1. claims the exact active document only when no related import or derivation work
   is pending, queued, or running;
2. removes FTS, Units, derivations, canonical generations, completed import lineage,
   the document, and affected-Library vector-generation metadata in dependency
   order; and
3. unregisters only unreferenced source Artifacts whose metadata and path prove they
   belong to the Knowledge source CAS.

The commit is the retrieval visibility cutover. Post-commit maintenance removes
unreachable import logs and proven-orphan source/canonical/vector bytes, then asks
the existing index owner for one coalesced corpus-change rebuild when searchable
content remains. Cleanup failure cannot restore retrieval visibility. The original
user file is outside all app-owned cleanup roots.

The Workspace exposes deletion only from the context menu of the item under the
pointer. Blank-area right-click has no action; there is no toolbar button. A
destructive translated confirmation names the document and explains the imported
copy/search/task removal, preservation of the original file, and lack of undo. The
command runs off the UI thread; busy, missing, and unexpected outcomes use bounded
translated copy.

## Acceptance Evidence

- Workspace/i18n focused cohort: `20 passed`.
- Storage/index maintenance focused cohort: `41 passed, 2 skipped`.
- Retrieval/semantic/lifecycle focused cohort: `46 passed`; the final lifecycle
  suite has four cases after shared-CAS coverage was added.
- Import service: `8 passed`; import lifecycle: `14 passed`.
- App composition: `7 passed`; app-entry: `58 passed`.
- Complete repository gate: `633 passed, 3 skipped`; app-entry second session:
  `58 passed`.
- Static checks and `git diff --check` pass.
- Source packaged-smoke test: `2 passed, 1 skipped`.
- Fresh frozen executable build: success in 915 seconds.
- `pdm run smoke-package`: success in 114.8 seconds. The frozen smoke performs
  spawned PPTX import, derivation and lookup, lifecycle removal, lookup absence,
  byte-for-byte original-file preservation, and same-SHA re-import as a fresh
  document identity.

The lifecycle black-box suite additionally proves typed busy rejection without
partial mutation, clean foreign keys and FTS, whole-Library vector invalidation and
remaining-corpus rebuild, same-SHA re-import, and preservation of a shared source
CAS object until the final cross-Library reference is removed.

## Closure

Sir accepted Phases J/K and the final
Import/Storage/Tool/UI/OCR/runtime/release/index cross-workstream result, closed
Slice 03 and the complete Knowledge follow-up task, and authorized the commit on
2026-07-24. Multimodal retrieval, undo/tombstones, bulk removal, and Agent deletion
tools remain outside the completed scope.
