---
name: xenix-data-modeling
description: Train, compare and apply models for prediction, forecasting, recommendation, clustering, anomalies, association rules and text analysis.
license: MIT
metadata:
  version: "0.11.0"
  product: "Xenix"
  language: "zh-CN"
  runtime: "tool-only; no script execution"
---

# Xenix Data Modeling

Choose candidates by the business objective, data and runtime cost. Features must be available at prediction time; repeated entities may need a group role. The training service owns splitting and learned preprocessing.

Training returns evaluation and baseline evidence. Use that evidence to select a retained model and distinguish failed candidates from usable ones. Model application reuses the saved object; raw-text analyzers retain their text preparation, and forecasting applies a future horizon.

Model roles and parameter schemas are available through `model.metadata`. Family references cover forecasting, recommendation, supervised and partially labeled learning, text classification, clustering, topics and retrieval. Predictions and associations alone do not establish causality.
