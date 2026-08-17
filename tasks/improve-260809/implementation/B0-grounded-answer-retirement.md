# Implementation Plan B0-GR — Retire Legacy Free-Prose Grounded-Answer Checks

**Status:** Completed and provider-free verified 2026-08-16.

**Handshake:** [IH-B0-GR](../handshakes/IH-B0-grounded-answer-retirement.md).

## Outcome

Remove the free-prose `_grounded_final_answer` regex from the four sibling B0
legacy cases so their deterministic semantic layer asserts only mechanical
grounding (exact Dataset + linked public Artifact), and add a local tripwire
against reintroducing free-prose grounding.

## Coherent Passes

1. For `test_ml_clustering.py`, `test_ml_forecasting.py`,
   `test_ml_recommendation.py`, and `test_ml_text_insight.py`: remove the
   `grounded_final_answer` `OutcomeCheck`, the `grounded_answer`
   assignment, the `_grounded_final_answer()` function (and
   `_profile_clause` in clustering), and `import unicodedata`.
2. Add the deterministic-structural tripwire to
   `benchmarks/agent_harness/AGENTS.md`.
3. Run `pdm run test -q`, `pdm run check`,
   `pdm run benchmark-agent-harness-check -q`, and collect-only in both modes.
4. Close the packet: execution record, dashboard Next Step, and the consumed
   handshake status.

## Stop Conditions

Stop if a case's remaining structural checks would become empty, or if the
change must touch the Judge cases or product code.

## Acceptance

All four cases expose exactly `exact_*_dataset` + `public_artifact_linked`
semantic checks, the AGENTS.md tripwire is present, and all offline gates pass.

## Execution

Recorded in `execution/B0-grounded-answer-retirement-2026-08-16.md`.
