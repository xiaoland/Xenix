# Artifact Link Contract

## Status

- Mode: Explore.
- Scope: sample artifact link format for Chatbot preview rendering.

## Goal

Tools return markdown summaries with artifact links. Chatbot detects artifact links and renders previews for images, tables, CSV/XLSX files, reports, model metadata, and metrics.

## Link Format

Candidate URI:

```text
artifact://<artifact_id>?view=<view>&title=<url_encoded_title>
```

Examples:

```markdown
训练完成，最佳模型为 RandomForestClassifier。

- 指标报告：[metrics.md](artifact://art_01JZ9METRICS?view=report&title=Metrics)
- 混淆矩阵：[confusion_matrix.png](artifact://art_01JZ9CM?view=image&title=Confusion%20Matrix)
- 预测结果：[predictions.csv](artifact://art_01JZ9PRED?view=table&title=Predictions)
- 清洗后数据：[cleaned_dataset.xlsx](artifact://art_01JZ9DATA?view=table&title=Cleaned%20Dataset)
```

## Preview Rules

- `view=image`: render image preview.
- `view=table`: render row/column preview with a configured row limit.
- `view=report`: render markdown report preview.
- `view=metrics`: render compact metrics table.
- `view=model`: render model metadata and training summary.
- Unknown view: render as a clickable artifact chip.

## Artifact Lookup

The URI contains only an artifact id and rendering hint. Chatbot asks the artifact resolver for:

```text
artifact_id
kind
title
mime_type
canonical_path
summary
preview_payload
```

## Open Questions

- Exact preview row limit for CSV/XLSX.
- Whether artifact ids should be UUIDs, prefixed ids, or database ids.
- Whether links should include thread id for additional validation.
