# Product TDD

Product TDD owns only technical contracts that multiple units must share to
preserve authority, topology, or compatibility. Source, schemas, configuration,
and tests remain authoritative for fields, enums, tool inventories, limits,
libraries, and other mechanically enforceable facts.

## Authority and Topology

The stable dependency direction is:

```text
UI -> services -> adapters and persistence
```

- UI collects intent and renders service results. It does not define business
  state, construct storage paths, or bypass services to operate on persisted data.
- Services own workflow semantics, validation, orchestration, and the coordination
  of SQLite records with filesystem artifacts.
- Agent Harness owns conversation and provider/tool orchestration. Data, artifact,
  and ML services retain their domain authority.
- Adapters own provider, filesystem, database, and ML execution mechanics without
  becoming product-state authorities.
- SSH workers provide execution and cache capacity. Successful remote work is
  finalized into local service-owned state and artifacts.

Internal invariants of Agent Harness and Chatbot UI belong in
[Unit TDD](../30-unit-tdd/README.md). Runtime paths, setup, migration,
observability, and recovery belong in [Deployment](../40-deployment/README.md).

## Contract Routes

| Contract | Dependent units | Failure if lost |
| --- | --- | --- |
| [Storage ownership](storage-ownership.md) | Services, persistence, Agent, data, artifact, and ML | State and bytes acquire competing authorities or unsafe deletion behavior. |
| [Artifact links](artifact-links.md) | Producing services, Agent Harness, Chatbot UI, LinkRouter, and ArtifactService | Dataset ids, artifact ids, or local paths become interchangeable and unsafe. |
| [ML task lifecycle](ml-task-lifecycle.md) | Agent tools, ML services, persistence, workers, and UI | Task state, placement, finalization, and result ownership diverge. |
| [Architecture decisions](adr/README.md) | Units affected by each accepted decision | Rationale and compatibility consequences are lost or silently rewritten. |

## Verification

Use the contract-specific source and test anchors named by each document. Run the
smallest focused checks that prove the affected boundary; use `pdm run test` when
the blast radius is repository-wide or uncertain.
