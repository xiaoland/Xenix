---
name: xenix-data-preprocessing
description: Clean missing values, duplicates and types; combine or reshape tables; tokenize text and bind model roles.
license: MIT
metadata:
  version: "0.8.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Preprocessing

Choose transformations from the intended business meaning. Missing values, leading-zero codes, outliers and duplicate keys may carry information; an unresolved choice matters when it changes the result.

Cleaning operations act on the current intermediate table. After changing columns, later positional references may identify different fields. Source-column positions also differ from positions in a projected query result.

Whole-Dataset cleaning produces reusable business data. Learned imputation, encoding, scaling and text preparation for model evaluation belong inside training, where the service fits them on training partitions.

SQL and cleaning operations can express the same transformation; choose the simpler representation. CSV dates may need explicit casts. Operation details and examples are available in the resource index.
