# Visualization and Vega Reference

Use this file before calling `analysis.graph`. The graph tool should receive a compact Vega specification for a registered, chart-ready dataset. Xenix injects the selected dataset into the Vega spec; do not add or edit Vega `data.values`.

## Chart selection

| User intent | Recommended chart | Data preparation |
|---|---|---|
| 比较类别大小、Top N、排名 | horizontal bar | `GROUP BY` category, sort descending, limit 10-20 |
| 趋势、时间变化 | line chart | aggregate by day/week/month/quarter |
| 占比结构 | bar or pie only for few categories | categories should sum to a meaningful whole |
| 两个数值变量关系 | scatter | sample or aggregate if there are too many points |
| 类别 × 类别 强度 | heatmap | group by both dimensions |
| 数值分布 | histogram or boxplot | bin or compute quantiles |
| 高频词、标签、关键词 | word cloud | word-frequency table with `word` and `frequency` |

## Visual quality rules

- Use a descriptive title and short subtitle when the Vega schema supports it.
- Prefer horizontal bars for more than 6 categories or long Chinese labels.
- Sort ranked charts by value descending.
- Limit category charts to Top 10-20; group the rest as “其他” when useful.
- Use readable labels: avoid raw technical column names in titles.
- Use restrained palettes. Do not overuse bright categorical colors.
- For Chinese text, prefer system fonts or `Noto Sans SC` when available.
- Avoid 3D, decorative gradients, excessive labels, and overloaded dashboards.

## Word cloud workflow

1. Use `data.query` to inspect candidate word-frequency results.
2. Remove empty words, stop words, meaningless one-character tokens, and overly generic business words.
3. Limit to around 80-150 words.
4. Use `data.transform` to materialize a registered dataset with exactly `word` and `frequency` columns.
5. Call `analysis.graph` with a Vega word-cloud spec using a mark-level `wordcloud` transform.
6. Explain the word cloud as a frequency view, not sentiment or causality.

A word cloud is appropriate for qualitative overview. It is not a substitute for exact ranking. Pair it with a Top-N bar chart when precise comparison matters.

## Vega word cloud template

Use `assets/vega/wordcloud.vg.json` as the default template. Before graphing, create a registered dataset shaped like:

```json
[
  {"word": "复购", "frequency": 128},
  {"word": "价格", "frequency": 96},
  {"word": "服务", "frequency": 73}
]
```

Do not place wordcloud under `from.transform`, and do not add top-level Vega `data`. The accepted Xenix profile puts the transform directly on the text mark:

```json
{
  "type": "text",
  "from": {"data": "xenix_data"},
  "encode": {"enter": {"text": {"field": "word"}}},
  "transform": [
    {
      "type": "wordcloud",
      "text": {"field": "word"},
      "fontSize": {"field": "datum.frequency"},
      "fontSizeRange": [12, 56]
    }
  ]
}
```

## Vega horizontal bar template

Use `assets/vega/topn-bar.vg.json` for ranked category comparisons. Prepare a registered dataset with:

```json
[
  {"category": "A", "value": 120},
  {"category": "B", "value": 96}
]
```

## Vega line chart template

Use `assets/vega/time-line.vg.json` for a single time-series metric. Prepare a registered dataset with:

```json
[
  {"period": "2026-01", "value": 1200},
  {"period": "2026-02", "value": 1380}
]
```

## Vega heatmap template

Use `assets/vega/heatmap.vg.json` for two categorical dimensions and one measure. Prepare a registered dataset with:

```json
[
  {"x": "渠道A", "y": "品类1", "value": 42},
  {"x": "渠道B", "y": "品类1", "value": 31}
]
```

## Common interpretation phrases

- “这个图展示的是出现频率，不表示好坏或因果。”
- “Top N 之外的长尾类别没有消失，只是为了阅读性被省略。”
- “趋势图反映的是按当前口径汇总后的变化，是否为真实季节性还需要更长时间跨度验证。”
- “词云适合快速看主题密度；若要精确比较，应同时查看频次表或柱状图。”
