---
name: xenix-data-preprocessing
description: >-
  Use this skill when the user asks Xenix to prepare tabular data before
  analysis or modeling: inspect schema quality, clean missing values, normalize
  column names, remove duplicates, convert types, standardize text/categories,
  clip outliers, encode categories, scale numeric fields, tokenize Chinese text,
  integrate datasets, transform/query data into derived datasets, select
  feature/target roles, or fix data-quality blockers. Use for Chinese requests
  such as “清洗数据”, “预处理”, “处理缺失值”, “去重”, “字段类型不对”, “合并表”,
  “构造特征”, “分词”, “选择特征和目标”, or “训练前准备数据”. Do not use as the
  primary skill for final analysis reports, charts, or prediction interpretation; use xenix-data-analysis or
  xenix-data-modeling after the data is ready.
license: MIT
metadata:
  version: "0.7.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Preprocessing

Prepare data for the user's intended use. Choose operations from known data and business meaning; no fixed profile/query/metadata/validation sequence is required. Existing tool results are usable evidence, and a successful transformation does not need a second read merely to confirm its reported effects.

## Capabilities

- `analysis.profile` summarizes structure and quality. `data.query` inspects values and computes DuckDB SQL; use these when information is missing.
- `data.clean` applies an operation list to a derived Dataset. `data.clean.metadata` describes unfamiliar operations.
- `data.transform` materializes SQL calculations, filters, joins, or aggregates. `data.integrate` vertically appends Datasets.
- `data.tokenize` creates text tokens or term frequencies. Modeling analyzers already handle their own raw-text preparation.
- `data.feature.select` binds model roles. `knowledge.lookup` supplies relevant saved business definitions.

Cleaning and SQL are alternatives where both express the operation. Choose the simpler representation. Derived Dataset and Artifact identifiers returned by the tools support follow-up work and delivery.

## Operation semantics

Cleaning operations run left-to-right on the current intermediate table. Names and zero-based indexes refer to that table; after a column-changing operation, use names for later operations because positions may have changed. SQL `column_reference: "indexes"` exposes temporary `c0`, `c1`, ... names for awkward headers. Positions from projected query results do not identify original source columns.

For SQL, a single Dataset is named `input`; explicit bindings use their aliases. CSV dates may be strings: cast them for date arithmetic or comparisons. Preserve meaningful identifiers such as leading-zero codes when converting types.

Common cleaning operations include `missing.fill_median`, `missing.fill_mode`, `missing.fill_constant`, `duplicate.exact_rows`, `text.trim`, `text.lowercase`, and `validation.non_negative`. Parameters and further examples are in [preprocessing-tools.md](references/preprocessing-tools.md).

Changes should reflect the requested business meaning. Ask only when an unresolved choice, such as the meaning of missing values or the intended aggregation grain, would materially alter the result. Existing user instructions authorize their requested transformations; do not ask again for each operation.

Learned model preprocessing belongs inside model training, while these tools transform the whole Dataset. Report the delivered result, material changes and unresolved issues; no prescribed checklist or handoff report is required. [Data-quality considerations](references/data-quality-checks.md) are optional guidance.
