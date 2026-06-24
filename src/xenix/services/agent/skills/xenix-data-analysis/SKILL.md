---
name: xenix-data-analysis
description: Use this skill when the user asks Xenix to analyze CSV, Excel, spreadsheet, or tabular business data; inspect a dataset; plan DuckDB SQL profiling with data.query; preview fields with data.peek; create Vega charts with analysis.graph; train, tune, or apply models with model.train, model.hyper_train, or model.apply; build or interpret classification, regression, association/basket, semi-supervised, neural-network comparison, segmentation, forecasting, or management-facing data reports. Use also for vague Chinese requests such as “帮我看看这个数据”, “分析一下这个表”, “哪些因素影响结果”, “预测一下”, “客户分层”, “商品组合”, “词云图”, or “生成数据分析报告”. Do not use for pure file-format conversion, manual spreadsheet editing, database import/export code, or chart design without real data analysis.
license: MIT
metadata:
  version: "0.2.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Analysis Skill

This skill guides Xenix Agent when it handles business-facing tabular data analysis. Xenix Agent has no script execution environment. Do not rely on Python, shell, local files, validators, or ad-hoc code. Use only the available data and analysis tools:

- `data.peek` for schema, preview rows, field summaries, and small samples.
- `data.query` for full-data computation through read-only DuckDB SQL.
- `analysis.graph` for charts through Vega specifications.
- `model.train` for baseline or candidate model training.
- `model.hyper_train` for constrained hyperparameter search.
- `model.apply` for prediction, scoring, probability output, and batch application.

The language model is the orchestration and interpretation layer. The tools are the execution layer.

## Non-negotiable rules

1. Do not send full raw datasets to the language model. Work from metadata, samples, SQL aggregates, model outputs, charts, and logs.
2. Do not invent unavailable tools, scripts, local validators, external packages, or background jobs.
3. Use `data.query` only for read-only SQL. Do not use destructive SQL such as `DROP`, `DELETE`, `UPDATE`, `INSERT`, `CREATE TABLE`, or `ALTER` unless the product explicitly provides a safe temporary-output mechanism.
4. Do not choose a model before identifying the business object, candidate target variable, candidate explanatory variables, time fields, entity fields, and likely leakage fields.
5. Prefer the simplest reliable analysis that answers the business question. Do not stack models to appear sophisticated.
6. Do not infer numeric results that tools did not return.
7. Never interpret correlation, association rules, coefficients, feature importance, or SHAP-like explanations as causality without explicit causal design.
8. Never claim that model output is suitable for automatic decision-making unless risk, compliance, threshold, and human-review boundaries have been checked.

## Default workflow

1. Understand the user's business intent. If the user says “帮我看看这个数据”, proceed with automatic data understanding and task planning.
2. Start with `data.peek`: inspect schema, sample rows, field names, inferred types, row count if available, and candidate semantic fields.
3. Use `data.query` for profiling: row count, missingness, cardinality, numeric ranges, categorical distributions, date ranges, duplicates, target distribution, and entity-item structure where relevant.
4. Identify the likely business scene, unit of analysis, key metrics, target candidates, time fields, subject-item candidates, and data quality blockers.
5. Use the embedded guidance below before proposing or executing the task. Load reference files only when Xenix exposes an explicit constrained skill-reference tool.
6. Produce a compact analysis plan: selected task, required fields, SQL checks, model calls if any, chart calls if any, expected outputs, risk checks, and whether user confirmation is needed.
7. Ask for confirmation only when multiple target variables are equally plausible, the unit of analysis is ambiguous, a business-sensitive threshold must be selected, or a user-visible destructive/exporting action is requested.
8. Execute through the tools. For modeling, train a simple baseline first, tune only when baseline is meaningful, and use `model.apply` for probabilities or predictions.
9. Explain returned results in management language: what the data appears to show, why it may matter, what action it supports, and what remains uncertain.
10. Include a process trace: assumptions, selected task, fields used/excluded, SQL checks, model settings, metrics, thresholds, charts, limitations, and report version.

## Optional references

The following references are packaged with this skill but are not directly readable unless Xenix exposes an explicit constrained skill-reference tool. When that tool is available, load only the relevant file:

- `references/tools-and-io.md` before mapping a plan to tool calls.
- `references/task-routing.md` when the user request or dataset structure is ambiguous.
- `references/duckdb-sql-recipes.md` before writing `data.query` SQL.
- `references/visualization-vega.md` before calling `analysis.graph`, especially for word clouds.
- `references/model-presets.md` before calling `model.train`, `model.hyper_train`, or `model.apply`.
- `references/supervised-learning.md` for classification or regression tasks.
- `references/semi-supervised-learning.md` when labels are partially missing or only some samples are labeled.
- `references/association-analysis.md` when data has order-product, subject-item, user-behavior, transaction-item, patient-symptom, student-course, or basket-like structure.
- `references/neural-network.md` only when using a neural network as a nonlinear comparison model.
- `references/reporting-and-risk.md` before producing a management-facing report.

## Ask-versus-act policy

Proceed without asking when the next step is reversible and useful: previewing data, profiling fields, drafting a candidate analysis plan, creating aggregate charts, or training a baseline model with obvious target and features.

Ask the user when:

- multiple target variables are equally plausible;
- a field could be either the target or an explanatory variable;
- the intended unit of analysis is unclear, such as customer, order, store, product, class, or patient;
- the business threshold is sensitive, such as risk rejection cutoff or marketing contact cutoff;
- a protected, sensitive, or potentially prohibited field may affect decisions;
- the operation would overwrite, delete, export, or publish user-visible data.

## Final-answer standard

A good Xenix data-analysis answer contains four layers:

1. Data understanding: what the dataset appears to represent and what fields matter.
2. Analysis decision: what task was selected and why simpler alternatives were accepted or rejected.
3. Computed evidence: only numbers, charts, model metrics, and rules actually returned by tools.
4. Business interpretation: actions, limitations, risks, and what data would improve confidence.

Avoid “algorithm showroom” reports. A concise report that explains business implications and limitations is better than a report that lists many models.
