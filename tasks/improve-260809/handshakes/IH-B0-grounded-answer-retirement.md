# Impact Handshake B0-GR — Retire Legacy Free-Prose Grounded-Answer Checks

**Status:** consumed; implemented and provider-free verified 2026-08-16.
Extends `IH-O4-E3` to the sibling B0 legacy cases and adds a local tripwire.

## Evidence Trigger

E3 retired the free-prose `_grounded_final_answer` regex in the cleaning case.
The same category error remains in four B0 legacy cases — `ml.clustering`,
`ml.forecasting`, `ml.recommendation`, and `ml.text_insight` — each of
which regex/keyword-matches free prose. They are latent (not in the A1 cohort)
but carry the same whack-a-mole risk. Retiring them keeps the deterministic
layer structural and prevents future false negatives. Sir directed this change.

## Address and Object

- `benchmarks/agent_harness/test_ml_clustering.py` (plus its `_profile_clause` helper)
- `benchmarks/agent_harness/test_ml_forecasting.py`
- `benchmarks/agent_harness/test_ml_recommendation.py`
- `benchmarks/agent_harness/test_ml_text_insight.py`
- `benchmarks/agent_harness/test_rainy_season_restock.py` (plus its six
  free-prose helper functions, discovered during implementation)
- `benchmarks/agent_harness/AGENTS.md` — add a tripwire: deterministic
  semantic checks are structural; explanation-quality grounding belongs to the
  Judge, not a deterministic regex.

For each case: remove the `grounded_final_answer` `OutcomeCheck`, the
`_grounded_final_answer()` function (and `_profile_clause` in clustering),
the `grounded_answer` assignment, and the now-unused `import unicodedata`.
Keep `exact_*_dataset` + `public_artifact_linked` + integrity; keep
`import re` and `_terminal_text` (the artifact-link resolver still uses them).

## State Diff

- **From:** each case's `semantic_checks` is 3 items (exact dataset, linked
  artifact, `grounded_final_answer`[regex]).
- **To:** each case's `semantic_checks` is 2 items (exact dataset, linked
  artifact).

## Blast Radius

Four B0 legacy benchmark cases' deterministic semantic rubrics and the
benchmark local `AGENTS.md`. Downstream: live verdicts for these
characterization-only cases (not the A1 cohort). No product, service, prompt,
oracle, fixture, budget, or Judge-case change.

## Invariants

- Exact-Dataset and linked-Artifact checks remain mandatory and byte-identical;
  integrity unchanged.
- The benchmark stays route-agnostic; the five Judge-based cohort cases and
  `_infra` are untouched.

## Verification

1. No `_grounded_final_answer`, `_profile_clause`, or `unicodedata`
   references remain in the four files.
2. `pdm run test -q`; `pdm run check`;
   `pdm run benchmark-agent-harness-check -q`; collect-only headless + headed.

## Prerequisite Evidence

- E-031; the O4-E3 execution record.

## Return-to-Discussion Triggers

- A case's remaining structural checks would become empty, or the change must
  touch the Judge cases or product code.
