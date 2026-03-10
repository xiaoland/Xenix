# L1 Plan 03: UI And Delivery

## UI Strategy

Issue `#72` should add one usable ML training screen, not a generic workflow framework.

The screen should include:

- dataset selector
- column-inspection driven feature selector
- target selector that appears only when the selected model requires it
- training mode selector:
  - manual training
  - hyperparameter tuning
- model selector:
  - single-select for manual training
  - multi-select for tuning
- a generic schema-driven form component used to render parameter editors
- task list
- task detail area with:
  - status
  - recent logs
  - summary
  - failure reason

Issue `#72` should not add an inference placeholder just for visual completeness. Inference is out of scope.

## UI Boundary Rules

The UI should:

- request dataset inspection from the service
- request model schema metadata from the service
- render forms from schema metadata
- submit typed ML requests through the service
- render service-provided task state and results

The UI should not:

- hardcode parameter forms model by model
- build training-only schema rendering logic that cannot be reused elsewhere
- infer business rules from model-key string parsing
- compare evaluation metrics on its own
- decide best-model updates on its own

## Dependency Strategy

The likely implementation dependency set for issue `#72` is:

- direct `pydantic` usage for request, result, and schema models
- `pandas`
- `numpy`
- `openpyxl`
- `scikit-learn`
- `joblib`

L1 does not require `xgboost` or `lightgbm`.
Those can stay out unless the chosen initial supported set requires them.

## Documentation Strategy

Issue `#72` should update project docs as part of the implementation.

Expected updates:

- `docs/contracts/task-lifecycle.md`
  - clarify ML-task execution guarantees if needed
- `docs/contracts/storage-ownership.md`
  - clarify trained-model and evaluation-summary ownership
- `docs/runbooks/runtime-state.md`
  - document task-local dataset copies and canonical model artifact locations
- `docs/runbooks/development.md`
  - document new ML dependencies and local verification commands
- `docs/task/issue-72-native-training-workflow/RESULT.md`
  - delivered scope
  - deferred items
  - verification results
- module-local `AGENTS.md` where complexity justifies it
  - for example `src/xenix/services/ml/AGENTS.md`

## Testing Strategy

The high-level test strategy should cover:

- schema migration behavior for the new trained-model and best-model metadata
- dataset inspection against supported file types
- model registry schema export and Pydantic validation
- ML request validation for:
  - supervised models
  - targetless models
  - manual training
  - tuning
- task execution behavior:
  - task-local dataset copy
  - per-task result file emission
  - per-task log emission
  - final artifact validation
- best-model update behavior under an explicit evaluation policy
- service-level failure handling and user-visible error summaries
- UI smoke coverage for schema-driven parameter rendering if practical

Tests should focus on contracts and orchestration first. Deep widget testing is lower priority than service and execution correctness.
