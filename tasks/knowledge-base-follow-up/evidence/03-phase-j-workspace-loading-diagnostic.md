# Slice 03 Phase J — Workspace Loading Diagnosis

**Date:** 2026-07-23
**Mutation:** task packet only; product code unchanged
**Follow-up:** Phase J is now implemented and locally accepted; see
[Phase J/K implementation evidence](03-phase-j-k-implementation.md).

## Observed sequence

```text
construct/retranslate
  -> empty-state text = "No Knowledge documents yet"
show
  -> start one background Workspace snapshot
       -> list documents
       -> summarize tasks
       -> read/verify OCR status
       -> inspect keyword/vector index status
            -> cold LanceDB/PyArrow load + strict generation verification
  -> emit aggregate
  -> render document rows and footer together
```

The shell itself opens asynchronously, but the visible document result is coupled to
the slowest optional status leaf. Before the aggregate arrives, the body claims the
Library is empty even though emptiness is not yet known.

## Read-only timing evidence

The current user database and vector generation were opened through a read-only
SQLite session. No provider request was made.

| Operation | Elapsed | Result |
| --- | ---: | --- |
| list documents | 17.53 ms | 1 document |
| summarize tasks | 6.75 ms | 4 recent tasks |
| OCR status snapshot | 2.34 ms | ready |
| index status, cold | 2168.22 ms | keyword ready / vector ready |
| aggregate snapshot after warm-up | 100.90 ms | 1 document |

The cold index read is expected to remain strict: it validates current projection
identity and the immutable Lance generation. The defect is that this footer concern
controls document viewport latency.

## Structural repair direction

The Workspace presentation boundary should expose two independently completable
read models:

```text
document list query -> document viewport state
status query        -> footer state
```

They do not become competing business authorities. Document lifecycle stays in the
Knowledge repository; OCR/index/task services retain their own truth; the Workspace
service only composes bounded DTOs for their respective visual consumers.

The document viewport owns explicit `cold`, `loading`, `ready`, `empty`, and
`unavailable` presentation states. Initial loading is visible. A refresh preserves
the last successful list until the replacement arrives. Footer loading/failure
cannot blank or delay documents.

## Missing acceptance today

The existing shell test proves only that the window appears in under 0.5 seconds
while a monolithic snapshot blocks. It does not assert the visible initial body
state, nor prove that document rows render before a blocked index/OCR status. Phase J
adds those black-box UI contracts before implementation.
