# L1 Plan 03: UI And Delivery

## UI Strategy

Issue `#75` should add one usable dataset-import and analysis screen, not just a raw file dialog.

The screen should include:

- project selector
- work-item selector or creator
- drag-and-drop zone
- file-picker button
- dataset summary area
- column-analysis table
- feature-column selector
- target-column selector
- confirm/save action
- clear import error area

## UI Boundary Rules

The UI should:

- collect dropped file paths and file-dialog results
- request inspection from services
- render returned summary and column metadata
- submit the chosen dataset-selection state for persistence

The UI should not:

- parse `.csv` or `.xlsx` files directly for business decisions
- infer column types on its own
- write dataset or work-item state directly

## Reusable Widget Direction

Issue `#75` should create reusable UI primitives where practical:

- drag-and-drop file target widget
- column-selection widget
- dataset summary widget

The column-selection widget should be built for reuse by issue `#72`.

## Dependency Direction

Issue `#75` likely needs to introduce or formalize:

- `pandas`
- `openpyxl`
- possibly `numpy` if needed by the inspection layer

These dependencies are justified here already because `.csv` / `.xlsx` inspection is the core feature of the issue.

## Documentation Strategy

Issue `#75` should update documentation alongside implementation.

Expected updates:

- `docs/contracts/storage-ownership.md`
  - clarify that dataset inspection metadata remains ephemeral
  - clarify that work-item owns dataset-selection state
- `docs/runbooks/runtime-state.md`
  - remove any implication that dataset temp copies are part of import
- `docs/runbooks/development.md`
  - document local dataset import dependencies and verification commands
- `docs/task/issue-75-native-dataset-import-column-analysis/RESULT.md`
  - delivered scope
  - deferred items
  - verification results

## Testing Strategy

The high-level test strategy should cover:

- dataset registration from valid `.csv` / `.xlsx`
- failure cases for missing file, unsupported file type, malformed content, and empty files
- dataset inspection output for row/column summary and inferred types
- work-item persistence of dataset linkage and feature/target selections
- UI smoke coverage for drag-and-drop, file picker, and column-selection flow if practical

Tests should emphasize service and persistence correctness first, with focused UI smoke coverage for the import surface.
