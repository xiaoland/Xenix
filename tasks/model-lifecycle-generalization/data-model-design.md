# Data Model Design

## Objective

Define the contract changes needed to support model families whose training and apply inputs are not limited to supervised feature/target roles.

## Core Product Definition

- A model is a reusable analyzer.
- A reusable analyzer is any persisted service-owned artifact that can be trained from declared input roles and later applied to compatible input roles.
- This includes supervised predictors, unsupervised segmenters, anomaly scorers, association-rule miners, recommenders, and future analysis engines.

## Naming Direction

### ModelFamily

`ModelFamily` answers: "What broad kind of analyzer is this?"

It is user/product-facing and useful for catalog grouping, Agent guidance, documentation, and result wording.

Candidate values:

- `supervised`
- `clustering`
- `anomaly_detection`
- `association_rules`
- `recommendation`

### ModelTaskKind

`ModelTaskKind` answers: "What lifecycle behavior does this trained artifact perform when applied?"

It is service/contract-facing and useful for validation, routing, default result handling, and capability checks.

Candidate values:

- `predictor`
- `segmenter`
- `anomaly_scorer`
- `rule_miner`
- `recommender`

### Difference Between ModelFamily And ModelTaskKind

The two concepts intentionally overlap but are not identical:

- `ModelFamily` is the product taxonomy.
- `ModelTaskKind` is the operational contract.

Examples:

| model key | ModelFamily | ModelTaskKind | Why |
| --- | --- | --- | --- |
| `regression.linear` | `supervised` | `predictor` | Learns target prediction from features. |
| `classification.random_forest` | `supervised` | `predictor` | Also predicts a target, with classification metrics. |
| `clustering.kmeans` | `clustering` | `segmenter` | Produces segment labels, not target predictions. |
| `anomaly.isolation_forest` | `anomaly_detection` | `anomaly_scorer` | Produces anomaly labels/scores. |
| `association.apriori_mlxtend` | `association_rules` | `rule_miner` | Produces reusable rules and applies baskets to rules. |
| `recommendation.item_similarity` | `recommendation` | `recommender` | Produces top-N recommendations from item/user evidence. |

Reason for keeping both:

- Two families can share one task kind in the future.
- One family can have multiple task kinds in the future.
- Agent presentation should not drive execution routing.
- Execution routing should not decide product taxonomy.

### ProblemKind Compatibility

- Keep `ProblemKind` for existing metric/evaluation compatibility in the short term.
- Stop adding new semantic load to `ProblemKind` beyond places that already require it.
- Add nullable or parallel `model_family` / `model_task_kind` fields to catalog and trained-model metadata first.
- Later decide whether storage rows need explicit columns or whether metadata payload is enough.
- Use generic `ProblemKind.ANALYSIS` for current association-rule and recommendation analyzers. The specific analyzer semantics live in `ModelFamily` and `ModelTaskKind`.

## Role Binding Contract

### Concept

`data.feature.select` evolves from feature/target selection into dataset column role binding.

The tool name can remain `data.feature.select` for provider/tool compatibility, but its user-facing description should become broader:

- current meaning: validate feature and target columns
- new meaning: bind dataset columns to semantic roles required by a model/analyzer

### Proposed Persistent Row

Replace `DatasetColumnSelectionRow` with `DatasetColumnBindingRow`.

Decision:

- A table rename is acceptable now.
- Backward-compatible runtime table aliases are not required.
- The implementation must include both schema migration and data migration.
- Existing rows in `dataset_column_selection` must be migrated into `dataset_column_binding` by converting `feature_columns` and `target_columns` into canonical role bindings.

Candidate fields:

- `id: str`
- `dataset_id: str`
- `role_bindings: list[ColumnRoleBinding]`
- `model_key: str | None`
- `model_family: str | None`
- `model_task_kind: str | None`
- `schema_version: int`
- `created_at: datetime`

`role_bindings` is the only canonical column-role source. Supervised feature/target labels may be projected for display from roles `feature` and `target`, but there should be no persisted `feature_columns` or `target_columns` fields in the new table or trained-model metadata.

Proposed SQL table:

```sql
CREATE TABLE dataset_column_binding (
    id VARCHAR NOT NULL PRIMARY KEY,
    dataset_id VARCHAR NOT NULL,
    role_bindings JSON NOT NULL,
    model_key VARCHAR,
    model_family VARCHAR,
    model_task_kind VARCHAR,
    schema_version INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY(dataset_id) REFERENCES dataset (id)
);
```

Migration direction:

1. Create `dataset_column_binding`.
2. Copy each `dataset_column_selection` row into `dataset_column_binding`.
3. For every row, build:
   - `role=feature`, `role_kind=many_columns`, `columns=feature_columns` when features exist.
   - `role=target`, `role_kind=single_column`, `columns=target_columns` when one target exists.
   - `role=target`, `role_kind=many_columns`, `columns=target_columns` only if existing data has multiple targets.
4. Preserve the same `id`, `dataset_id`, and `created_at`.
5. Create indexes on `dataset_id`, `model_key`, `model_family`, and `model_task_kind`.
6. Drop `dataset_column_selection` after copy verification.

Fresh schema should create only `dataset_column_binding`.

### ColumnRoleBinding

Candidate shape:

```json
{
  "role": "feature",
  "columns": ["age", "income"],
  "role_kind": "many_columns",
  "required": true,
  "metadata": {}
}
```

Fields:

- `role: str`
- `columns: list[str]`
- `role_kind: "single_column" | "many_columns"`
- `required: bool`
- `metadata: dict`

Rules:

- `single_column` roles must bind exactly one column.
- `many_columns` roles must bind one or more columns unless the role schema marks them optional.
- Every column must exist in the registered dataset inspection.
- A model may reject extra roles unless its role schema allows additional roles.

## Role Schema Contract

Model catalog entries should expose training and apply role schemas.

### TrainRoleSchema

Candidate shape:

```json
{
  "roles": [
    {
      "name": "feature",
      "kind": "many_columns",
      "required": true,
      "description": "Input columns used to train the predictor."
    },
    {
      "name": "target",
      "kind": "single_column",
      "required": true,
      "description": "Outcome column the predictor learns to predict."
    }
  ],
  "additional_roles": false
}
```

Examples:

- Supervised predictor:
  - `feature: many_columns`
  - `target: single_column`
- Clustering/anomaly:
  - `feature: many_columns`
- Association rules, current wide basket table:
  - `item: many_columns`
- Association rules, possible future long transaction table:
  - `transaction_id: single_column`
  - `item: single_column`
- Item similarity recommendation:
  - `user: single_column`
  - `item: single_column`
  - `rating: single_column`

### ApplyRoleSchema

Candidate examples:

- Supervised predictor:
  - `feature: many_columns`, usually derived from trained metadata.
- Association rules, current wide basket apply:
  - `item: many_columns`, derived from the trained role binding.
- Item similarity recommendation:
  - `item: single_column`, derived from the trained role binding.

## Agent Tool Shape

### Evolved `data.feature.select`

Candidate schema:

```json
{
  "dataset_id": "dataset-id",
  "model_key": "association.apriori_mlxtend",
  "role_bindings": [
    {"role": "item", "columns": ["Item_1", "Item_2", "Item_3"]}
  ]
}
```

Supervised models use the same canonical shape:

```json
{
  "dataset_id": "dataset-id",
  "model_key": "classification.logistic_regression",
  "role_bindings": [
    {"role": "feature", "columns": ["age", "income"]},
    {"role": "target", "columns": ["churn"]}
  ]
}
```

Behavior:

- `role_bindings` is required.
- `model_key` is strongly preferred because it lets the tool validate against the model's train role schema.
- Return `binding_id`, `dataset_id`, `role_bindings`, and resolved model-family metadata when available.

Naming note:

- The provider tool name can stay `data_feature_select` initially for compatibility with existing provider-call mapping.
- The canonical service concept should become `column binding`.
- Public payload should return `binding_id`; the old `selection_id` name should not be carried into the generalized contract.

### `model.train`

Candidate schema change:

```json
{
  "binding_id": "binding-id",
  "models": ["association.apriori_mlxtend"],
  "params_by_model": {
    "association.apriori_mlxtend": {
      "min_support": 0.02,
      "min_confidence": 0.3
    }
  },
  "run_name": "Cross sell rules"
}
```

`binding_id` points to a persisted `dataset_column_binding` row.

### `model.apply`

Candidate schema change:

```json
{
  "trained_model_id": "trained-model-id",
  "input_files": ["path/to/new-baskets.xlsx"],
  "input_rows": {
    "header_index_map": {"item": 0},
    "data": [["Coffee"], ["Milk"]]
  },
  "input_roles": [
    {"role": "basket_items", "columns": ["item"]}
  ],
  "params": {
    "top_n": 10
  }
}
```

Rules:

- For supervised predictors, omit `input_roles` when trained metadata can infer required apply roles and their role-backed columns.
- For association/recommendation, `input_roles` or inline role payloads may be required.
- `params` covers apply-time settings such as `top_n` and score thresholds.

Naming decision:

- New Agent and service contracts should use `model.apply`, not `model.inference`.
- Existing stored or test data using `inference` should be migrated to `apply` where storage contains the value.
- No new public payload fields should use `inference_*`; use `apply_*`.

## Trained Model Metadata

Each trained model should persist:

- `model_key`
- `model_family`
- `model_task_kind`
- `train_role_bindings`
- `apply_role_schema`
- `training_params`
- `artifact_paths`
- `result_contract`

`train_role_bindings` and `apply_role_schema` are canonical. `feature_columns` and `target_columns` must not be persisted as trained-model metadata fields. If a supervised UI or report needs to display them, it should derive those labels on demand from the role bindings.

## Result Contract

Generalized train and apply results should return artifact descriptors, not only prediction CSV paths.

Candidate descriptor:

```json
{
  "artifact_kind": "report",
  "title": "Association Rules",
  "absolute_path": "F:/.../association_rules.csv",
  "mime_type": "text/csv",
  "preview_kind": "table",
  "summary": "248 rules generated.",
  "metadata": {
    "row_count": 248,
    "columns": ["antecedents", "consequents", "support", "confidence", "lift"]
  }
}
```

Preview kinds:

- `table`
- `text`
- `markdown`
- `image`
- `file`
- `model`

Open/export behavior should be driven by registered artifact metadata.

## Storage Strategy

Chosen path:

- Replace `dataset_column_selection` with `dataset_column_binding`.
- Use `binding_id` in Agent and service contracts.
- Store generalized trained-model data in `TrainedModelRow.metadata_payload` first.
- Consider physical trained-model columns for `model_family` and `model_task_kind` only after query needs are proven.
