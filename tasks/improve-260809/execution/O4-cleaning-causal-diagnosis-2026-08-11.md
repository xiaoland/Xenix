# O4 Cleaning Causal Diagnosis — 2026-08-11

## Executive Finding

The eight-round historical success is not adequately described as “the Agent made an extra transform.” The real system has overlapping cleaning authorities, an opaque ordered-operation contract, an incomplete cleaning-result projection, and a deterministic nullable-value bug in `data.clean`. Two retained same-case/same-model runs followed different valid-looking plans:

1. a one-call-clean route hit the nullable bug, then entered recovery;
2. a staged clean → transform → clean route passed but created three derived Datasets and still took eight rounds.

The historical runtime was deleted, so its exact Tool order is unknowable. Its aggregate shape is compatible with a two-Dataset transform/filter → clean path and also with a clean failure → transform recovery path. This record does not choose between them.

## Historical Evidence

Run `d4fc5a8482a94c81a1909b1760345b24`:

| Fact | Value |
| --- | --- |
| Case/model | `ml.cleaning_service_tickets` / `kimi/kimi-k2.6` |
| Outcome | completed; semantic and integrity pass |
| Cost | 8 rounds; 69,863 tokens; 102.266 seconds; 0 retries |
| Tool multiset | activate ×1, profile ×1, query ×2, transform ×1, clean metadata ×1, clean ×1 |
| Outputs | 2 derived Datasets; final 5 × 4 result; Artifact link; median 21 |

The report preserves only Tool counts. Normal execution placed the cell runtime inside nested `TemporaryDirectory` contexts and deleted the SQLite conversation, logs, Tool arguments/results, Dataset IDs, and ordered lineage after assessment. No 2026-08-09 cleaning runtime survived under `execution/raw/` or the system temporary directory.

The historical and fresh runs share the exact fixture/case/settings identities:

- fixture SHA-256 `AE3663...B43C`;
- case-definition SHA-256 `7DACCD...71E5`;
- settings SHA-256 `578FB6...E026`;
- effective-settings SHA-256 `E0FC36...987A`.

The cleaning and transform service blobs are byte-identical from historical repository commit `e1241fee...` to current `HEAD`. The Harness runtime hash differs, so fresh runs are reproductions, not historical replay.

## Retained Reproduction A — One-Call Clean Failure

Run `cd06c2749edc4333b8ef3aa98025c04d` retained its runtime at logical cell `cell-po99t6rj`.

The first six calls recorded by SQLite were:

```text
activate preprocessing Skill
→ profile source
→ metadata(validation)
→ SELECT * FROM input ORDER BY parcel_count
→ one data.clean with five ordered operations
→ query the returned cleaned Dataset
```

The clean call was exactly:

```text
duplicate.exact_rows(keep=first)
→ validation.non_negative(parcel_count, action=drop_rows)
→ text.trim(state)
→ text.lowercase(state)
→ missing.fill_median(parcel_count)
```

Expected output was five rows with the missing value filled by 21. The service returned four rows and silently lost the row whose `parcel_count` was missing.

### Deterministic service cause

The canonical registered Parquet loads `parcel_count` as nullable Pandas `Int64`. The actual comparison mask is:

```text
[False, <NA>, False, False, True, False, False]
```

`_apply_validation_operation` applies `frame.loc[~mask]`. Pandas excludes the `<NA>` row as well as the `True` negative row. Therefore `validation.non_negative(drop_rows)` removes a missing value even though `_validation_mask` reports only one violation. The later median fill sees no missing row.

The persisted Artifact metadata makes the inconsistency measurable:

- duplicate operation reports one row removed;
- validation reports one violation and one row removed;
- top-level cleaning report says three rows removed;
- final Dataset has four rows.

No ordinary service test covers a numeric validation/drop before later imputation on a nullable column. The Foundation test imputes before `validation.max`, so the nullable-mask path never appears.

### Provider projection consequence

The compact structured cleaning report contains `validation_rules`, but Xenix Table Text renders only ordinary operation names and warnings. The Provider saw:

```text
Rows: 7 -> 4
rows_removed: 3
operations: [duplicate.exact_rows, text.trim, text.lowercase]
```

It did not see the validation action/violation/removal fact. It therefore reasoned that validation or median fill might have been ignored and spent a query confirming an anomaly already visible in the complete four-row preview.

### Diagnostic-only cross-drive failure

The Agent then attempted two correct-looking SQL recovery transforms. Both failed generically. Direct service reproduction found `WinError 17`: `data.transform` creates `transform-output.parquet` with system `tempfile.TemporaryDirectory()` on C: and moves it with `Path.replace` to the task-local runtime on F:. Windows cannot atomically replace across volumes.

This is a real portability defect for an app home on another drive, but it was introduced into this diagnostic by retaining runtime on F:. The historical runtime used the system temporary drive and had a successful transform, so the cross-drive failure is not attributed to the historical run.

The generic Provider failure contained no cause. The worker deleted request/result/traceback in `finally`, and the runtime log contained only the LLM usage journal. The Agent issued four diagnostic queries, reached the 12-round cap, and the cell ended `budget_exceeded` after 102,352 tokens and 99.126 seconds.

## Retained Reproduction B — Successful Staged Route

Run `68cf62b1764b4750a3c1938ae9765c98` set task-local `TEMP`/`TMP` to the same F: volume and completed with semantic/integrity pass.

SQLite proves the complete sequence:

```text
Round 1  activate preprocessing Skill
Round 2  analysis.profile
Round 3  broad SELECT * source query
Round 4  data.clean.metadata(groups=[text])
Round 5  data.clean: exact dedupe + trim + lowercase       7 → 6
Round 6  data.transform: retain non-negative or NULL      6 → 5
Round 7  data.clean: fill_median                          5 → 5
Round 8  final answer with Artifact link, 5 rows, fill 21
```

SQLite Dataset lineage is a four-node chain:

```text
source
→ clean_step1_dedup_trim_lower
→ clean_step2_filter_negative
→ clean_step3_fill_median
```

The run used 7 Tool calls, 3 derived Datasets, 62,502 tokens, and 101.532 seconds. Per-round reported totals grew with accumulated context:

| Round | Input | Cached input | Output | Total |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 1,654 | 0 | 136 | 1,790 |
| 2 | 6,016 | 0 | 207 | 6,223 |
| 3 | 6,620 | 4,096 | 624 | 7,244 |
| 4 | 7,478 | 6,144 | 515 | 7,993 |
| 5 | 8,197 | 6,144 | 746 | 8,943 |
| 6 | 9,280 | 8,192 | 173 | 9,453 |
| 7 | 9,768 | 8,192 | 183 | 9,951 |
| 8 | 10,282 | 8,192 | 623 | 10,905 |

Skill activation increased the next request's input by about 4.36k tokens. Every later round carried a longer conversation, so eliminating an early unnecessary call saves more than that call's output.

## Causal Layers

### 1. Overlapping authority — proven

The preprocessing Skill routes “filters” to `data.transform`, while `data.clean.metadata` exposes `validation.non_negative(action=drop_rows)` for the same business operation. The Agent therefore has two legitimate-looking owners for negative-row removal.

The direct recipes list exact dedupe, median fill, and trim, but omit both `text.lowercase` and non-negative row removal. Reproduction B queried text metadata; reproduction A queried validation metadata. The route varies by which missing recipe the model notices first.

### 2. Ordered-operation contract is obscure — proven from reasoning/schema

`DataCleanInput.operations` and `CleaningOperationInput` carry no provider description stating that operations execute strictly left-to-right on the preceding result. Reproduction A explicitly said it was unsure whether row removal would precede median fitting. It queried raw rows, but that query could not answer the execution-order question.

### 3. Raw source query did not change a business decision — proven

The user had already supplied all cleaning semantics. Profile returned column indexes, one duplicate, one missing value, minimum −3, and numeric facts. Both reproductions still used a broad raw `SELECT *` to manually enumerate records. Reproduction A initially calculated the post-filter median as 18 even after reading the rows, then corrected it to 21 later; reproduction B also oscillated between 18 and 21 before relying on the service. The extra disclosure did not provide missing business authority or reliable arithmetic.

### 4. Result contract lacks the actual imputation value — proven

The cleaning report records `cells_filled` but not the resolved median/mean/mode value. If the affected row is outside the preview, the Agent cannot ground “filled with 21” from the cleaning report and needs another query. The historical second query may have served this purpose, but its exact position is unknown.

### 5. Validation projection hides causal effects — proven

Structured Tool output retains bounded validation facts, but Provider-facing Xenix Table Text omits them. Top-level `rows_removed` can therefore disagree with the visible operation effects without an explanation.

### 6. Tool failure observability is insufficient for diagnosis — proven

The canonical database stores only `tool_execution_failed`; the Provider sees the same generic message; the preprocessing worker deletes the detailed exception; no operational Tool log survives. Raw SQLite retention recovered reasoning and calls, but the cross-drive exception required a separate direct service reproduction.

## What Can and Cannot Be Said About the Historical Run

Facts:

- it passed in eight rounds with one clean, one transform, two queries, and two derived Datasets;
- all Tool results succeeded;
- the exact case/settings match the fresh runs;
- the relevant cleaning/transform service code has not changed.

Unknown:

- the order of its first seven Tool calls;
- whether the clean call used `validation.non_negative`;
- whether the transform was planned from the start or recovered from a semantically wrong clean result;
- which query grounded the final median.

High-confidence structural conclusion:

- the historical two-Dataset route is explained by the same overlapping `filter → transform` versus `validation → clean` authority reproduced now;
- the old aggregate count alone did not prove waste;
- one of its two queries was unnecessary for business semantics, while the other may have compensated for the missing fill-value result fact.

## Proposed Ablation Matrix

Implementation requires a new exact handshake. Apply the slices sequentially so the first causal improvement remains attributable.

| Variant | Change owner | Deterministic gate before live run | Live hypothesis |
| --- | --- | --- | --- |
| A0 | none | retain current service/result behavior | three headless repetitions quantify path variance |
| [A1](../implementation/O4-A1-cleaning-service-correctness.md) | cleaning service/test | canonical registered data proves nullable numeric validation preserves missing rows; top-level/operation removal counts reconcile; one ordered clean yields 5 rows and the independently calculated median | one-call-clean route no longer needs recovery |
| A2 | cleaning result + XTT | expose bounded validation effects and actual resolved fill value | no result-query needed merely to explain 21 |
| A3 | Tool schema/Skill | declare left-to-right operation order; make validation-supported row rejection the cleaning owner; add common lowercase/non-negative recipes; reserve transform for predicates without atomic cleaning support | no broad source query, metadata call, or transform for this unambiguous case |
| A4 | preprocessing worker/diagnosis | cross-volume-safe finalization and an explicit ignored local diagnostic-retention route preserve classified failures | alternate-drive runtime succeeds; future root cause is recoverable without source patching |

For each live variant, run the exact cleaning case three times on one pinned model and record semantic/integrity verdict, ordered Tool route from task-local retained evidence, rounds, tokens, seconds, failed calls, and derived Dataset count. Do not optimize a failed outcome.

Target after A3:

- 3/3 semantic and integrity pass;
- exactly one derived Dataset descended from the source;
- no `data.transform` and no broad raw-row query for this explicit request;
- median fill 21 and validation removal facts grounded directly from the clean result;
- median no more than five sampling rounds, with four as the expected direct-recipe route;
- hard 12-round/900-second/500k-token protections unchanged.

## Next Decision

Start with the separately audited [O4-A1 handshake](../handshakes/IH-O4-A1-cleaning-service-correctness.md) because this is a service correctness defect independently of Agent efficiency. A2 and A3 then reduce orchestration based on trustworthy output. A4 is separate operational hardening and must not be credited as cleaning-quality improvement.
