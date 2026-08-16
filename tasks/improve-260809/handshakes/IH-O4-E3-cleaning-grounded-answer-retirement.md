# Impact Handshake O4-E3 — Retire Cleaning Free-Prose Grounded-Answer Check

**Status:** consumed; implemented and provider-free verified 2026-08-16.
Supersedes `IH-O4-E2` (whose regex patch is withdrawn).

## Evidence Trigger

The A4 paid series shows `ml.cleaning_service_tickets` uses a free-prose regex
(`_grounded_final_answer`) to judge "did the answer mention 5 rows and median
21". It false-negatives on two correct grounded answers (a markdown table
`最终行数 | **5**`, and `最终有效记录：5 行`). E1/E2 patch the regex, but the
real defect is a category error: the cleaning case is the only A1-cohort case
whose deterministic semantic layer regex-matches free prose for number
grounding. The five Judge-based cohort cases check only structural markers
(artifact URI, limitations) deterministically and delegate explanation quality
to the Judge. Free prose is unbounded, so no finite regex is robust. Sir chose
option B: retire the regex, keep structural deterministic checks, defer the
Judge (option A) as separate future work.

## Address and Object

- `benchmarks/agent_harness/test_ml_cleaning.py` — remove the
  `grounded_final_answer` `OutcomeCheck`, the `_grounded_final_answer`
  function, the `grounded_answer` assignment, and the now-unused
  `import unicodedata`.

No benchmark prompt, fixture, case identity, expected-Dataset oracle, integrity
checks, `_infra` runtime, report schema, budget, product, or service changes
are authorized. `_terminal_text` and `import re` remain (still used by the
artifact-link resolver).

## State Diff

- **From:** `semantic_checks = (exact_cleaned_dataset, public_artifact_linked,
  grounded_final_answer[regex])`.
- **To:** `semantic_checks = (exact_cleaned_dataset, public_artifact_linked)`.
  Grounding is asserted structurally: the answer links the correct public
  Artifact (`public_artifact_linked`) and the Dataset is exactly the expected
  5 × 4 (`exact_cleaned_dataset`). Explanation-quality grounding (reporting
  5 rows and median 21 in prose) is no longer regex-checked and becomes Judge
  scope under option A.

## Blast Radius

Only the cleaning case's deterministic semantic rubric. Downstream consumers
are live benchmark verdicts and the A1 formal acceptance policy for this case.
The report's `semantic` channel for cleaning changes from 3 to 2 checks; no
report schema, policy, or `_infra` change is required (check lists are
per-case and unconstrained above 1).

## Invariants

- Correctness is not weakened: the exact 5 × 4 Dataset and the linked-Artifact
  checks remain mandatory and byte-identical; integrity checks unchanged.
- No product/Skill/service change; no Judge added (option A deferred); no
  prompt/oracle/fixture/budget change; the benchmark stays route-agnostic.
- The median requirement and the exact-Dataset oracle are untouched.

## Verification

1. The cleaning case's `assess()` no longer references
   `_grounded_final_answer` or `cleaning_summary_*`.
2. Replay the retained A4 reports: all three cells already pass
   `exact_cleaned_dataset` + `public_artifact_linked` + integrity, so their
   deterministic semantic verdict becomes pass 3/3 without any re-run.
3. `pdm run test -q`; `pdm run check`;
   `pdm run benchmark-agent-harness-check -q`; exact case `--collect-only`
   in headless and headed modes.

## Prerequisite Evidence

- E-031; the A4 execution record and its two retained false-negative cells.

## Return-to-Discussion Triggers

- The change would have to touch the median matcher, the other legacy cases'
  regexes, or add a Judge path (option A) — each is a separate owner.
