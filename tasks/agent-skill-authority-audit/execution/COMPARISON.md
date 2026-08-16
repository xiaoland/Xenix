# Before → After Comparison (single-sample characterization)

subject kimi/kimi-k2.6, judge kimi-k2.5, 2026-08-16
harness-variant: baseline → skill-prose-compressed

| case | semantic | rounds | before tokens | after tokens | token delta | seconds |
| --- | --- | --- | --- | --- | --- | --- |
| analysis.revenue_by_region_chart | pass→pass | 4→4 | 22,934 | 21,526 | -1,408 (-6.1%) | 56.19→32.14 |
| knowledge.rainy_season_restock | pass→pass | 5→5 | 47,155 | 32,354 | -14,801 (-31.4%) | 56.64→55.2 |
| ml.cleaning_service_tickets | pass→pass | 4→4 | 24,614 | 25,399 | +785 (3.2%) | 38.74→48.51 |
| ml.clustering_two_segments | fail→fail | 8→10 | 90,165 | 115,718 | +25,553 (28.3%) | 65.81→72.67 |

| **total** | **3/4 → 3/4** | — | **184,868** | **194,997** | **+10,129 (+5.5%)** | — |

## Notes

- Success rate unchanged (3/4). clustering_two_segments fails in both.
- revenue and rainy_season consume fewer tokens; cleaning ~flat; clustering +28%.
- Single-sample characterization: NOT gating evidence. Formal A/B requires
  3 comparable headless repetitions per the benchmark policy.
- The two earlier revenue runtime_errors were an artifact of running the
  benchmark concurrently with the full 149-test suite (child-process/stream
  interference). Isolated re-runs both pass.
- The clustering case failure is pre-existing (fails in baseline too) and
  is a separate diagnosis, not a skill-prose effect.
