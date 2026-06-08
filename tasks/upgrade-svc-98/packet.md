# SVC v9.8 Upgrade Packet

## MVT Core

- Objective & Hypothesis: Align Xenix Native repository governance with the verified local upstream SVC v9.8 baseline while preserving product behavior and native app architecture.
- Guardrails Touched: Durable owner routing stays in `docs/`/`AGENTS.md`; task-local reasoning stays under this packet until promoted.
- Verification: Static diff and targeted text search prove all active SVC baseline and task-packet guidance references are coherent.

## Current State

- Current Understanding: `F:/CODING/svc` now verifies SVC v9.8 at `src/index.md`, with upstream commits after the older Xenix v9.7 alignment.
- User-Confirmed Constraints: User requested "升级 SVC 框架（见 F:\CODING\svc）".
- Active Mode or Transition Note: Execute after explicit user confirmation.
- Next Step: Complete final status report.

## Exploration Scaffold

- Perturbation: Upstream framework baseline changed from the Xenix-applied SVC v9.7 to local SVC v9.8.
- Input Type: Constraint.
- Governing Anchors: root `AGENTS.md`, `docs/00-meta/`, `tasks/README.md`, upstream `F:/CODING/svc/src/index.md`, `F:/CODING/svc/CHANGELOG.md`.
- Impact Hypothesis: Mostly repository governance docs and task templates; no application behavior or `src/xenix/` code should change.
- Temporary Assumptions: Align to released v9.8 only, not the current uncommitted upstream Unreleased implementation-taste edits, unless explicitly confirmed.
- Negotiation Triggers: Pause before durable-doc mutation because the change crosses repository-level governance docs.
- Promotion Candidates: Active Xenix baseline becomes SVC v9.8; task packets become explicitly agent-owned task-local workspaces; normal source/doc search excludes volatile task workspaces by default.

## Notes

- `F:/CODING/svc/README.md` states current framework baseline is v9.8.
- `F:/CODING/svc/src/index.md` states version v9.8, last edited `2026-06-07T17:01+08:00`.
- `F:/CODING/svc/CHANGELOG.md` records v9.8.0 on `2026-06-07`.
- `F:/CODING/svc` also has uncommitted edits in `CHANGELOG.md` and `src/sections/implementation-taste.md`; those are treated as Unreleased unless the user says otherwise.

## Execution Notes

- Updated Xenix's active SVC baseline references from v9.7 to v9.8.
- Added local `docs/00-meta/` route docs for Intent, Constraint, Reality, and Artifact.
- Added `docs/00-meta/concepts.md` because root guidance already references it.
- Added `docs/00-meta/implementation-taste.md` for non-trivial implementation judgment.
- Updated mode overlays for agent-owned task packets, non-linear mode transitions, verification shape, and search isolation.
- Updated task workspace guidance and templates, including a new `tasks/templates/packet.md`.
- Historical `tasks/align-svc-98/` records were left unchanged as historical evidence.

## Verification Results

- Command: `rg -n "SVC v9\.7|SVC v9\.3|SVC v9\.1" README.md CONTRIBUTING.md AGENTS.md docs tasks\README.md tasks\templates`
- Observed: no matches.
- Command: `rg -n "implementation-taste|agent-owned|Search Guidance|Search Isolation|volatile.*search|input-intent|input-constraint|input-reality|input-artifact|concepts\.md|tasks/templates/packet\.md" AGENTS.md README.md CONTRIBUTING.md docs tasks\README.md tasks\templates`
- Observed: expected v9.8 guidance entry points found.
- Command: `git diff --check`
- Observed: passed.
