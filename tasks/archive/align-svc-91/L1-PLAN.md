# L1 Plan

## Stage Goal

Progressively align repository structure to SVC v9.1 canonical layers while keeping compatibility with existing links and review workflows.

## Why This Plan Exists

The repo has mature documentation content but non-canonical layer names. L1 introduces SVC naming and task-first execution behavior with migration shims so ongoing work is not blocked.

## Scope

Included:

- Create canonical layer folders:
  - `docs/10-prd/`
  - `docs/15-alignment/`
  - `docs/20-product-tdd/`
  - `docs/30-unit-tdd/` (only if needed)
  - `docs/40-deployment/`
- Create top-level `tasks/` as the only location for new volatile work.
- Migrate selected durable docs into canonical folders.
- Keep old folders as pointer shims during transition.
- Update `AGENTS.md` with full v9.1 dynamic protocol.

Excluded:

- immediate deletion of all legacy folders
- full historical rewrite of all old task files

## Migration Mapping (Target)

- `docs/10-prd/product-scope.md` -> `docs/10-prd/` (product what/why)
- `docs/20-product-tdd/runtime-boundaries.md` -> `docs/20-product-tdd/`
- `docs/20-product-tdd/task-lifecycle.md` -> `docs/20-product-tdd/`
- `docs/20-product-tdd/storage-ownership.md` -> `docs/20-product-tdd/`
- key ADRs -> `docs/20-product-tdd/adr/` or remain in `docs/20-product-tdd/adr/` with explicit map
- `docs/40-deployment/` + `docs/40-deployment/` -> `docs/40-deployment/`
- `tasks/archive/issue-*` -> stay temporarily, marked archived
- all new plans -> `tasks/`

## Proposed Phases

### Phase 1: Protocol and Entry Points

1. Update `AGENTS.md` with Mode A/B/C and pre-execution restatement requirements.
2. Add `tasks/README.md` and templates (`exploration`, `execution`, `result`).
3. Update `CONTRIBUTING.md` to point new task planning to `tasks/`.

### Phase 2: Canonical Layer Introduction

1. Create numbered SVC docs folders.
2. Move or copy canonical files to new locations.
3. Leave redirects/index notes in legacy folders to preserve discoverability.

### Phase 3: Gradual Cleanup

1. New edits happen only in canonical folders.
2. Legacy folders accept only pointer updates.
3. After a stabilization window, archive or remove legacy duplicates.

## Deliverables

- numbered SVC layer folders under `docs/`
- `tasks/` onboarding + templates
- updated `AGENTS.md`
- transition notes in legacy doc roots
- updated `docs/README.md` and `CONTRIBUTING.md`

## Acceptance Criteria

- Every durable doc has a clear SVC layer home.
- Every new ambiguous feature starts in `tasks/` exploration mode.
- Existing contributors can still navigate old paths during the migration window.

## Risk Profile

- Medium migration effort
- Medium coordination overhead
- Strong long-term maintainability gains due to clearer layer semantics


