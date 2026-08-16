# Impact Handshake O4-E2 — Cleaning Row-Count Matcher Format Robustness

**Status:** superseded by `IH-O4-E3` (option B: retire the regex instead of
patching it). A separate owner from `IH-O4-A4` (product) and `IH-O4-E1` (first
wording repair).

## Evidence Trigger

The A4 paid three-cell characterization eliminated the redundant `data.query`
re-read (route target 3/3) but its semantic verdict is 1/3. Both misses are
`grounded_final_answer` row-count false negatives over correct, grounded
answers:

- `dbb0ad3881e245b4a0e869571a95449e` puts the count in a markdown table
  (`最终行数 | **5**`): the number `5` has no trailing row unit and the
  `行数` label sits in an adjacent cell.
- `0a08d1bb22224b569026ba59ecf95514` writes `最终有效记录：5 行` and
  `最终 5 行`: the unit is present but the preceding word is not a whitelisted
  anchor.

All three answers state the final count and median fill `21` correctly; exact
Dataset and integrity checks pass 3/3. Removing the query widened the answer
format (tables, bullets), exposing that the matcher's whitelist-prefix-plus-
trailing-unit structure is too rigid. This is the same defect class E1 repaired
for `最终有效行数：5 行`.

## Address and Object

- `benchmarks/agent_harness/test_ml_cleaning.py::_grounded_final_answer` — the
  row-count expression only.

No benchmark prompt, fixture, case identity, expected-Dataset oracle, median
requirement, `_infra` runtime, report schema, or product file changes are
authorized.

## State Diff

- **From:**

  ```python
  row_count = bool(
      re.search(r"(?:结果|保留|共|剩余|清洗后|有效行数|行数).{0,8}5(?:行|条|个记录)", normalized)
  )
  ```

- **To:** a structural two-branch matcher that accepts either "5" followed by a
  row unit, or a row-count label within a short window of "5":

  ```python
  _ROW_LABEL = r"(?:行数|有效行数|最终行数|记录数|有效记录)"
  _ROW_UNIT = r"(?:行|条|个记录)"
  row_count = bool(
      re.search(rf"{_ROW_LABEL}.{0,8}5", normalized)
      or re.search(rf"(?<![第序])5{_ROW_UNIT}", normalized)
  )
  ```

  The value stays exactly `5`; a row unit or a row-count label is still
  mandatory; an ordinal `第5行`/`序5行` is excluded; the median requirement
  is untouched. This accepts equivalent wording/formats; it does not accept a
  wrong or absent count.

## Blast Radius

Only the deterministic row-count matcher of `ml.cleaning_service_tickets`.
Downstream consumers are live benchmark verdicts and the formal acceptance
policy for this case. No service, product, or `_infra` behavior moves.

## Invariants

- The semantic requirement is unchanged: the final answer must ground the row
  count `5` (as a number plus unit, or a row-count label near the number) and
  the median fill `21`.
- No weakening: the count stays exactly `5`, a unit or row-count label remains
  required, ordinals are rejected, and the median requirement is unchanged.
- Case ID, fixture bytes/hash, prompt, expected rows, budgets, and report
  schema are unchanged.
- No new case-specific pytest file and no `_infra_tests` mirror is added; the
  repair is proven by a bounded deterministic replay.

## Verification

1. Deterministic replay of the real `_grounded_final_answer` over a bounded
   matrix recorded in the execution log:
   - the two retained A4 false-negative answers now pass;
   - the one retained A4 passing answer, the E1 `最终有效行数：5 行` form, and
     the historical accepted phrasings still pass;
   - negative controls still fail: count `6`, count `7`, absent count,
     absent median, wrong median `22`, ordinal `第5行` without a real count,
     and a count far from any row-count language.
   No raw transcripts or private rows are retained in tracked summaries.
2. `pdm run check`; `pdm run benchmark-agent-harness-check -q`; exact case
   `--collect-only` in headless and headed modes.
3. Live re-measurement is not required for the repair itself; the repaired
   matcher applies to the next paid cleaning series and the A1 cohort.

## Prerequisite Evidence

- E-031; the A4 execution record and its two retained false-negative cells.

## Return-to-Discussion Triggers

- The expression must accept a wrong or absent count to pass a real answer.
- The change spreads beyond the row-count expression (e.g. the median matcher,
  the Dataset oracle, or the prompt).
