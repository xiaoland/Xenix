# L3 Plan 04: UI, Verification, And Documentation

## Step 1: Extend The Existing Shell Instead Of Replacing It

Files:

- `src/xenix/app.py`
- `src/xenix/ui/main_window.py`
- `src/xenix/ui/dataset_workspace.py`
- `src/xenix/ui/ml_workspace.py`
- `src/xenix/ui/widgets/json_schema_form.py`
- `src/xenix/ui/widgets/task_log_view.py`

Current baseline:

- the shell is dataset-centric after issue `#75`

Target delivery:

- keep dataset import usable
- add a dedicated training workspace beside it

Recommended composition:

- `QTabWidget` with:
  - `Datasets`
  - `Training`

This keeps issue `#75` intact while making issue `#72` reviewable as an additive change.

## Step 2: Training Workspace Interaction Flow

`MLWorkspace` should read existing work-item state rather than asking the user to rebuild it.

Interaction flow:

1. user selects project
2. user selects work item
3. UI loads the linked dataset and stored feature/target columns
4. UI loads the model catalog
5. user chooses:
   - manual training with a single model
   - tuning with one or more selected models
6. UI renders the selected schema(s)
7. UI submits one workflow request for manual training or multiple workflow requests for bulk tuning
8. UI refreshes task list and detail view
9. UI shows logs, summary, persisted trained models, and best-model status

Required empty-state handling:

- no project selected
- no work item selected
- work item has no linked dataset
- work item has invalid or missing stored column selections

## Step 3: Generic JSON-Schema Form Delivery

Files:

- `src/xenix/ui/widgets/json_schema_form.py`

Supported field shapes in v1:

- `boolean`
- `integer`
- `number`
- `string`
- `enum`
- arrays of primitives
- nullable primitive fields from Pydantic JSON Schema

Implementation sequence:

1. normalize schema properties into field specs
2. map field specs to Qt widgets
3. prefill defaults from the schema
4. serialize widget values back into plain dictionaries
5. return user-facing validation messages before submit

UI rule:

- the generic form widget should remain training-agnostic so later inference work can reuse it

## Step 4: Task List, Details, And Logs

Files:

- `src/xenix/ui/ml_workspace.py`
- `src/xenix/ui/widgets/task_log_view.py`

The first UI delivery should show:

- task status
- task type
- created, started, and finished timestamps
- evaluated metric summary if available
- failure summary if failed
- recent parsed log entries
- persisted trained-model list for the selected work item
- current best model marker

Implementation note:

- polling is acceptable in v1
- prefer a small `QTimer` refresh loop over introducing a more complex event bus
- the task list should make chained `FIT -> EVALUATE` and `HYPERPARAMETER_TUNING -> EVALUATE` flows understandable rather than looking like duplicate rows

## Step 5: Verification Order

Tests to add or extend:

- `tests/test_migrations.py`
- `tests/test_ml_registry.py`
- `tests/test_ml_models.py`
- `tests/test_ml_service.py`
- `tests/test_ml_execution.py`
- `tests/test_json_schema_form.py`

Recommended execution order:

1. storage and repository tests
2. registry and model-helper tests
3. service and execution tests
4. widget tests
5. full suite

Commands:

```bash
pdm run test
pdm run check
```

If Qt widget tests need a headless fixture, add it in the same step instead of relying on manual runs.

## Step 6: Documentation And Result Output

Files to update:

- `src/xenix/services/ml/AGENTS.md`
- `docs/20-product-tdd/storage-ownership.md`
- `docs/40-deployment/runtime-state.md`
- `docs/40-deployment/development.md`
- `tasks/archive/issue-72-native-training-workflow/RESULT.md`

`src/xenix/services/ml/AGENTS.md` should document:

- the `MLService` boundary
- sequential execution in v1
- worker files vs SQLite responsibilities
- evaluation policy ownership
- the rule that dataset inspection metadata stays ephemeral
- the rule that dataset inspection remains in the dataset domain
- the rule that model services are implemented under `src/xenix/services/ml/`

`RESULT.md` should be written only after implementation and should include:

- delivered scope
- verification commands
- acceptance-criteria mapping
- explicit deferred items, if any

