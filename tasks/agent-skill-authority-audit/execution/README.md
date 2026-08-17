# Execution

A/B benchmark setup (before/after), same subject model, same 4-case subset:

- subject: kimi-k2.6 (moonshot), judge: kimi-k2.5, embedding: qwen3.7-text-embedding
- subset: test_revenue_by_region_chart (analysis), test_rainy_season_restock
  (analysis+knowledge), test_ml_cleaning (preprocessing), test_ml_clustering
  (modeling)
- before: --harness-variant baseline   -> execution/before/
- after:  --harness-variant skill-prose-compressed -> execution/after/

Note: the harness benchmark spawns each cell via Windows named pipes
(multiprocessing), which the default confined sandbox denies. The before-run
was therefore escalated to danger-full-access (per the one-shot escalation
rule) so the benchmark the user requested can execute.
