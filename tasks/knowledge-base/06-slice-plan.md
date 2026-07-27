# Incremental Slice Plan

> This is the original implementation sequencing record. Current remediation uses
> one Slice 01 with internal phases; see the
> [follow-up ledger](../knowledge-base-follow-up/slices/README.md). All locally
> provable phases, the later live Agent outcome, and the Slice 03 Phase F structural
> repair pass. One final coupled product review with Sir remains.

## End State

One global Knowledge Library lets a local operator import TXT, DOC/DOCX, PPT/PPTX,
PDF, JPEG, and PNG material into auditable canonical Docling IR/envelope generations. Later
storage derives chunks/indexes; a later Agent tool retrieves bounded, cited evidence.
The product supports an optional Xenix-owned official Paddle Inference C++ worker
archive without treating OCR as chat/VLM behavior. Markdown and VLM are
outside the MVP.

## Thin Vertical Slices

| Slice | Objective and hypothesis | Included | Deferred | Primary proof |
| --- | --- | --- | --- | --- |
| 0 — Import technology spikes | Prove that the selected content/runtime routes are viable before implementation commits them. | Docling IR/JSON/assets/model-cache/package spike; TXT mapping; DOC PDF-vs-DOCX conversion; per-page PDF routing; private Paddle worker contract; pikepdf and package evidence. | Product implementation/schema/UI mutation. | Clean Windows/package fixtures, fidelity/provenance report, license inventory, bounded resource evidence. |
| 1 — Canonical import spine | A user can import supported thin-path source(s) into a source-preserving canonical-ready Docling envelope and see durable lifecycle state. | Snapshot/artifact, singleton library, attempts/generations, Docling envelope/validation, secondary workspace + modeless queue, cancel/retry/recovery. | Full format promise, chunks/indexes, Agent tool. | Atomic generation, artifact activation, close/reopen queue, no paths/secrets, fixture determinism. |
| 2 — Full MVP format ingestion | All promised source types produce provenance-preserving canonical output where technically possible. | DOC→DOCX route selected by spike; JPG/PNG; page-level PDF native/OCR/hybrid; native local PaddleOCR; encrypted retry; capability warnings. | Structured PP-StructureV3 enrichment, chunks/indexes, Agent tool. | CJK DOC/PDF/image fixtures, per-page merge, temporary password, pipeline provenance. |
| 3 — Storage derivation | Canonical-ready generations become locally searchable through structure-aware derived generations. | Chunking from frozen Docling IR, keyword/embedding/index lifecycle, data model/layout/migration/backup decisions. | Agent tool and multi-library UX. | Generation compatibility, ranking/index correctness, bootstrap/upgrade/recovery. |
| 4 — Agent evidence | The Agent can explicitly obtain bounded knowledge evidence without raw paths or hidden context. | `knowledge.lookup`, citations, replay, typed UI detail, enabled/off control. | Multi-library selection and scale optimization. | Normal/streaming persisted replay and citation opening. |
| 5 — Measured extension | Scale or add capabilities only after evidence. | ANN if justified, explicit multi-library UI, local structured-document sidecar, retention/purge. | VLM/Markdown remain separate product decisions. | Measured corpus/runtime/quality and owner-approved contracts. |

## Slice 0 Candidate Impact Handshake

This is a candidate for discussion only, not authority to edit code or dependencies.

| Field | Candidate |
| --- | --- |
| Address and object | Isolated spike harness/fixtures and dependency/package experiment only; no production service, schema, UI, or durable-owner mutation. |
| From -> To | From: technical choices are design assumptions. To: version-pinned empirical evidence decides whether Docling, pikepdf, the private Paddle runtime, and DOC route are viable. |
| Blast radius | Development/package environments and temporary task evidence only. |
| Invariants | User source untouched; no production state/migration; secrets excluded; no external document sent except through an intentionally configured test profile. |
| Verification | Fixture report, hash/provenance inspection, offline/package smoke, resource measurements, license inventory, and cleanup confirmation. |

## Verification Matrix

| Concern | Required test/evidence |
| --- | --- |
| IR | Docling JSON/reference assets round-trip with page/table/picture provenance and no absolute/provider references. |
| Parsing | TXT/DOCX/PDF/image fixtures retain real locators, warnings, and deterministic envelope manifests. |
| PDF/OCR | Per-page native/scan/mixed/OCR-layer/complex route fixtures, coordinate mapping, temporary password, and remote provider failure behavior. |
| Source safety | Original input unchanged; snapshot hash matches attempt; no provider-visible local path. |
| Lifecycle | Cancel/fail/retry/restart cannot publish a partial generation; old generation remains current. |
| UI | Header entry, singleton secondary window/queue reuse, no false percent, close/reopen durable refresh, translation. |
| Runtime | Windows 3.12–3.14/clean package, model-cache/offline behavior, PyInstaller/native DLL process evidence. |
| Privacy | External test double/profile receives only selected bytes/regions; no credential/raw response leakage. |

## Next Concrete Action

All locally executable Slice 03 and Phase F gates pass. The next action is the final
coupled Import/Storage/Tool/UI/OCR/runtime/release/index review with Sir; close the
slice only if that review accepts the resulting product boundary. Multimodal
retrieval remains outside this slice.
