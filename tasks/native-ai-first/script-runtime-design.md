# Script Runtime Future Direction

## Status

- Mode: Explore.
- Scope: deferred direction only.
- Current first slice does not expose LLM-authored arbitrary Python scripts.

## Current Decision

The first LLM tool registry starts with bounded data and model tools:

```text
data_peek
data_integrate
data_clean
data_feature_select
model_train
model_hyper_train
model_inference
```

LLM-authored custom preprocessing, training, inference, or generic Python execution is deferred.

## Future Direction

Later, Xenix may add a managed Python runtime where the LLM can use preset scripts or self-authored scripts.

Any future script run must:

- execute in a managed workspace
- declare required outputs before execution
- produce outputs through Xenix-provided APIs
- register datasets, models, metrics, predictions, tables, charts, or reports
- validate a manifest before success

## Why Deferred

The generic script runtime is powerful but broad. First-slice design should validate the AI-first interaction model with a smaller, safer function-calling registry.

## Presentation Rule Still Applies

Tools can return markdown links to images, tables, CSV/XLSX outputs, reports, and charts. ChatBox handles preview rendering.
