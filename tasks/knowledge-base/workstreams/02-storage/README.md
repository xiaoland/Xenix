# Knowledge Base — Retrieval Storage Workstream Packet

## Objective & Hypothesis

Define the smallest persistent information model that lets the later Agent lookup
reliably return relevant, bounded, source-linked knowledge from imported documents.
The hypothesis is that storage begins with the lookup result—not with a database,
filesystem, or recovery protocol:

```text
query + mode + optional document filter
  -> small set of Knowledge Units
  -> quote + source anchor + relevance explanation
```

For this MVP, a Knowledge Unit is a searchable passage/table-derived text unit from
an imported document. The workstream does not expand scope to Xenix conversations,
datasets, models, logs, a general knowledge graph, or automatically inferred facts.

## Status

**Keyword MVP implemented and integrated.** The 2026-07-14 media-first
storage draft was removed because it made recoverability/auditability and physical
media the primary design axis. The current packet starts from content and retrieval
purpose. Sir has supplied a promising candidate stack; its evaluated, conditional
position is recorded below. SQLite stores current searchable units and FTS5 is the
guaranteed access path. Semantic/LanceDB remains gated by a separate quality and
packaging spike.

## Durable Owners / Blast Radius

| Claim | Intended durable owner when approved | Main affected surfaces |
| --- | --- | --- |
| Retrieval-unit catalog and query semantics | Knowledge Base service / cross-unit contract | SQLModel rows, repositories, derivation, lookup service |
| Source anchor and citation identity | Import + Agent-tool contracts | Docling locators, ArtifactService activation, replay/UI |
| Keyword/semantic projection implementation | Retrieval runtime | package/runtime, background work, performance tests |
| Physical placement of searchable text/indexes | Storage ownership decision | SQLite policy, filesystem layout, backup/delete behavior |
| Tool schema and enabled scope | Later Agent-tool workstream | Harness, ToolScope, provider exposure, typed citation UI |

## State Diff (From -> To)

**From:** documents can become canonical-ready, but there is no defined retrieval
corpus, searchable unit, source anchor, invalidation policy, or lookup-ready state.

**To:** every searchable imported document contributes current Knowledge
Units. Each unit contains the normalized text needed for a bounded quote and a source
anchor needed to reopen/cite the relevant document location. Keyword and semantic
representations are derived access paths over those units, not the definition of the
knowledge itself.

## Invariants

- The user-visible contract is retrieval: return relevant units, bounded quotes, and
  honest source anchors. Recovery/audit features may support this but are not MVP
  drivers.
- Original source bytes, DoclingDocument IR, images, and OCR payloads are not copied
  into a generic search record. They remain Import-owned source material.
- A Knowledge Unit binds to one current document/canonical revision and a precise
  page/section/item locator. It is never a free-floating generated assertion.
- Keyword indexes, embeddings, ranks, snippets, and index-health state are derived
  and rebuildable. They may not become a second authority for document content.
- A source change/removal must invalidate or remove affected units predictably;
  lookup must not silently return stale text as current.
- The one global MVP Library stays an internal scope key. No multi-library UI or
  source expansion is implied.
- No raw local paths, credentials, raw provider payloads, full documents, or index
  dumps cross the later Agent-tool boundary.

## Decisions Consumed

- MVP imports TXT, DOC, DOCX, PPT, PPTX, and PDF, and Import ends at
  canonical-ready DoclingDocument/envelope output.
- MVP exposes one global Library with future multi-library extension space.
- Lookup will support keyword, semantic, and hybrid modes through an Agent tool.
- Source opening remains through `ArtifactService`/`artifact://`; a locator is not an
  external local path.
- OCR/embedding are independent document-AI capabilities; VLM and Markdown remain
  out of MVP.
- Sir's 2026-07-15 correction: model this workstream by **what is stored and why**,
  with **retrievability** as MVP's primary goal.

## Retrieval-driven decisions

1. SQLite owns the current searchable Knowledge Unit catalog, including bounded
   normalized display text, source locator, and pre-tokenized FTS text. This is
   business/search state, not a large-object leak.
2. MVP units are hierarchy-aware passages plus table-derived row/group text. OCR text
   uses the same unit contract and retains page/geometry locators.
3. Keyword retrieval is the guaranteed baseline. Semantic/hybrid activates only when
   a compatible embedding profile and vector projection are ready.
4. Reimport/removal immediately excludes old units from new lookup. Already persisted
   bounded ToolResults remain historical conversation evidence.
5. The atomic tool accepts query plus optional document IDs and a bounded top-k; type,
   date, tags, labels, retrieval mode, and library selection are not MVP inputs.

## Verification Plan

- Define test queries and expected unit/quote/anchor results before choosing an index
  engine; include Chinese, mixed-language, short exact terms, section concepts,
  tables, and OCR-derived text.
- Prove an imported canonical document creates retrievable units with valid source
  locators, and a document update/removal invalidates them correctly.
- Prove keyword lookup works without embedding availability; verify semantic/hybrid
  only against an explicit compatible embedding profile.
- Measure recall, P95 latency, memory, indexing time, and package behavior on a real
  target corpus before accepting native ANN/vector infrastructure.
- Before code, resolve searchable-text placement and the later ToolScope enabled/off
  contract; current Harness behavior would otherwise advertise a new registered tool
  by default.

## Verification Run Log

- 2026-07-15: read-only repository and contract review found that project-level
  storage guidance permits bounded, queryable SQLite state; it does not itself ban
  all text. Current conversation/tool payloads already contain bounded text in
  SQLite. The prior no-chunk-text rule was task-packet direction, not implemented
  project truth.
- 2026-07-15: local development SQLite reports FTS5 availability, but that alone
  does not establish Chinese-tokenization quality or PyInstaller support. No FTS or
  vector capability is selected by this packet.

## Next Action

Add refresh/removal semantics and enable semantic projection only after it improves
the benchmark corpus and passes Windows packaging. LanceDB remains a gated derived
projection, never a prerequisite for useful keyword lookup.

## Packet Map

- [Retrieval-first information model](retrieval-model.md)
- [Storage-policy decision and technology consequences](storage-options.md)
- [Candidate stack evaluation and flow](candidate-stack-evaluation.md)
- [Reframing decision register](reframe-register.md)
