# RT On-Demand Material Adoption

**Status:** Proposed guardrail for `IH-RT`. Inventory is read-only; no RT reference script has been executed and no private material is authorized for Provider upload.

This file narrows the general [on-demand material-adoption contract](on-demand-adoption.md) to recommendation and text. Original bytes, every derivative, precomputed recommendation, truth, label, analysis-text field, topic membership, answer, and reference output remain ignored/evaluator-private. No ZIP is re-extracted and no serialization artifact is loaded.

## Logical Material Inventory

The set digest binds a canonical ordered manifest of file kind, byte size, and raw SHA-256. Exact per-file locators and hashes stay in a future ignored G0/G1 manifest. Shape is recorded only to size the clean-room/private evaluation risk.

| Material ID | Shape | Set digest | Admitted purpose and contamination boundary |
| --- | --- | --- | --- |
| `M14-R-BASIC` | `600×9 + 240×10 + 6000×9` | `DD209770C25AC2F7F32AE1CF74B3DD9ED861AEFC97312017D79C0D4069F37C88` | cold/popularity design inspiration only; hard-coded weights/segments/decay and no holdout are not product truth |
| `M14-R-CONTENT` | `1200×14 + 9000×6` | `85BD852E2E97925EF68F9F3943CEA21CFCDAFF0C328CE9D23FBE7B76FACD95E1` | private scale/runtime and seen-exclusion characterization; full-data fit/no evaluation cannot qualify metrics |
| `M14-R-CF` | `700×4 + 320×8 + 10000×6` | `CD4E435B3356EA7B9DAED22B0B10A8B845B49BDC7481997C7CEC0A74A86556EC` | private user/item CF reference; structural missingness and absent time/cold/evaluation prevent acceptance use |
| `M14-R-MF` | `900×5 + 450×9 + 16126×5` | `ED3E8E7AF151F5E784375376AC07491FA6FB14BC34777480BCDA29A0AFFB133A` | later matrix-factorization ablation only after a separately approved scope; never RT-R baseline |
| `M14-R-EVAL` | `300×8 + 2082×4 + 18000×5 + 5000×9` | `D417A4A1C8455D050012D053FFA375F62A6214DD65C04CB8DD38867816AB68A1` | evaluator-only metric/A-B aggregation reference; precomputed Top-10 and truth are critically colocated and never subject-visible |
| `M16-T-PREP` | `1500×5` | `9D24E823F459496B3080C5B3F93C7283B6EDB77203E2F882416B2A66E8AAF497` | deterministic preparation reference; missing/duplicate behavior and identifier/URL content require private-only handling |
| `M16-T-DICT` | `1200×7 + 11×2 + 14/16/17 lines` | `4817ECB3C7F4CDF2DDA41BD7D338DF2B0250BE652B0CA8D5B8707BEB0331789C` | dictionary/stopword/process-isolation characterization; supplied terms never become product defaults |
| `M16-T-KEYWORD` | `1200×8`, 221 unique raw/analysis texts | `F4D820DF4E375A4E3F9BADBDBF44BE642B7613DDB9F13B2D70D30590EF579241` | method/failure-mode reference only; pre-generated analysis text and GUI/font/WordCloud tails are excluded |
| `M16-T-VECTOR` | `1200×8`, 20 unique raw/analysis texts | `38F00527125CA3BF5DCD3CC4822380FCEF28016531B3A08BA10E8C8DB8352952` | extreme-template leakage demonstration only; no representation/generalization verdict |
| `M16-T-MODEL` | `1500×8`, 359 raw texts, 38 analysis texts | `EAEDF56D366166B1826AB5A2586BAF992A138757241FE40BBEB06CB102AA67DC` | leakage diagnosis only: template→label is effectively deterministic and random split is not a generalization oracle |

There is no single ch14 reference pipeline that owns training interactions, independent future truth, personalized Top-K evaluation, and reusable apply. RT-R product truth therefore comes from independently specified contracts and clean-room tests, not stitched textbook outputs.

## Clean-Room Correspondence

### Recommendation

- Service fixture `SVC-RANK-CR1`: approximately 12 users, 16 items, 72 explicit-rating events plus event time and a separate known/sparse/cold apply-user list. The test privately owns positive holdout truth, exact seen exclusions, ranking order, popularity fallback, and independently recomputed metrics.
- Agent fixture `AG-RANK-CR1`: a different domain and values, approximately 10 accounts, 15 contents, and 65 interactions plus a target-user attachment. The case privately checks per-user Top-3, cold fallback, public Dataset/Artifact/lineage, and the offline-not-online final explanation.
- `M14-R-CONTENT` / `M14-R-CF` may later characterize scale/runtime only; `M14-R-EVAL` may privately qualify formulas only. No material verdict replaces clean-room service or Agent evidence.

### Text

- Service fixture `SVC-TEXT-PREP-CR1`: 28 independently written bilingual rows covering NFKC/case/whitespace, URL/email/number rules, empty text, duplicate/templates, and independently written custom terms/stopwords.
- Service fixture `SVC-TEXT-CLASS-CR1`: independently written grouped templates, labels, business groups, and a separate raw-text apply input; private truth qualifies zero overlap and predictions.
- Service fixture `SVC-TEXT-INSIGHT-CR1`: 36 independently written documents across three hidden themes and four template families; private membership qualifies clustering/topic facts permutation-invariantly.
- Agent classification/topic fixtures use different business domains, text, IDs, and truth again. They share only the logical risk, not bytes, helpers, expected values, or reports.
- `M16-T-PREP` / `M16-T-DICT` may later qualify deterministic policy and process isolation. `M16-T-MODEL` may only reproduce leakage and cannot issue an acceptance verdict.

## Admission and Isolation Gates

1. Create one G0 adoption spec for one exact real-scale, performance, ablation, diagnosis, or final-manual-acceptance question. Mere chapter availability is not a trigger.
2. Bind every selected file's canonical path, raw hash, size, kind, set digest, runtime, and license status. Any mismatch fails closed.
3. License remains `internal_only`. Publication, commit, and Provider upload require separate explicit clearance; none is inferred from another.
4. Build physically disjoint reference, subject, and evaluator roots and scan for labels, truth, precomputed rankings, analysis text, answers, locators, hashes, executables, and archives.
5. Select CSV only. Block network, GUI, subprocess, package install, serialization, user/runtime access, ZIP/PDF/image/worksheet-output consumption, and writes outside one bounded output root.
6. A reviewed ignored patch may remove an Excel loader or GUI/plotting tail; the original hash, patch hash/diff, static review, and output manifest remain private.
7. Recompute every promoted metric/fact with a second independent evaluator. Reference code is evidence, never automatic product truth.
8. Run the matching clean-room service selector first. Private characterization and paid Agent evidence remain independent commands and verdicts.
9. Promote only logical IDs, hashes, shapes, bounded aggregate metrics/runtime, limitations, and verdict. Never promote rows, terms, memberships, recommendation lists, truth, labels, answers, or raw traces.

## Trigger Order

No RT private run is needed to approve design or begin clean-room implementation. Earliest useful triggers are:

- recommendation real-scale/runtime after RT-R service acceptance;
- dictionary/process-isolation characterization after RT-T1 clean-room preparation acceptance;
- template-leakage diagnosis only if a new classifier result cannot be explained by clean-room evidence;
- manual-acceptance support for Sir's final real-world review.

Private material remains prohibited from paid Agent cells until license and privacy/provider-upload review explicitly clears the exact projection.
