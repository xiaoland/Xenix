# O4-E1 Cleaning Row-Count Matcher Robustness — 2026-08-16

## Outcome

The `ml.cleaning_service_tickets` semantic matcher now accepts the demonstrated
equivalent row-count phrasing "最终有效行数：5 行" while every negative control
keeps failing. This closes the O4-A3 evaluator false negative without touching
product behavior or weakening the outcome requirement.

## Implemented State Diff

- `benchmarks/agent_harness/test_ml_cleaning.py::_grounded_final_answer`
  row-count expression gained the anchors `有效行数` and `行数`. The numeric
  value remains exactly `5`, a row unit `(?:行|条|个记录)` remains mandatory
  after the value, and the median requirement is unchanged.

## Verification

- Deterministic replay of the real matcher: `16/16` matched. The retained
  false-negative phrase and all historical accepted phrasings pass; negative
  controls (wrong count, missing count, missing unit, wrong/absent median,
  exceeded window, unrelated digit, and the documented `有效记录` non-goal) all
  still fail. Replay script retained at
  `execution/raw/o4-e1-cleaning-matcher/replay.py` (ignored).
- `pdm run test -q`: 145 passed.
- `pdm run check`: passed.
- `pdm run benchmark-agent-harness-check -q`: 33 passed.
- Headless and headed `--collect-only`: 13 live cases each.

## Evaluator Version Note

This change edits the case module, so the `ml.cleaning_service_tickets`
evaluator version differs from the O4-A3 paid series. The next paid cleaning
series (`IH-O4-A4`) runs under this repaired matcher and must record that
identity. The repair accepts equivalent wording only; it does not weaken the
count, unit, or median requirement.

## Acceptance

Implementation is complete and provider-free verified. No paid re-measurement is
required for the repair itself; the first live proof is the A4 series under
this matcher.
