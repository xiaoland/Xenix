# O4-A4 Implementation Plan — Clean-Result Finalization Authority

**Status:** Completed and verified 2026-08-16. Route target met 3/3; paid semantic 1/3 with two evaluator row-count false negatives owned by `O4-E2`.

**Handshake:** [IH-O4-A4](../handshakes/IH-O4-A4-cleaning-result-finalization-authority.md).

## Outcome

Make the bounded `data.clean` result the authoritative finalization evidence
when it is complete and warning-free, so a correct cleaning workflow does not
re-read result rows merely to verify service arithmetic.

## Coherent Passes

1. Revise `xenix-data-preprocessing/SKILL.md`: conditional finalization rule
   in "Efficient Cleaning Path" and the read-only-evidence qualification in
   "Safety and Authority".
2. Revise `references/preprocessing-tools.md`: remove the blanket post-clean
   validation use and align "Planning Pattern" with the conditional rule.
3. Revise `xenix_table_text.py::_render_cleaned_dataset_result` note to
   "next operation" wording without a verification invitation.
4. Regenerate the Skill catalog with `pdm run agent-skills-generate` and
   `pdm run agent-skills-check`.
5. Extend `tests/test_agent_data_cleaning_guidance.py` with durable
   finalization-authority anchors; update the pinned note assertion in
   `tests/test_ml_foundation_profile_cleaning.py` only where wording changed.
6. Run focused guidance/projection selectors, `pdm run test -q`,
   `pdm run benchmark-agent-harness-check -q`, exact case `--collect-only`,
   `pdm run check`, and `pdm run smoke`.
7. After `IH-O4-E1` closes, run the retained three-cell paid series per the
   handshake protocol; inspect SQLite/usage/lineage before summarizing.
8. Close the packet: execution record, evidence promotion, handshake status,
   and dashboard update.

## Stop Conditions

Stop if the fix requires cleaning-service, Tool-execution, or benchmark
prompt/oracle changes; if a Tool must be hidden; if guidance must name the
benchmark case or its values; or if a provider-free test would snapshot prose.
Stop paid repetitions on an infrastructure or integrity failure until its
cause is classified.

## Acceptance

The implementation portion is complete when the guidance, catalog, note, and
contract tests are mechanically verified. The O4-A4 outcome claim is complete
only after three valid paid cells are causally inspected; efficiency is never
promoted without semantic and integrity correctness.

## Execution

See the execution record created after the handshake starts.
