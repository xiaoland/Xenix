# Documentation Audit

## MVT Core

- Objective & Hypothesis: Define an audit scheme for `**/AGENTS.md`, `docs/`, and one-week retention under `tasks/`; reducing contradictory authority and stale retrieval surfaces matters more than reducing raw document count.
- Guardrails Touched: Repository routing, durable truth ownership, local seam guidance, volatile task retention, existing uncommitted workspace changes.
- Verification: Inventory instruction scope, durable-doc topology, task recency and promotion risk; agree on audit goals, modes, sequence, and deletion gates before durable mutation.

## Current State

- Current Understanding: The initial Xenix corpus had 5 `AGENTS.md` files and 38 durable Markdown documents. Root correction exposed a broader defect: the canonical SVC minimal kernel is neither minimal nor capability-complete, and Xenix lacks a compact working/mutation protocol plus development/debug fast path. Sir chose to remove the current repo skills instead of repairing their projection model.
- User-Confirmed Constraints: `tasks/README.md`, `tasks/archive/`, untracked content, and all other top-level task entries outside the rolling seven-day modification window may be deleted without promotion review.
- Active Mode or Transition Note: Constraint + Verify complete. The root repair and minimal SVC capability closure are applied; the candidate is uncommitted.
- Next Step: Sir reviews the candidate and explicitly chooses whether to commit it. The SVC copy-safety debt may be handled as a later SVC source hotfix without blocking Xenix.

## Exploration Scaffold

- Governing Anchors: Root `AGENTS.md`, `docs/README.md`, `docs/00-meta/implementation-taste.md`, and `CONTRIBUTING.md`.
- Temporary Assumptions: None for retention; Sir selected a rolling filesystem-modification rule with no promotion review.
- Negotiation Triggers: Conflicting owners, cross-layer truth movement, deletion of untracked evidence, or changing the existing archive policy.
- Evidence Summary: The highest-risk durable-doc hotspots remain `agent-harness.md`, `runtime-boundaries.md`, and runtime/storage docs. Root routing now owns input lenses, working postures, durable destinations, and the simple seven-day task-retention rule.
- SVC Audit Summary: Current SVC repeats route/mode/task rules across root, index, sections, templates, skills, and installable agent definitions; its minimal form requires nine meta files but still lacks a consumable mutation-gate owner, task disposal policy, and development/debug contract. `Reality` and `Constraint` ownership claims are semantically incorrect or incomplete.

## Execution Notes

- Task cleanup cutoff: `2026-07-03T12:18:40.1812084+08:00`.
- Task cleanup result: deleted 60 top-level entries and about 593.48 MiB; retained 12 entries, 577 files, and about 262.36 MiB. No expired top-level entry remains.
- Control-plane result: root `AGENTS.md` is the single routing owner; `docs/00-meta/` retains only `implementation-taste.md`; `docs/15-alignment/` and its obsolete archive route were removed; contributor and repository indexes now link canonical owners.
- Mechanical verification: `git diff --check` passed; all local Markdown links resolve; stale control references and removed WorkItem runtime-path snapshots are absent; declared PDM commands exist.
- Routing verification: UI copy, SQLite migration, Agent tool schema, ML worker, and packaging tasks now resolve deterministically from the root entry. Remaining failures are contained in local `AGENTS.md` scope and stale durable-doc claims for later slices.
- Final outcome: first slice complete; no source code, PRD, Product TDD, Unit TDD, or Deployment content was changed.
- SVC-1 result: canonical source now has one 640-word working protocol, a four-document capability-complete consumer kernel, a durable-owner registry including implementation truth, repository workflow, and ADRs, pressure-driven optional owners, and direct task deletion under project retention with no promotion review.
- SVC deletion result: removed 43 repo-skill files, three installable Codex agent definitions, their installer/command/tests, eight route/mode templates, duplicate protocol sections/maps/sequence, and the broken duplicate monolith wrapper. No replacement projection surface was introduced.
- SVC-2 result: `[Unreleased]` now records the breaking changes and a five-step v9.8 migration path; no numbered release was created.
- SVC verification: 19 tests pass; strict monolith build includes all 18 reachable source Markdown files; repository contract checks cover local paths/fragments, undefined reference labels, path escape, percent-encoded paths, minimal topology, capability anchors, owner-surface removal, five-field tasks, word budgets, and canonical Mutation Gate ownership; `git diff --check` and trailing-whitespace checks pass.
- SVC size result: canonical Markdown fell from 33 files / 12,453 words / 85,948 bytes to 18 files / 4,113 words / 29,543 bytes; the removed skills contributed another 87,921 bytes. Normal cold start fell to 1,177 words.
- Remaining excluded debt: old SVC task history still mentions removed skills; it is volatile historical evidence, excluded from live-reference checks and from this approved slice.
- SVC-3 result: re-audited Unreleased migration, version neutrality, ignored generated output, and commit scope; committed the complete SVC candidate as `4e06dd9 docs: establish minimal SVC kernel`. The SVC worktree is clean.
- Root-slice correction: the root audit, problem confirmation, and repair design occurred before the SVC prerequisite. Re-auditing it after SVC was a packet bookkeeping error; the settled design is recorded in `control.md` and remains the next Apply slice.
- Xenix minimal-SVC baseline: `AGENTS.md`, `docs/00-meta/implementation-taste.md`, and `docs/10-prd/README.md` exist, but `docs/00-meta/working-protocol.md` is absent; root duplicates the missing protocol; implementation taste is the pre-cutover SVC version; `docs/README.md` incorrectly assigns routing/posture to root. The PRD entry has real contentful owners behind it, so this slice only makes those links explicit rather than auditing PRD content.
- Consumer-instantiation note: the committed SVC protocol links optional templates inside the SVC source repo. Xenix retains the complete five-field task contract but omits those framework-repo-only links so its four-document kernel is self-contained; this copy-safety defect remains a future SVC source follow-up rather than an Xenix cross-repo dependency.
- Root/minimal-SVC result: root `AGENTS.md` is 427 words with only Repository Map, Knowledge Owners, Development Workflow, and Execution Rules; `Instruction Scope`, Working Model, High-Risk table, standalone Task Retention, and Mutation Gate copies are removed. The exact retention policy is one Knowledge Owners sentence, and the working protocol is the only Mutation Gate/posture/task owner.
- Kernel result: all four required documents are present and non-placeholder. The consumer protocol is self-contained at 630 words; implementation taste is byte-identical to SVC commit `4e06dd9` at 492 words; the contentful PRD split remains behind direct links in `docs/10-prd/README.md`.
- Development result: root exposes the authoritative PDM entry, wrapper-aware test command, GammaRay caveat, `%LOCALAPPDATA%\Xenix`, `XENIX_APP_HOME`, SQLite/log/settings paths, diagnostics, smoke, and packaging fast paths while leaving detailed runtime truth in Deployment.
- Root verification: strict local Markdown path/fragment/reference closure passes for all seven modified entry surfaces; declared PDM commands exist; no cross-repo links or duplicated protocol headings remain; `git diff --check` and trailing-whitespace checks pass. Root + protocol + product scope is 1,850 words, below the 1,900-word normal cold-start ceiling. No code tests were required because this slice changes documentation only.
