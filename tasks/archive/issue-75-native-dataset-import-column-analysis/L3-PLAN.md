# L3 Plan

## Stage Goal

Translate the approved issue `#75` strategy into a concrete implementation roadmap, including file-by-file changes, execution order, pseudo-code, validation rules, and verification steps.

Per explicit user approval, this task skips a standalone L2 document. This L3 therefore includes the concrete low-level decisions needed to implement `#75` directly.

## Implementation Outcome

After this plan is implemented, the native branch should have:

- a usable dataset import and analysis workspace
- file-picker and drag-and-drop import for `.csv`, `.xlsx`, and `.xls`
- service-owned dataset inspection with typed column metadata
- persisted dataset registration metadata
- persisted work-item dataset linkage and feature/target column selection
- reusable dataset-analysis primitives that issue `#72` can consume

## Execution Order

Implement in this order:

1. dependency and schema changes
2. repository and service changes
3. UI workspace and reusable widgets
4. tests
5. documentation updates

This order keeps the import flow built on stable storage and service primitives rather than embedding early logic in the UI.

## Review Map

- `L3-PLAN-01-STORAGE-SERVICES.md`
  - schema changes
  - repositories
  - dataset inspection and persistence services
- `L3-PLAN-02-UI-FLOW.md`
  - workspace structure
  - drag-and-drop
  - file picker
  - reusable widgets
- `L3-PLAN-03-TESTS-DOCS.md`
  - tests
  - fixtures
  - docs
  - downstream alignment with `#72`

## Approval Gate to Enter Implementation

Implementation should proceed only if this roadmap is accepted:

- `WorkItem` is extended directly with dataset linkage and selected feature/target columns
- dataset inspection metadata remains ephemeral
- import and analysis land as one coherent workspace rather than separate dialogs
- issue `#72` will consume this work-item dataset-selection state later
