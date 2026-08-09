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

## Candidate Mapping

| Risk ID | Source case | Future `tests/` responsibility | Future `benchmarks/agent_harness/` responsibility | Current disposition |
| --- | --- | --- | --- | --- |
| `clean-orders-v1` | ch05 multi-source orders | import -> integrate/clean -> derived Dataset; exact issue/final membership, completeness, lineage, source immutability | route multiple files, choose preparation Tools, deliver public cleaned Dataset and grounded issue summary | First live portfolio candidate |
| `grouped-preparation-v1` | ch07 leakage-safe preparation | group-disjoint split, fit-on-train-only transformation, stable train/holdout/apply schema, no identifier leakage | no separate live prompt; corresponding Agent workflows consume only public outputs and do not re-prove split math | Mandatory service qualification |
| `cluster-selection-v1` | ch12 clustering evaluation | execute candidates, permutation-invariant labels, internal metrics, stability, noise semantics, profile Artifact, honest apply capability | choose defensible segmentation workflow, deliver assignment Dataset/profile Artifact, explain segments and limits | First live portfolio candidate; hidden labels evaluator-only |
| `recommendation-ranking-v1` | ch14 recommendation evaluation | Top-K schema, seen-item exclusion, cold-start, ranking/beyond-accuracy metrics, reusable apply; bounded A/B summary without causal overclaim | deliver per-user recommendations and explain offline evidence/cold start/business limitations | First live portfolio candidate; truth evaluator-only |
| `forecast-validation-v1` | ch15 forecast validation | time role, cutoff/rolling split, baseline/candidate evaluation, horizon, point/interval output, future apply | infer time grain/horizon, deliver future forecast Dataset/Artifact, communicate uncertainty | First live portfolio candidate; future window evaluator-only |
| `bilingual-text-preparation-v1` | ch16 preprocessing | missing/duplicate handling, language-aware normalization/tokenization, custom dictionary/stopwords, reusable preparation result | safe topic/text-insight workflow, or classification only after grouped-template split/new fixture | Service candidate; safe live derivative required |

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
