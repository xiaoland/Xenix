# L1 Plan 03: UI And Delivery

## Workspace Strategy

Issue `#73` should add one focused inference workspace rather than overloading the training screen.

Preferred L1 direction:

- keep the existing `Datasets` workspace for source-dataset inspection and work-item setup
- keep the existing `Training` workspace for fit/tuning and task review
- add a dedicated `Inference` workspace for:
  - model selection
  - manual row entry
  - batch file selection
  - inference task status
  - result summary
  - open/export actions

This is cleaner than squeezing prediction UI into the training tab because the operator mental model is different:

- training configures and produces models
- inference consumes models and produces prediction outputs

## Dataset Workspace Adjustment

Issue `#73` still needs one important UI change outside the inference tab.

High-level direction:

- the dataset/work-item setup flow should evolve from:
  - create work item
  - later attach dataset selection
- to:
  - inspect/import source dataset
  - select feature columns
  - create the work item from that dataset setup directly

This keeps the forward path aligned with the new immutability rule.

The current independent "new work item first" flow should no longer be the primary path for inference-capable work items.

## Manual Entry Widget Strategy

Manual inference input must use a dedicated row-entry widget.

The widget should be table-editor oriented, not scalar-form oriented.

Minimum responsibilities:

- render one column per selected feature
- allow one or more rows
- allow row add/remove actions
- collect cell values as text initially
- surface lightweight validation errors before submission

Boundary rule:

- the widget collects row data only
- the service owns normalization into CSV, schema validation, and final request construction

This keeps the widget reusable without pushing business rules into the UI.

## Inference Screen Strategy

The screen should include:

- project selector
- work-item selector
- trained-model selector
  - default to best model when present
  - allow override to another trained model on the same work item
- input-mode switch:
  - manual entry
  - batch file
- manual entry panel with the dedicated row editor
- batch file picker panel
- submit action
- task list and task detail area
- result summary area
- open canonical result action
- export-copy action

The existing task-table and task-log patterns from the training workspace should be reused where sensible.

## UI Boundary Rules

The UI should:

- request work-item and trained-model data from services
- request any dataset/feature metadata needed to configure the row-entry widget
- collect manual rows or batch file paths
- submit inference through service-owned request models
- render service-provided task state and result references

The UI should not:

- load model artifacts directly
- derive feature-contract rules from task JSON itself
- serialize export files on its own
- guess canonical storage paths

## Open And Export Behavior

Chosen product behavior:

- `Open` targets the canonical app-managed result artifact
- `Export` opens a save/copy flow and copies the canonical artifact to the user-selected path

This choice should be reflected consistently in the UI wording so users do not confuse:

- app-owned canonical results
- exported user-owned copies

## Documentation Strategy

Issue `#73` should update project docs as part of implementation.

Expected updates:

- `docs/20-product-tdd/storage-ownership.md`
  - generated inference datasets
  - canonical result versus exported copy ownership
- `docs/20-product-tdd/task-lifecycle.md`
  - inference task result guarantees
- `docs/40-deployment/runtime-state.md`
  - managed dataset copies on work items
  - canonical inference artifact locations
- `docs/40-deployment/development.md`
  - inference verification workflow
- `tasks/archive/issue-73-native-inference-workflow-result-viewing-export/RESULT.md`
  - delivered scope
  - deferred items
  - verification results

## Testing Strategy

The high-level test strategy should cover:

- migration behavior for generated-dataset linkage
- work-item creation validation under the new immutable dataset/feature contract
- inference request validation:
  - missing best model fallback behavior
  - manual temporary CSV path creation
  - batch file validation
- worker execution behavior:
  - trained-model loading
  - normalized input-file consumption
  - prediction result emission
  - generated dataset registration
- open/export service behavior
- UI smoke coverage for:
  - row-entry widget behavior
  - model default selection
  - result action enablement

Tests should prioritize service and lifecycle contracts first, then add targeted widget-level coverage for the new row-entry component.

