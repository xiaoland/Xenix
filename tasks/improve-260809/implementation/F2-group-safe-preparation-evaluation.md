# Foundation 2 Implementation Plan — Group-Safe Preparation, Evaluation, and Lifecycle Facts

**Status:** Implemented and objectively service-verified on 2026-08-09.
**Authorization owner:** [Impact Handshake F2 — Group-safe preparation, evaluation, and lifecycle facts](../handshakes/IH-F2.md).
**Execution record:** [Foundation execution — 2026-08-09](../execution/foundations-2026-08-09.md).

## Outcome

Supervised model training can bind an optional business group, prove it trained against the same immutable Dataset content that was role-bound, keep groups disjoint across evaluation, fit learned preprocessing only on the training side, compare the candidate with a simple same-holdout baseline, and expose bounded lifecycle facts without leaking paths or raw model metadata.

Native temporal splitting remains owned by the later clustering/forecasting slice. This plan adds no time-role shortcut and does not reuse grouped random splitting as forecasting evidence.

## Working Set

Load only:

- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/ml/evaluation.py`
- `src/xenix/services/ml/models/base.py`
- `src/xenix/services/ml/models/text_analysis.py` for the supervised text-classification seam only
- `src/xenix/services/ml_service.py`
- `src/xenix/services/ml_task_service.py`
- `src/xenix/services/trained_model_metadata.py`
- `src/xenix/services/storage/models.py`
- `src/xenix/services/storage/migrations.py`
- `src/xenix/services/agent/tool_inputs.py`
- `src/xenix/services/agent/tools.py`
- `src/xenix/services/agent/skills/xenix-data-modeling/SKILL.md`
- `src/xenix/services/agent/skills/xenix-data-modeling/references/supervised-learning.md`
- focused storage, registry, execution, and Tool-projection tests listed below
- `tests/fixtures/ml_foundation/grouped_lifecycle_v1.csv`
- `tests/fixtures/ml_foundation/grouped_lifecycle_apply_v1.csv`

Do not change clustering, recommendation, forecasting, or unrelated text algorithms in this plan.

## Pass 1 — Freeze Dataset Identity at Role Binding

Add a typed Dataset snapshot containing:

- Dataset ID;
- source content SHA-256 and byte size;
- ordered column/schema digest;
- snapshot schema version.

Persist it in `DatasetColumnBindingRow.dataset_snapshot_payload` and advance new bindings to schema version 2. The forward migration adds the nullable JSON field. Existing version-1 bindings are not backfilled from current bytes because doing so would invent historical identity; using one for new training fails with an actionable request to rebind.

At fit/tune admission, recompute and compare the snapshot before worker dispatch. Same columns with changed bytes is a hard integrity failure.

## Pass 2 — Add Optional Group Role and Versioned Split Facts

Extend supervised role schemas with optional single-column `group`:

- group is never a model feature;
- target, group, identifiers, and post-outcome fields remain distinct responsibilities;
- explicit roles are accepted;
- the Agent asks only when multiple plausible group/target choices would materially alter leakage or evaluation meaning.

Implement a versioned `group_hash_holdout.v1` outer split. It deterministically assigns whole canonicalized group values using the policy seed and Dataset fingerprint, targets the configured holdout size, and records only opaque membership digests. It must produce non-empty partitions, zero group overlap, and a credible target distribution; otherwise it fails with an actionable error. It never silently falls back to row-random splitting.

Row-random regression and stratified classification retain their existing intended policies, but execution must match the declared policy. An infeasible stratified split fails instead of persisting a false `stratified_holdout` claim.

For tuning, use group-aware folds inside the outer training partition and pass group membership explicitly to the search. Classification uses a stratified group-aware fold only when its constraints are satisfied; no ordinary-fold fallback is reported as group-safe.

Persist typed split facts:

- requested and realized strategy/policy version;
- source Dataset snapshot digest;
- eligible/train/holdout row and group counts;
- opaque train/holdout membership digests;
- group-overlap count;
- split seed and evaluation scope.

## Pass 3 — Record Preparation and Same-Holdout Baseline Evidence

Keep sklearn preprocessing inside the existing Pipeline. The outer split happens before fitting; imputation, one-hot encoding, scaling, and vectorization fit only on the outer training partition. The canonical apply analyzer may still refit the same declared pipeline on all eligible rows after evaluation scope has been fixed.

Record bounded preparation facts, not learned values:

- preparation policy/version;
- fit scope and fit row count;
- raw feature count and transformed feature count;
- numeric/categorical/text column counts;
- unknown-category handling and output-schema digest.

Evaluate a simple `DummyClassifier` or `DummyRegressor` trained on the same outer training partition and scored on the same holdout. `EvaluateTaskResult` becomes the canonical authority for candidate metrics, baseline metrics, metric directions, comparison, split facts, and preparation facts.

Materialize a bounded evaluation report and register it as `MLTaskArtifactKind.EVALUATION_REPORT`; Agent-facing code may expose a generic metrics/report Artifact ID, but not its absolute path. `TrainedModelMetadata` keeps the direct `evaluation_ml_task_id` reference and may retain compatibility projections; consumers resolve authoritative facts through the referenced Evaluate task rather than scanning tasks or trusting copied metrics.

## Pass 4 — Preserve Real Apply Lineage

Extend `ApplyInputFile`/apply request facts with registered source Dataset/Artifact identity. On finalization:

- exactly one registered Dataset input becomes `derived_from_dataset_id` of the result Dataset;
- multiple or non-Dataset inputs do not falsely point to the training Dataset;
- the bounded task/report facts retain the ordered source Dataset/Artifact ID list;
- the training Dataset remains the analyzer owner, not the claimed source of unrelated scoring rows.

The clean-room case uses one registered apply Dataset and requires exact source lineage.

## Pass 5 — Bound Agent Lifecycle Projection

Replace raw projections from `_trained_model_payload` and `_ml_task_details_payload` with typed bounded facts:

- stable task/model/Dataset/Artifact IDs;
- task state, model key, declared roles, training/apply scope;
- candidate/baseline metrics with direction and comparison;
- split/preparation counts, policies, digests, and limitations;
- bounded error/status/log summaries.

Do not expose absolute paths, raw worker result payloads, preview rows, full metadata payloads, Joblib locators, or unbounded logs. The modeling Skill tells the Agent to explain role choices, actual split scope, baseline comparison, action, and limitations instead of reciting algorithm names.

## Pass 6 — Independent Service Qualification

Create an independently designed fixture with roughly 18 entities x 4 periods and a separate apply fixture. It contains numeric/categorical/missing fields, a binary target, an entity identifier, a group field, and a post-outcome leakage lure. The apply fixture includes an unseen category.

Ordinary tests own:

- `tests/test_ml_registry.py`: optional group role and model catalog contracts;
- `tests/test_ml_execution.py`: binding -> worker fit -> evaluate -> finalize -> apply through public services;
- `tests/test_agent_ml_tool_projection.py`: bounded Agent Tool results and path/raw-value non-disclosure;
- `tests/test_migrations.py` and `tests/test_storage_bootstrap.py`: version-2 snapshot persistence, legacy rebind behavior, and forward migration.

The lifecycle test asserts source immutability, snapshot mismatch rejection, zero group overlap, feature exclusion, train-only preparation scope, stable transformed schema, unseen-category apply, recomputable candidate/baseline facts, deterministic membership/prediction digests, authoritative evaluation reference, evaluation Artifact readiness, and true apply lineage. It never imports or invokes Agent benchmark code.

## Verification Order

1. `pdm run pytest --direct tests/test_ml_registry.py tests/test_ml_execution.py tests/test_agent_ml_tool_projection.py tests/test_migrations.py tests/test_storage_bootstrap.py -q`
2. `pdm run test -q`
3. `pdm run check`
4. `pdm run smoke`
5. Run `pdm run package` and `pdm run smoke-package` if the migration or shipped worker payload changes packaging behavior.
6. Later verticals independently dispatch their matching paid Agent cells only after their own service selectors are green.

## Stop and Return to Design

Stop before or during execution if:

- time-aware evaluation is needed to make this slice coherent;
- a version-1 binding would need silent backfill rather than explicit rebind;
- credible group evaluation requires a user-selectable split-algorithm menu;
- authoritative evaluation facts cannot be referenced directly without a new persistent entity;
- multi-source Dataset lineage requires a general lineage graph rather than bounded source IDs;
- a change outside the Impact Handshake is needed to pass acceptance.
