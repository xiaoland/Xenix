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

1. SVC minimal-kernel repair and unsupported repo-skill removal — current prerequisite slice.
2. Root `AGENTS.md` correction in Xenix.
3. `[4,5]` — PRD, ADR, and Product TDD.
4. `[6,3]` — Unit TDD and local `AGENTS.md` files.
5. `[7]` — Deployment and runtime truth.

## Global Documentation Quality Constraint

- Keep every document clean, concise, direct, and non-redundant.
- Optimize for token efficiency at the corpus, document, section, and claim levels.
- Compression must not remove the owner, trigger, scope, invariant, exception, or verification needed to avoid ambiguity.
- Keep one canonical statement for each durable claim; use short references instead of parallel restatements.
- Every retained sentence must improve routing, decision quality, execution safety, or expensive-to-recover understanding.

## Current Gate

- Phase: Verify complete — Xenix root plus minimal SVC adoption; awaiting Sir's review or explicit commit command.
- Completed surface: the approved SVC canonical kernel, templates, entry docs, unsupported repo skills, Codex agent definitions/installer, monolith validation, tests, and Unreleased release notes.
- Durable mutation: the explicitly approved root/meta/index surfaces are applied. No further durable scope or commit is implied.
- Confirmed scope: work directly in the clean `F:\CODING\svc` worktree; delete the repo skills and installable Codex agent surface without replacement; perform the atomic minimal-kernel cutover and Unreleased closure.
- Excluded: Xenix durable docs, a numbered SVC release, commit, push, and unrelated task history.
- Exit condition: met. SVC commit `4e06dd9` passed verification and the SVC worktree is clean.

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
