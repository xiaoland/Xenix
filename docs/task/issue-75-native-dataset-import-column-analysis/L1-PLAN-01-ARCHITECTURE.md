# L1 Plan 01: Architecture

## Scope Boundary

Issue `#75` should deliver the first usable native dataset-import and analysis flow, not a full data-management product.

In scope:

- import local `.csv`, `.xlsx`, and `.xls` files through:
  - drag and drop
  - file picker
- inspect the selected file and display:
  - file name
  - row count
  - column count
  - column names
  - inferred column kinds
- register the dataset into the local storage layer
- choose feature columns and target columns
- persist the chosen dataset-selection state on a `WorkItem`
- expose reusable dataset-analysis primitives for issue `#72`

Out of scope:

- training execution
- inference execution
- advanced preprocessing
- long-term dataset profiling or versioning

## Native Product Flow

The intended native business flow is:

1. user selects a project
2. user selects or creates a work item
3. user imports a local dataset through drag-and-drop or file picker
4. service inspects the dataset source file
5. UI renders summary and column analysis
6. user confirms:
   - dataset registration
   - feature-column selection
   - target-column selection
7. service persists:
   - `Dataset` registration metadata
   - `WorkItem` dataset-selection state
8. UI shows the registered dataset and saved work-item selection state

Important interpretation:

- dataset import and dataset analysis are part of one user-facing flow
- dataset inspection happens before or alongside dataset registration, but the canonical dataset file remains external
- work-item selection is part of the flow because work item is now the persistence owner for feature/target selection

## Layer Strategy

Use the existing boundary model:

- `UI`
  - drag-and-drop handling
  - file dialog selection
  - summary rendering
  - column-selection widgets
- `dataset analysis service`
  - validates files
  - inspects datasets
  - registers datasets
  - persists work-item dataset-selection state
- `persistence`
  - `Dataset` registration metadata
  - `WorkItem` selection state
- `filesystem`
  - reads user-managed source files only

Allowed dependency direction:

`UI -> services -> repositories -> SQLite/filesystem`

## Service Strategy

Issue `#75` should extend the existing dataset service surface rather than introduce a separate import subsystem.

Recommended service direction:

- keep `DatasetService` for registration concerns
- add a new service boundary for inspection and work-item dataset-selection persistence, or grow the dataset service carefully if that remains readable
- keep drag-and-drop and file picker concerns out of the service layer

Maintainability rule:

- do not let the UI infer column kinds or validation rules from raw pandas behavior
- do not let the UI write dataset registration or work-item selection state directly

## Reuse Strategy For Issue `#72`

Issue `#75` should intentionally produce reusable primitives:

- dataset inspection models
- dataset inspection service methods
- column-selection widget(s)
- work-item dataset-selection persistence

Issue `#72` should reuse those rather than reimplement training-only dataset setup.
