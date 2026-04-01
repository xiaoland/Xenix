# L1 Plan

## Stage Goal

Define the high-level technical strategy for issue `#75` using the approved L0 analysis and the approved decision that feature/target selection belongs on `WorkItem`, not on `Dataset`.

This stage is intentionally split into smaller review files. `L1-PLAN.md` is the index and decision summary. The detailed strategy lives in the sub-plan files below.

## Review Map

- `L1-PLAN-01-ARCHITECTURE.md`
  - scope boundary
  - import and analysis flow
  - service boundaries
- `L1-PLAN-02-WORK-ITEM-STATE.md`
  - persistence ownership
  - work-item selection state
  - dependency impact on issue `#72`
- `L1-PLAN-03-UI-DELIVERY.md`
  - drag-and-drop UI
  - file picker UI
  - reusable widgets
  - dependency and testing direction

## L1 Decisions

The revised L1 locks these high-level decisions:

- issue `#75` owns dataset import and first-class dataset-analysis UX
- dataset files remain external and only registration metadata is persisted on `Dataset`
- dataset inspection metadata stays ephemeral and runtime-derived
- feature/target selection is persisted on `WorkItem`
- issue `#75` therefore includes a minimal work-item context selection flow
- drag-and-drop and file selection stay UI-owned, while parsing, inspection, and persistence stay service-owned
- the dataset-analysis primitives built here should be reusable by issue `#72`
- issue `#75` is allowed to introduce the first work-item schema extension required to store dataset linkage and column selections

## Approval Gate to Enter L2

L2 should proceed only if this L1 direction is accepted:

- `#75` owns dataset import, inspection, and column-analysis UX
- `WorkItem` becomes the persistence owner for dataset selection state
- `Dataset` remains registration metadata only
- `#72` will consume the primitives built here instead of rebuilding them
