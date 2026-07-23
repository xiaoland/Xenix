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
| [03 — Local OCR, Workspace responsiveness, and Knowledge operations](03-local-ocr-workspace-operations.md) | Phase I locally accepted; coupled review pending | KB3-F01–F08 plus KB-D26–D38 | Complete the global Import/Storage/Tool/UI/OCR/runtime/release/index review |

## Prior Locally Delivered Slice

| Slice | State | Carry-forward |
| --- | --- | --- |
| [02 — Knowledge operations, workspace, and index control](02-knowledge-operations-workspace-indexes.md) | Locally verified and committed; global cross-review pending | Slice 03 supersedes the import-specific Queue UI decision and carries the global review into Phase E. |

## Closed Slices

| Slice | State | Closure note |
| --- | --- | --- |
| [01 — Known-findings realignment](01-known-findings-realignment.md) | Closed by Sir on 2026-07-22 | All local A–G evidence passed. The original two live cells remain historical failures; the carried `KB2-F01` oracle repair and later configured-provider rerun now pass without rewriting that history. |

## Internal Phase Map for Slice 01

| Phase | State | Purpose | Findings / decisions |
| --- | --- | --- | --- |
| A — Agent boundary checkpoint | Locally verified | Minimal Tool contract, selectable modes, integrated data-work methodology, canonical replay | KB-F01; Knowledge-specific parts of F10/F12; F13; F15; F16; interface part of F14 |
| B — Semantic/hybrid retrieval and outcome benchmark | Implementation locally verified; historical cells failed, later rerun passed | Real embedding/vector retrieval, measured hybrid behavior, and outcome verification over final answer surfaces | execution part of F14; KB-D05/D08; re-verification of the Phase A benchmark correction |
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
| D — Outcome and cross-workstream acceptance | Live outcome and local delivery passed; global findings pending disposition | Repair the carried Agent-answer residual, run delivery evidence, and review Import/Storage/Tool/UI/runtime topology as one system | KB2-F01 and all active Slice 02 findings |

## Current Gate

Slice 01 is closed with its failed benchmark evidence intact. Slice 02 is locally
verified and committed, while its global review remains explicit. Sir opened Slice
03 on 2026-07-22 and authorized task-packet work plus one local Knowledge-data reset
and PPTX diagnostic, deletion of the unreleased Python sidecar, and a disposable
official Paddle C++ compatibility spike. The spike passed on the selected PP-OCRv6
medium models and its upstream guard/dependency/size/performance evidence is recorded.
Sir approved the [detailed Impact Handshake](03-implementation-plan.md). The clean
native build, frozen offline activation, complete repository suite, release manifest,
and live final-answer outcome now pass. The global review ran on 2026-07-23 and
opened KB-D26–D31; Sir admitted the single Phase F convergence repair, whose
source/full/package/native/live evidence now passes. The final review then opened
KB-D32–D33 for omitted PPT/PPTX admission and Workspace drag-and-drop. Sir started
their Phase G implementation; focused/full/package/public-fixture evidence passes.
The real Workspace re-import then exposed KB-D34–D35. Sir started Phase H; the
production process-topology, structured failure result, named-fixture regression,
package smoke, and local queue naming repairs are implemented and locally accepted.
The resumed review exposed KB-D36–D37: source-mode OCR setup had no composed bundle
source, and a provider batch-limit rejection was hidden behind a generic semantic
task failure. Sir started Phase I. Batch size remains user-configurable and now
defaults to 20; the current profile is 20, and a 67-Unit manual rebuild plus semantic
retrieval pass. OCR now has an explicit local-or-release bundle source, development
installation reaches native `ready`, and safe OCR/Embedding failures reach their
existing UI/task presentation planes. Phase I is locally accepted. The coupled
package gate additionally exposed KB-D38: staging-path self-test did not prove the
long final native-model path. A compact content-addressed generation name and
final-path self-test repaired it; fresh package plus real native OCR packaged smoke
now pass. The coupled review must now resume before Slice 03 can close.
Multimodal retrieval (`KB2-F06`) remains parked outside the active slice.
