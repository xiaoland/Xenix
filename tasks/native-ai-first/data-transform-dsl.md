# Deferred Data Transform DSL

## Status

- Mode: Explore.
- Scope: future `data_transform` transformation language.
- Current first slice excludes `data_transform` and does not require DuckDB.

## Decision Candidate

Use DuckDB SQL as the future `data_transform` DSL.

Reasoning:

- SQL is the mature, widely understood transformation language.
- DuckDB runs embedded in Python and fits the native desktop architecture.
- DuckDB can query CSV files and Pandas DataFrames from Python.
- DuckDB supports SELECT expressions, casts, joins, aggregates, window functions, and common analytical transforms.
- DuckDB has an Excel extension for `.xlsx` workflows.

Sources checked:

- DuckDB Python data ingestion: https://duckdb.org/docs/stable/clients/python/data_ingestion
- DuckDB SELECT statement: https://duckdb.org/docs/current/sql/statements/select.html
- DuckDB Excel extension: https://duckdb.org/docs/lts/core_extensions/excel

## Tool Shape

Future `data_transform` can accept a bounded DuckDB SQL SELECT query over registered input dataset aliases.

```text
data_transform(
  dataset_id?,
  input_aliases?,
  sql,
  output_name?,
)
```

Example:

```sql
WITH typed AS (
  SELECT
    customer_id,
    CAST(order_date AS DATE) AS order_date,
    TRY_CAST(amount AS DOUBLE) AS amount,
    region
  FROM input
),
aggregated AS (
  SELECT
    customer_id,
    region,
    COUNT(*) AS order_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount
  FROM typed
  GROUP BY customer_id, region
)
SELECT * FROM aggregated;
```

## Scope

Good fit:

- type conversion
- column derivation
- joins
- unions
- filtering
- aggregation
- date/time extraction
- one-hot style CASE columns when needed
- numeric normalization through SQL expressions

Model-specific preprocessing can remain inside `model_train` / `model_hyper_train` pipelines, especially scikit-learn encoders, imputers, scalers, and model-specific handling.

## Output

Future `data_transform` creates a derived dataset artifact and can mark it as the active thread dataset.

Output:

```text
dataset_id
row_count
schema
transform_summary
markdown_summary
artifact_links
```

## Open Questions

- Whether first slice accepts only one input alias `input` or multiple aliases.
- Whether Excel files are normalized through pandas/openpyxl before DuckDB, or DuckDB reads `.xlsx` directly through its Excel extension.
- Whether SQL validation only allows SELECT/CTE query shapes.
