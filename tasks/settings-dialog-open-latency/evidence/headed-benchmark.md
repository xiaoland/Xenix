# Headed Benchmark Evidence

Date: 2026-07-29

## Discovery

`pdm run benchmark-agent-harness-headed -- --collect-only`

Result: `3` cases collected.

The cleaning case requires an exact external private source and was not admitted
without that file. The two self-contained live cases were executed with the
existing explicit Subject, Embedding, and Judge settings.

## Live Results

### Knowledge rainy-season restock

- execution mode: `headed`
- run status: `completed`
- semantic verdict: `pass`
- integrity: `pass`
- turn time: `32.206 s`
- provider retries: `0`
- total subject tokens: `19,074`

Its integrity checks proved the real MainWindow, composer file drop, terminal
Assistant rendering, Knowledge Workspace visibility, terminal Knowledge task
queue, clean window shutdown, and readable SQLite database.

Report:
`build/settings-diagnosis-headed-benchmark-20260729/knowledge.rainy_season_restock-kimi-kimi-k2.6-e5b98cb32fb442df89614d5c3b334e89.json`

### Revenue by region chart

- pytest result: `1 passed, 2 deselected`
- execution mode: `headed`
- run status: `completed`
- semantic verdict: `pass`
- integrity: `pass`
- Judge status/verdict: `completed / pass`
- turn time: `48.447 s`
- provider retries: `0`
- total subject tokens: `24,447`

Its integrity checks proved the real MainWindow, composer file drop, terminal
Assistant rendering, clean window shutdown, and readable SQLite database.

Report:
`build/settings-diagnosis-headed-benchmark-20260729/analysis.revenue_by_region_chart-kimi-kimi-k2.6-9a50965585fc4088bc5aebe44865c50c.json`

The run emitted a Windows `0x8001010d` diagnostic while showing the Qt window.
It did not change the process exit code, persisted result, headed integrity
checks, semantic verdict, or Judge verdict. It is retained as a separate
non-blocking diagnostic rather than silently treated as Settings latency
evidence.

## Evidence Hygiene

The two persisted reports were scanned case-insensitively for API-key,
authorization, bearer-token, URL, and `XENIX_*` patterns. Match count: `0`.

The headed benchmark preloads settings into an isolated runtime and does not
open `SettingsDialog`; it validates the broader visible product journey, while
the Settings click path was measured separately in
[diagnosis.md](diagnosis.md).

## Post-repair Rerun

After the Settings implementation reached its final architecture, the same two
self-contained headed cases were selected again with the explicit Kimi,
Embedding, and Judge settings. Both runs opened the real application and
persisted bounded reports, but the subject provider returned
`llm_provider_http_429` before either Agent turn could complete. A sequential
Knowledge-only retry after a two-minute cooldown received the same provider
response.

These three post-repair attempts are external-provider runtime errors, not
semantic failures or product acceptance passes:

- completed runs: `0`
- `llm_provider_http_429`: `3`
- semantic verdict: `not_evaluated`
- Judge: `not_requested` or `blocked`
- credential-, endpoint-, or `XENIX_*`-shaped report matches: `0`

The earlier successful headed results above remain the completed broad
end-to-end evidence. The repair changes only the Settings status-request path,
which the headed cases intentionally do not open; its final code is covered by
the real-runtime first-paint measurement, service-topology regressions, full
manifest, and application smoke.
