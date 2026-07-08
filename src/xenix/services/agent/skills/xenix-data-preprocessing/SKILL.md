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
  version: "0.3.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Preprocessing Skill

This skill guides Xenix Agent when the task is to prepare data safely before analysis or modeling. It covers inspection, quality checks, cleaning plans, transformations, dataset integration, feature preparation, and role binding.

Xenix Agent has no script execution environment. Use only available Xenix tools:

- `data.query` for schema projection, preview rows, read-only profiling, and validation checks.
- `data.integrate` when multiple registered datasets need to be vertically appended.
- `data.clean.metadata` to inspect supported cleaning operations.
- `data.clean` to apply explicit predefined cleaning operations to one dataset.
- `data.tokenize` to create a derived dataset from one Chinese text column before word clouds or text-analysis models.
- `data.transform` to materialize SELECT/CTE transformations as a derived dataset.
- `data.feature.select` to create a role-binding snapshot before modeling.

## Non-negotiable Rules

1. Never invent cleaning operations. Call `data.clean.metadata` before planning unfamiliar `data.clean` operations.
2. Do not overwrite or delete user data. Cleaning and transformations should create derived datasets or tool-result checks.
3. Do not silently drop rows or columns. Explain the operation and why it is acceptable.
4. Use read-only `data.query` for evidence before changing data.
5. Preserve business meaning. Normalize types, names, and categories without destroying semantic distinctions.
6. Treat role binding as a durable modeling boundary: target, partial_target, feature, excluded fields, and reasons must be explicit.
7. If the task becomes descriptive analysis or reporting, activate `xenix-data-analysis`. If it becomes training/scoring, activate `xenix-data-modeling`.

## Default Workflow

1. Use `data.query` to inspect schema, sample rows, row/column counts, missingness, duplicates, cardinality, numeric ranges, category variants, date parseability, and candidate target/feature quality.
3. Classify issues by impact:
   - blockers: impossible type, missing target, duplicate keys, invalid unit of analysis, severe leakage;
   - quality risks: missingness, outliers, category inconsistencies, high-cardinality text;
   - convenience cleanup: column names, type casts, whitespace, display formats.
4. Call `data.clean.metadata` before selecting cleaning operations.
5. Use `data.clean` for atomic supported operations such as missing-value handling, duplicate handling, type conversion, text standardization, outlier clipping, categorical encoding, or numeric scaling.
6. Use `data.tokenize` when raw Chinese text must become a stable derived dataset for word clouds, text clustering, text classification, topic modeling, or similarity retrieval.
7. Use `data.transform` for SQL-derived features, filtering, joins, aggregation, reshaping, or durable chart/model-ready derived datasets. Use it, not `data.integrate`, for horizontal joins.
8. Use `data.feature.select` when a modeling task needs explicit target/features/exclusions.
9. Validate the result with `data.query`.
10. Hand off to `xenix-data-analysis` or `xenix-data-modeling` only after the prepared dataset or role binding is clear.

## Optional References

When the resource tool is available, load only the relevant file:

- `references/preprocessing-tools.md` before mapping preprocessing work to Xenix tools.
- `references/data-quality-checks.md` before profiling missingness, duplicates, type quality, category consistency, leakage, or role binding.

## Ask-Versus-Act Policy

Proceed without asking when the next step is reversible and diagnostic: previewing data, profiling quality, listing cleaning options, or validating an existing derived dataset.

Ask the user when:

- dropping rows or columns would remove meaningful business records;
- a missing value may mean a real business state rather than absence;
- multiple fields could be the target or unit identifier;
- category merging changes business taxonomy;
- a transformation changes grain, such as order line to order, customer, day, or product;
- a sensitive field may affect model features or decision support.

## Final-Answer Standard

A good preprocessing answer contains:

1. Original data quality findings.
2. Cleaning or transformation operations actually applied.
3. Derived dataset or role-binding identifiers returned by tools.
4. Remaining risks and assumptions.
5. Clear handoff: ready for analysis, ready for modeling, or blocked pending user decision.
