# Documentation Audit

## MVT Core

- Objective & Hypothesis: Define an audit scheme for `**/AGENTS.md`, `docs/`, and one-week retention under `tasks/`; reducing contradictory authority and stale retrieval surfaces matters more than reducing raw document count.
- Guardrails Touched: Repository routing, durable truth ownership, local seam guidance, volatile task retention, existing uncommitted workspace changes.
- Verification: Inventory instruction scope, durable-doc topology, task recency and promotion risk; agree on audit goals, modes, sequence, and deletion gates before durable mutation.

## Current State

- Current Understanding: The initial corpus had 5 `AGENTS.md` files and 38 durable Markdown documents. Confirmed risks include ambiguous/non-topological local `AGENTS.md` scope, duplicated routing guidance, stale schema/export/branch claims, and retrieval-hostile contract blobs. The first task cleanup removed 60 expired top-level entries and retained 12 entries modified within the rolling previous seven days.
- User-Confirmed Constraints: `tasks/README.md`, `tasks/archive/`, untracked content, and all other top-level task entries outside the rolling seven-day modification window may be deleted without promotion review.
- Active Mode or Transition Note: Intent + Solidify/Execute. First slice covers the global baseline and control plane.
- Next Step: Verify the consolidated root routing surface, references, and representative task replay; record remaining local-AGENT and durable-doc work for later slices.

## Exploration Scaffold

- Governing Anchors: Root `AGENTS.md`, `docs/README.md`, `docs/00-meta/implementation-taste.md`, and `CONTRIBUTING.md`.
- Temporary Assumptions: None for retention; Sir selected a rolling filesystem-modification rule with no promotion review.
- Negotiation Triggers: Conflicting owners, cross-layer truth movement, deletion of untracked evidence, or changing the existing archive policy.
- Evidence Summary: The highest-risk durable-doc hotspots remain `agent-harness.md`, `runtime-boundaries.md`, and runtime/storage docs. Root routing now owns input lenses, working postures, durable destinations, and the simple seven-day task-retention rule.

## Execution Notes

- Task cleanup cutoff: `2026-07-03T12:18:40.1812084+08:00`.
- Task cleanup result: deleted 60 top-level entries and about 593.48 MiB; retained 12 entries, 577 files, and about 262.36 MiB. No expired top-level entry remains.
- Control-plane result: root `AGENTS.md` is the single routing owner; `docs/00-meta/` retains only `implementation-taste.md`; `docs/15-alignment/` and its obsolete archive route were removed; contributor and repository indexes now link canonical owners.
- Mechanical verification: `git diff --check` passed; all local Markdown links resolve; stale control references and removed WorkItem runtime-path snapshots are absent; declared PDM commands exist.
- Routing verification: UI copy, SQLite migration, Agent tool schema, ML worker, and packaging tasks now resolve deterministically from the root entry. Remaining failures are contained in local `AGENTS.md` scope and stale durable-doc claims for later slices.
- Final outcome: first slice complete; no source code, PRD, Product TDD, Unit TDD, or Deployment content was changed.
