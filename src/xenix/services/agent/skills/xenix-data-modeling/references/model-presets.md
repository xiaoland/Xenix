# Model Choices and Parameters

Examples of interpretable candidates are `classification.logistic_regression`, `classification.decision_tree`, `regression.linear`, and `regression.ridge`. Gradient boosting, random forests, and MLPs offer nonlinear alternatives. These are options, not a required progression.

`model.metadata` returns current parameter schemas and defaults. A known model key needs no family browse first; `include_details: true` can return a whole family's schemas in one call. `include_param_grid_schema: true` includes tuning contracts when needed.

`model.train` accepts distinct keys in `models` and per-key parameters in `params_by_model`; omitted overrides use defaults. `model.hyper_train` accepts supported grids. Select search size by likely business value rather than a fixed grid from this document.

For MLP, `hidden_layer_size` is one integer. Reuse retained models for Apply. Further training is useful only if it answers an unresolved question or improves a requested outcome.
