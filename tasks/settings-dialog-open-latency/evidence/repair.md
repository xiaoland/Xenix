# Repair Evidence

Date: 2026-07-29

## Implemented Boundary

`SettingsDialog` now owns only the UI projection, scheduling policy, and
interest in one request:

```text
showEvent returns
  -> cached/checking state is paintable
  -> zero-delay timer creates a KnowledgeIndexStatusRequest bridge
    -> KnowledgeIndexService.request_status submits to its one-query executor
      -> active text-vector task: fast `building` projection
      -> otherwise: semantic and LanceDB generation-integrity validation
    -> request-identity + generation-matched result returns through an explicit
       queued Qt connection
      -> cached state is rendered
      -> another read is scheduled only while a rebuild is queued/running
```

The rebuild mutation worker and status query executor are separate
`KnowledgeIndexService` lanes. This preserves observable `running/building`
state while preventing either a queued rebuild or a deep status read from
starving the other through one FIFO. Physical vector publication and inspection
remain serialized by the vector-store lifecycle boundary.

The dialog permits one status request at a time. Hiding or closing it increments
the lifecycle generation, stops polling, and cancels queued interest without
waiting for a running read. Request identity prevents an old completion from
clearing a newer request. Application shutdown closes query admission, cancels
queued reads, and makes `KnowledgeIndexService` quiesce its running status lane
before SettingsStore or SQLAlchemy ownership is released.

No vector-store, SettingsStore, AMD, provider, or persistence contract was
changed. `KnowledgeIndexService` gained the asynchronous query port and an
active-vector-task fast projection; its idle deep check and rebuild publication
integrity check remain intact.

## Direct UI Probes

A deliberately blocked status implementation proved first-paint behavior:

| Observation | Result |
| --- | ---: |
| Dialog construction | `0.012640 s` |
| `show()` return | `0.002072 s` |
| Visible while status remained blocked | `true` |
| Status executed outside the GUI thread | `true` |
| Calls during first activation | `1` |

A hide/reopen sequence held the first generation open while requesting the
second:

- calls: `2`
- maximum in flight: `1`
- old result rendered: `false`
- final current-generation state: `ready`

## Real Runtime Timing

An isolated runtime used an SQLite online backup plus the current Knowledge
vector generation and provider settings. `start_worker=False` disabled only the
mutation worker; the service-owned status lane deliberately remains available.

| Segment | Elapsed |
| --- | ---: |
| Settings dialog construction | `0.034272 s` |
| `show()` return | `0.002908 s` |
| Idle deep status read on query lane | `2.573765 s` |

The dialog was visible with `Checking Knowledge index status` when `show()`
returned, and the actual status completed successfully in the background. This
final-architecture run confirms that mutation-worker availability is not coupled
to query availability. A prior cold run measured the same idle deep operation at
`6.829751 s`, directly reproducing the user's `5–8 s` range without assigning it
to the GUI thread.

One earlier full-application probe timed out without producing admissible timing
output because unrelated runtime teardown did not finish. Its exact project
processes were terminated and its temporary runtime was deleted; it is not used
as evidence above.

Every isolated runtime that copied provider configuration was permanently
deleted after use. The source development runtime was not modified.

## Automated Verification

- Focused Settings, service-topology, and embedding regression: `7 passed`
- Full repository manifest: `51 passed`
- `pdm run check`: passed
- `pdm run smoke`: passed
- English translations: `420 finished`, `0 unfinished`
- Simplified Chinese translations: `420 finished`, `0 unfinished`

The service-level regressions prove that a status request observes
`running/building` while a real rebuild worker is blocked, does not invoke the
deep vector inspection in that state, remains available when the mutation
worker is disabled, and cannot outlive service shutdown. UI regressions prove
first paint, single-flight generation fencing, explicit queued delivery, and
non-blocking dialog shutdown.

The previously persisted headed benchmark reports remain the broader real
MainWindow end-to-end proof. They do not open Settings; the focused UI and
service tests cover the repaired first-paint and lifecycle contracts directly.
