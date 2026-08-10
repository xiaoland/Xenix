# M1 Private-Material Service Characterization — 2026-08-10

## Scope and Safety Result

Four independent internal-only cells ran under the existing material-adoption guardrails. Foundation and clustering/forecasting produced qualified bounded characterizations. Recommendation and text stopped with stable fail-closed reasons. This satisfies M1's acceptance rule without changing product semantics.

All selected files were individually SHA-256-bound. Reference, subject, evaluator, and run roots were physically disjoint, with zero cross-projection content-hash overlap. Provider attempts, reference-code executions, and supplied/reference serialization loads were all zero. Supplied code was static-scanned only; Xenix public ML lifecycles consumed only artifacts they created themselves. No supplied byte or derivative was committed, published, or uploaded.

## Clean-Room Gates

| Cell | Safe selector result |
| --- | --- |
| `M1-FOUNDATION-260810` | 7 passed: analysis profile, Foundation cleaning, and grouped lifecycle selectors |
| `M1-CF-260810` | 24 passed: clustering evidence/lifecycle and forecasting engine/service selectors |
| `M1-RECOMMENDATION-260810` | 8 passed: recommendation engine/service selectors |
| `M1-TEXT-260810` | 17 passed: tokenization and text-classification engine/service selectors |

The selectors remain acceptance authority. Their existing Joblib/NumPy deprecation warnings did not change any verdict.

## Qualified Cells

### Foundation

- source manifest: `d7582f93f782804a9bddda00cdbab3c586e0ffa2a60f8802fb730b1d5deaa028`;
- bounded result: `19750babb8ad0f25848b74dedbe4827bf31fd6e3da69c5ce65fdd309d9a76292`;
- profile: `5,000 × 15`, 15 bounded field facts, 6 numeric summaries, 2 datetime ranges, and no truncation;
- whole-Dataset cleaning: `227 -> 223` rows, 4 removals, `79 -> 0` missing cells, and verified derived lineage;
- lifecycle: `2,000` training rows, `80` apply rows, 13 features, ordered apply schema match, stratified holdout, train-side learned preparation, unknown-category ignore, and verified apply lineage;
- primary metric: candidate `0.7458477061` versus same-holdout baseline `0.6801758087`, verdict `candidate_better`;
- bounded service time: `1.334 s` total.

These are one private characterization's bounded facts, not a new model-quality threshold or product oracle.

### Clustering and Forecasting

- source manifest: `3c4c7880da3d06b32a05b0c12bbbe5b13d2bdddd09cb26b787c5b9c87482bf51`;
- bounded result: `bb4cef4d762f9f6786721547f2f0e0cdd0057ad2da87dddfab3a65969d00fcf6`;
- clustering quality case: `1,640 × 4`, silhouette `0.4511907662`, mean five-run stability ARI `0.7988131402`, and evaluator-only permutation-invariant membership ARI `0.9081552787`;
- clustering profile case: `1,500 × 13`, silhouette `0.3044660390`, mean five-run stability ARI `0.9982709064`, and evaluator-only membership ARI `0.7774670149`;
- DBSCAN case: `1,300 × 2`, 3 non-noise clusters, 99 noise rows, silhouette `0.5140899667`, and mean five-run stability ARI `0.9636057889`;
- rolling Holt-Winters case: 2,007 observations, 3 temporal folds, zero future overlap, no duplicate keys or missing periods, candidate MAE `48.7309314014` versus baseline `54.1190476190`, and empirical `0.8`-interval coverage `0.7380952381`;
- bounded-auto SARIMA case: 2,557 observations, 3 folds, zero future overlap, `27/27` fits converged, 27 bounded warnings, budget not exhausted, candidate MAE `46.3601329131` versus baseline `57.2857142857`, and empirical coverage `0.8333333333`;
- seasonal-naive case: 1,277 observations, candidate/baseline tie at MAE `84.2857142857`, with empirical coverage `0.7380952381`;
- bounded service time: `18.566 s` total.

Membership values and label numbers remained evaluator-private. Interval coverage is empirical and not guaranteed. The SARIMA warning count is a retained limitation despite full convergence.

## Stable Fail-Closed Cells

| Cell | Manifest | Stable reason | Bounded disposition |
| --- | --- | --- | --- |
| `M1-RECOMMENDATION-260810` | `8af1f4d737b4573983801af9cddd9c193c4c361e747f2abce9e8a9905bdebec5` | `oracle_qualification_failed / recommendation_holdout` | The first admitted content set had no admissible held-out positive item in the training-side catalog. The cell stopped; it did not substitute a split, continue to the CF set, or consume evaluator-only `M14-R-EVAL`. |
| `M1-TEXT-260810` | `f243dafb46430fdef0a96fcf06258e6df4de6d811ec0a1e065d4b6552ad3cfdc` | `format_semantic_mismatch / text_resource_admission` | The admitted English resource is a two-column expression-to-standard mapping, while the public staged text-resource contract accepts exactly one term column. The cell stopped before service execution and did not use `M16-T-MODEL` as an oracle. |

Recommendation failure is material insufficiency under the accepted holdout contract, not evidence to weaken that contract. Supporting two-column text normalization mappings would change the public preparation semantics and requires a new exact Impact Handshake plus an independently designed clean-room regression before any private rerun.

## Fail-Closed Probes

The ignored runner was also exercised with missing and hash-mismatched inputs. Both returned nonzero with stable `material_missing` and `hash_mismatch` reasons, created no admitted profile, and made no Provider or reference-code attempt.

## Safe Command Contract

The task-local runner and all raw/private outputs remain under the ignored private-material root. The exact safe command shape is:

```text
pdm run python tasks/improve-260809/evidence/private/materials/private_material_runner.py qualify --spec <ignored-g0-spec.json> --output <ignored-cell-root>
pdm run python tasks/improve-260809/evidence/private/materials/private_material_runner.py run-service --cell <foundation|cf|recommendation|text> --qualification-root <ignored-qualified-cell-root> --run-id <bounded-run-id>
```

Each service command binds the qualified source-manifest digest. It never searches for substitutes, falls back to a clean-room fixture, executes supplied code, or dispatches a paid Agent.
