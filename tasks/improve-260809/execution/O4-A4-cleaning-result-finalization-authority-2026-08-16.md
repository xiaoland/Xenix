# O4-A4 Clean-Result Finalization Authority — 2026-08-16

## Outcome (provider-free)

The cleaning finalization authority is now projected through product guidance
and the `data.clean` Tool Result note so a successful bounded clean result is
the authoritative finalization evidence, removing the verification invitation
that O4-A3 located. The change is provider-free verified; the paid three-cell
characterization, isolated smoke, and provider-free Harness check remain to run.

## Implemented State Diff

- `xenix-data-preprocessing/SKILL.md` (version 0.6.0 -> 0.7.0):
  - Safety rule 1 gains the finalization qualifier (complete warning-free
    bounded result is authoritative; do not re-read rows to re-verify reported
    arithmetic).
  - Efficient Cleaning Path step 6 becomes the conditional finalization rule,
    and states that a source-profile statistic may legitimately differ from a
    post-operation resolved value, so the Tool Result owns resolved values.
  - Final Answer adds: report bounded facts; do not copy row payload into the
    answer unless the user explicitly asked for row-level inspection.
- `references/preprocessing-tools.md`: the `data.query` "validation after
  cleaning or transformation" bullet is replaced by a conditional rule, and
  Planning Pattern step 8 mirrors the authoritative-result rule.
- `llm/xenix_table_text.py::_render_cleaned_dataset_result`: the note now
  reads "use dataset_id for the next operation on this Dataset" instead of
  "for local follow-up tools".
- `skills/catalog.json` regenerated (3 skills).
- `tests/test_agent_data_cleaning_guidance.py`: version assertion 0.7.0 plus a
  new finalization-authority contract test.
- `tests/test_ml_foundation_profile_cleaning.py`: negative assertion that the
  clean result note no longer advertises "local follow-up tools".

## Verification (done)

- Focused guidance/projection selectors: 8 passed.
- `pdm run test -q`: 146 passed. One Holt-Winters lifecycle test failed once,
  then passed in isolation and on full-suite rerun; it is a pre-existing flake
  unrelated to this change (A4 touches no forecasting surface).
- `pdm run check`: passed (lint, typecheck, catalog validation, compileall).
- Headless and headed `--collect-only`: 13 live cases each.

## Verification (completed)

- Focused guidance/projection selectors: 8 passed.
- `pdm run test -q`: 146 passed (one unrelated Holt-Winters flake passed on rerun).
- `pdm run check`: passed.
- Isolated `pdm run smoke`: passed.
- `pdm run benchmark-agent-harness-check -q`: 33 passed.
- Headless and headed `--collect-only`: 13 live cases each.

## Paid Three-Cell Characterization

Same retained-runner protocol, case, fixture, `kimi/kimi-k2.6` subject, and
budgets as O4-A3; the evaluator is the E1-repaired matcher.

| Run | Semantic | Integrity | Rounds | Tokens | Tool path | Broad query |
| --- | --- | --- | ---: | ---: | --- | --- |
| `dbb0ad3881e245b4a0e869571a95449e` | fail | pass | 4 | 24,781 | activate → profile → clean | none |
| `093db36d937644cb86b8e2c73e483805` | pass | pass | 4 | 24,994 | activate → profile → clean | none |
| `0a08d1bb22224b569026ba59ecf95514` | fail | pass | 4 | 24,977 | activate → profile → clean | none |

All three valid cells produced the exact 5 × 4 Dataset, a ready linked Artifact,
and passed every integrity check. The route target is met: zero
`data.query`/`data.transform`/`data.clean.metadata`, exactly one
`data.clean` call and one descendant per run, and no answer copies the cleaned
row payload back into context. Median rounds 4 and median tokens ~24,977 are
both below the A3 series (5 rounds, ~33,042 tokens).

## Causal Diagnosis

The two semantic fails are both `grounded_final_answer` row-count false
negatives, not Dataset, service, or grounding failures. All three answers state
the final count and the median fill correctly:

- `dbb0ad...`: the answer puts the count in a markdown table
  (`最终行数 | **5**`), so the number `5` has no trailing row unit and the
  `行数` label sits in an adjacent cell.
- `0a08d1...`: the answer writes `最终有效记录：5 行` and `最终 5 行`; the
  unit is present but the preceding word is `最终`/`有效记录`, not one of the
  matcher's whitelist anchors.

Both are wording/format false negatives of the same kind E1 repaired for
`最终有效行数：5 行`. The A4 guidance change removed the `data.query`
re-read, which widened the model's answer format (markdown tables, bullet
lists) and exposed that the matcher's rigid whitelist-prefix-plus-trailing-unit
structure is too strict for correct grounded answers. This is an evaluator
defect and a separate follow-up (`IH-O4-E2`); it is not permission to change
Agent product behavior or weaken the outcome requirement.

## Acceptance

The product change is implemented and verified: the redundant result re-read is
eliminated (route target 3/3) and no run copies row payload into the answer.
The paid semantic target is 1/3, with two demonstrated evaluator wording false
negatives; the exact Dataset and integrity checks pass 3/3. A4 is complete as a
product slice; the evaluator matcher repair is owned by `IH-O4-E2`.
