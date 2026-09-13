# Data Preparation Notes

Tool definitions describe callable inputs and results. `data.clean.metadata` provides operation parameters, and `model.metadata` provides model roles; these notes explain choices that depend on the data.

## Table grain and SQL

Appending compatible rows with `data.integrate` preserves the row grain. A join may multiply rows when keys repeat; its keys and expected cardinality determine whether later totals still answer the business question. `data.transform` supports joins, filters, calculations and aggregation without requiring an atomic-cleaning attempt.

`data.query` computes a result for inspection; `data.transform` saves one for reuse or delivery. Both use DuckDB SQL, with `input` for a single Dataset or explicit aliases from `bindings`.

Names and indexes are alternative column selectors. `column_reference: "indexes"` exposes source columns as `c0`, `c1`, ... for that SQL call. For a source ordered as `[order_id, amount, status]`, this projection returns two columns, but amount remains source index 1:

```sql
SELECT c1 AS amount, c2 AS status FROM input
```

The returned table's positions describe that projection, not the original Dataset. Named result columns make saved transformations easier to reuse.

## Cleaning order

Operations consume the preceding operation's output. For example, filtering invalid rows before filling missing values with the median fits the median on retained rows; reversing them uses the original population. Removing or expanding columns changes the positions available to later operations; known names can remain clearer across such changes.

Row-validation operations and SQL predicates can express the same business rule. Choose the representation that makes the intended result easiest to understand. Identifiers with leading zeroes, missing labels and repeated events are examples where mechanical type conversion, filling or deduplication can change business meaning.

## Text preparation

`data.tokenize` creates reusable token data. `token_text` keeps source rows and appends `token_text` and `token_count`; `token_rows` emits one token per row with `source_row_number`, optional identifiers, `token_index` and `token`.

The multilingual profile supports single terms or two-word phrases, plus one-column custom dictionary and stopword Datasets. The Chinese profile uses its built-in preparation. Aggregating token rows by term produces frequencies for a word cloud; tokenization alone does not count across documents.

Raw-text models retain their own preparation for training and application. A separate token Dataset is useful when the requested analysis itself needs tokens, rather than a prerequisite for every text model.

## Model roles

`data.feature.select` saves roles for training. The appropriate roles depend on the model: examples include feature/target, text, user/item/rating, time and group. Features should represent information available at prediction time; repeated entities may require a group role to prevent the same entity appearing across evaluation partitions. Learned imputation, encoding and scaling belong inside training so evaluation partitions do not influence fitting.
