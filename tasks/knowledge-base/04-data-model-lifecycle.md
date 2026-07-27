# Metadata, Files, and Lifecycle

## Current Boundary

Import publishes immutable canonical-ready identity; independent derivation publishes
bounded retrieval Units/FTS readiness; semantic lookup may publish a rebuildable
Lance generation. SQLite owns mutable lifecycle/current pointers and Unit text. The
filesystem owns source/canonical CAS and vector bytes. This follows the retrieval-
first decision recorded in Workstream 02.

## Minimum Metadata Semantics

| Concept | Purpose | Must not contain |
| --- | --- | --- |
| internal `knowledge_library` | One stable global default library in MVP; future extension anchor | user-visible multi-library UI state/full content |
| `knowledge_document` | Stable logical document and current canonical generation pointer | raw source bytes/Docling JSON/chunks |
| `knowledge_import` | One queued/running/terminal immutable attempt, phase/error/retry lineage | passwords, provider response body, parser output |
| canonical generation descriptor | Envelope/Docling/asset hashes and versioned locator | full Docling JSON or images |
| source artifact relation | Stable registered snapshot identity | raw local source path in UI/tool fields |

The import boundary does not decide the eventual retrieval store. The import runner
and its storage ports decide transaction/migration shape only after an Impact
Handshake; UI code cannot infer or write this state.

## Immutable Files

The conceptual relationship is deliberately more important than a path spelling:

```text
stable source snapshot (registered artifact)
    └── document / canonical generation
          ├── canonical-document-envelope.json
          ├── docling-document.json
          ├── referenced assets / OCR projections / sidecar locators
          └── checksummed manifest
```

Source snapshots belong outside movable generation staging so an `ArtifactService`
registration never points at a path later atomically renamed/deleted. Canonical output
uses Docling JSON with referenced app-owned assets, not embedded base64 blobs or
absolute/provider URLs. The exact knowledge root and retention policy are storage
workstream decisions.

## Atomic Publication and Recovery

1. Create a durable attempt and private staging authority.
2. Copy/hash user bytes into a stable app-owned source snapshot.
3. Register the snapshot as an artifact only after it has a final stable location.
4. Probe, normalize, route, parse, and write Docling/envelope/assets beneath staging.
5. Validate containment, manifests, checksums, source/IR descriptors, and envelope.
6. Atomically promote filesystem output, then advance the document canonical pointer
   in the metadata transaction.
7. On restart, resume only a complete matching checkpoint; otherwise clean derived
   staging and preserve source/attempt history for retry.

Retry/reparse creates a new immutable generation. Cancellation keeps the stable source
snapshot, removes unpublished derived staging at a safe boundary, and never overwrites
a prior canonical-ready generation.

## Derivation and Storage Resolution

[Workstream 02](workstreams/02-storage/README.md) now owns the implemented contract:

- `knowledge_unit` rows are bounded passages tied to one current canonical
  generation; page provenance becomes `page N`, otherwise `passage N`;
- FTS5 is a derived SQLite projection over Chinese-pretokenized Unit text;
- LanceDB stores immutable `unit_id -> vector` generations bound by SQLite/manifest
  corpus and Embedding-profile fingerprints;
- canonical-ready and retrieval-ready remain separate transitions; and
- cleanup reclaims only proven staging/orphans. Bounded retention of superseded
  healthy Lance generations remains an explicit performance/space follow-up.

These decisions consume the immutable envelope/Docling contract and do not force the
importer to write Units, embeddings, or indexes.
