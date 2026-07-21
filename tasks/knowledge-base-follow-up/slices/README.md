# Knowledge Base Follow-up Slice Ledger

## Slice Semantics

A slice is one admitted cohort of findings and the product promise required to close
that cohort. It is **not** one technical subsystem, migration, or implementation
phase. The earlier ledger incorrectly promoted seven work packages into seven slices;
Sir corrected that granularity on 2026-07-21.

While a slice is open, its work may be sequenced into internal phases for dependency
and verification control. Completing a phase is only a checkpoint. It cannot close
the slice, withdraw the remaining findings, or skip the final cross-workstream review.
New findings related to the same Knowledge Base delivery join Slice 01 through an
explicit Impact Handshake revision. Slice 02 is reserved for a genuinely later cohort
after the present known findings have been reconciled.

## Active Slice

| Slice | State | Cohort | Completion boundary |
| --- | --- | --- | --- |
| [01 — Known-findings realignment](01-known-findings-realignment.md) | In progress; reopened after an undersized closeout | KB-F01 through KB-F16, accepted discussion decisions, semantic/hybrid retrieval, and final-answer benchmark correction | All findings resolved or explicitly rejected; Import/Storage/Tool contracts agree; delivery evidence passes; global cross-review completed with Sir |

## Internal Phase Map for Slice 01

| Phase | State | Purpose | Findings / decisions |
| --- | --- | --- | --- |
| A — Agent boundary checkpoint | Verified phase; not slice completion | Minimal Tool contract, selectable modes, integrated data-work methodology, canonical replay | KB-F01; Knowledge-specific parts of F10/F12; F13; F15; F16; interface part of F14 |
| B — Semantic/hybrid retrieval and outcome benchmark | Research and design in progress | Real embedding/vector retrieval, measured hybrid behavior, and benchmark oracles over final answer surfaces rather than ToolResults | execution part of F14; KB-D05/D08; benchmark correction |
| C — Canonical envelope and content identity | Pending | Complete the application envelope and make canonical payload identity immutable and self-validating | KB-F05, F06 |
| D — Storage, migration, and index authority | Pending | Fix historical migration edges and establish retrieval-generation/index ownership discovered by Phase B | KB-F07 plus Phase B storage consequences |
| E — Import lifecycle and atomic publication | Pending | Restore canonical-ready boundary, service-owned queue, and one consistent publication transition | KB-F02, F03, F04 |
| F — Runtime, UI, security, and packaged delivery | Pending | OCR readiness, path/schema closure, translated service-driven UI, frozen-app exercise | KB-F08, F09, remaining F10/F11/F12 |
| G — Cross-workstream acceptance | Pending | Re-run outcome benchmarks and globally cross-audit Import, Storage, and Tool as one system | all findings and accepted workstream contracts |

Phases may be reordered when research exposes a real dependency, but they remain
inside Slice 01. No future phase receives an independent “slice complete” claim.

## Current Gate

Phase A is a checkpoint ready to commit. Phase B begins with research, trade-off
analysis, and an implementation preplay before semantic/vector product code changes.
Sir has authorized continuing through implementation after that design gate. The
overall Slice 01 remains open throughout.
