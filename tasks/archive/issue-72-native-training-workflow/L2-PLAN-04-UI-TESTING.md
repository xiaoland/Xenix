# L2 Plan 04: UI And Testing

## UI Module Layout

The UI additions should use these files:

- `src/xenix/ui/main_window.py`
  - extend the current shell to host both dataset and training workspaces
- `src/xenix/ui/ml_workspace.py`
  - project, work item, mode, and model selection
- `src/xenix/ui/widgets/json_schema_form.py`
  - reusable generic form renderer for JSON Schema
- `src/xenix/ui/widgets/task_log_view.py`
  - task status and recent logs

This keeps the generic form widget separate from the ML workspace.

## Minimal Workspace Composition

The ML workspace should contain:

- project selector
- work item selector scoped by project
- work-item dataset summary panel
- work-item column-selection summary panel
- model selection panel
- generic schema form panel
- submit controls
- task list
- task detail/log panel

Project and work-item selection are required because training output must be attached to a `WorkItem`, and the current app has no other navigation context.

## Generic JSON-Schema Form Component

`JsonSchemaFormWidget` should expose:

- `set_schema(schema: dict[str, Any], values: dict[str, Any] | None = None) -> None`
- `get_value() -> dict[str, Any]`
- `validate() -> list[str]`

Internal algorithm:

1. normalize the JSON Schema into a list of supported field specs
2. map each field spec to a Qt editor widget
3. initialize the widget from schema defaults or provided values
4. serialize widget state back into a plain dictionary

Widget mapping rules:

- `boolean` -> `QCheckBox`
- `integer` -> `QSpinBox`
- `number` -> `QDoubleSpinBox`
- `string` with `enum` -> `QComboBox`
- plain `string` -> `QLineEdit`
- `array` of primitives -> editable list control or newline-delimited text adapter in v1

For nullable fields:

- render an explicit empty-state choice
- serialize empty state to `None`

## UI Interaction Flow

1. user selects project and work item
2. UI loads the work item's linked dataset and stored column selections
3. UI requests `DatasetService.inspect_source_file()` through the existing dataset domain service
4. UI requests `list_models()`
5. user selects mode and model(s)
6. UI loads model schema into `JsonSchemaFormWidget`
7. user confirms parameters
8. UI submits the workflow request through `MLService`
9. UI refreshes task list from `MLService`
10. UI shows recent logs by reading parsed task details

Bulk tuning behavior:

- the UI may let the user select multiple models
- submission creates one tuning task per selected model
- task list ordering should match submission order

## Testing Layout

Add or update tests:

- `tests/test_migrations.py`
  - `v2 -> v3` migration
- `tests/test_ml_registry.py`
  - catalog entries
  - JSON schema export
- `tests/test_ml_service.py`
  - manual training validation
  - tuning validation
  - bulk tuning fan-out
  - explicit workflow chaining through `fit_with_evaluate()` and `tune_with_evaluate()`
  - best-model update behavior
  - incompatible-policy behavior
- `tests/test_ml_execution.py`
  - queue order
  - worker-process result ingestion
  - canonical model copy
  - task-executor artifact finalization
  - explicit evaluation-task chaining
  - failure handling
- `tests/test_json_schema_form.py`
  - basic field rendering
  - enum handling
  - nullable values

## Fixtures

Add small test fixtures under `tests/fixtures/`:

- `regression_small.csv`
- `classification_small.csv`
- `regression_small.xlsx`

These should be tiny and deterministic so worker integration tests stay fast.

## AGENTS Guidance

Add `src/xenix/services/ml/AGENTS.md`.

Its scope should document:

- the public ML service boundary
- the rule that dataset inspection metadata is ephemeral
- the rule that dataset inspection belongs to the dataset domain, not the ML domain
- the rule that the registry is Pydantic-declared and JSON-Schema-exportable
- the rule that worker code must not mutate SQLite directly
- the supported JSON-Schema envelope for the reusable form widget

## L3 Preparation

When L3 starts, the work should be staged in this order:

1. storage v3 and repository changes
2. Pydantic contracts and registry declarations
3. ML service and execution manager
4. worker-process module and model services
5. UI workspace and generic JSON-Schema form widget
6. tests and documentation
