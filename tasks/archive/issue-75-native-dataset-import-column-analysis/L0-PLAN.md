# L0 Plan

## Task

- Issue: `#75 Native: 数据集导入、拖拽与列分析`
- Source: `https://github.com/xiaoland/Xenix/issues/75`
- Parent issue: `#46 基于PySide开发本地版`
- Issue publish date: `2026-03-10`
- Review date: `2026-03-10`

## Objective of This Stage

Deconstruct issue `#75`, compare it against the current native branch, identify the overlap and dependency boundary with issue `#72`, and surface the main design constraints that should govern L1.

This stage does not lock the final architecture yet. It establishes what `#75` must own, what already exists, what is missing, and where the boundary with `#72` must stay clean.

## Issue Text, Restated

Issue `#75` asks the native app to implement local dataset import and column-analysis capability.

Required outcomes:

- import local `.csv` / `.xlsx` files through:
  - drag and drop
  - file picker
- recognize and read supported dataset files
- display basic dataset summary:
  - file name
  - row count
  - column count
  - column names
  - inferred data types
- allow the user to choose:
  - feature columns
  - target columns
- show clear validation and error messages for common import failures
- persist imported dataset metadata into the local storage layer

Explicitly out of scope:

- training execution
- inference execution
- advanced data cleaning and preprocessing

## Current Native Baseline

### Implemented today

- runtime bootstrap and Qt shell window exist
- `DatasetService.register_dataset()` already validates and persists external dataset files
- supported source formats are already constrained to:
  - `.csv`
  - `.xlsx`
  - `.xls`
- `DatasetRow` already stores:
  - `project_id`
  - `name`
  - `source_path`
  - `source_format`
- `DatasetService.list_datasets()` and `get_dataset()` already exist

### Missing today

- no file-picker import UI exists
- no drag-and-drop import UI exists
- no dataset inspection service exists
- no column metadata model exists
- no inferred type summary exists
- no feature/target selection UI exists
- no import-flow specific error messaging beyond service validation exceptions
- the main window is still only a placeholder shell

## Existing Contracts That Constrain This Task

- `docs/20-product-tdd/runtime-boundaries.md`
  - UI must not parse datasets directly for business logic
  - services should expose structured request/result objects
- `docs/20-product-tdd/storage-ownership.md`
  - SQLite stores metadata and references
  - datasets remain external user-managed files
  - dataset-derived metadata should not become canonical stored dataset content
- `docs/10-prd/product-scope.md`
  - local dataset selection and drag-and-drop import are already part of product scope
- issue `#70` result
  - dataset registration metadata already exists
  - source datasets remain external rather than copied into app-managed canonical storage

These constraints mean `#75` should extend the dataset service/UI surface, not invent a second import system outside the service boundary.

## Dependency Relationship With Issue `#72`

Issue `#75` should be treated as a prerequisite for `#72`.

`#75` should own:

- drag-and-drop import
- file-picker import
- dataset parsing for inspection
- basic summary rendering
- column-analysis UI
- feature/target selection UX during dataset analysis

`#72` should consume:

- registered datasets
- dataset inspection capability
- reusable column-selection UI/service primitives where appropriate

`#72` should not re-own:

- drag-and-drop dataset import
- file-picker dataset import
- first-class dataset-analysis UX

This prevents duplicated dataset-parsing logic and duplicated UI flows across the two issues.

## Main Architectural Tensions Identified

### 1. Dataset inspection is needed, but the inspection result should stay ephemeral

The issue requires row count, column names, inferred types, and column selection UX.

The current storage model persists only dataset registration metadata, which is correct.

Maintainable interpretation:

- inspection data should be derived from the source file on demand
- inspection data should be represented with typed service objects
- inspection data should not be persisted into the dataset table by default

This keeps the database small and avoids stale schema metadata when external dataset files change.

### 2. Column selection exists in issue `#75`, but the ownership of persisted selections is not obvious

The issue says the user should be able to choose feature columns and target columns.

However, a feature/target choice does not always belong to the dataset itself:

- different work items may use the same dataset differently
- training configurations may evolve over time
- unsupervised flows may not use target columns at all

This means there is a real design question for later stages:

- should `#75` treat feature/target selection as import-time analysis state only, or
- should it persist some reusable selection preset, and if so, where

Persisting feature/target selections directly on the dataset would likely hurt maintainability because that would couple one dataset to a single downstream modeling interpretation.

### 3. Drag-and-drop must stay UI-thin

Drag-and-drop is inherently a UI behavior, but parsing and validation should remain service-owned.

The maintainable split is:

- UI handles dropped files and file-dialog selection
- services validate file type, inspect content, and persist registration metadata
- UI renders returned summaries and errors

### 4. Issue `#75` can reduce later complexity if it produces reusable primitives rather than a one-off wizard

If `#75` builds:

- a dataset inspection service
- column metadata models
- a reusable column-selection widget

then `#72` can reuse them for training setup rather than rebuilding them.

This is the main reason it should be done first.

## Gap Analysis

To satisfy issue `#75`, the branch needs at least:

1. dataset inspection service support for `.csv` / `.xlsx`
2. typed column metadata and dataset summary models
3. file-picker import UI
4. drag-and-drop import UI
5. column-selection UI
6. clear import and inspection validation errors
7. tests for import, inspection, and UI integration boundaries

## Recommended Direction for L1

L1 should proceed around these assumptions unless explicitly rejected:

- keep dataset files external and persist only registration metadata
- represent dataset summary and column metadata with Pydantic models
- treat inspection metadata as ephemeral rather than persisted
- build reusable dataset-analysis primitives that `#72` can consume
- keep drag-and-drop and file selection in the UI layer, but keep parsing and validation in services

## Approval Gate to Enter L1

L1 should proceed only if the following interpretation is accepted:

- issue `#75` is the prerequisite owner for dataset import and column-analysis UX
- issue `#72` should consume, not duplicate, the dataset-analysis capability built here
- dataset inspection metadata should stay runtime-derived rather than stored in SQLite
- feature/target selection should not be persisted directly on the dataset entity unless a later stage justifies a cleaner location for that state

