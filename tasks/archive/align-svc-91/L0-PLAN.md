# L0 Plan

## Stage Goal

Reach behavioral compliance with SVC v9.1 while preserving the existing documentation topology (`contracts/adr/runbooks/migrations`) and minimizing move/rename impact.

## Why This Plan Exists

This repository already has a working code-first architecture and useful durable docs. The largest v9.1 misalignment is process shape (task-first ambiguity handling and dynamic execution protocol), not missing technical content. L0 focuses on that gap first.

## Scope

Included:

- Introduce top-level `tasks/` as the default volatile workspace for new work.
- Keep `tasks/archive/` as historical archive during transition.
- Update `AGENTS.md` with:
  - Pre-Execution Restatement Rule
  - Dynamic mode selection (Mode A/B/C)
  - explicit task-first handling for ambiguous prompts
- Add one mapping doc that explains how current folders map to SVC v9.1 layers.

Excluded:

- large scale file moves between docs folders
- renaming all current docs to numbered SVC folders
- CI policy enforcement for doc layer compliance

## Proposed Steps

1. Add `tasks/README.md` and a simple task template that distinguishes Mode A exploration from Mode C execution notes.
2. Update `AGENTS.md` to include mode triggers and required actions per mode.
3. Add `docs/SVC-LAYER-MAP.md`:
   - PRD equivalent today: `docs/10-prd/product-scope.md`
   - Product TDD equivalent today: runtime/storage/task contracts + selected ADRs
   - Deployment equivalent today: `docs/40-deployment/` and `docs/40-deployment/`
4. Mark `tasks/archive/` as legacy location for existing issue records and freeze it for new tasks.
5. Update contributor guidance so new planning starts in `tasks/`.

## Deliverables

- `tasks/README.md`
- `tasks/_template.md`
- updated `AGENTS.md`
- `docs/SVC-LAYER-MAP.md`
- short update in `CONTRIBUTING.md`

## Acceptance Criteria

- New ambiguous requests are handled in `tasks/` first (Mode A behavior).
- New execution tasks can proceed directly with explicit restatement (Mode C behavior).
- Team members can map current docs to SVC v9.1 without guessing.

## Risk Profile

- Low migration risk
- Low review disruption
- Main limitation: naming remains partially non-canonical vs strict SVC folder schema


