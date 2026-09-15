# ML Task Lifecycle

## Admission

Agent tools, ML services, persistence, execution workers, and UI projections depend
on one task identity, lifecycle, placement, and finalization contract. Losing it can
make status, results, or canonical ownership disagree across units.

This contract governs persisted ML work, not task packets under `tasks/`.

## Identity and Authority

- Each accepted operation has a stable task id and individually addressable state.
- Training inputs use an immutable dataset role-binding snapshot. Services expand
  stable references into the execution request before dispatch.
- A trained analyzer is the aggregate for its canonical apply artifact, role
  contract, evaluation work, and final metrics. Consumers do not reconstruct that
  relationship by scanning unrelated dataset tasks.
- For supervised work, holdout evidence belongs to the split-trained evaluation
  artifact. The canonical apply artifact may be refit on all eligible rows and must
  not inherit an unsupported holdout-performance claim.
- New grouped supervised evaluation derives its partition seed from source content, not the transient Dataset id assigned on import. Retained task policies keep their original partition semantics when earlier analyzers are evaluated again.
- New multilingual text classification uses grouped out-of-fold evidence for selection. Its evaluation artifact contains predictions from models fitted without the respective validation groups; the canonical apply model is refit on all eligible rows. Incomplete validation is reported explicitly and does not inherit a score from its successful subset. Agent-selected preparation is retained with the analyzer, independently of any preceding business Dataset transformation.

Exact task fields, operation enums, model taxonomy, and persistence shapes are owned
by source, schemas, and tests.

## Lifecycle and Placement

The shared semantic progression is:

```text
pending -> running -> succeeded | failed | cancelled
pending -> cancelled
```

- `succeeded` means every declared canonical output is locally present and ready.
- `failed` means the operation did not produce all required outputs.
- `cancelled` means cancellation control stopped accepted work before success.
- Services choose the local or SSH worker. Agent tool inputs do not select workers,
  and placement does not change task identity or lifecycle states.
- Worker or remote-command failure fails the task. Automatic failover is outside the
  current contract.

## Result and Failure Contract

- Completed Agent train, tune, and apply results deliver their public output references directly, including finalized Dataset identifiers and Artifact links. Apply also delivers the generated column names and types. Consumers can use these outputs without querying the task again. Worker result schemas describe execution output, not the richer service-finalized result; tool adapters must preserve finalization facts. Task queries remain available for pending work and additional details.

- Text-discovery evaluation recomputes metrics from the retained analyzer and source Dataset. FIT diagnostics are historical evidence, not an exact-equality gate for new metrics; the source snapshot and evidence type must still match.
- Remote directories are execution/cache state. Results become authoritative only
  after they are downloaded, normalized, finalized locally, and registered by the
  owning service.
- Terminal metadata preserves enough identity, status, result references, and error
  summary for later review independently of the originating conversation.
- User-relevant task logs remain available through the ML task service. Log file
  layout and application-log rotation belong to source and Deployment.
- Failure detail is actionable and may include bounded worker/setup diagnostics,
  but never SSH credentials or private-key material.
- Synchronous train, tune and apply waits include the persisted task error summary when reporting a failed terminal task. The originating Tool caller should not need an additional status query to learn why execution failed.
- User-openable outputs follow the [artifact link contract](artifact-links.md);
  storage medium and deletion follow [storage ownership](storage-ownership.md).

## Verification

Lifecycle and placement coverage lives in `tests/ml/test_ml_execution.py`, the
ML engine/service tests under `tests/ml/`, and the end-to-end Agent paths under
`tests/e2e/agent_harness/`. Persistence mechanics are covered by the repository
and migration tests under `tests/storage/`.
