# LLM Tool Inventory

## Status

- Mode: Explore.
- Scope: minimal static tool registry exposed to the LLM through function calling.
- Current decision: start small; do not support LLM-authored custom training, prediction, or arbitrary Python scripts in the first slice.

## Boundary

This document lists tools exposed directly to the LLM.

It does not list:

- internal Xenix services
- Python APIs
- script-runtime APIs
- UI preview/rendering code
- direct raw service invocation tools

## Presentation Rule

Tool outputs can include markdown text with links to generated artifacts:

```markdown
[confusion_matrix.png](artifact://...)
[predictions.csv](artifact://...)
[metrics.md](artifact://...)
```

ChatBox previews linked images, tables, reports, and CSV/XLSX artifacts automatically. Chart/table rendering is therefore a UI renderer concern, not a separate LLM tool family.

## Provider Naming

Provider-facing names should use snake_case for OpenAI-compatible and DeepSeek-compatible function name safety.

Documentation aliases may use dotted names:

```text
data.peek              -> data_peek
data.integrate         -> data_integrate
data.clean             -> data_clean
data.feature.select    -> data_feature_select
model.train            -> model_train
model.hyper_train      -> model_hyper_train
model.inference        -> model_inference
```

## Required Turn Tool

### `turn_end`

Purpose: explicitly end the current turn.

Inputs:

```text
summary?
next_actions?
user_visible_final_text?
```

Output:

```text
turn_end_message_id
summary
```

Notes:

- Reserved Harness tool.
- A turn starts with one user message and ends with this tool.
- Most providers do not have a native turn-end message, so this remains required.

## Data Tools

### `data_peek`

Alias: `data.peek`

Purpose: inspect one or more CSV/XLSX files or thread datasets before deeper processing.

Inputs:

```text
file_refs?
dataset_ids?
preview_rows?
```

Output:

```text
file_summaries
dataset_summaries
columns
preview_tables
quality_warnings
markdown_summary
artifact_links
```

Side effect: read-only.

### `data_integrate`

Alias: `data.integrate`

Purpose: combine multiple CSV/XLSX files or datasets into one canonical thread dataset.

Inputs:

```text
sources
strategy
join_keys?
concat_axis?
sheet_selection?
output_name?
```

Output:

```text
dataset_id
integration_summary
row_count
columns
quality_warnings
markdown_summary
artifact_links
```

Side effect: creates a derived dataset artifact and returns references in the tool result.

### `data_clean`

Alias: `data.clean`

Purpose: handle missing values, outliers, duplicate rows, inconsistent values, and erroneous data.

Inputs:

```text
dataset_id?
operations
output_name?
```

Output:

```text
dataset_id
cleaning_summary
changed_cells_or_rows
warnings
markdown_summary
artifact_links
```

Side effect: creates a cleaned dataset artifact and returns references in the tool result.

### `data_feature_select`

Alias: `data.feature.select`

Purpose: select feature columns and target columns for modeling.

Inputs:

```text
dataset_id?
feature_columns
target_columns
problem_kind?
reason?
```

Output:

```text
feature_columns
target_columns
problem_kind
validation_summary
markdown_summary
```

Side effect: emits a feature-selection tool result for later model tools to use.

## Model Tools

### `model_train`

Alias: `model.train`

Purpose: train and evaluate a specified set of models using the selected dataset, features, targets, and parameters.

Inputs:

```text
dataset_id?
models
parameters?
evaluation_config?
```

Output:

```text
training_run_id
model_artifact_ids
metrics_artifact_ids
best_model_artifact_id?
markdown_summary
artifact_links
```

Side effect: starts training/evaluation and registers model + metrics artifacts.

### `model_hyper_train`

Alias: `model.hyper_train`

Purpose: run hyperparameter training for a specified set of models and parameter spaces.

Inputs:

```text
dataset_id?
models
parameter_spaces
search_config?
evaluation_config?
```

Output:

```text
training_run_id
model_artifact_ids
metrics_artifact_ids
best_model_artifact_id?
best_params
markdown_summary
artifact_links
```

Side effect: starts hyperparameter training/evaluation and registers model + metrics artifacts.

### `model_inference`

Alias: `model.inference`

Purpose: run inference with a selected trained model and produce prediction results.

Inputs:

```text
model_artifact_id
input_dataset_id?
input_file_refs?
output_name?
```

Output:

```text
prediction_artifact_id
row_count
markdown_summary
artifact_links
```

Side effect: creates prediction artifacts.

## First-Slice Static Registry

```text
turn_end
data_peek
data_integrate
data_clean
data_feature_select
model_train
model_hyper_train
model_inference
```

## Deferred

These are deliberately out of the first LLM tool registry:

- LLM-authored arbitrary Python scripts
- generic `script_run_python`
- generic script preset management
- `data_transform`
- DuckDB SQL transformation DSL
- artifact open/export tools
- direct database query tools
- direct raw service invocation tools
- destructive artifact deletion
- arbitrary filesystem read
- arbitrary network access
- arbitrary package installation
