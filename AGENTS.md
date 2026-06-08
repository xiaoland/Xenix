# Xenix Native

Xenis is a non-technical user friendly business-directed machine-learning workbench.

## Repository Layout (crucial only)

- `src/xenix/`: native application package
- `src/xenix/ui/`: Qt Widgets UI layer
- `src/xenix/services/`: service layer and orchestration boundaries
- `src/xenix/services/ml/`: native ML execution, registry, and model adapters
- `src/xenix/services/storage/`: SQLite models, repositories, migrations, and storage layout logic
- `tests/`: unit and boundary tests
- `docs/`: durable project knowledge
- `tasks/`: agent-owned task-local workspaces for volatile reasoning, evidence, artifacts, migration notes, and collaboration state
- `scripts/`: developer and packaging helpers
- `ml/`: legacy model scripts kept intact unless a task explicitly targets migration or deletion

## Technical Overview

- Language runtime: Python `3.12+`
- Desktop UI: `PySide6` with Qt Widgets
- Data and persistence: `SQLModel`, SQLite, filesystem-managed artifacts
- Data processing: `pandas`, `openpyxl`
- ML: `scikit-learn`, `joblib`
- Packaging: `PyInstaller`
- Project tooling: `PDM`
- Testing: `pytest`

## Documentation

Read following documents for the current work when needed and keep them current.

- `docs/00-meta/`: typed input routes, mode SOPs, implementation taste, and framework concepts.
- `docs/00-meta/concepts.md`: load only when boundary language or owner terminology is unclear.
- `docs/00-meta/implementation-taste.md`: load for non-trivial code design or implementation changes that shape structure, boundaries, data shape, authority flow, durable naming, abstraction, or complexity budget.
- `docs/10-prd/`: product what/why, user-visible workflows, rules, scope, and business vocabulary.
- `docs/15-alignment/`: load only when MVT is not enough to constrain mutation safely.
- `docs/20-product-tdd/`: cross-unit technical realization and authority boundaries.
- `docs/30-unit-tdd/`: open only when a named hard-unit doc exists and is relevant.
- `docs/40-deployment/`: runtime, rollout, observability, and recovery truth.
- `CONTRIBUTING.md`: contributor workflow, review expectations, and testing intent.
- `tasks/`: active entropy buffer for non-trivial work. Every non-trivial task packet should preserve a compact control surface with `Objective & Hypothesis`, `Guardrails Touched`, `Verification`, current understanding, and next step.
- Nearer `**/AGENTS.md`: local constraints are additive and should be checked before edits in that subtree.

## Operating Model

1. Classify the incoming request as `Intent`, `Constraint`, `Reality`, or `Artifact`.
2. Identify the durable owner and blast radius before choosing how to work.
3. For non-trivial work, open or update an agent-owned task packet under `tasks/`.
4. Keep the task packet current when discussion, exploration, implementation friction, or verification changes the working state.
5. Choose the active mode for the current slice: `Explore`, `Solidify`, `Execute`, or `Diagnose`.
6. Load only the route doc, mode SOP, and governing anchors needed for that slice.
7. For non-trivial code design or implementation changes, load `docs/00-meta/implementation-taste.md`.
8. Search source and durable docs with volatile workspaces excluded by default.
9. Expand into alignment substrate fields only when references, boundaries, state, evidence, or blast radius are still ambiguous.
10. Execute with explicit verification.
11. Re-enter a different mode if evidence or clarity changes.
12. Promote only stable truths after verification.

### Typed Input Guide

- `Intent`: the business wants new behavior, scope, or policy. Update PRD first.
- `Constraint`: product behavior stays the same, but technical, dependency, or environment boundaries changed. Update Product TDD or Unit TDD.
- `Reality`: observed runtime behavior diverges from expectation. Gather evidence first, then fix and add recurrence guards if needed.
- `Artifact`: the requested deliverable is a bounded script, analysis, migration helper, or one-off output. Keep it tactical unless reuse is proven.

### Mode Guide

- `Explore`: map unknowns, alternatives, and assumptions.
- `Solidify`: restate findings into explicit claims, contracts, or decisions.
- `Execute`: implement a clear, verified change.
- `Diagnose`: investigate mismatches between expected and observed reality.

Mode guidance:

- do not assume one task equals one mode
- creative engineering is non-linear; design formation, verification preparation, execution, and diagnosis may reshape each other
- prepare verification shape as soon as a design claim is stable enough to act on
- switch modes when evidence or clarity changes
- mode selection never overrides durable ownership

### Task Packet Guidance

- Task packets are agent-owned inside their own task boundary, but code, durable docs, public configuration, and generated release artifacts keep their normal ownership rules.
- Keep each packet readable, inspectable, and steerable by the human.
- Split a packet into multiple files only when collaboration pressure makes the compact control surface hard to scan.
- Keep volatile packet content out of durable docs until it passes the promotion test.

### Search Guidance

- For ordinary source and durable-doc search, exclude `tasks/`, generated output, dependency folders, virtual environments, and tool caches by default.
- Search volatile workspaces only when the task explicitly targets them, when recovering task state, or when reviewing task evidence.

### Development Guidelines

- Prefer solving ambiguity by making the underlying contract explicit. Avoid stacking fallback heuristics when a durable invariant or projection boundary can be defined instead.
- Preserve a single source of truth for durable facts, state, relationships, and decisions.
- Treat cross-boundary values by provenance: authority fact, stable reference, command or proposal, user-authored value, or derived projection.
- Name durable semantics directly and consistently.
- Shape data and authority boundaries before adding clever control flow or generalized machinery.
- Spend complexity only for clear return; measure before optimizing and avoid premature abstraction.
- For Qt Widgets UI debugging, prefer using GammaRay when available to inspect widget hierarchy, properties, layout geometry, visibility, and event behavior. Treat it as the Qt-side equivalent of a browser DOM inspector.

### Impact Handshake

Before mutating durable truth after alignment expansion, or when blast radius is not obviously local, pause and restate:

- Address and Object: what exact files, anchors, or symbols will change
- State Diff: `From -> To`
- Blast Radius Forecast: what downstream files, modules, or surfaces could be affected
- Invariants Check: what must remain unchanged
- Verification: what concrete proof will bound side effects

If evidence is missing or the durable owner is still unclear, return to `Explore` or `Diagnose` instead of guessing.

### Negotiation Triggers

Pause and ask for human confirmation when:

- the requested change conflicts with an existing product claim or technical contract
- blast radius crosses multiple durable owners and the correct owner is unclear
- a shortcut would damage maintainability, readability, simplicity, or an explicit guardrail
- evidence is insufficient for a bug fix or architectural decision
