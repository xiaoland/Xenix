# Impact Handshake CF — Trustworthy Clustering and Native Forecasting

**Status:** Consumed. Implementation and objective acceptance completed on 2026-08-09; paid characterization is recorded in the [CF execution record](../execution/CF-2026-08-09.md), with formal independent-Judge evidence deferred.
**Implementation plans:** [CF-C — clustering trustworthiness](../implementation/CF-C-clustering-trustworthiness.md) and [CF-F — native forecasting](../implementation/CF-F-native-forecasting.md).
**Private-material plan:** [CF on-demand material adoption](../materials/cf-on-demand-adoption.md).

## Evidence and Decisions Consumed

- Existing clustering has five useful adapters but only assignments/counts, no trustworthy selection/stability/profile evidence, and DBSCAN advertises an apply path it cannot support.
- Native forecasting does not exist; the legacy regression split and SQL lag transform cannot represent temporal evaluation or future apply.
- Foundation 2 supplies immutable Dataset identity, typed candidate comparison, dual evaluation/apply training scope, authoritative Evaluate-task references, truthful lineage, and bounded Agent projection.
- `E-002`, `E-003`, `E-005`, `E-006`, `E-014`, `E-017`, `D-014`, and `D-015`.

## Address and Object

Authorized objects are:

- explicit model evaluation/apply capabilities and one durable public-Artifact reference from ML task finalization;
- typed clustering quality, stability, size/noise, label-map, null-baseline, and original-scale profile facts;
- materialized clustering assignment Dataset plus report/profile Artifact and truthful per-model apply admission;
- first-class forecasting family/task/evaluation/problem semantics with required `time`, required `target`, and optional `group` roles;
- seasonal-naive, Holt-Winters, and bounded-auto SARIMA retained analyzers;
- regular-cadence temporal preparation, bounded rolling-origin outer evaluation, SARIMA training-side inner selection, model-comparable residual-quantile intervals, and future-horizon apply;
- bounded Agent Tool/Skill projection, independently owned service cases, and independently owned paid Agent cases.

Recommendation, text, anomaly, association, exogenous/hierarchical/probabilistic/deep forecasting, irregular-calendar repair, partial-group success, and broad orchestration optimization remain outside this handshake.

## Product State Diff

### Clustering

- **From:** a chosen adapter returns a CSV with cluster IDs and counts; label meaning and apply support are weak or discovered at runtime.
- **To:** a user receives one derived assignment Dataset and an openable profile/report Artifact; the Evaluate task reports internal quality, fixed-seed stability, cluster/noise sizes, a permuted-label null baseline, bounded original-scale profiles, and limitations. Labels are stable within one retained analyzer, while cross-run evaluation remains permutation-invariant. Unsupported apply is rejected before dispatch.

### Forecasting

- **From:** no native model family; random-holdout regression or SQL transformation can be mistaken for forecasting.
- **To:** a user binds time/target/optional group, compares seasonal-naive, Holt-Winters, and SARIMA on identical rolling temporal folds, receives point/interval evidence and limitations, retains a full-history analyzer, and applies it with a future horizon to create a derived forecast Dataset and openable Artifact.

## Product Contract

### Shared Capability and Artifact Facts

- Catalog entries declare `supports_evaluation`, `supports_apply`, and `apply_mode`; lifecycle admission uses those facts rather than `requires_target` or runtime attribute discovery.
- Ready-to-open ML task outputs are registered once during finalization as public Artifacts. `MLTaskArtifactRow` stores the stable public Artifact reference; Agent Tools never re-register duplicates or return absolute paths.
- Task-specific Evaluate result contracts remain typed. Supervised, clustering, and forecasting results share only genuinely common metrics/comparison/digest primitives.

### Parameter Authority

- The Agent fills typed model-parameter objects from user intent and public metadata; optional omissions use documented versioned defaults.
- Additional fields are admitted only when shallow, semantically explicit, independently validatable, bounded in value/cardinality, and charged to an enforceable task budget. No open parameter bag or arbitrary estimator kwargs cross the Tool/service boundary.
- User/business semantics may determine fields such as candidate cluster counts, forecast horizon, declared cadence/season, interval level, or another equally bounded model choice. The service remains authoritative for validation and admission.
- Leakage-sensitive split/cutoff construction, shared fold identities and metric meaning, stability/null seeds, open-ended search, SARIMA order candidates/inner selection, convergence controls, optimizer arguments, and fit/time ceilings remain versioned service policy.
- Once comparison starts, candidate-specific parameters cannot change the shared Dataset binding, roles, cadence, horizon, folds, primary metric, or interval-calibration contract.

### Clustering Facts

- Quality: silhouette, Calinski-Harabasz, Davies-Bouldin, evaluated/noise counts, and typed unavailable reasons.
- Stability: fixed versioned seeds and subsamples, permutation-invariant agreement, run count, and digest.
- Baseline: fixed-seed permuted labels preserving cluster sizes; report median null silhouette and candidate margin.
- Size: exact cluster/noise counts and proportions with minimum-segment warnings.
- Profile: bounded original-scale numeric median/IQR and categorical top-value/share by cluster. Task-purpose aggregate category labels may be provider-visible; raw rows and entity/group/identifier values may not.
- Label identity: artifact persists raw-to-display mapping. Noise is `-1`; retained analyzers reuse their mapping for apply. Different analyzers never claim semantic equivalence from display-number equality.
- Apply: KMeans, MiniBatch KMeans, BIRCH, and Gaussian Mixture declare apply only when the retained estimator supports deterministic `predict`; DBSCAN declares `supports_apply=false` and fails admission before a worker starts.

### Forecast Facts

- First-class keys: `forecasting.seasonal_naive`, `forecasting.holt_winters`, and `forecasting.sarima`.
- V1 accepts regular daily, weekly, or monthly cadence, aligned group cutoffs, finite numeric targets, and at most 24 independent groups. Duplicate `(group,time)`, missing periods, mixed cadence/cutoff, or insufficient history fail closed; no silent filling or partial success.
- Common `ForecastOptions` supplies evaluation horizon, seasonal period, optional explicit frequency, interval level, and rolling-window count for every selected model. Model-specific params never change shared folds.
- Default evidence uses three expanding rolling origins and the same horizon/cutoffs across all methods. Primary metric is MAE; RMSE, sMAPE, and MASE are also reported overall and per group.
- Intervals use `residual_quantile.v1`, default 80%, calibrated only from training-side rolling residuals. The report states calibration count, empirical holdout coverage, and mean width; it does not promise nominal coverage.
- Seasonal-naive requires sufficient seasonal history. Additive Holt-Winters requires at least two full seasonal cycles before the outer evaluation windows.
- SARIMA requires at least four full seasonal cycles and uses a versioned bounded order set with two inner temporal folds inside each outer-training prefix. Non-convergence, invalid initialization, non-finite point/interval output, or a versioned fit-count/wall-time budget breach fails that SARIMA task. No raw order tuples are ordinary-user inputs; selected per-group orders and warning/failure facts are bounded report facts.
- A forecast task fails as a whole when any admitted group fails. Other model tasks remain independently valid.
- Evaluation analyzers use only each chronological training prefix; retained future analyzers refit on all observed history after evaluation facts are fixed.
- `model.apply` accepts a forecast horizon mutually exclusive with row/file inputs. Forecast apply uses the retained history and therefore derives its output from the training Dataset; updated history requires a new fit, not state mutation of the old analyzer.
- Output is ordered and unique on `(group?, forecast_time)` and contains `forecast`, `lower_bound`, `upper_bound`, model key, interval method, and horizon facts.

## Blast Radius

- storage problem kind, ML task artifact reference, and forward migration;
- ML catalog/types/contracts/evaluation/preparation/registry and worker payloads;
- clustering base/adapters plus a new forecasting adapter module;
- ML service admission, continuation, apply routing, finalization, trained metadata, Dataset/Artifact lineage;
- Agent model inputs, metadata/apply/task projection, modeling Skill and forecast reference;
- packaging smoke for Statsmodels forecasting paths;
- separate service fixtures/tests and separate live benchmark fixtures/cases.

## Invariants

- Source Dataset bytes and immutable binding snapshots remain authoritative and unchanged.
- Service tests and Agent benchmarks remain physically and executably independent.
- Hidden memberships/future windows and textbook answers never enter subject-visible assets.
- Clustering does not claim external validity or causal segment explanations from internal metrics.
- Temporal future/holdout rows never fit preprocessing, model selection, residual calibration, or candidate training for the fold that evaluates them.
- SARIMA never silently degrades to seasonal-naive/Holt-Winters or treats a numeric result with non-convergence as success.
- Forecasting is never reported as random-holdout regression or SQL lag transformation.
- The Agent receives stable IDs and bounded decision facts, not paths, raw rows, full model metadata, raw order-search traces, or unbounded logs.

## Acceptance Boundary

- `CF-C` and `CF-F` pass their independent ordinary service selectors and full repository gates.
- Each slice then runs exactly one independently owned headless paid characterization; formal `3 × headless + 1 × headed` remains later acceptance evidence.
- Clustering acceptance proves recomputable quality/stability/null/profile facts, deterministic within-analyzer labels, DBSCAN admission refusal, user-openable outputs, unseen-category apply, and real lineage.
- Forecast acceptance proves same-fold three-method comparison, no future leakage, bounded SARIMA selection/convergence/budget facts, residual interval evidence, full-history future apply, package inclusion, and real lineage.
- `pdm run package` and a targeted packaged forecast smoke must pass. The existing unrelated OCR golden-image blocker remains explicitly separate; a direct packaged diagnostic is not renamed as the official whole-app `smoke-package` pass.

## Return to Discussion

Return before widening the approved diff if the design would require irregular-calendar repair, more than 24 groups in v1, partial-group success, user-authored SARIMA orders, exogenous variables, a new ML task type, a new Agent Tool name, a general lineage graph, or a parameter that cannot satisfy `D-015`.
