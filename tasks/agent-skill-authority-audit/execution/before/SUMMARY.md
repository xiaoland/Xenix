# Before (baseline) — harness-variant=baseline

subject kimi/kimi-k2.6, judge kimi-k2.5, 2026-08-16

| case | semantic | rounds | tokens | seconds |
| --- | --- | --- | --- | --- |
| analysis.revenue_by_region_chart | pass | 4 | 22,934 | 56.19 |
| knowledge.rainy_season_restock | pass | 5 | 47,155 | 56.64 |
| ml.cleaning_service_tickets | pass | 4 | 24,614 | 38.74 |
| ml.clustering_two_segments | fail | 8 | 90,165 | 65.81 |

total tokens = 184,868; semantic = 3/4 pass
