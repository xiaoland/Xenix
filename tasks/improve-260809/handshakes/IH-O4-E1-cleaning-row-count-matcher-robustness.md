# Impact Handshake O4-E1 — Cleaning Row-Count Matcher Wording Robustness

**Status:** proposed. Harness-only evaluator repair; requires Sir's explicit
start. Never combined with `IH-O4-A4` into one optimization.

## Evidence Trigger

O4-A3 paid cell `a416062bf6184f67bbb93164ebba62c0` ended with the semantically
correct summary "最终有效行数：5 行" and median fill `21`. Direct deterministic
replay of the case matcher returns `row_count = false`, `median = true`: the
row-count expression accepts "结果/保留/共/剩余/清洗后" near `5 行` but not the
equivalent "最终有效行数". The exact Dataset and linked-Artifact checks both
passed. This is a demonstrated evaluator wording false negative, not a Dataset,
service, or Agent-grounding failure, and it must not justify any product change.

## Address and Object

- `benchmarks/agent_harness/test_ml_cleaning.py::_grounded_final_answer` — the
  row-count regular expression only.

No benchmark prompt, fixture, case identity, expected-Dataset oracle, median
requirement, `_infra` runtime, report schema, or product file changes are
authorized.

## State Diff

- **From:**

  ```python
  row_count = bool(
      re.search(r"(?:结果|保留|共|剩余|清洗后).{0,8}5(?:行|条|个记录)", normalized)
  )
  ```

- **To:**

  ```python
  row_count = bool(
      re.search(r"(?:结果|保留|共|剩余|清洗后|有效行数|行数).{0,8}5(?:行|条|个记录)", normalized)
  )
  ```

The added anchors accept the demonstrated "最终有效行数：5 行" family. The value
remains exactly `5`, a row unit `(?:行|条|个记录)` remains mandatory after the
value, and the median requirement is untouched. This widens accepted wording; it
does not accept a wrong or absent count.

## Blast Radius

Only the deterministic semantic matcher of `ml.cleaning_service_tickets`.
Downstream consumers are live benchmark verdicts (headless/headed) and the
formal acceptance policy for this case. No service, product, or `_infra`
behavior moves.

## Invariants

- The semantic requirement is unchanged: the final answer must ground the row
  count `5` with row-count language and the median fill `21`.
- No weakening: the count stays exact and must sit near row-count language; an
  unrelated "5" keeps failing.
- Case ID, fixture bytes/hash, prompt, expected rows, budgets, and report
  schema are unchanged.
- No new case-specific pytest file and no `_infra_tests` mirror is added
  (benchmark-local tripwires); the repair is proven by a bounded deterministic
  replay.

## Verification

1. Deterministic replay of `_grounded_final_answer` over a bounded constructed
   matrix recorded in the execution log:
   - the retained false-negative phrasing "最终有效行数：5 行" with median
     `21` now passes;
   - every historical accepted phrasing (结果/保留/共/剩余/清洗后 … 5 行/条/个记录)
     still passes;
   - negative controls still fail: count `6`, missing count, missing row unit,
     wrong/absent median, count far from row-count language.
   No raw transcripts or private rows are retained.
2. `pdm run check`; `pdm run benchmark-agent-harness-check -q`; exact case
   `--collect-only` in headless and headed modes.
3. Live re-measurement is not needed for the repair itself. The next paid
   cleaning series (`IH-O4-A4`) runs under the repaired matcher; its three
   verdicts are the first live proof.

## Prerequisite Evidence

- E-031 and the O4-A3 execution record causal-diagnosis section.

## Return-to-Discussion Triggers

- The expression must accept a wrong or absent count to pass a real answer.
- The change spreads beyond the row-count expression (e.g. the median matcher,
  the Dataset oracle, or the prompt).
