# O4-E1 Implementation Plan — Cleaning Row-Count Matcher Wording Robustness

**Status:** Completed and provider-free verified on 2026-08-16.

**Handshake:** [IH-O4-E1](../handshakes/IH-O4-E1-cleaning-row-count-matcher-robustness.md).

## Outcome

Accept the demonstrated semantically equivalent row-count phrasing
"最终有效行数：5 行" in the cleaning case matcher while keeping the same
semantic requirement and every negative control failing.

## Coherent Passes

1. Apply the approved row-count expression to
   `benchmarks/agent_harness/test_ml_cleaning.py::_grounded_final_answer`.
2. Run the deterministic replay matrix over constructed phrasings (the retained
   false-negative form now passes; historical accepted forms still pass;
   negative controls still fail) and record it in
   `execution/O4-E1-cleaning-row-count-matcher-robustness-2026-08-16.md`.
3. Run `pdm run check`, `pdm run benchmark-agent-harness-check -q`, and the
   exact case `--collect-only` in headless and headed modes.
4. Close the packet: execution record, dashboard Next Step, and the consumed
   handshake status.

## Stop Conditions

Stop if the expression must accept a wrong or absent count, if the median
matcher must change, if any product file must move, or if a new case-specific
test file would be needed.

## Acceptance

The replay matrix is all-green, the offline gates pass, and the diff touches
only the one benchmark module plus task-packet files.

## Execution

Recorded in `execution/O4-E1-...` after the handshake starts.
