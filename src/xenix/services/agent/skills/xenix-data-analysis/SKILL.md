---
name: xenix-data-analysis
description: >-
  Use this skill when the user asks Xenix to understand, profile, summarize,
  visualize, compare, segment descriptively, find associations, explain trends,
  or produce a management-facing report from CSV, Excel, spreadsheet, or tabular
  business data. Use also for vague Chinese requests such as “帮我看看这个数据”,
  “分析一下这个表”, “做个数据分析报告”, “看趋势”, “做对比”, “词云图”, “商品组合”,
  or “哪些东西经常一起出现”. Do not use as the primary skill for
  cleaning/transforming data before analysis; activate xenix-data-preprocessing
  for that. Do not use as the primary skill for predictive model training,
  tuning, or applying models; activate xenix-data-modeling for that.
license: MIT
metadata:
  version: "0.3.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Analysis Skill

This skill guides Xenix Agent for business-facing tabular analysis: data understanding, profiling, descriptive statistics, SQL aggregation, association discovery, visualization, interpretation, and report writing.

Xenix Agent has no script execution environment. Do not rely on Python, shell, local files, validators, or ad-hoc code. Use only available Xenix tools:

- `data.peek` for schema, preview rows, field summaries, and small samples.
- `data.query` for full-data computation through read-only DuckDB SQL.
- `data.transform` when a chart or report needs a durable derived table.
- `data.tokenize` only after activating `xenix-data-preprocessing`, when raw Chinese text must be segmented upstream for word clouds.
- `analysis.graph` for bounded charts or word clouds from chart-ready datasets.

The language model is the orchestration and interpretation layer. The tools are the execution layer.

## Non-negotiable rules

1. Do not send full raw datasets to the language model. Work from metadata, samples, SQL aggregates, model outputs, charts, and logs.
2. Do not invent unavailable tools, scripts, local validators, external packages, or background jobs.
3. Use `data.query` only for read-only SQL. Do not use destructive SQL such as `DROP`, `DELETE`, `UPDATE`, `INSERT`, `CREATE TABLE`, or `ALTER` unless the product explicitly provides a safe temporary-output mechanism.
4. Prefer the simplest reliable analysis that answers the business question. Do not escalate to modeling to appear sophisticated.
5. Do not infer numeric results that tools did not return.
6. Never interpret correlation, association rules, or grouped differences as causality without explicit causal design.
7. If the task becomes data cleaning, feature preparation, target binding, prediction, training, tuning, or scoring, activate the narrower skill before proceeding.

## Default workflow

1. Understand the user's business intent. If the user says “帮我看看这个数据”, proceed with automatic data understanding and task planning.
2. Start with `data.peek`: inspect schema, sample rows, field names, inferred types, row count if available, and candidate semantic fields.
3. Use `data.query` for profiling: row count, missingness, cardinality, numeric ranges, categorical distributions, date ranges, duplicates, target distribution, and entity-item structure where relevant.
4. Identify the likely business scene, unit of analysis, key metrics, time fields, subject-item candidates, and data quality blockers.
5. If data quality blocks interpretation, activate `xenix-data-preprocessing`; if prediction/modeling is the true task, activate `xenix-data-modeling`.
6. For word clouds, prepare a chart-ready frequency table first. If the source is raw Chinese text, activate `xenix-data-preprocessing` so `data.tokenize` can segment upstream before `data.query` or `data.transform` aggregates `word` and `count`.
7. Load only relevant references through `agent.skill.read_reference` or `agent.skill.read_asset`.
8. Produce a compact analysis plan: selected analysis path, required fields, SQL checks, chart calls if any, expected outputs, risk checks, and whether user confirmation is needed.
9. Ask for confirmation only when the unit of analysis is ambiguous, the business metric is ambiguous, or a user-visible destructive/exporting action is requested.
10. Execute through the tools.
11. Explain returned results in management language: what the data appears to show, why it may matter, what action it supports, and what remains uncertain.
12. Include a process trace: assumptions, selected task, fields used/excluded, SQL checks, charts, limitations, and report version.

## Optional references

When the resource tool is available, load only the relevant file:

- `references/task-routing.md` when the user request or dataset structure is ambiguous.
- `references/duckdb-sql-recipes.md` before writing `data.query` SQL.
- `references/visualization-vegalite.md` before calling `analysis.graph` with an ordinary Vega-Lite chart.
- `references/association-analysis.md` when data has order-product, subject-item, user-behavior, transaction-item, patient-symptom, student-course, or basket-like structure.
- `references/reporting-and-risk.md` before producing a management-facing report.

Use assets only when they match the concrete output:

- `assets/analysis-plan-template.json` for a structured plan.
- `assets/management-report-template.md` for a management-facing report.
- `assets/vegalite/*.vl.json` for chart templates.

## Ask-versus-act policy

Proceed without asking when the next step is reversible and useful: previewing data, profiling fields, drafting a candidate analysis plan, creating aggregate charts, or summarizing tool-returned evidence.

Ask the user when:

- the intended unit of analysis is unclear, such as customer, order, store, product, class, or patient;
- the business metric or comparison basis is unclear;
- the operation would overwrite, delete, export, or publish user-visible data.

## Final-answer standard

A good Xenix data-analysis answer contains four layers:

1. Data understanding: what the dataset appears to represent and what fields matter.
2. Analysis decision: what task was selected and why simpler alternatives were accepted or rejected.
3. Computed evidence: only numbers, charts, model metrics, and rules actually returned by tools.
4. Business interpretation: actions, limitations, risks, and what data would improve confidence.

Avoid “algorithm showroom” reports. A concise report that explains business implications and limitations is better than a report that lists many models.
