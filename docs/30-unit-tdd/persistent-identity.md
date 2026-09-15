# Persistent Object Identity

The [storage boundary](../20-prd-tdd/storage-ownership.md) owns the public identity contract; this page explains allocation and state evolution. Exact tables and migration versions remain source truth.

## Allocation

All application-owned business records draw from one SQLite integer sequence. A shared sequence avoids presenting unrelated objects with the same number and gives Tools, UI and records the same identity without an alias lookup. It is local to one runtime database, not a cross-installation identity service.

Ordinary ORM inserts receive their ID on flush through the current transaction's connection. Repositories flush before returning a newly created record. When an ID must escape before the record transaction finishes—such as a staged ToolCall, worker request or import file path—the service reserves and commits it first. Reservations leave gaps when work is abandoned; deleting a record never rewinds the sequence. Allocation must not open another write transaction from inside an active write transaction.

Dataset derivations share the Dataset's identity; paged Tool results reuse their reserved ToolCall identity. These dependent records do not need a second independently allocated handle. Provider call IDs, client submission keys, model keys, installation diagnostics, content fingerprints and temporary file names retain their own representations.

Services and canonical JSON carry integers. URI/path construction, Markdown and display widgets convert them to decimal text at their boundaries; an Artifact URI therefore looks like `artifact://42`. Qt signals carrying persisted IDs use Python objects to avoid a 32-bit Qt integer truncating a SQLite identity. Ephemeral UI event keys remain separate presentation values.

## Existing state

The forward migration builds an in-memory mapping for existing primary keys and references, recreates their SQLite columns as integers, and rewrites persisted relationships, JSON, conversation references, and Artifact links. No UUID alias table or runtime fallback remains. Opaque registered dataset paths remain valid; directories addressed through an object's ID move to decimal names.

Managed task, model and apply directories and Knowledge canonical bundles are copied before SQLite publishes their new references. Canonical envelopes receive integer identities and updated content-addressed paths; source content remains unchanged. Knowledge Units keep their text and receive persistent numbers. Vector generations become stale and rebuild from those Units; corpus fingerprints include ordered Unit identities without loading their text bodies during status queries.

Historical ML snapshots retain their sampling fingerprint so changing an object's ID cannot reshuffle an existing evaluation split. Current content validation compares the snapshot's Dataset and content fields independently of that retained seed. Copied text analyzer binaries receive integer resource references while retaining learned weights, vocabulary and historical preparation digests. Historical usage journals remap known conversation correlation hashes while preserving recorded token counts.

Migration and restart operations follow [Local state evolution](../40-deployment/local-state-evolution.md). The migration does not make an unavailable source file readable or repair an originally incorrect Artifact link.
