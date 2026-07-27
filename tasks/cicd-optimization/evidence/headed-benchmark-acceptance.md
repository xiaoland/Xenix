# Headed Agent Benchmark Acceptance

Date: 2026-07-27
Runtime: Windows, Python 3.14.2
Subject: `kimi/kimi-k2.6`
Embedding: `qwen3.7-text-embedding`, batch size 20
Judge: explicit same-model Kimi judge for the chart case

## Proof Shape

`pdm run benchmark-agent-harness-headed` collected the same three case modules as
the headless benchmark. Each cell received a fresh temporary `XENIX_APP_HOME`,
opened the real MainWindow, selected the configured model, dropped the real source
file into the Qt composer, clicked Send, rendered the terminal Assistant message,
closed the window/runtime, and passed SQLite integrity validation.

The Knowledge case additionally opened the Knowledge Workspace, dropped the real
TXT rule, observed its task queue, waited for derivation and the real vector rebuild,
verified the document list, then dropped the inventory CSV into the composer.

No replay, scripted provider, reduced fixture, Tool-trace oracle, or ordinary pytest
case was introduced. Persisted schema-v4 results were scanned for local paths, URLs,
credentials, transcripts, and Tool payloads; all three bounded results passed.

## Results

| Case | Run | Integrity | Semantic | Time | Tokens |
| --- | --- | --- | --- | ---: | ---: |
| `knowledge.rainy_season_restock` | completed | pass | pass | 65.61 s | 19,349 |
| `analysis.revenue_by_region_chart` | completed | pass | pass | 69.21 s | 17,771 |
| `cleaning.april_dine_in_sales` | completed | pass | fail | 1,102.37 s | 239,758 |

The chart Judge completed and is explicitly recorded as `same_model`, not
independent.

The cleaning cell created a readable output and correctly removed the report row,
embedded header row, and exact duplicates. Its final Dataset did not promote the
expected headers, had the wrong shape, and did not preserve the business-row set.
That is the Agent's answer quality, so pytest correctly completed while the semantic
channel recorded `fail`.

## Findings During Acceptance

1. The first live close left `xenix.log` open because process-wide logging setup had
   no matching runtime shutdown. The application now closes and removes owned
   handlers during runtime teardown.
2. The benchmark's SQLite integrity probe used the connection context manager,
   which commits or rolls back but does not close. Explicit connection closure now
   permits deterministic temporary-runtime reclamation.
3. A 15-minute headed Subject timeout contradicted the historical cleaning case.
   The safety valve is now 60 minutes; provider request timeouts remain independently
   configured.
4. Two cleaning attempts encountered provider/Validation failures amid retries.
   Structured Harness exceptions now cross the Qt signal boundary as objects; only
   stable `error_code` values may enter benchmark results. A later complete headed
   run supplied the semantic evidence above.

## Final Local Regression

- `pdm run test`: `30 passed` in 11.58 s.
- `pdm run check`: passed in 4.8 s.
- `pdm run smoke`: passed in 77.8 s.
- Headless and headed offline discovery: the same three cases.
- `git diff --check`: passed.
