# Impact Handshake O4-A4 — Clean-Result Finalization Authority

**Status:** proposed. Product-side guidance/projection repair; requires Sir's
explicit start. Never combined with `IH-O4-E1` into one optimization; the paid
characterization runs only after `IH-O4-E1` closes so its semantic verdict
uses the repaired matcher.

## Evidence Trigger

O4-A3 paid characterization: all three valid cells produced the exact 5 × 4
cleaned Dataset with one `data.clean` descendant and zero transform/metadata,
yet all three still issued broad `SELECT * FROM input` after the successful
clean. Retained Assistant reasoning identifies three causes:

1. "start a data-changing step with read-only evidence" was generalized into
   re-inspecting every source row even though `analysis.profile` had already
   supplied the required structural evidence;
2. two runs distrusted the source-profile median `18` against the authoritative
   post-filter resolved fill value `21`, then queried the complete result to
   re-verify arithmetic `data.clean` had already performed and reported;
3. the Skill's validation guidance was generalized into an unconditional
   full-row verification query, and the `data.clean` result note advertises the
   result Dataset ID for "local follow-up tools", making that branch easy.

The canonical Tool Result already supplied `7 → 5`, the two removed rows, one
duplicate removal, one negative violation/removal, four trim changes, four
lowercase changes, one filled cell, resolved `21.0`, and both public IDs. The
post-clean query added no decision authority and, in one run, reintroduced the
five-row payload O4-A2 deliberately removed from Agent context.

## Address and Object

- `src/xenix/services/agent/skills/xenix-data-preprocessing/SKILL.md` —
  "Efficient Cleaning Path" step 6 and "Safety and Authority" rule 1;
- `src/xenix/services/agent/skills/xenix-data-preprocessing/references/preprocessing-tools.md` —
  the `data.query` "validation after cleaning or transformation" bullet and
  "Planning Pattern" step 8;
- `src/xenix/services/llm/xenix_table_text.py::_render_cleaned_dataset_result` —
  the `data.clean` result note;
- generated `src/xenix/services/agent/skills/catalog.json` (regenerated via
  `pdm run agent-skills-generate`; never hand-edited);
- `tests/test_agent_data_cleaning_guidance.py` — provider-free finalization
  contract anchors;
- `tests/test_ml_foundation_profile_cleaning.py` — bounded-projection
  assertions that pin the note text, updated only if the note wording changes.

No cleaning service, `data.query`/`data.transform` execution, result-payload
contents, benchmark prompt/oracle, Provider settings, budgets, or model changes
are authorized. The generic generated-dataset note of
`data.transform`/`data.integrate`/`data.tokenize` is out of scope; the
diagnosis is cleaning-specific.

## State Diff

- **From:** the Skill says "Validate the derived Dataset with
  `analysis.profile`; use a focused `data.query` only when exact result
  membership or values must be checked."; the reference lists "validation after
  cleaning or transformation" as a `data.query` use and repeats validation as
  the final planning step; the XTT note says "use dataset_id for local
  follow-up tools".
- **To:** a successful bounded `data.clean` result is authoritative
  finalization evidence when it reports every requested operation effect, all
  validation effects, resolved fill values, zero warnings with none omitted, and
  the public Dataset/Artifact IDs. Do not re-read result rows merely to verify
  counts or arithmetic the Tool Result already reports; a source-profile
  statistic may legitimately differ from a post-operation resolved value
  because operations execute left-to-right. A follow-up profile or focused
  query is justified only when the result carries warnings or omitted facts, or
  when a business decision needs values the bounded report does not contain.
  Explicit user requests for row-level inspection remain allowed and are
  inspection, not verification. The XTT note becomes, e.g., "cleaned rows and
  schema preview are omitted; use dataset_id for the next operation on this
  Dataset and artifact_id for the user-openable complete result."

## Blast Radius

Agent-facing guidance and the `data.clean` XTT note only. Consumers are the
LLM Provider context and the provider-free contract tests. The note is shared
by every cleaning Tool result, so the wording must remain general.
`analysis.profile` and `data.query` stay fully available; capability is not
hidden.

## Invariants

- Cleaning execution semantics and `data.clean` result payload contents are
  unchanged (bounded, under 4,096 characters, no row/schema preview, resolved
  scalars, effects, warnings, and IDs all remain).
- `data.query` and `analysis.profile` remain visible after preprocessing
  activation; no Tool is removed or gated.
- The benchmark prompt, fixture, oracle, and route-agnostic evaluator remain
  byte-identical; no Tool-trace assertions are added anywhere.
- Guidance stays generic: no benchmark case name, fixture shape, or expected
  value appears in product text.
- Source immutability and derived lineage behavior are unchanged.

## Verification

Provider-free:

1. The real Skill catalog contains the conditional finalization rule through
   durable anchors: authoritative complete result; no re-query merely to verify
   reported arithmetic; conditional follow-up justification.
2. The real embedded reference repeats the conditional rule and drops the
   blanket post-clean validation bullet.
3. The real XTT renderer emits the revised note and still omits row/schema
   preview, paths, and raw payload; `tests/test_ml_foundation_profile_cleaning.py`
   bounded-projection assertions pass.
4. `pdm run test -q`; `pdm run check`; `pdm run smoke`;
   `pdm run benchmark-agent-harness-check -q`; exact case `--collect-only`.

Paid characterization, after `IH-O4-E1` closes, with the same retained-runner
protocol, case, fixture, `kimi/kimi-k2.6` subject, and budgets as O4-A3 —
three independent cells with retained SQLite/usage/lineage:

- 3/3 semantic and integrity pass; exact 5 × 4 Dataset, resolved median `21`,
  ready public Artifact link;
- exactly one `data.clean` call, one derived descendant, zero
  transform/metadata/failed results/retries;
- zero broad `SELECT *` result queries; any profile/query call must trace to a
  missing fact or an explicit user request for row inspection in retained
  SQLite reasoning;
- median sampling rounds ≤ 5 with all hard budgets unchanged.

A target miss is valid evidence, not permission to weaken the outcome oracle or
add another optimization in this slice.

## Prerequisite Evidence

- E-031; the O4-A3 execution record.

## Return-to-Discussion Triggers

- Guidance or the note would need benchmark-specific values or a prescribed
  Tool trace.
- A provider-free test would have to snapshot prose instead of durable anchors.
- Paid evidence shows the broad-query target missed from a seam other than
  model synthesis.
