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
- `tasks/`: volatile task packets, migration notes, and temporary reasoning
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

- `docs/00-meta/`: typed input routes, mode SOPs, and framework concepts.
- `docs/00-meta/concepts.md`: load only when boundary language or owner terminology is unclear.
- `docs/10-prd/`: product what/why, user-visible workflows, rules, scope, and business vocabulary.
- `docs/15-alignment/`: load only when MVT is not enough to constrain mutation safely.
- `docs/20-product-tdd/`: cross-unit technical realization and authority boundaries.
- `docs/30-unit-tdd/`: open only when a named hard-unit doc exists and is relevant.
- `docs/40-deployment/`: runtime, rollout, observability, and recovery truth.
- `CONTRIBUTING.md`: contributor workflow, review expectations, and testing intent.
- `tasks/`: active entropy buffer for non-trivial work. Every non-trivial task packet should record `Objective & Hypothesis`, `Guardrails Touched`, and `Verification`.
- `apps/backend/AGENTS.md`, `apps/frontend/AGENTS.md`, and nearer `**/AGENTS.md`: local constraints are additive and should be checked before edits in that subtree.

## Operating Model

1. Classify the incoming request as `Intent`, `Constraint`, `Reality`, or `Artifact`.
2. Identify the durable owner and blast radius before choosing how to work.
3. For non-trivial work, open or update a task packet under `tasks/`.
4. Choose the active mode for the current slice: `Explore`, `Solidify`, `Execute`, or `Diagnose`.
5. Load only the route doc, mode SOP, and governing anchors needed for that slice.
6. Expand into alignment substrate fields only when references, boundaries, state, evidence, or blast radius are still ambiguous.
7. Execute with explicit verification.
8. Re-enter a different mode if evidence or clarity changes.
9. Promote only stable truths after verification.

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
- switch modes when evidence or clarity changes
- mode selection never overrides durable ownership

### Development Guidelines

- Prefer solving ambiguity by making the underlying contract explicit. Avoid stacking fallback heuristics when a durable invariant or projection boundary can be defined instead.
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
