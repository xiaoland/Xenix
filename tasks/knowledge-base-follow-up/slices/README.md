# Knowledge Base Follow-up Slice Ledger

## Slice Semantics

A slice is one admitted cohort of findings and the product promise required to close
that cohort. It is **not** one technical subsystem, migration, or implementation
phase. The earlier ledger incorrectly promoted seven work packages into seven slices;
Sir corrected that granularity on 2026-07-21.

While a slice is open, its work may be sequenced into internal phases for dependency
and verification control. Completing a phase is only a checkpoint. It cannot close
the slice, withdraw the remaining findings, or skip the final cross-workstream review.
New findings related to the current cohort join the active slice through an explicit
Impact Handshake revision.

## Active Slice

| Slice | State | Cohort | Completion boundary |
| --- | --- | --- | --- |
| [02 — Knowledge operations, workspace, and index control](02-knowledge-operations-workspace-indexes.md) | Locally verified; global cross-review with Sir pending | KB2-F01–F05 and F07; F06 parked | All admitted findings resolved; delivery evidence passes; global Import/Storage/Tool/UI/runtime review completed with Sir |

## Closed Slices

| Slice | State | Closure note |
| --- | --- | --- |
| [01 — Known-findings realignment](01-known-findings-realignment.md) | Closed by Sir on 2026-07-22 | All local A–G evidence passed. The two live cells still failed final-answer grounding; this is carried as `KB2-F01` and is not retroactively described as passing. |

## Internal Phase Map for Slice 01

| Phase | State | Purpose | Findings / decisions |
| --- | --- | --- | --- |
| A — Agent boundary checkpoint | Locally verified | Minimal Tool contract, selectable modes, integrated data-work methodology, canonical replay | KB-F01; Knowledge-specific parts of F10/F12; F13; F15; F16; interface part of F14 |
| B — Semantic/hybrid retrieval and outcome benchmark | Implementation locally verified; live outcome failed twice | Real embedding/vector retrieval, measured hybrid behavior, and outcome verification over final answer surfaces | execution part of F14; KB-D05/D08; re-verification of the Phase A benchmark correction |
| C — Canonical envelope and content identity | Locally verified | Complete the application envelope and make canonical payload identity immutable and self-validating | KB-F05, F06 |
| D — Storage and migration stabilization | Locally verified | Fixed historical migrations, current-generation invariants, and safe derived-storage reclamation | KB-F07 and Phase B storage consequences |
| E — Import lifecycle, format routing, and atomic publication | Locally verified | Canonical-ready boundary, promised image routing, service-owned queue, and consistent publication transitions | KB-F02, F03, F04, routing part of F17 |
| F — Runtime, UI, security, and packaged delivery | Locally verified | OCR readiness, format/UI promise closure, path/schema closure, translated service-driven UI, frozen-app exercise | KB-F08, F09, remaining F10/F11/F12, UI/delivery part of F17 |
| G — Cross-workstream acceptance | Locally verified; external Phase B cell excluded | Outcome oracle/fixtures and global Import/Storage/Tool topology agree | all findings and accepted workstream contracts |

Phases may be reordered when research exposes a real dependency, but they remain
inside Slice 01. No phase receives an independent “slice complete” claim.

## Internal Phase Map for Slice 02

| Phase | State | Purpose | Findings / decisions |
| --- | --- | --- | --- |
| A — Import process and logs | Locally verified | Move one import attempt's heavy execution behind a spawned process while the parent retains publication authority; expose bounded task logs | KB2-F02 |
| B — Workspace and settings information architecture | Locally verified, including bilingual visual QA | List logical documents; make Knowledge own Embedding/OCR/index settings and direct navigation | KB2-F03, KB2-F05 |
| C — Index compatibility and rebuild control | Locally verified | Remove surprise lookup-time builds; confirm compatibility-changing settings; add observable automatic/manual rebuild jobs | KB2-F04, KB2-F07 |
| D — Outcome and cross-workstream acceptance | Live outcome and local delivery passed; review with Sir pending | Repair the carried Agent-answer residual, run delivery evidence, and review Import/Storage/Tool/UI/runtime topology as one system | KB2-F01 and all active Slice 02 findings |

## Current Gate

Slice 01 is closed with its failed benchmark evidence intact. Sir approved the
recommended Slice 02 decisions and authorized implementation on 2026-07-22.
Multimodal retrieval (`KB2-F06`) is parked outside this slice. Sir authorized the
locally verified work to be organized into implementation and documentation commits
on 2026-07-22; the global cross-review remains the Slice 02 closure gate.
