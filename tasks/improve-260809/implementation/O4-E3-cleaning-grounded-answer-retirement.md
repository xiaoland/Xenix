# O4-E3 Implementation Plan — Retire Cleaning Free-Prose Grounded-Answer Check

**Status:** Completed and provider-free verified 2026-08-16.

**Handshake:** [IH-O4-E3](../handshakes/IH-O4-E3-cleaning-grounded-answer-retirement.md).

## Outcome

Remove the free-prose number regex from the cleaning benchmark so its
deterministic semantic layer asserts only mechanical grounding (exact Dataset +
linked public Artifact) and no longer false-negatives on correct answers.

## Coherent Passes

1. In `benchmarks/agent_harness/test_ml_cleaning.py`:
   remove the `grounded_answer = _grounded_final_answer(...)` line, the
   `grounded_final_answer` `OutcomeCheck`, the `_grounded_final_answer`
   function, and `import unicodedata`. Leave `_terminal_text` and
   `import re` (artifact-link resolver still uses them).
2. Replay the retained A4 reports to confirm the three cells' deterministic
   semantic verdict flips to pass 3/3 (no re-run).
3. Run `pdm run test -q`, `pdm run check`,
   `pdm run benchmark-agent-harness-check -q`, and the exact case
   `--collect-only` in headless and headed modes.
4. Close the packet: execution record, dashboard Next Step, and the consumed
   handshake status.

## Stop Conditions

Stop if the change must also alter the median matcher, the other legacy cases'
  regexes, or add a Judge path — those are separate owners and out of scope.

## Acceptance

The cleaning case's deterministic semantic checks are exactly
`exact_cleaned_dataset` + `public_artifact_linked`, the retained A4 cells
read as semantic pass 3/3, and all offline gates pass.

## Execution

Recorded in `execution/O4-E3-...` after the handshake starts.
