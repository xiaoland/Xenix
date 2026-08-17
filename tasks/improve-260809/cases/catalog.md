# Case Catalog

## Planning-Only Business-Risk Map

This catalog maps evidence from the supplied material to product risks. It is not an executable registry, shared manifest, or importable case contract. Each risk may produce:

- an independently owned service black-box case under `tests/`, with its own helpers, fixtures, oracle, selector, and result;
- an independently owned paid live Agent case under `benchmarks/agent_harness/`, with its own admitted fixture, evaluator evidence, rubric, case ID, and report;
- a human-readable mapping here for post-run diagnosis.

The two executable trees never import, invoke, or read reports from each other. Public manifests contain logical IDs, hashes, shapes, and safe statistics only. Exact labels, future rows, truth tables, answer text, and private locators remain under ignored evaluator storage.

## Fixture Profiles

| Profile | Bytes | Committed | Default CI | Purpose |
| --- | --- | ---: | ---: | --- |
| `ci_synthetic` | Independently designed, small deterministic business data; separately owned copies/projections per executable tree | yes | service only | Ordinary service acceptance; benchmark copies collect offline but execute only in paid live runs |
| `external_full` | Ignored original textbook data under a verified projection | no | no | Internal realistic Agent/service runs and performance |
| `private_derived` | Any transformed, sampled, normalized, or split derivative of textbook bytes | no | no | Private evaluator inputs and ablations |
| `oracle_private` | Hidden labels, future windows, truth, exact reference outputs | no | never subject-visible | Private scoring |

Renaming, sampling, cleaning, or converting textbook data does not make it a clean-room fixture. Default CI never searches for or downloads external material. An explicitly selected external run fails closed on missing or mismatched hashes rather than silently skipping.

Risk-scoped selection, license/hash/isolation qualification, reference-code execution, private profile production, and trigger policy are owned by the [on-demand material-adoption plan](../materials/on-demand-adoption.md). This catalog remains planning-only and is not an executable material registry.

## Candidate Mapping

| Risk ID | Source case | Future `tests/` responsibility | Future `benchmarks/agent_harness/` responsibility | Current disposition |
| --- | --- | --- | --- | --- |
| `profile-cleaning-v1` | ch06 profile + ch07 quality/preparation risks | Dataset-ID typed profile -> explicit whole-Dataset clean -> derived Dataset/Artifact; exact bounded facts, membership, lineage, source immutability, and default value non-disclosure | use low-sensitivity profile facts first, issue a focused value query only for material semantic ambiguity, then deliver a grounded cleaned result | Foundation integration and O4-A1 nullable validation/imputation service matrix pass; paid characterization passed route-agnostically; corrected full ch07 expected-result cell fails closed and exposes broader cleaning gaps |
| `clean-orders-v1` | ch05 multi-source orders | import -> integrate/clean -> derived Dataset; exact issue/final membership, completeness, lineage, source immutability | route multiple files, choose preparation Tools, deliver public cleaned Dataset and grounded issue summary | First live portfolio candidate |
| `grouped-preparation-v1` | ch07 leakage-safe preparation | group-disjoint split, fit-on-train-only transformation, stable train/holdout/apply schema, no identifier leakage | no separate live prompt; corresponding Agent workflows consume only public outputs and do not re-prove split math | Mandatory service qualification passed through registry, lifecycle, migration, and Agent Tool projection tests |
| `cluster-selection-v1` | ch12 clustering evaluation | execute candidates, permutation-invariant labels, internal metrics, stability, noise semantics, profile Artifact, honest apply capability | choose defensible segmentation workflow, deliver assignment Dataset/profile Artifact, explain segments and limits | Service qualification passed; paid samples drove final-answer, Tool-schema, and Harness-channel fixes; final sample passed all deterministic semantic/integrity checks |
| `recommendation-ranking-v1` | ch14 recommendation evaluation | Explicit-rating per-user holdout, same-truth popularity baseline, Top-K schema, seen-item exclusion, cold-user fallback, ranking/beyond-accuracy metrics, reusable user-list apply | deliver per-user recommendations and explain offline evidence/cold start/business limitations | Service, ordinary Agent, package, and one paid characterization passed; ch14 truth remains evaluator-only |
| `forecast-validation-v1` | ch15 forecast validation | time role, cutoff/rolling split, baseline/candidate evaluation, horizon, point/interval output, future apply | infer time grain/horizon, deliver future forecast Dataset/Artifact, communicate uncertainty | Service/package qualification passed; paid improvement sample passed semantic/integrity checks within budget |
| `bilingual-text-preparation-v1` | ch16 preprocessing | missing/duplicate handling, language-aware normalization/tokenization, bounded custom dictionary/stopword references, reusable preparation spec and derived Dataset | inspect/frequency workflows through atomic `data.tokenize`; no separate paid case required | Service, ordinary Agent projection, and package qualification passed; supplied terms/text remain private |
| `text-grouped-classification-v1` | ch16 classification leakage risks | raw-text preparation retention, train-only vocabulary, business/template-disjoint split, baseline comparison, raw-text apply | train/evaluate/apply a classifier and distinguish offline generalization evidence from decision authority | Service, ordinary Agent, package, and one paid characterization passed |
| `text-topic-discovery-v1` | ch16 vector/model risks | raw-text topic preparation, held-out/permutation-invariant topic evidence, bounded sanitized terms, document-topic output/apply | discover exploratory themes, deliver public outputs, and state that topics are not ground truth | Service/ordinary Agent/package passed; paid FIT/EVALUATE/APPLY outcomes pass but final-answer grounding/privacy remains open |
| `text-retrieval-evidence-v1` | ch16 similarity/vector risks | self-excluding unique Top-K; ranking metrics only with bound relevance truth, otherwise `index_diagnostic` | no live case until a relevance-bearing business scenario and private truth are accepted | Service, ordinary Agent projection, and package qualification passed; live case remains intentionally deferred |

## Implemented Capability Agent Live Assets

These assets are independently authored `ci_synthetic` inputs and case-owned evaluators. They do not contain, transform, sample, or derive textbook bytes. Each module exposes exactly one `agent_harness_live` test and judges final public Dataset/Artifact/Assistant outcomes without prescribing a Tool trace. Headless and headed collect-only currently contain thirteen cases; collection does not call a provider.

| Case | Live module | Independent fixture | Frozen identity | Current verification boundary |
| --- | --- | --- | --- | --- |
| `cluster-selection-v1` | [`test_ml_cluster_selection.py`](../../../benchmarks/agent_harness/test_ml_cluster_selection.py) | [`cluster_selection_accounts.csv`](../../../benchmarks/agent_harness/fixtures/ml_capabilities/cluster_selection_accounts.csv) | 388 bytes; SHA-256 `BC692350CF2C0FB23905EEC264A48F6D361A09030DECBB5C1BAC2B6627B1D2EA` | provider-free schema/oracle/collection checks, then one bounded paid characterization after the CF-C service boundary is green |
| `forecast-validation-v1` | [`test_ml_forecast_validation.py`](../../../benchmarks/agent_harness/test_ml_forecast_validation.py) | [`monthly_regional_demand.csv`](../../../benchmarks/agent_harness/fixtures/ml_capabilities/monthly_regional_demand.csv) | 4,226 bytes; SHA-256 `28F3BAD3A223D2CA18A17F5C673834E4CCB5A2EAE371C3F719EEFEF03EC53F68` | provider-free schema/oracle/collection and packaged forecast checks, then one bounded paid characterization after the CF-F boundary is green |

## Isolation Requirements

- Subject and evaluator get different filesystem projections; a prompt instruction is not isolation.
- Qualification denies path overlap and content-hash overlap and scans subject assets for answer strings.
- Cluster labels are physically removed from subject inputs and compared permutation-invariantly.
- Recommendation truth is private; subject outputs must exclude already seen items.
- Forecast cutoffs physically hide evaluation/future windows.
- Text splits group duplicate/templates; the supplied naïve random classification split is not a generalization oracle.
- `license_status != cleared` means `internal_only`; source data and derived fixtures are not published.

## Ordering Without Dependency

Development guidance and paid CI run the service suite first. A red service job prevents CI from dispatching the paid Agent job. A benchmark invoked directly remains fully independent and produces an Agent verdict without reading service state. Post-run diagnosis may correlate the planning `Risk ID`, repository revision, and runtime facts, but those fields create no executable dependency.
