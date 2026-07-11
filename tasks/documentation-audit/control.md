# Documentation Audit Control

## Slice Protocol

Every documentation-audit slice follows this sequence:

1. **Audit**: inspect the scoped surfaces read-only, collect evidence, and report concrete problems. Task-packet updates are allowed; durable files remain unchanged.
2. **Confirm**: Sir confirms the problem set, scope, priorities, and any claims that require human product or architecture judgment.
3. **Design**: discuss alternatives and iterate the repair plan. Settle canonical owners, exact files, state diff, invariants, blast radius, and verification.
4. **Apply**: mutate durable files only after Sir explicitly approves the settled repair plan for that slice.
5. **Verify**: run the agreed static, semantic, and routing checks; report remaining issues without silently expanding scope.
6. **Commit**: stage and commit only after an explicit Sir command, including only the current slice by default.

Audit authorization is not implementation authorization. Approval is slice-specific; if evidence changes the owner, scope, or state diff, return to Confirm or Design before continuing.

## Planned Slice Order

1. SVC minimal-kernel repair and unsupported repo-skill removal — complete.
2. Root `AGENTS.md` correction in Xenix — complete.
3. `[4,5]` — PRD, ADR, and Product TDD — complete.
4. `[6,3]` plus `[7]` — Unit TDD, the bounded local-owner handshake, and Deployment — Apply complete; Verify current.

## Global Documentation Quality Constraint

- Keep every document clean, concise, direct, and non-redundant.
- Optimize for token efficiency at the corpus, document, section, and claim levels.
- Compression must not remove the owner, trigger, scope, invariant, exception, or verification needed to avoid ambiguity.
- Keep one canonical statement for each durable claim; use short references instead of parallel restatements.
- Every retained sentence must improve routing, decision quality, execution safety, or expensive-to-recover understanding.

## Current Gate

- Phase: Verify complete — Sir approved the settled `[6,7]` design and its bounded local-owner handshake; durable documentation changes are applied and verified but uncommitted.
- Durable mutation: authorized and applied only for the addresses in `slice-6-7-design.md`; commit still requires a separate explicit command.
- Confirmed calibration: current source, configuration, scripts, and tests define implemented behavior; SVC admission and one-owner rules govern retention.
- Applied scope: `docs/30-unit-tdd/`, `docs/40-deployment/`, direct root/docs/contributor routes, and the approved Agent/storage/ML/UI local-instruction handshake.
- Excluded: source, tests, dependencies, configuration, `.vscode`, credentials, runtime state, generated packages, SSH defect repair, and commit.
- Settled design anchors: no Deployment VS Code content; ignored local credentials excluded from action; Qt custom-paint seam moves to UI local `AGENTS.md`; stale branch governance is deleted; Agent/UI event mechanics stay in source/tests; diagnostic bundles are local sensitive support artifacts with manual-sharing review.
- Sub-agent constraint: every future sub-agent must use `gpt-5.3-codex-spark`. Because the current collaboration API exposes no model selector, do not delegate unless that model can be guaranteed.
- Design correction: local-owner review found required downward moves for Agent, storage, ML, and UI tripwires plus wrong-owner claims that must leave broad local guidance. The design now includes this bounded number-3 handshake.
- Exit condition: report the uncommitted Apply result; further edits or commit require Sir's next direction.
- Final acceptance: Sir treats rolling task expiry as ongoing maintenance rather than a blocker and approved closing the task after correcting the ML local-instruction scope. The correction is verified; this authorized commit closes the audit.

## Settled Xenix Root Slice

- Add `docs/00-meta/working-protocol.md` from the repaired canonical SVC source; it owns input lenses, working postures, task control, Mutation Gate, and documentation quality.
- Reduce root `AGENTS.md` to project identity, crucial repository map, Knowledge Owners, Development Workflow, and Execution Rules.
- Keep only a short mandatory working-protocol reference in Execution Rules; do not restate modes or the Mutation Gate.
- Put the concrete task-retention rule in one sentence under Knowledge Owners.
- Remove Instruction Scope.
- Compress high-risk entry guidance into one or two Knowledge Owners sentences.
- Add executable development/debug fast paths, including PDM commands, Qt/GammaRay guidance, and `%USERPROFILE%\AppData\Local\Xenix\state\xenix.db`.
- Update only direct indexes or references required to make the new protocol discoverable and links closed.

## Root Slice Impact Handshake

- Address: root `AGENTS.md`, `docs/00-meta/working-protocol.md`, `docs/00-meta/implementation-taste.md`, root `README.md`, `docs/README.md`, `docs/10-prd/README.md`, and the direct protocol entry in `CONTRIBUTING.md`.
- State Diff: duplicated root protocol + incomplete `00-meta` -> compact project root + complete four-document SVC kernel with canonical protocol/taste.
- Blast Radius: repository cold start, task/mutation behavior, contributor discovery, and later documentation slices; no product or implementation behavior changes.
- Invariants: existing product truth, ADR/TDD/Deployment ownership, local `AGENTS.md` scope, PDM command behavior, runtime paths, and unrelated dirty task work remain unchanged.
- Verification: four kernel documents exist and are non-placeholder; protocol/taste preserve committed SVC semantics without SVC-repo-only asset links; root required headings and debug entries exist; old protocol headings are absent; local links and declared commands resolve; word budgets and `git diff --check` pass.

## Current Audit Scope `[4,5]`

- `docs/10-prd/`: product truth and business vocabulary.
- `docs/20-product-tdd/adr/`: accepted/superseded technical decisions, rationale, status, and current realization.
- Remaining `docs/20-product-tdd/`: cross-unit authority, topology, lifecycle, artifact, and storage contracts.
- Source, configuration, and tests are read-only evidence used to distinguish durable claims from stale snapshots or implementation-owned facts.
- Excluded: Unit TDD/local `AGENTS.md` repair, Deployment repair, source-code mutation, and any fix proposal beyond evidence-backed audit findings.
