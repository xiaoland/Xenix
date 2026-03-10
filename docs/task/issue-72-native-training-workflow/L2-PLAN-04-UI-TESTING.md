# L2 Plan 04: UI And Testing

## UI Module Layout

The native UI additions should use these files:

- `src/xenix/ui/main_window.py`
  - switch from placeholder shell to host the ML workspace
- `src/xenix/ui/ml_workspace.py`
  - project, work item, dataset, mode, and model selection
- `src/xenix/ui/widgets/json_schema_form.py`
  - reusable generic form renderer for JSON Schema
- `src/xenix/ui/widgets/task_log_view.py`
  - task status and recent logs

This keeps the generic form widget separate from the ML workspace.

## Minimal Workspace Composition

The ML workspace should contain:

- project selector
- work item selector scoped by project
- dataset selector scoped by project
- column inspection panel
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

1. user selects project, work item, and dataset
2. UI requests `inspect_dataset()`
3. UI requests `list_models()`
4. user selects mode and model(s)
5. UI loads model schema into `JsonSchemaFormWidget`
6. user selects columns and parameters
7. UI submits typed request through `MLService`
8. UI refreshes task list from `MLService`
9. UI shows recent logs by reading parsed task details

## Testing Layout

Add or update tests:

- `tests/test_migrations.py`
  - v1 to v2 migration
- `tests/test_ml_registry.py`
  - catalog entries
  - JSON schema export
- `tests/test_dataset_inspection.py`
  - csv/xlsx inspection
  - no persistence side effects
- `tests/test_ml_service.py`
  - manual training validation
  - tuning validation
  - best-model update behavior
  - incompatible-policy behavior
- `tests/test_ml_execution.py`
  - queue order
  - worker result ingestion
  - canonical model copy
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
- the rule that the registry is Pydantic-declared and JSON-Schema-exportable
- the rule that worker code must not mutate SQLite directly
- the supported JSON-Schema envelope for the reusable form widget

## L3 Preparation

When L3 starts, the work should be staged in this order:

1. storage v2 and repository changes
2. Pydantic contracts and registry declarations
3. ML service and execution manager
4. worker module and model services
5. UI workspace and generic JSON-Schema form widget
6. tests and documentation
