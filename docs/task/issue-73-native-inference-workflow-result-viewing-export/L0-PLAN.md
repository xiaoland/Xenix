# L0 Plan

## Task

- Issue: `#73 Native: 推理工作流与结果查看/导出`
- Source: `https://github.com/xiaoland/Xenix/issues/73`
- Background issues:
  - `#72 Native: 调优与训练工作流（调优 / 训练）`
  - `#75 Native: 数据集导入、拖拽与列分析`
- Parent issue: `#46 基于PySide开发本地版`
- Issue publish date: `2026-03-08`
- Review date: `2026-03-11`

## Objective of This Stage

Deconstruct issue `#73`, compare it against the current native branch after `#72` and `#75`, identify what capability already exists versus what is still missing, and define the constraints that should govern L1.

This stage does not lock the final architecture yet. It establishes the real baseline, the highest-risk trade-offs, and the approval gate for the next planning stage.

## Issue Text, Restated

Issue `#73` asks the native app to add local inference capability on top of already trained models.

Required outcomes from the issue text:

- execute inference from a trained model
- default to the current best model on the work item
- allow the user to switch to another trained model
- support two input modes:
  - manual entry for one or more rows
  - batch inference from an imported file
- show inference status, error messages, and result summary
- support local open/export of result files
- persist inference outputs and related metadata in the local storage layer

Explicitly out of scope:

- training itself
- cloud or multi-user capability

Acceptance criteria stated by the issue:

- default to the best model but allow switching
- support both manual entry and batch-file inference
- expose clear status and error feedback during inference
- show result summaries inside the app
- allow local open or export of result files

## Current Native Baseline

### Implemented today

- desktop bootstrap, runtime directories, logging, and Qt Widgets shell exist
- storage schema is at version `3`
- issue `#75` already delivers:
  - local dataset inspection for `.csv`, `.xlsx`, `.xls`
  - dataset summary and inferred column kinds
  - persisted work-item dataset selection:
    - `dataset_id`
    - `feature_columns`
    - `target_columns`
- issue `#72` already delivers:
  - trained-model persistence in `trained_model`
  - best-model tracking on `work_item.best_trained_model_id`
  - background ML task queueing with process-based workers
  - task-owned `request.json`, `result.json`, and `logs.jsonl`
  - task status table, task details, and task log viewing in the UI
  - canonical trained-model artifacts under `artifacts/models/<work-item-id>/`
  - evaluation task chaining after fit/tuning
- the storage layout already reserves `artifacts/inference/`
- current dependencies already include what first-pass inference likely needs:
  - `pandas`
  - `openpyxl`
  - `joblib`
  - `scikit-learn`
- the model services already persist `scikit-learn` pipelines and already prove that loading a trained model artifact for downstream use is feasible

### Missing today

- no workflow-facing inference service exists
- no `INFERENCE` task request/result contracts exist under `src/xenix/services/ml/`
- `MLTaskService` cannot execute `MLTaskType.INFERENCE`
- no inference worker entrypoint exists
- no inference-result persistence model exists beyond generic `ml_task` JSON and artifacts
- no UI for:
  - model selection for inference
  - manual prediction-row entry
  - batch inference file selection
  - inference-result summary viewing
  - open/export actions for inference outputs
- no tests exist for inference execution, inference persistence, or inference UI flow

## Contracts Already Binding This Task

- `docs/contracts/runtime-boundaries.md`
  - UI must stay thin
  - services must own workflow validation, path resolution, and artifact coordination
  - UI must not load arbitrary models or construct storage paths directly
- `docs/contracts/task-lifecycle.md`
  - inference should use the same persisted task identity and status model as other background work
  - `succeeded` requires declared outputs to exist
  - canonical application logs remain under `logs/`
- `docs/contracts/storage-ownership.md`
  - SQLite stores queryable metadata and references
  - filesystem stores large result files and user-openable exports
  - trained-model binaries remain filesystem-owned artifacts
  - work-item dataset selection state belongs on the work item, not the dataset
- issue `#72` result
  - `MLService` is the workflow-facing ML boundary
  - `MLTaskService` owns atomic task execution and finalization
- issue `#75` result
  - dataset inspection and column-kind inference already exist and should be reused for batch-input validation and manual-input typing

These contracts strongly imply that issue `#73` should extend the existing service/task/artifact pipeline, not create a direct UI-to-model shortcut.

## Current ML Reality That Matters For Inference

The current trained models are not opaque black boxes from the app's perspective.

Observed facts from the branch:

- training persists app-owned `joblib` model artifacts
- evaluation already loads those artifacts and calls `predict(...)`
- the supported models are built as `scikit-learn` pipelines with a `ColumnTransformer`
- training and evaluation both rely on `ColumnSelection.feature_columns`
- the current model implementations split dataframes by named feature columns and exactly one target column

Practical implications:

- inference can reuse the same persisted trained-model artifacts and the same background task system
- inference input must be validated against the trained model's feature contract, not only against whatever the current UI happens to collect
- batch inference does not need new heavy dependencies for a first pass because the repo already has the dataframe and Excel stack installed

## External Observations That Affect Design

### 1. Persisted model loading should stay restricted to trusted app-owned artifacts

The current branch uses `joblib` persistence for trained models. The official scikit-learn persistence guidance treats these serialization formats as trusted-environment mechanisms rather than safe arbitrary-file interchange.

Practical implication for `#73`:

- the inference workflow should load only trained models already registered in local storage
- the UI should not accept an arbitrary external `.joblib` path as an inference source

This is both a maintainability and safety constraint.

### 2. Feature-name alignment is a first-class inference contract

The current models use `ColumnTransformer` and dataframe column names during fit/evaluate flows. That means inference inputs must preserve the expected feature columns cleanly enough for the persisted pipeline to transform them the same way.

Practical implication for `#73`:

- inference cannot safely depend on free-form row dictionaries without validating column names and missing fields
- manual entry and batch-file inference should converge on one normalized feature-frame contract before calling the model

## Dependency Relationship With `#72` And `#75`

Issue `#73` should build on the previous two issues, not reopen them.

Issue `#72` should remain the owner of:

- trained-model creation
- best-model selection logic
- task queueing and worker execution
- training/evaluation task history

Issue `#75` should remain the owner of:

- file import UX patterns
- source-file inspection for `.csv` / `.xlsx` / `.xls`
- inferred dataset column-kind metadata

Issue `#73` should own:

- selecting a previously trained model for prediction
- normalizing manual rows and batch files into prediction inputs
- running the atomic inference task
- persisting inference summaries and result-file references
- viewing/opening/exporting inference outputs

This prevents inference from duplicating training orchestration or dataset setup.

## Key Architectural Tensions Identified

### 1. Default model selection is easy; stable model-input contracts are not

The issue requirement to default to the best model maps cleanly onto `work_item.best_trained_model_id`.

The harder problem is that the current branch does not persist the training-time feature contract on `trained_model`. Today that contract only exists indirectly through:

- mutable work-item feature selection state
- training/evaluation task payload JSON

That creates a correctness risk:

- if a work item's selected feature columns change after training, an old trained model may no longer match the current work-item state
- inference could then silently target the wrong feature set unless the service reconstructs the original training contract from durable metadata

This is the main L0 risk.

### 2. Manual entry and batch-file inference should not become two separate engines

The issue requires two input modes, but they should converge into one service-owned normalized structure before execution.

If the branch implements:

- one validation path for manual rows
- another unrelated validation path for batch files

then the feature typing, missing-value rules, and error messages will drift quickly.

### 3. Result persistence scope is required, but the minimum durable shape is still open

The issue explicitly requires saving inference results and metadata locally.

Two broad approaches remain possible at L0:

- lean on `ml_task.result_payload` plus `ml_task_artifact` for the first delivery
- add a small dedicated inference-result row to make history, model linkage, and open/export references first-class

The current branch does not yet justify which option is cleaner long term, but it does justify that generic task JSON alone may become hard to query and hard to present once multiple inference runs accumulate.

### 4. Manual multi-row entry needs a UI primitive that does not exist yet

The current `JsonSchemaFormWidget` is field-form oriented. It works well for model hyperparameters, but issue `#73` needs row-oriented data entry:

- one row
- or several rows with the same feature schema

That means L1 must decide whether to:

- extend the generic schema form enough to represent record arrays, or
- introduce a dedicated row-entry widget for inference input

Locking that too early in L0 would be premature, but ignoring it would underestimate the UI work.

### 5. Batch-file inference should reuse file parsing, but not dataset registration semantics

Issue `#75` already solved local file inspection and supported formats. That is useful.

But an inference input file is not the same thing as a registered project dataset:

- it may be a transient file used only for one prediction run
- it may omit target columns entirely
- it should not automatically become a durable `dataset` row

So `#73` should reuse parsing capability and UX patterns from `#75`, while keeping batch inference files outside dataset-registration ownership.

### 6. Open versus export needs a clear ownership rule

The issue asks for local open/export of results.

That leaves an important design question for L1:

- is the app-managed artifact under `artifacts/inference/` already the canonical export file, with "Open" meaning reveal/open that file
- or does "Export" mean copy a canonical result artifact to a user-chosen destination

Both are viable. They have different consequences for simplicity, duplicate files, and service API shape.

## Minimum Capability Gaps That L1 Must Address

To satisfy the issue without violating current contracts, the next stage must define a strategy for at least:

1. selecting the inference model default from `best_trained_model_id` while still supporting manual model switching
2. reconstructing or persisting a stable feature contract for each trained model
3. introducing explicit inference request/result contracts and a worker entrypoint
4. validating both manual rows and batch files against one normalized prediction-input shape
5. deciding the minimum durable persistence model for inference summaries and result-file references
6. defining how result files under `artifacts/inference/` are opened and exported
7. adding a Qt inference UX that fits the existing `Datasets` and `Training` workspaces cleanly

## L1 Guardrails

The next stage should proceed with these guardrails:

- do not allow arbitrary external model-file picking for inference
- reuse the existing `MLService` / `MLTaskService` workflow boundary rather than creating a second inference execution stack
- keep manual and batch inference on one normalized service contract
- reuse issue `#75` file-inspection patterns, but do not register transient batch-inference files as project datasets by default
- treat result viewing/opening/export as service-owned artifact policy, not UI path guessing
- assume the current trained-model metadata is insufficiently explicit for stable inference until L1 proves otherwise
- avoid forcing a broad analytics/reporting subsystem when the issue only requires status, summary, open, and export

## Approval Gate to Enter L1

L1 should proceed only if the following L0 interpretation is accepted:

- issue `#73` should be built on the current task queue, artifact pipeline, and trained-model persistence from `#72`
- issue `#73` should reuse file-inspection patterns from `#75`, but batch inference files should not automatically become registered datasets
- inference should load only locally registered trained models, not arbitrary external model files
- manual and batch prediction should converge on one service-owned validation/execution contract
- the branch should treat stable trained-model input metadata as a first-class concern, because relying only on mutable work-item column state would weaken correctness and maintainability
- a storage-shape decision is still open for L1:
  - either keep first-pass inference history inside generic task metadata and artifacts
  - or introduce a minimal dedicated inference-result row if that proves materially clearer

## Sources

- Issue `#73`: `https://github.com/xiaoland/Xenix/issues/73`
- Issue `#72`: `https://github.com/xiaoland/Xenix/issues/72`
- Issue `#75`: `https://github.com/xiaoland/Xenix/issues/75`
- scikit-learn model persistence: `https://scikit-learn.org/stable/model_persistence.html`
- scikit-learn `ColumnTransformer`: `https://scikit-learn.org/stable/modules/generated/sklearn.compose.ColumnTransformer.html`
