---
name: xenix-data-analysis
description: >-
  Use this skill when the user asks Xenix to understand, profile, summarize,
  visualize, compare, segment descriptively, find associations, explain trends,
  produce a management-facing report, or apply saved business rules and experience
  to CSV, Excel, spreadsheet, or tabular business data. Use also for vague Chinese
  requests such as “帮我看看这个数据”,
  “分析一下这个表”, “做个数据分析报告”, “看趋势”, “做对比”, “词云图”, “商品组合”,
  or “哪些东西经常一起出现”. Do not use as the primary skill for
  cleaning/transforming data before analysis; activate xenix-data-preprocessing
  for that. Do not use as the primary skill for predictive model training,
  tuning, or applying models; activate xenix-data-modeling for that.
license: MIT
metadata:
  version: "0.5.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Analysis

Answer the business question using computed evidence and a useful explanation. Select tools according to what is missing; profiling, Knowledge lookup, charts, and a multi-section report are not mandatory stages.

## Capabilities

- `analysis.profile`: Dataset structure and quality summaries.
- `data.query`: DuckDB SQL for inspection, aggregation, comparisons, and calculations. Queries may retrieve the values needed for the question.
- `data.transform`: a reusable derived table, including joins or chart data.
- `analysis.graph`: charts from a registered Dataset; word clouds use `wordcloud_spec`.
- `knowledge.lookup`: saved business rules and context when relevant. Attribute retrieved claims separately from computations.

Tools are activated lazily through Skills. Modeling capabilities belong to `xenix-data-modeling`; cleaning and tokenization belong to `xenix-data-preprocessing`. Activate additional capabilities when needed. There is no script execution environment.

Use the user's stated intent and available evidence. Ask about ambiguity only when plausible interpretations would materially change the answer. Reuse existing results instead of repeating checks, and finish when the requested analysis is supported. A chart or model is useful only if it improves the answer.

Present the meaningful findings, public output links, and decision-relevant limitations in the user's language. Match detail to the request. Correlation and co-occurrence alone do not establish causality.

## Optional references

- [Task choices](references/task-routing.md)
- [DuckDB examples](references/duckdb-sql-recipes.md)
- [Association analysis](references/association-analysis.md)
- [Charts](references/visualization-vegalite.md)
- [Reporting](references/reporting-and-risk.md)
