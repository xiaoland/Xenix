# On-Demand Adoption of Supplied Code and Data

**Status:** Active task-local operating plan. Foundation 1 and Foundation 2 completed against independent clean-room fixtures. One explicitly bounded ch15 private-material spike was admitted for `O-004`; later material use still requires its own trigger below.

## Purpose and Authority

This plan defines how a single planning risk may consume the minimum necessary original code and data from the ignored corpus for private qualification, realistic characterization, ablation, or diagnosis. It owns the private material-admission procedure and artifact shape. It does not own product behavior, service acceptance, Agent acceptance, license interpretation outside this task, or mutation authorization.

The clean-room service case remains the CI authority. A private full-material profile is additional internal evidence bound to the same planning risk, not a replacement fixture, a shared executable kernel, or a second acceptance verdict.

Non-goals:

- importing the corpus into the repository, package, default CI, or Agent Knowledge Library;
- converting, renaming, sampling, or cleaning supplied bytes into a committed fixture;
- using reference outputs as product requirements without independent qualification;
- executing every chapter or precomputing every ablation;
- loading supplied or reference-produced Joblib/Pickle artifacts;
- sharing service fixtures, Agent fixtures, evaluators, commands, or reports across executable trees.

## Material Profiles and Trust

| Profile | Authority and contents | Storage | Admission |
| --- | --- | --- | --- |
| `external_full` | Hash-bound original code/data selected for one risk; code is evaluator/reference-only, while an admitted data projection may be a service or Agent subject input | ignored private storage | Explicit run only; never default CI |
| `private_derived` | Any split, sample, normalized file, reference-code projection, subject/evaluator projection, or ablation derived from supplied bytes | ignored private storage | Parent hashes, transformation hash, parameters, and runtime must be recorded |
| `oracle_private` | Hidden membership, labels, expected facts, reference outputs, tolerance, and private locators | evaluator-only ignored storage | Never mounted into a service/Agent subject root |
| `ci_synthetic` | Independently designed committed service or Agent fixture | its owning executable tree | Default service CI or explicit paid Agent run according to that tree's policy |

The current chapter manifests record source PDF/ZIP locations but no license or redistribution grant. Therefore current supplied material is `license_status=unknown`, which means `internal_only`. A future `cleared` decision must name the evidence, reviewer, allowed use, and redistribution scope; it never silently authorizes committing material. `prohibited` material is not run or transformed.

## Risk- and Slice-Scoped Selection

All paths below are relative to the ignored `business_data_mining_and_analysis_agent_special/` root. They are candidate minimum sets, not an automatic allowlist. A run selects only the rows needed for its stated hypothesis. CSV is preferred; the matching XLSX is admitted only for a format-specific question.

| Slice / risk | Original reference code | Original data | Intended private evidence |
| --- | --- | --- | --- |
| F1 / `profile-cleaning-v1`: bounded profile | `ch06/code/data_overview/data_overview_distribution_structure.py` | `ch06/code/data_overview/ecommerce_customer_spending.csv` | Shape/type/missingness, bounded numeric distribution, date and category-profile behavior |
| F1 / `profile-cleaning-v1`: whole-Dataset cleaning | `ch07/code/data_issues/duplicates_missing_outliers_preprocessing.py` | `ch07/code/data_issues/enterprise_customer_raw_sample.csv` | Exact/business-key duplicate distinction, missingness, range validity, anomaly treatment, operation ordering |
| F2 / `grouped-preparation-v1`: split and learned preparation | `ch07/code/preprocessing_pipeline/data_split_leakage_pipeline.py` | `ch07/code/preprocessing_pipeline/business_park_company_monthly_ops.csv` | Row-random versus group-safe risk, train-only fitting, stable train/holdout/apply schema, unknown-category apply |
| F2 / evaluation metric recomputation | `ch09/code/classification_evaluation/classification_model_evaluation.py` | `ch09/code/classification_evaluation/fitness_churn_model_evaluation.csv` | Classification metric formulas and bounded confusion/probability facts; not a group-generalization oracle |
| F2 / CV leakage and baseline | `ch10/code/pipeline_tuning/pipeline_tuning_leakage.py`; `ch10/code/fair_comparison/baseline_candidate_fair_comparison.py` | `ch10/code/pipeline_tuning/cross_border_returns_pipeline.csv`; `ch10/code/fair_comparison/enterprise_late_payment_fair_comparison.csv` | Preprocessing inside each fold, group-aware replacement where required, same-split baseline comparison, runtime cost |
| F2 / reusable lifecycle and apply | `ch11/code/model_delivery/train_supplier_delay_model.py`; `ch11/code/model_delivery/predict_supplier_delay.py` | `ch11/code/model_delivery/supplier_delay_history.csv`; `ch11/code/model_delivery/supplier_delay_pending.csv` | Feature-order validation, evaluation/apply scope, bounded model facts, reusable apply and result lineage |

Co-located sample outputs, metrics CSV/JSON, generated figures, model-info answers, predictions, Joblib files, PDFs, and archives are not selected by default. The ch09/ch10 row-random examples supply metric and Pipeline-placement evidence only. The ch11 scripts supply lifecycle evidence; their business threshold, algorithm choice, feature names, result ordering, and sample answers are not product oracles.

## Trigger Policy

A material adoption has one explicit `trigger_kind`:

| Trigger | Earliest useful point | Required question |
| --- | --- | --- |
| `real_scale` | After the matching clean-room service selector is green | Does the accepted public contract remain correct and operationally bounded at realistic shape/cardinality? |
| `format_compatibility` | After CSV behavior is green | Is an XLSX/sheet/type issue absent from the clean-room CSV case? |
| `ablation` | After a measured quality, cost, or correctness gap and a named hypothesis | Does one controlled change explain the gap without changing fixture identity or evaluator truth? |
| `diagnosis` | After a service, private characterization, or paid Agent mismatch | Where is the first divergence between admitted input, reference facts, public service result, and Agent outcome? |
| `manual_acceptance_support` | Before Sir's final real-world acceptance when the material covers a remaining high-cost risk | What additional internal evidence is necessary beyond clean-room acceptance? |

Do not run a full-material profile merely because a chapter exists. Do not run an ablation matrix before one failing observation identifies a plausible variable. A private run never turns a red clean-room selector green and never dispatches a paid Agent case by itself.

## Private Artifact Topology

All material state lives under the already ignored root:

```text
evidence/private/materials/<adoption-id>/
  adoption-spec.json
  qualification/
    source-manifest.json
    license-decision.json
    isolation-report.json
    qualification-result.json
  reference/
    code-projection/
    input/
    output/
    reference-patch.diff
    reference-run.json
  profiles/
    external_full/
      subject/
      evaluator/
      profile-manifest.json
    private_derived/
      subject/
      evaluator/
      derivation-manifest.json
    oracle_private/
      oracle-manifest.json
      truth/
  runs/
    service/<run-id>/
      runtime.json
      result.json
      artifacts-manifest.json
    agent/<run-id>/
      runtime.json
      report.json
      artifacts-manifest.json
```

Raw logs, subprocess output, screenshots, and DB/runtime copies remain ignored. Tracked evidence receives only bounded logical IDs, hashes, shapes, runtime identity, tolerance policy, verdict, and limitations.

## Adoption and Qualification Gates

### G0 — Declare the adoption

Create `adoption-spec.json` before reading data values or executing code. It records:

- `adoption_id`, `risk_id`, `slice_id`, `trigger_kind`, and the exact question;
- repository revision and requested `material_profile`;
- selected logical source entries and expected kinds (`reference_code` or `input_data`);
- intended subject (`service`, `agent`, or `reference_only`) and private output root;
- license status and allowed purpose;
- time, memory, output-size, and provider-cost bounds;
- expected service/Agent selector or private adapter identity.

If the selector/adapter or enforceable sandbox does not exist, record `missing_capability` and stop. Do not substitute a clean-room selector, silently skip, or broaden the source set.

### G1 — Bind identity and provenance

For every selected file, resolve the canonical path and reject reparse points, symlinks, path traversal, or anything outside the ignored corpus root. Record raw-byte SHA-256, byte size, media type, chapter/logical ID, and provenance. Canonicalize the manifest as sorted UTF-8 JSON and record its SHA-256.

For every derived file, record:

- ordered parent content hashes;
- transformation code/configuration hash and parameters;
- runtime and library identity;
- derived content hash, byte size, schema/shape, and creation time;
- intended projection and retention class.

A missing file, size/hash mismatch, changed parent, unsupported format, or unrecorded derived output is a hard qualification failure.

### G2 — Qualify license and permitted use

`license-decision.json` records `unknown`, `internal_only`, `cleared`, or `prohibited`, with evidence, reviewer, decision time, permitted purpose, redistribution scope, and expiry/review condition. Current material qualifies only for internal evaluation. Publication, commit, provider upload, or redistribution is denied unless separately cleared for that exact use.

### G3 — Build physically separate projections

The reference workspace, service/Agent subject workspace, and evaluator workspace are separate canonical roots. Qualification rejects path overlap and content-hash overlap. Reference code, sample outputs, oracle truth, answer text, and private locators never enter the subject projection. The evaluator does not retain a duplicate of subject input bytes after reference facts are materialized.

Before execution, scan subject files for:

- reference-output or answer strings;
- hidden labels/future windows/private columns;
- source or evaluator paths;
- executable/archive/model artifacts;
- identical hashes from the evaluator projection.

Any finding fails qualification; a prompt instruction is not isolation.

### G4 — Execute reference code in isolation

Reference code is optional and evaluator-only. Run it only after static review and only in a disposable sandbox that can enforce:

- no network, package installation, subprocess spawning, interactive GUI, or access to repository/user runtime state;
- read-only mounts for the selected code and input data;
- one bounded writable output directory;
- explicit wall-time, memory, process-count, and output-size limits;
- an output-extension allowlist and a clean runtime manifest;
- non-interactive plotting with no display dependency.

Reject dynamic execution, unbounded filesystem access, archive extraction, credentials/environment reads, and unreviewed native extensions. Supplied/reference Joblib, Pickle, model binaries, and cached bytecode are never admitted or loaded. Product services may consume only artifacts they created themselves through their public lifecycle.

If a selected script contains persistence/load or unsafe tail blocks, do not execute it as-is. A minimal reviewed `private_derived` reference projection may remove those blocks; its source hash, patch diff, AST/static-scan result, and reviewer are recorded, and it remains ignored. Ch11 reference execution must keep training and apply in one isolated process or use an independently implemented evaluator; it may not serialize/reload a model. If safe isolation cannot be enforced, use static method evidence only and stop any reference-execution claim.

Unexpected files, writes outside the output root, serialization artifacts, timeout, resource breach, network attempt, or nonzero exit fail the reference run. Partial outputs never qualify an oracle.

### G5 — Qualify the oracle

An independent evaluator recomputes required facts from admitted data or checks the reference output against a second implementation. `oracle-manifest.json` binds:

- risk, source manifest, derivation, runtime, and oracle version hashes;
- hidden truth/membership locators and their hashes;
- metric formula/direction, split policy, tolerance, and comparison scope;
- expected public Dataset/Artifact/result shape without raw answer text;
- contamination and subject/evaluator-isolation reports.

Reference output is evidence, not automatically truth. Disagreement, nondeterminism outside tolerance, insufficient class/group support, or a runtime mismatch fails oracle qualification.

### G6 — Run one explicit profile

Run service characterization before any matching paid Agent characterization. The service and Agent invocations use separate adapters, projections, reports, and verdicts; neither reads the other's files. Every run binds the qualified manifest hash, repository/runtime identity, selector identity, seed, and resource policy.

### G7 — Retain and promote evidence

Keep raw/private artifacts ignored. Promote only a bounded observation to `evidence/` and a bounded command/result record to `execution/`. If a private run reveals a defect, create a new independently designed clean-room regression at the lowest responsible layer; never promote the failing material row or reference answer.

## Command Contract and Fail-Closed Behavior

No material-adoption command is currently added to `pyproject.toml`. The commands below define the required interface for an ignored evaluator-owned runner or a separately approved tracked adapter. Until such a runner and the slice-owned selector exist, G0 returns `missing_capability`; documentation must not present the interface as already runnable.

```text
<private-material-runner> qualify \
  --spec <adoption-spec.json> \
  --output <qualification-directory>

<private-material-runner> run-reference \
  --qualification <qualification-result.json> \
  --output <reference-directory>

<private-material-runner> derive \
  --qualification <qualification-result.json> \
  --derivation <derivation-spec.json> \
  --output <private-derived-directory>

<private-material-runner> build-oracle \
  --qualification <qualification-result.json> \
  --reference-run <reference-run.json> \
  --output <oracle-private-directory>

<private-material-runner> run-service \
  --profile-manifest <profile-manifest.json> \
  --adapter <slice-owned-public-service-adapter> \
  --output <service-run-directory>
```

An admitted material-specific Agent case, if later implemented in its independently owned benchmark module, uses the existing paid command surface:

```text
pdm run benchmark-agent-harness -- \
  --source <qualified-subject-input> \
  --model <one-pinned-subject-model> \
  <one-material-specific-selector>
```

Headed mode replaces `benchmark-agent-harness` with `benchmark-agent-harness-headed`. If the selector does not explicitly accept the admitted source, the invocation is invalid; do not repurpose a clean-room case. Agent scoring continues through the benchmark-owned evaluator/report policy, never through a service report.

Each verb writes its manifest/result atomically only after success. On failure it exits nonzero, writes at most a bounded `qualification-failure.json`, and produces no admitted profile. Required stable failure kinds are:

- `material_missing`, `path_escape`, `hash_mismatch`, `manifest_invalid`;
- `license_not_admitted`, `selector_missing`, `sandbox_unavailable`;
- `subject_evaluator_overlap`, `answer_contamination`;
- `unsafe_reference_code`, `joblib_or_pickle_detected`, `unexpected_output`;
- `reference_execution_failed`, `runtime_mismatch`, `oracle_qualification_failed`;
- `budget_exceeded`.

An explicit material run never skips, downloads, searches elsewhere, substitutes another file, falls back to `ci_synthetic`, or reports a semantic verdict after qualification failure.

## Clean-Room CI to Full-Material Correspondence

The correspondence key is `risk_id + slice_id + contract_version`, not shared bytes, field names, expected values, helper code, or reports.

| Slice | Clean-room CI authority | Optional private full-material profile | Corresponding invariants |
| --- | --- | --- | --- |
| F1 | Independently designed profile/cleaning fixture and public service case under `tests/` | ch06 bounded profile plus ch07 data-issue data/code selected above | Bounded typed facts, default value non-disclosure, explicit whole-Dataset cleaning, source immutability, derived lineage |
| F2 | Independently designed grouped lifecycle train/apply fixtures and public service case under `tests/` | ch07 split/preparation, ch09 metrics, ch10 CV/baseline, ch11 delivery/apply selected above | Immutable input identity, group disjointness, train-only learned preparation, truthful split facts, same-holdout baseline, authoritative evaluation, real apply lineage |

Full-material outcomes are compared to contract invariants and independently recomputed oracle facts, never to clean-room numeric answers. A private full-material failure is diagnostic evidence, not an automatic CI failure; a new clean-room regression is required before it becomes a repository gate.

## Foundation-Specific Adoption Order

### F1

1. Complete the clean-room profile/cleaning service selector.
2. Use ch06 only when realistic cardinality, profile bounds, type inference, or output size is in question.
3. Use ch07 data-issues only when operation ordering, missingness, key duplication, validation, or anomaly treatment needs realistic characterization.
4. Keep category values, identifiers, sample rows, and exact cleaned membership evaluator-private.
5. Run any material-specific paid cleaning case only after a separately admitted Agent case exists and the matching service contract is green.

### F2

1. Complete the clean-room grouped lifecycle selector and immutable binding/split/evaluation/apply facts.
2. Use ch07 preprocessing first for realistic group cardinality and train-only transformation.
3. Add ch09 only to recompute classification metrics; do not inherit its row-random split as group-safe truth.
4. Add ch10 only when testing fold-local preprocessing, baseline comparison, tuning cost, or a measured ablation.
5. Add ch11 history/pending data only for reusable apply, schema validation, and lineage characterization. Do not select its model file, result files, threshold answer, or serialized pipeline.
6. F2 does not authorize temporal splitting; any time-based material claim waits for the later forecasting handshake.

## Verification Checklist

Before accepting a private material run, verify:

- one bounded risk/question and minimum source set;
- canonical path containment, raw-byte size/SHA, and manifest SHA;
- explicit license decision and permitted use;
- reference/subject/evaluator path and hash disjointness;
- no supplied/reference Joblib/Pickle admission or load;
- safe reference execution or an explicit static-only disposition;
- derivation and oracle provenance complete;
- exact selector/adapter, runtime, seed, budget, and repository revision bound;
- nonzero fail-closed behavior exercised for missing and hash-mismatched inputs;
- clean-room CI remains independent and green on a machine with no corpus;
- only bounded safe facts promoted to tracked evidence/execution records.
