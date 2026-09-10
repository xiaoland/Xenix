---
name: xenix-data-modeling
description: >-
  Use this skill when the user asks Xenix to predict, classify, regress, score,
  rank, train a model, tune hyperparameters, apply a trained model, estimate
  risk/probability, identify drivers through model output, compare supervised
  models, produce personalized Top-K recommendations from explicit ratings,
  forecast a regular time series, compare seasonal-naive,
  Holt-Winters, and bounded-auto SARIMA, handle partially labeled data, run text classification, text
  clustering, topic modeling, similarity retrieval, or use neural networks as a
  candidate model. Use for Chinese requests such as “预测一下”, “训练模型”,
  “哪些因素影响结果”, “客户流失预测”, “风险评分”, “转化概率”, “调参”, “应用模型”,
  “销量预测”, “需求预测”, “未来几周”, “个性化推荐”, “推荐商品”, “Top-K 推荐”,
  “文本分类”, “主题分析”, “相似检索”, or “半监督”.
  Do not use for pure descriptive profiling, charts, reporting, or association
  analysis unless modeling is explicitly part of the task; use xenix-data-analysis
  for that. Additional preprocessing tools are available through xenix-data-preprocessing.
license: MIT
metadata:
  version: "0.10.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Modeling

Solve the user's modeling question with the available Xenix tools. Choose the work needed for the requested deliverables; there is no mandatory sequence of profiling, metadata, baseline, tuning, inspection, or charts. Reuse information and completed results already available.

## Capabilities

- `model.metadata` describes models, roles, and parameters. A known `model_key` gives details directly; `model_family` with `include_details: true` gives candidate schemas together. Metadata is useful when the required contract is unknown.
- `data.feature.select` creates the role binding consumed by training. `model.train` accepts several distinct model keys together; different parameterizations of one key need separate calls. `model.hyper_train` searches supported parameter grids.
- `model.apply` uses a retained model for predictions. Completed results expose the generated Dataset and Artifact; `model.task.query` supplies pending status or missing details. Reuse the retained model instead of training it again for delivery.
- `analysis.profile` summarizes structure and quality; `data.query` computes or inspects values; `data.transform` creates derived tables. Use whichever evidence the question needs, without a one-query quota.
- `knowledge.lookup` retrieves relevant saved business definitions. `analysis.graph` creates a chart when it helps answer the question.

## Modeling judgment

Choose candidates by business objective, data, and runtime cost. A comparison need not include every model. Training already supplies evaluation and baseline evidence; use those results without rechecking their arithmetic or internal digests. Investigate missing or contradictory evidence, and distinguish failed candidates from successful ones.

Features should be available at prediction time. Repeated entities can be bound as `group`; learned imputation, encoding, scaling, and vectorization belong to model training. The service owns split construction and validation. Explain meaningful evaluation limitations rather than reciting implementation checks.

Raw-text analyzers accept raw text and retain their preparation. Forecasting uses time/target roles and optional group; forecast apply takes a future horizon instead of input rows. Exact contracts and optional domain guidance are below.

Deliver the requested outputs with returned public links, the evidence supporting the choice, and relevant limitations. Stop when that answers the request; extra models, charts, queries, and report sections are optional. Predictions and associations alone do not establish causality.

## References

Read a reference when its domain detail is useful:

- [Forecasting](references/forecasting.md)
- [Supervised learning](references/supervised-learning.md)
- [Recommendation](references/recommendation.md)
- [Text classification](references/text-classification.md)
- [Text discovery and retrieval](references/text-discovery-retrieval.md)
- [Semi-supervised learning](references/semi-supervised-learning.md)
- [Neural networks](references/neural-network.md)
- [Model parameters](references/model-presets.md)
