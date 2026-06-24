# Xenix Tool Contract

Xenix Agent has no script runtime. Every full-data operation must be expressed through the product tools. Treat this file as the boundary between reasoning and execution.

## Tool responsibilities

### `data.peek`

Use for fast inspection:

- schema and inferred field types;
- first rows or small representative sample;
- row/column counts if available;
- candidate identifiers, time fields, categorical fields, numeric fields, and text fields;
- existing tool-produced summaries.

Use `data.peek` before writing SQL when table names, column names, or field types are unknown.

### `data.query`

Use for all full-data computation with read-only DuckDB SQL:

- profiling;
- missingness, cardinality, distributions, ranges, quantiles;
- grouped statistics and business metrics;
- association-analysis pair counts;
- trend aggregation;
- preparing small chart-ready result tables.

Do not use destructive SQL. Prefer CTEs over persistent tables.

### `analysis.graph`

Use for charts through Vega specifications. The input should be a compact chart-ready table, usually from `data.query`. Do not pass huge row-level datasets to a graph unless the chart type genuinely requires points and the tool can handle them.

### `model.train`

Use for baseline and candidate model training. Provide:

- task type: classification or regression;
- target field;
- allowed feature fields;
- excluded fields with reasons;
- split policy;
- preprocessing expectations;
- metrics required;
- random seed if supported.

### `model.hyper_train`

Use for constrained hyperparameter search after a baseline exists. Do not tune every possible model. Tune one or two plausible candidates with a small grid.

### `model.apply`

Use for scoring and batch prediction. Classification output should request class probabilities when available. Regression output should include prediction values and, if supported, prediction residuals on test data or uncertainty intervals.

## Planning pattern

A robust plan usually follows this sequence:

1. `data.peek` to inspect the dataset.
2. `data.query` to profile the candidate target and feature fields.
3. `data.query` to create grouped or chart-ready aggregates.
4. `analysis.graph` for charts that help explain the result.
5. `model.train` for a simple baseline if prediction is justified.
6. `model.hyper_train` only if baseline results and business value justify tuning.
7. `model.apply` to generate scored records, ranked lists, or prediction outputs.

## Field handling rules

Always identify and exclude fields that are not valid predictive features:

- pure identifiers: ID, UUID, order number, transaction number, phone number, email, name;
- post-outcome fields: approval date after target, churn reason after churn, repayment status after default;
- duplicates of target: outcome text that directly encodes the label;
- sensitive fields if the business context makes their use risky or prohibited;
- high-cardinality free text unless the tool has a text feature pipeline and the user needs text modeling.

## Output discipline

When tool output is incomplete, say so. Do not patch missing metrics through estimation. If the model tool returns only accuracy, ask for or run a second evaluation that includes the task-appropriate metrics.
