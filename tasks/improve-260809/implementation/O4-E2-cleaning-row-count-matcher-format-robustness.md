# O4-E2 Implementation Plan — Cleaning Row-Count Matcher Format Robustness

**Status:** Proposed; awaiting the explicit start of
[IH-O4-E2](../handshakes/IH-O4-E2-cleaning-row-count-matcher-format-robustness.md).

**Handshake:** [IH-O4-E2](../handshakes/IH-O4-E2-cleaning-row-count-matcher-format-robustness.md).

## Outcome

Accept the two demonstrated correct-but-rejected A4 answer formats (markdown
table count cell, and `最终有效记录：5 行`/`最终 5 行`) while keeping every
negative control failing and the median requirement unchanged.

## Coherent Passes

1. Apply the approved two-branch row-count expression to
   `benchmarks/agent_harness/test_ml_cleaning.py::_grounded_final_answer`.
2. Run the deterministic replay matrix over the two retained A4 false-negative
   terminal texts (extracted from the ignored retained SQLite), the retained
   passing text, the E1 phrase, historical accepted forms, and the negative
   controls (wrong/absent count, wrong/absent median, ordinal `第5行`, far
   count). Record it in
   `execution/O4-E2-cleaning-row-count-matcher-format-robustness-2026-08-16.md`.
3. Run `pdm run check`, `pdm run benchmark-agent-harness-check -q`, and the
   exact case `--collect-only` in headless and headed modes.
4. Close the packet: execution record, dashboard Next Step, and the consumed
   handshake status.

## Stop Conditions

Stop if the expression must accept a wrong or absent count, if the median
matcher must change, if any product file must move, or if a new case-specific
test file would be needed.

## Acceptance

The replay matrix is all-green (both A4 false negatives now pass; all negative
controls still fail), the offline gates pass, and the diff touches only the one
benchmark module plus task-packet files.

## Execution

Recorded in `execution/O4-E2-...` after the handshake starts.
