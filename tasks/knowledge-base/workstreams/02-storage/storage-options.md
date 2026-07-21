# Storage Policy Decision and Technology Consequences

## The Decision Is About Searchable Text, Not Source Files

Raw user bytes, Docling JSON, images, and provider payloads should remain outside a
general application database. The unresolved question is narrower and more important:

> May the normalized text of small Knowledge Units—and the keyword index over it—be
> persisted in SQLite because it exists specifically to support local lookup?

Current durable storage guidance permits bounded, queryable application state. The
earlier task-packet phrase “SQLite metadata only” is stricter, but it has not yet been
established as a product policy. These are two genuinely different designs.

## Option A — Strict Metadata-Only SQLite

SQLite stores document/unit IDs, source anchors, filters, and index health only.
Knowledge Unit text, lexical postings, and vectors live in a dedicated local retrieval
store or sidecar files.

This preserves the earlier strict boundary, but the MVP must then own or adopt a
separate keyword engine and its CJK tokenization, update, deletion, and packaging
behavior. It is not automatically simpler merely because raw document files already
live on disk.

## Option B — SQLite Holds Bounded Retrieval Corpus

SQLite stores normalized small Knowledge Units plus a local full-text index; raw
documents, canonical IR, images, and vector bulk data remain outside. This puts the
data next to the access pattern it serves: keyword filtering, exact phrases, snippets,
and unit/document joins. SQLite FTS5 is a plausible implementation candidate, but its
default tokenizer is not proof of acceptable Chinese retrieval quality and packaging
must still be tested.

This is the simplest likely MVP path **if Sir confirms that the original
metadata-only rule is a preference rather than a hard policy**. It is not permission
to put arbitrary PDFs, Docling JSON, images, or unlimited content into SQLite.

## Semantic Retrieval Is a Separate Choice

Semantic lookup needs a vector for each Knowledge Unit, a profile descriptor
(provider/model/revision/dimension/metric/normalization), and a candidate-search
method. It does not require choosing an ANN engine at the start:

- keyword retrieval should remain usable with no embedding profile configured;
- a small corpus can use exact vector comparison as the quality baseline;
- sqlite-vec, HNSW, FAISS, or an external vector service become evidence-driven
  implementation choices, not the domain model; and
- hybrid lookup merges candidates by a transparent policy such as reciprocal-rank
  fusion, then retrieves the actual unit and source anchor.

## Recommendation Pending Sir's Answer

Do not select a media layout yet. First decide Option A versus Option B. My default
recommendation is **Option B**, narrowly scoped to bounded normalized retrieval units
and keyword indexing, because the product goal is retrieval and the existing project
does not impose a blanket text-in-SQLite ban. If the strict policy reflects a privacy,
backup, or product commitment, choose Option A deliberately and budget for a real
local search-store implementation.
