# Implementation Preplay

> **Post-implementation audit, 2026-07-21:** the implementation diverged materially
> from this preplay and from related Unit/Product TDD. In particular, the import
> boundary absorbed retrieval publication, UI daemon threads became the runner, and
> migration/package proof was insufficient. See the
> [follow-up compliance audit](../knowledge-base-follow-up/compliance-audit.md).
> This document remains design history, not evidence of current conformance. The
> [Phase C–G closeout](../knowledge-base-follow-up/slices/01-phases-c-g-closeout.md)
> records the reconciled implementation and global review.

## Vertical Slice 1 — Retrieval Before Parsers

1. Add schema v16 for `knowledge_document`, `knowledge_unit`, and an FTS5 projection.
   Store current bounded unit text and locators in SQLite; keep a hidden global
   `library_id` seam.
2. Add a Knowledge service that indexes already-normalized text and performs safe CJK
   keyword lookup. Chinese query/document pre-tokenization uses `jieba`; FTS is a
   derived candidate path and rows are revalidated against current units.
3. Register one bounded `knowledge.lookup` Tool. The reconciled contract accepts only
   `query/mode?` and returns `mode/results[{source, location?, excerpt}]`.
4. Integrate knowledge-evidence use into the three data Skills; no standalone
   Knowledge Skill or authorization switch remains.
5. Extend benchmark setup through public product services and make the rainy-season
   case pass. Keep existing cases and offline defaults unchanged.

## Vertical Slice 2 — Import and Canonical CAS

Add FileProbe, FormatNormalizer, ParserRouter, Parse, and Canonicalizer around Docling.
TXT is decoded/normalized directly; DOCX/PDF/JPEG/PNG use registered Docling/image
routes; DOC uses the spike-selected DOCX converter capability. Publish
source bytes and compressed Docling JSON through staging into an app-owned
content-addressed store.

## Vertical Slice 3 — Local OCR and Full Format Gate

Add a locally managed PaddleOCR sidecar with one-click install, pinned runtime/model
manifest, hashes, health probe, progress, retry, and uninstall. Route PDF pages by
page-level probe, preserving locators through OCR/Docling canonicalization. Verify all
six promised extensions with packaged Windows smoke coverage.

## Vertical Slice 4 — Semantic/Hybrid

Only after an embedding profile and target-corpus measurements exist, project current
units into LanceDB and fuse vector candidate IDs with SQLite FTS candidates. LanceDB
is rebuildable and never authoritative.

## Impact Handshake for Slice 1

- State diff: schema 15 becomes 16; fresh and upgraded databases gain knowledge rows
  and FTS projection. No existing Dataset/Artifact identities change.
- Files: storage models/migration/repository, Knowledge service, Agent composition and
  tool registration, Skill source/generated catalog, benchmark contracts/runner/case,
  focused tests, and task/durable docs.
- Blast radius: local database initialization, headless Agent composition, tool scope,
  benchmark discovery, and packaging dependency graph.
- Invariants: Knowledge is off unless the canonical conversation scope enables it;
  Skill activation cannot grant authority; ToolResults stay under 64 KiB; no raw path;
  fresh/upgrade schema both work; existing Agent benchmarks remain unchanged.
- Verification: migration tests, CJK retrieval tests, tool enable/disable and replay
  tests, Skill catalog tests, benchmark-infra tests, live rainy-season matrix, project
  check, and packaged smoke when dependencies change.

No commit is included without Sir's explicit command.
