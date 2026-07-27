# Knowledge Base — Retrieval Storage Workstream Packet

## Objective

Store exactly what `knowledge.lookup` needs to find and return useful evidence. The
MVP driver is **retrievability**: persistence and indexes serve current bounded
Knowledge Units; recovery and audit mechanics are supporting constraints, not the
product objective.

```text
query + mode
  -> current bounded Knowledge Units
  -> small {source, location?, excerpt} results
```

## Status

**Locally implemented and reconciled by follow-up Slice 01.** SQLite owns current
document/readiness state and Unit text; SQLite FTS5 owns keyword projection; LanceDB
owns only immutable rebuildable vectors. Source/canonical bytes remain in the
Import-owned content-addressed store. The live real-provider Agent outcome passes;
the active global review now owns the vector build/status snapshot finding.

## What Is Stored, and Why

| Content/state | Owner | Retrieval purpose |
| --- | --- | --- |
| Source snapshot | local SHA-256 CAS + Artifact identity | preserve/open the exact imported source without leaking paths |
| Canonical content | immutable DoclingDocument bundle + envelope, Zstandard-compressed | reproduce the content/provenance from which Units are derived |
| Document/current-generation/readiness metadata | SQLite | exclude stale generations and decide whether a document is searchable |
| Bounded Unit display text, FTS text, source title, locator | SQLite | keyword ranking and final bounded evidence projection |
| FTS5 index | SQLite derived table | guaranteed Chinese-pretokenized keyword lookup |
| Unit vectors | immutable LanceDB generation | semantic candidate ranking without becoming content authority |
| Corpus/profile/generation binding | SQLite metadata + bounded Lance manifest | reject stale, partial, wrong-model, wrong-library, or corrupt vector projections |

## Invariants

- A Unit belongs to one document and canonical generation. Retrieval resolves only
  Units from the document's current retrieval generation.
- Unit content is independently bounded before both SQLite publication and Embedding
  transmission. Unicode normalization expansion cannot cross the provider bound.
- Page provenance produces `page N`; non-page material produces an honest
  `passage N`. Raw paths and opaque storage locators never cross the Tool.
- Keyword, semantic, hybrid, and auto are real modes. Explicit unavailable semantic/
  hybrid calls fail; `auto` falls back only for expected semantic unavailability and
  reports the mode actually used.
- SQLite Units are content authority. FTS, vectors, scores, snippets, ranks, and
  generation directories are derived and rebuildable.
- Reimport/removal changes the current SQLite fingerprint immediately. A stale Lance
  generation cannot remain eligible merely because its files still exist.
- One hidden stable `library_id` scopes every row/generation, preserving a future
  multiple-library extension while MVP exposes only the global Library.

## Retrieval and Publication Topology

```text
immutable canonical-ready generation
  -> KnowledgeDerivationService
  -> bounded Units + FTS in one SQLite publication
  -> document retrieval_generation_id becomes current

semantic-capable lookup
  -> freeze independent Embedding operation/settings
  -> fingerprint current SQLite corpus
  -> reuse or build/validate/atomically publish immutable Lance generation
  -> exact cosine candidate Unit IDs
  -> re-resolve and revalidate current SQLite Units

hybrid
  -> SQLite FTS rank + Lance cosine rank
  -> deterministic reciprocal-rank fusion
  -> bounded current Unit matches
```

Import has no Embedding or LanceDB dependency. Production `KnowledgeService` is
read-only; only derivation writes Units. Tests that need a small isolated corpus use
an explicitly named test seeder, while integration/benchmark preparation uses the
real Import→Canonical→Derivation path.

## Technology Decisions

- SQLite WAL plus the existing storage/session authority handles business state.
- SQLite FTS5 with Chinese pre-tokenization is the always-available lexical path.
- LanceDB OSS exact-flat cosine is sufficient for the MVP corpus; ANN requires
  measured scale/latency evidence.
- Staging + atomic rename publishes immutable filesystem generations.
- Integrity cleanup removes proven orphan/staging objects and never treats derived
  files as authority.

## Verification

- Fresh and fixed historical migration edges through schema v20, including FK/FTS/
  ORM readability and deterministic duplicate-attempt repair.
- Chinese/mixed keyword, lexical-miss semantic-hit, deterministic RRF, explicit
  unavailability, malformed provider output, stale/corrupt generation, concurrent
  corpus change, multi-library isolation, and Unicode-expansion bounds.
- Import→canonical→derivation continuity, removal/current-generation exclusion,
  query-centered excerpts, and page/passage locations.
- Real Lance write/close/rename/reopen/search in development and frozen packaged
  smoke.

## Explicit Follow-ups

- Add hierarchy-aware neighboring context and richer table/OCR grouping only after
  labelled retrieval evaluation.
- Add bounded retention for superseded healthy Lance generations; current cleanup
  safely reclaims proven orphans and stale staging only.

## Packet Map

- [Retrieval-first information model](retrieval-model.md)
- [Storage-policy decision and technology consequences](storage-options.md)
- [Candidate stack evaluation and flow](candidate-stack-evaluation.md)
- [Reframing decision register](reframe-register.md)
- [Follow-up compliance/closeout](../../../knowledge-base-follow-up/README.md)
