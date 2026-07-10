# Xenix Native

Xenix Native is a desktop machine-learning workbench for non-technical business users. Product scope and vocabulary are owned by `docs/10-prd/`.

## Repository Map

- `src/xenix/ui/`: Qt Widgets UI
- `src/xenix/services/`: service and orchestration boundaries
- `src/xenix/services/storage/`: SQLite models, repositories, migrations, and storage layout
- `src/xenix/services/ml/`: native ML execution, registry, and adapters
- `tests/`: automated verification
- `scripts/`: development and packaging helpers
- `docs/`: durable project knowledge
- `tasks/`: disposable agent workspaces
- `ml/`: legacy model scripts; leave intact unless a task explicitly targets migration or deletion

Dependency and Python-version constraints are authoritative in `pyproject.toml`. Runtime paths, packaging, and recovery procedures are owned by `docs/40-deployment/`.

## Instruction Scope

- This file applies to the whole repository.
- A nearer `AGENTS.md` adds rules for its physical subtree. It does not silently cancel parent rules.
- Local guidance must not claim sibling or out-of-tree scope. Put shared guidance at the nearest common ancestor or in the owning durable document.
- Local `AGENTS.md` files own current editing constraints, seam hazards, and required verification. They do not duplicate product, architecture, or runtime truth.
- If parent and child guidance conflict, stop and resolve the conflict before mutation.

## Knowledge Owners

Each durable claim has one canonical owner. Other documents should link to that owner instead of copying the claim.

| Concern | Canonical owner |
| --- | --- |
| Product behavior, scope, and business vocabulary | [`docs/10-prd/`](docs/10-prd/README.md) |
| Cross-unit architecture, authority, and technical contracts | [`docs/20-product-tdd/`](docs/20-product-tdd/README.md) |
| Accepted or superseded product-level technical decisions | [`docs/20-product-tdd/adr/`](docs/20-product-tdd/adr/README.md) |
| Expensive-to-rediscover invariants of a complex local unit | [`docs/30-unit-tdd/`](docs/30-unit-tdd/README.md) |
| Runtime, packaging, observability, migration operations, and recovery | [`docs/40-deployment/`](docs/40-deployment/README.md) |
| Human contributor workflow and testing policy | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Non-trivial implementation judgment | [`docs/00-meta/implementation-taste.md`](docs/00-meta/implementation-taste.md) |
| Volatile reasoning, evidence, and temporary artifacts | `tasks/<task-slug>/` |

Fast-changing versions, enumerations, configuration defaults, and schema identifiers should be authoritative in source, configuration, or tests. Durable docs explain their contract and operational meaning without creating parallel snapshots.

### High-Risk Entry Points

| Surface | Required entry |
| --- | --- |
| Storage models, repositories, or migrations | nearest service guidance, [`local-state-evolution.md`](docs/40-deployment/local-state-evolution.md), then storage source and migration tests |
| Packaging, runtime resources, or app-home behavior | [`development.md`](docs/40-deployment/development.md) and, when state layout changes, [`runtime-state.md`](docs/40-deployment/runtime-state.md) |
| Agent Harness, tool schemas, provider loop, or message lifecycle | nearest service guidance and [`agent-harness.md`](docs/30-unit-tdd/agent-harness.md) |
| ML task lifecycle or worker placement | nearest ML guidance and [`ml-task-lifecycle.md`](docs/20-product-tdd/ml-task-lifecycle.md); load ADR 0005 only when changing the SSH-worker decision |
| Chatbot interaction or rendering contract | nearest UI guidance and [`chatbot-ui.md`](docs/30-unit-tdd/chatbot-ui.md) when behavior, not presentation alone, changes |

## Working Model

Use the input labels as lenses, not mutually exclusive buckets:

- `Intent`: desired product behavior, scope, or policy. Settle the PRD claim before downstream realization.
- `Constraint`: a technical, dependency, governance, packaging, performance, or environment boundary. Route it to the affected technical, deployment, or repository owner without rewriting product intent.
- `Reality`: observed behavior differs from expectation. Gather evidence before mutation, then update the owner revealed by the cause.
- `Artifact`: the requested result is a bounded script, report, helper, or other one-off output. Keep it local unless the request also changes durable truth.

Choose the posture for the current slice:

- `Explore`: map unknowns and alternatives; durable surfaces stay unchanged.
- `Solidify`: settle claims, owner, scope, invariants, and verification before execution.
- `Execute`: make a bounded change whose owner and verification are clear.
- `Diagnose`: gather discriminating evidence for a Reality mismatch before fixing it.

A task may change lenses and postures as evidence changes. Ownership always takes precedence over posture.

## Execution Rules

1. Identify the affected surface, dominant input lens, durable owner, and blast radius.
2. Read this file, the nearest local `AGENTS.md`, and only the governing documents needed for the change.
3. For non-trivial code design or implementation that shapes boundaries, data, authority, naming, abstraction, or complexity, load `docs/00-meta/implementation-taste.md`.
4. Use a task packet for non-trivial, multi-step, or cross-turn work. Keep at least the objective, touched guardrails, verification, current understanding, and next step.
5. Search source and durable docs with `tasks/`, generated output, dependencies, virtual environments, and caches excluded unless the task explicitly targets them.
6. Update the canonical owner in the same change when verified work changes durable truth; do not leave a parallel truth in a task packet or local guidance.
7. Execute with explicit verification and re-enter Explore, Solidify, or Diagnose if evidence invalidates the planned owner or change shape.

### Task Retention

- `tasks/` is disposable scratch space and never a canonical owner.
- A top-level task entry is retained only while its latest recursive filesystem modification is within the rolling previous `7 x 24` hours.
- Delete older entries immediately. Do not maintain `tasks/archive/` and do not require a promotion review before deletion.

## Mutation Gate

Before mutating durable truth when the blast radius is not obviously local, restate:

- Address and object: exact files, anchors, or symbols
- State diff: `From -> To`
- Blast radius: downstream modules and surfaces
- Invariants: what must remain unchanged
- Verification: concrete proof that bounds side effects

Pause for human confirmation when:

- the requested change conflicts with a product claim or technical contract
- the blast radius crosses multiple durable owners and the correct owner is unclear
- evidence is insufficient for a bug fix or architectural decision
- the proposed shortcut would violate an explicit guardrail or materially damage maintainability
