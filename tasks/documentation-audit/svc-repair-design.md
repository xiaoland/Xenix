# SVC Repair Design

Status: Applied, verified, and committed as `4e06dd9` on 2026-07-10. No numbered release was created.

## Objective

Repair SVC source-first before Xenix consumes it again.

- **Minimal**: do not create an independent surface without a distinct owner, trigger, consumer, or change cadence.
- **Complete**: a fresh agent can find the durable owner, working protocol, development entry, mutation gate, and verification without guessing.
- **Documentation quality**: one claim, one owner; short references instead of restatement; token efficiency must not remove scope, trigger, invariant, exception, or proof.

## State Diff

```text
four competing execution loops + eight route/mode templates
-> one directly reusable working-protocol owner

input type assigns a fixed document owner
-> composable input lenses; claim semantics and root cause select the owner

tasks as a durable destination with promotion-dependent exit
-> disposable work surface with project-owned retention and no deletion promotion gate

hand-maintained, stale, flattened repo skills
-> delete the unsupported skill surface and all live references; do not replace it

12-document minimal startup shape
-> four durable consumer documents; all other layers are pressure-driven
```

## Minimal Consumer Kernel

```text
AGENTS.md
docs/00-meta/working-protocol.md
docs/00-meta/implementation-taste.md
docs/10-prd/README.md
```

- Create `tasks/` only when active work needs a packet.
- Do not generate `tasks/README.md`, archives, empty glossaries, route/mode files, TDD layers, Deployment, Alignment, or local `AGENTS.md` by default.
- `implementation-taste.md` exists by default but loads only for its non-trivial implementation trigger.

## Canonical SVC Ownership

| Surface | Unique responsibility |
| --- | --- |
| `src/index.md` | Framework purpose, minimal consumer kernel, layer registry, extension admission links |
| `src/sections/working-protocol.md` | Input lenses, owner resolution, modes, task minimum, search rules, permission/mutation gate, verification, documentation quality |
| `src/sections/implementation-taste.md` | Non-trivial implementation judgment only |
| `src/sections/prd.md` | Product-truth purity and optional PRD expansion |
| `src/sections/product-tdd.md` | Cross-unit contract admission and ownership |
| `src/sections/unit-tdd.md` | Unit design versus local seam guidance |
| `src/sections/deployment.md` | Runtime and operational truth admission |
| `src/sections/extensions/alignment.md` | Repeated coordination-drift extension only |
| `src/sections/extensions/multi-repo.md` | Multi-repo extension only |
| `CHANGELOG.md` | Framework history and migration notes |

Retain layer documents that have distinct consumers. Remove or merge duplicated protocol surfaces:

- `meta-engine.md` protocol claims -> `working-protocol.md`
- `filesystem.md` minimal/extension registry -> `index.md`
- `ontology.md`, `promotion-rules.md`, `tasks.md`, and `durable-destination-map.md` essential claims -> `working-protocol.md` or the owning layer document
- `migration-guidance.md` supported migration note -> `CHANGELOG.md`
- `SEQUENCE_OF_USE.md` -> delete; the working protocol owns sequence semantics
- four `input-*.template.md` and four `mode-*.template.md` -> delete; copy the canonical working protocol directly instead of maintaining another projection

## Consumer Root Template

The root template has five sections and a review ceiling of about 450 English words:

1. Project
2. Repository Map
3. Knowledge Owners
4. Development Workflow
5. Execution Rules

It provides project-specific development/debug fast paths and a short mandatory reference to `working-protocol.md`. It does not restate modes, the mutation gate, implementation taste, or optional layers that do not exist.

## Working Protocol Contract

One document, with a review ceiling of 650 English words, owns:

- `Intent`, `Constraint`, `Reality`, and `Artifact` as composable lenses
- durable-owner resolution by claim semantics, provenance, and diagnosed cause
- `Explore`, `Solidify`, `Execute`, and `Diagnose`
- audit/planning permission is not mutation permission; approval is scope-specific
- the five-field packet minimum: Objective, Guardrails, Verification, Current Truth, Next Step
- the full mutation gate: address, state diff, blast radius, invariants, verification, and human pause triggers
- source/durable search isolation and explicit verification
- global documentation-quality rules

The project root owns the concrete task-retention sentence. The framework supplies the retention hook but no universal TTL.

## Optional Admission

Do not generate empty placeholders. Add a durable surface only when the claim is stable, expensive to recover, not better enforced mechanically, has a clear owner, and has real content now.

- Product TDD: another unit depends on the contract to interoperate safely.
- ADR: alternatives and rationale cannot be recovered cheaply from code/tests.
- Unit TDD: one unit has expensive internal invariants not cheaply preserved elsewhere.
- Local `AGENTS.md`: a physical subtree has a repeated fragile seam or mandatory local verification.
- Deployment: runtime, package, migration, observability, or recovery truth is non-trivial.
- Alignment: existing owners and anchors still show repeated reference/state/operation drift.
- Multi-repo: one product spans repositories, shared truth would otherwise drift, and freshness can be enforced mechanically.
- Structured PRD/glossary: the single product document has distinct consumers or change cadence that justify a split.

## Unsupported Skill Surface

- Delete the root `.agents/` directory; it contains only the two unsupported skill bundles.
- Remove live references to `init-svc` and `edit-svc-shared-docs`.
- Do not retain deprecation stubs, flattened copies, projection tooling, manifests, or drift tests.
- Historical task evidence may mention the removed skills; it is not current framework truth and is outside this slice.
- Keep the monolith builder strict for missing local Markdown paths and fragments so canonical-source drift cannot be hidden.

## Implementation Slices

### SVC-1 — Atomic Minimal-Kernel Cutover

- Rewrite canonical protocol/index/task ownership.
- Rewrite the root template and make the canonical working protocol directly reusable by consumers.
- Remove the eight route/mode templates and obsolete duplicate surfaces.
- Delete both repo skill bundles and their live references without replacement.
- Keep PRD/TDD/Deployment/extension guidance only where it has unique responsibility.
- Make monolith link handling strict and add repository contract tests.
- Run semantic replay and token/cold-start comparison.

### SVC-2 — Release Closure

- Update changelog and any selected version metadata.
- Record only the supported migration from the previous public baseline.
- Build the ignored monolith as verification, not canonical source.
- Do not mark a release unless Sir explicitly chooses a version.

### SVC-3 — Commit Closure

- Re-audit Unreleased migration coverage, version neutrality, ignored generated output, and staged scope.
- Re-run tests, strict monolith generation, and diff checks.
- Keep the framework under Unreleased because no numbered version was authorized.
- Commit the complete SVC candidate only after Sir's explicit command.

## Impact Handshake

- **Address**: `F:\CODING\svc` canonical Markdown, templates, unsupported root skills, monolith tooling/tests, and repository entry docs.
- **Blast radius**: future manual SVC adoption, removal of the two unsupported skills, monolith generation, and later Xenix adoption.
- **Invariants**: PRD what/why, code/config/tests authority, evidence-first diagnosis, non-linear modes, mono-repo default, pressure-driven layers, and the clean baseline remain intact.
- **Excluded**: no Xenix durable edits until SVC repair is verified; no push, release, or commit without explicit command.

## Verification

- `pdm run test`
- strict `pdm run build-monolith`
- local-link closure across canonical docs and templates
- no live reference to the removed skills
- no references to deleted route/mode templates or obsolete protocol names
- one canonical definition each for Constraint routing, Reality routing, task minimum, and mutation gate
- minimal init creates exactly four durable documents and no empty optional layers
- fresh-agent replay for Intent, environment Constraint, runtime Reality, one-off Artifact, cross-owner mutation, task deletion, and minimal/expanded initialization
- `git diff --check`
- before/after report for canonical bytes, root/protocol words, and normal cold-start words

Review budgets:

- root <= 450 words
- working protocol <= 650 words
- normal cold start: root + working protocol + one owner, <= 1,900 words
- implementation taste <= 650 words and loaded only on trigger

Budgets are review ceilings, not permission to remove required semantics.

## Apply Decisions

Settled:

1. Work directly in the now-clean `F:\CODING\svc` worktree; do not create an independent worktree.
2. Use the four-document consumer minimum and one working-protocol owner.
3. Delete the eight route/mode templates.
4. Delete the root repo skills and do not build a replacement skill/projection system.
5. Keep the repair under `Unreleased` unless Sir explicitly selects a version.

6. Delete `src/.agents/codex-agents/*.toml`, the `install-agents` command, its implementation, and its tests; do not replace this second protocol projection surface.

## Verification Result

- `pdm run test`: 19 passed.
- `pdm run build-monolith`: passed; 18 linked source Markdown files included.
- Strict link coverage: missing path, missing fragment, same-document fragment, missing reference label, reference-style target, root escape, percent-encoded path, and corpus-wide closure.
- Review budgets: root template 254 words; working protocol 640; implementation taste 492; normal cold start 1,177.
- Corpus: 33 -> 18 canonical Markdown files; 12,453 -> 4,113 words; 85,948 -> 29,543 bytes; 87,921 bytes of skill copies removed separately.
- Semantic replay: Intent, environment Constraint, runtime Reality, one-off Artifact, cross-owner mutation, direct task deletion, minimal adoption, local seam, and ADR ownership all resolve without fixed input-to-document routing.
- Hygiene: no live obsolete references outside tests and historical task evidence; removed agent/skill directories have no physical residue; `git diff --check` and trailing-whitespace checks pass.
- Commit closure: `4e06dd9 docs: establish minimal SVC kernel`; SVC worktree clean.
