# Knowledge Base — Product Delivery Packet

**Status:** Slice 03 Phase H locally accepted; final cross-review pending
**Opened:** 2026-07-14
**Posture:** implementation locally verified; commit organization authorized on 2026-07-22

> **Follow-up opened 2026-07-21:** the implemented vertical path and benchmark are
> useful evidence, but the cross-contract completion gate failed. Current diagnosis,
> additional findings, and corrected boundaries are owned by the
> [Knowledge Base follow-up packet](../knowledge-base-follow-up/README.md). Do not use
> this packet's earlier implementation-ready/completion language as current status.

## Objective

Define a locally authoritative Knowledge Base through which a user can import work
journals and industry material into one global Library, let Xenix derive searchable
evidence from TXT, DOC/DOCX, PPT/PPTX, PDF, JPEG, and PNG files, and let the Agent retrieve
bounded, cited evidence to improve data-analysis interpretation. The internal library
identity remains extensible to multiple instances without exposing that UX in MVP.

The target capability supports keyword, semantic, and hybrid retrieval. The MVP is
organized around one primary outcome: a user question can retrieve bounded,
source-linked Knowledge Units. SQLite may therefore own bounded normalized unit text
as well as metadata; large source/canonical bytes stay in an app-owned CAS.

## Guardrails

- Product implementation is authorized once this packet records the product contract,
  benchmark cases, Impact Handshake, and implementation preplay. Commits still require
  an explicit request from Sir.
- A user-selected source file is never modified or deleted. The recommended import
  path creates an app-owned immutable snapshot and retains only optional provenance
  about the original path.
- `Dataset`, `Artifact`, `Knowledge Document`, and `Evidence Chunk` remain distinct
  identities. A document is not a tabular dataset; a chunk is not a user-openable
  artifact.
- Artifact identity remains `artifact://<artifact_id>`. Provider-facing schemas and
  tool results never contain absolute local paths, raw index files, credentials, or
  unbounded document content.
- OCR and embedding are document-AI capabilities, not implicit features of
  `LLMService`. MVP OCR is a locally deployed PaddleOCR capability with a one-click
  setup flow; process isolation keeps its runtime independent of the desktop Python.
  VLM is out of MVP.
- `DoclingDocument` is content IR; Xenix lifecycle, full source identity, and
  canonical-generation provenance live in an envelope alongside it.
- Retrieval citations must preserve source artifact, document generation, chunk,
  and page/section provenance so an analysis claim remains reviewable after replay.
- Existing Agent Harness persistence and canonical-tool-result invariants remain
  intact. A retrieval result is one bounded canonical tool result, not a hidden
  second context channel.

## Verification

- The packet has a scoped authority model, topology, Canonical Document shape,
  retrieval/tool contract, storage lifecycle, decisions, and staged verification
  plan.
- Before implementation, an approved Impact Handshake names exact files, migration
  edge, state diff, blast radius, invariants, and focused tests.
- Each executable slice proves its relevant fresh/upgrade state, deterministic
  parsing/IR provenance, artifact activation, and later index/tool replay behavior.
- 2026-07-14 packet validation passed: required control headings are present,
  internal links resolve, and packet files have no trailing whitespace.

## Current Truth

- SQLite owns import/document/readiness/current-generation state and bounded Units;
  the app-owned content-addressed store owns source and canonical bytes;
  `ArtifactService` owns user-openable source identity.
- Import is a durable service queue that ends at an immutable DoclingDocument bundle
  and canonical-ready publication. Independent derivation is the only production
  publisher of bounded Units and FTS readiness.
- TXT, DOC/DOCX, PPT/PPTX, PDF, JPEG, and PNG are the intended MVP format registry.
  Format registry v2 implements PPTX through Docling and PPT through explicit
  PPT→PPTX normalization. Markdown and VLM remain out of scope. Images without OCR
  can be canonical-ready while honestly remaining unavailable for retrieval.
- Local PaddleOCR is an optional one-click-installed native worker built on official
  Paddle Inference C++, with a verified runtime/model archive, bounded protocol, and
  no Python/pip/global-model-cache dependency.
- Embedding settings are independent from LLM settings. Keyword uses SQLite FTS5;
  semantic uses immutable LanceDB exact-cosine generations; hybrid uses deterministic
  RRF; explicit unavailable modes fail rather than masquerade as keyword.
- `knowledge.lookup` has one canonical `mode/results[{source, location?, excerpt}]`
  value. Production retrieval is read-only, and the Agent benchmark imports its rule
  through the real canonical/derivation path and grades final answer surfaces.
- The repeatable DOC fidelity spike selected DOC→DOCX: both routes preserved all body
  markers and the table, while DOCX retained the picture and PDF only added page
  locators. Evidence is under `evidence/` and the executable report is written under
  `build/knowledge-doc-fidelity-spike/`.
- Detailed remediation, the passing live-provider outcome, and the final global
  review gate are in the
  [follow-up packet](../knowledge-base-follow-up/README.md).

## Next Step

Resume the coupled [cross-workstream review](09-cross-workstream-review.md) with Sir.
Phase H source/full/fresh-package evidence proves the named PPTX and generated
DOCX/PPTX through the real spawned Import topology. Tool telemetry remains
diagnostic and cannot substitute for the Agent's final answer and Dataset outcomes.

## Packet Map

- [01 — Architecture and authority](01-architecture.md)
- [02 — Canonical Document and ingestion](02-canonical-document.md)
- [03 — Retrieval and Agent contract](03-retrieval-agent-contract.md)
- [04 — Metadata, files, indexes, and lifecycle](04-data-model-lifecycle.md)
- [05 — Decision register](05-decision-register.md)
- [06 — Incremental slice plan](06-slice-plan.md)
- [07 — Technology-stack proposal](07-technology-stack.md)
- [08 — UI and interaction design](08-ui-design.md)
- [Workstream 01 — Import service and UI](workstreams/01-import/README.md)
- [Workstream 02 — Storage](workstreams/02-storage/README.md)
- [Workstream 03 — Agent Tool and Skill](workstreams/03-agent-tool/README.md)
- [10 — Product contract refresh](10-product-contract-refresh.md)
- [11 — Typical Agent benchmarks](11-agent-benchmark-cases.md)
- [12 — Implementation preplay](12-implementation-preplay.md)
- [09 — Cross-workstream review gate](09-cross-workstream-review.md)
- [Evidence — Current architecture](evidence/current-architecture.md)
