# Knowledge Base — Product Delivery Packet

**Status:** initial delivery packet; engineering completion withdrawn after compliance audit
**Opened:** 2026-07-14
**Posture:** implementation authorized after design/preplay; no commit authority

> **Follow-up opened 2026-07-21:** the implemented vertical path and benchmark are
> useful evidence, but the cross-contract completion gate failed. Current diagnosis,
> additional findings, and corrected boundaries are owned by the
> [Knowledge Base follow-up packet](../knowledge-base-follow-up/README.md). Do not use
> this packet's earlier implementation-ready/completion language as current status.

## Objective

Define a locally authoritative Knowledge Base through which a user can import work
journals and industry material into one global Library, let Xenix derive searchable
evidence from TXT, DOC/DOCX, PPT/PPTX, and PDF files, and let the Agent retrieve
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

- SQLModel and SQLAlchemy are already project dependencies; no ORM introduction is
  needed.
- SQLite is the established owner of bounded local application state and the local
  filesystem is the owner of large/user-openable bytes. `ArtifactService` already
  owns artifact registration, resolution, and activation.
- No document parser, OCR, embedding capability, vector index, general
  retrieval service, document/chunk storage model, or document-import lifecycle
  currently exists.
- The existing TF-IDF text-similarity model is a trained ML analyzer over tokenized
  tabular data, not a reusable RAG index.
- The current Agent attachment flow materializes CSV/Excel-style datasets; a PDF or
  DOCX can be registered as a source artifact but cannot enter Agent work today.
- Product decisions confirmed and refreshed through 2026-07-21: MVP exposes one global Library while
  retaining an internal future extension path; DoclingDocument is its content IR with
  a separate Xenix lifecycle envelope; MVP accepts TXT, DOC/DOCX, PPT/PPTX, and PDF
  but not Markdown, standalone images, or VLM; local PaddleOCR plus one-click private
  deployment is required; same-SHA sources reuse by
  default; encrypted documents use transient passwords; and DOC PDF-vs-DOCX selection
  follows an agreed fidelity spike.
- The first split workstream now defines import as source snapshot through
  **canonical-ready** publication. Chunking, embeddings, indexes, and Agent exposure
  are intentionally deferred so their storage/tool decisions do not leak into the
  import contract.
- Workstream 02 is being reset around a retrieval-first model: start with the query
  contract and the knowledge units it needs to return, then choose persistence and
  indexing mechanisms. Its earlier media-first draft is superseded; no physical
  storage topology, retention policy, or dependency is approved by this packet.
- Related evidence and exact source anchors are in
  [evidence/current-architecture.md](evidence/current-architecture.md).

## Next Step

Continue discussion and contract reconciliation in the
[follow-up packet](../knowledge-base-follow-up/README.md). Repair implementation may
begin only after that packet produces a reviewed repair preplay and Impact Handshake.

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
