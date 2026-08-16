# O4-A3 Cleaning Tool and Skill Authority — 2026-08-11

## Outcome

O4-A3 is implemented, provider-free verified, and paid-characterized. The
change removed the previously observed metadata and transform branches: every
valid paid run used one ordered `data.clean` call and produced exactly one
correct source descendant. It did not eliminate redundant broad result
queries, so the paid route-minimality target is not accepted.

Three valid cells produced the same exact `5 × 4` result and passed integrity.
The formal semantic result was `2/3` pass. Direct replay of the deterministic
matcher shows that the third final answer contained both required facts but
used the unrecognized phrase “最终有效行数：5 行”; this is an Agent Harness
wording false negative rather than a Dataset or service failure.

Two additional attempts failed at the Subject provider and are excluded from
Agent-behavior conclusions. Both have `failure_kind =
llm_provider_network_error`; one failed before any Tool call, and one failed
after Skill activation but before any data Tool.

## Implemented State Diff

- Provider schema now states that `data.clean.operations` execute strictly
  left-to-right on the current intermediate Dataset.
- `data.clean` owns advertised atomic validation and row rejection, including
  the non-negative rule; `data.transform` remains available for unsupported
  predicates and relational/derived-data work.
- The preprocessing Skill and reference are profile-first, expose lowercase
  and non-negative direct recipes, and no longer recommend broad schema/sample
  queries or `SELECT *` merely to recover source indexes.
- Preprocessing Tool-scope tests prove that `data.clean`, `data.transform`, and
  `data.query` remain available after activation. Guidance changed; capability
  was not hidden.
- Cleaning service semantics, result projection, benchmark prompt/oracle,
  model, and budgets were unchanged.

## Provider-Free Verification

- focused guidance, Tool-scope, service, and cleaning benchmark checks: `13
  passed`;
- ordinary suite: `145 passed`, with 488 existing Joblib/NumPy deprecation
  warnings;
- provider-free Agent Harness checks: `33 passed`;
- exact cleaning selector: one collected cell;
- `pdm run check`: passed;
- `pdm run smoke`: passed;
- `git diff --check`: passed before documentation closeout.

The independent boundary audit is recorded separately in [O4-A3 cleaning
Tool/Skill authority audit](O4-A3-cleaning-tool-skill-authority-audit-2026-08-11.md).

## Paid Runs

The ignored retained runner used the same case, fixture, pinned
`kimi/kimi-k2.6` Subject, and Harness budgets for every attempt. Each cell kept
its isolated SQLite database, usage journal, Dataset files, and Artifact files
under `execution/raw/o4-a3-cleaning-ablation/` for causal inspection. These are
task diagnostics, not formal cohort evidence.

| Run | Formal result | Rounds | Tokens | Tool path | Derived Datasets |
| --- | --- | ---: | ---: | --- | ---: |
| `886cb068fdd94749afb9d302e705f8ad` | semantic pass; integrity pass | 5 | 33,042 | activate → profile → clean → query | 1 |
| `aec32f609dbc41c58704ae5c41c764cd` | semantic pass; integrity pass | 6 | 44,800 | activate → profile → query → clean → query | 1 |
| `a416062bf6184f67bbb93164ebba62c0` | semantic fail; integrity pass | 5 | 32,488 | activate → profile → clean → query | 1 |

Median rounds were `5`. No valid run called `data.clean.metadata` or
`data.transform`. All four queries were broad `SELECT * FROM input` calls, so
the no-broad-query paid target failed. Median reported Subject usage was
`33,042` tokens and median Subject turn time was `68.521` seconds. The token
median is about 47% below the retained staged reference of `62,502`, but these
are stochastic, non-contemporaneous samples and do not isolate an A3 causal
saving.

Excluded infrastructure attempts:

- `ed0681227d22491eb2780eaa50a18af6`: network error in round 1 after two
  provider attempts; zero Tool calls and zero reported tokens;
- `24d7aaa36bac43c594cb533ddb35c4f5`: network error in round 2 after Skill
  activation; 1,784 reported tokens and no data Tool.

## Database and Lineage Proof

Read-only SQLite queries, not the bounded reports alone, establish the
following for all three valid runs:

- the `dataset` table contains exactly one imported source and one derived
  Dataset;
- each derived row has `derived_from_dataset_id` equal to its run-local source;
- the `artifact` table contains exactly one ready-to-open Dataset Artifact for
  the derived result;
- the source Parquet SHA-256 is the same in all cells; the derived Parquet
  SHA-256 is also the same in all cells;
- each derived frame contains the same five exact rows, the original four
  columns, normalized `state`, no negative count, and the missing count filled
  with `21`.

The `conversation_message` table proves that every `data.clean` call used the
same ordered operation list:

1. exact-row deduplication;
2. non-negative validation with `drop_rows`;
3. trim `state`;
4. lowercase `state`;
5. median-fill `parcel_count`.

The canonical Tool Result already supplied `7 → 5`, two removed rows, one
duplicate removal, one negative violation/removal, four trim changes, four
lowercase changes, one filled cell, resolved fill value `21.0`, the public
Dataset ID, and the Artifact ID. No later query was needed to calculate or
ground those facts.

## Causal Diagnosis

### Why the broad queries remained

The retained Assistant reasoning identifies three concrete causes:

1. One run treated “start a data-changing step with read-only evidence” as a
   reason to inspect all source rows even though `analysis.profile` had already
   supplied the required structural evidence.
2. Two runs distrusted the difference between the source profile median `18`
   and the authoritative post-filter fill value `21`, then queried the complete
   result to verify arithmetic that `data.clean` had already performed and
   reported.
3. The Skill still says to validate a derived Dataset and permits a focused
   query when exact membership or values must be checked. The Agent generalized
   that permission into an unconditional full-row verification query. The Tool
   Result note also advertises the result Dataset ID for local follow-up tools,
   which makes that branch easy even when there is no warning or missing fact.

In the six-round run, the post-clean query also caused the final answer to copy
the complete five-row preview. The query did not create another Dataset, but it
did reintroduce the very row payload that A2 deliberately removed from the
`data.clean` Provider result. This is acceptable only when the user actually
asks for row-level inspection; it added no decision authority in this case.

Thus A3 fixed operation ownership but not finalization authority. The first
divergence is after sufficient authoritative evidence is already present, not
inside the cleaning service and not in Tool-result transport.

### Why the third semantic check failed

The final answer for `a416062bf6184f67bbb93164ebba62c0` states “最终有效行数：5
行” and gives the median fill as `21`. Independent replay of the case matcher
returns `row_count = false`, `median = true`: its row-count expression accepts
“结果/保留/共/剩余/清洗后” near `5 行` but not the semantically equivalent
“最终有效行数”. The exact Dataset and linked Artifact checks both passed.

This false negative is a Harness evaluator defect. It must not be used to
justify changing Agent product behavior or weakening the outcome requirement.

## Acceptance and Next Boundary

The implementation portion is complete. The paid target is only partially met:

- exact Dataset and integrity: `3/3`;
- one clean-derived Dataset and no transform/metadata: `3/3`;
- median rounds no greater than five: met (`5`);
- formal semantic verdict: `2/3`, with one demonstrated wording false negative;
- no broad query: `0/3`.

Any next mutation needs a new exact handshake. Product-side work should target
clean-result finalization authority: when a successful bounded `data.clean`
result contains every requested fact and no warning, do not re-read rows merely
to verify it. Harness-side work should separately make the grounded row-count
matcher wording-robust while retaining the same semantic requirement. These
owners must not be combined into one optimization.
