# O4-E3 Cleaning Grounded-Answer Check Retirement — 2026-08-16

## Outcome

The cleaning benchmark no longer regex-matches free prose for row count and
median. Its deterministic semantic layer asserts only mechanical grounding: the
exact 5 × 4 Dataset and a linked public Artifact. This removes the false
negatives E1/E2 chased and aligns the case with the structural-only convention
used by the Judge-based cohort cases. Explanation-quality grounding (reporting
5 rows and median 21 in prose) is deferred to the Judge (option A, future).

## Implemented State Diff

- `benchmarks/agent_harness/test_ml_cleaning.py`:
  - removed the `grounded_final_answer` `OutcomeCheck`;
  - removed `_grounded_final_answer()` (the regex) and `import unicodedata`;
  - `semantic_checks` is now `(exact_cleaned_dataset, public_artifact_linked)`.
  - `_terminal_text` and `import re` remain for the artifact-link resolver.

## Verification

- Replayed the retained A4 reports: all three cells have
  `exact_cleaned_dataset` + `public_artifact_linked` + integrity passing, so
  their deterministic semantic verdict reads pass 3/3 (previously 1/3 due to the
  removed regex false negatives).
- `pdm run test -q`: 146 passed.
- `pdm run check`: passed.
- `pdm run benchmark-agent-harness-check -q`: 33 passed.
- Headless and headed `--collect-only`: 13 live cases each.

## Acceptance Consequence

`ml.cleaning_service_tickets` is now deterministic-only: its acceptance is the
exact Dataset, the linked Artifact, and integrity (3/3). It has no Judge and no
regex "explanation" gate; prose explanation quality is future Judge scope
(option A). This is honest — no semantic verdict is fabricated from free prose.

## Acceptance

Implementation is complete and provider-free verified. No paid re-run is
required; the retained A4 evidence is re-read under the new check set.
