# Model Lifecycle Generalization Exploration

## Input Classification

- Type: `Intent`
- Secondary type: `Constraint`
- Requested outcome:
  - Treat `model` as a reusable analyzer rather than only a supervised sklearn estimator.
  - Keep association analysis and recommendation inside the `model.train -> model.apply` lifecycle.
  - Accept a larger refactor to support non-supervised and non-`predict()` style models.
  - Establish this task packet before implementation and keep it updated while decisions evolve.

## Objective & Hypothesis

- Objective: generalize Xenix Native's model lifecycle so supervised learning, unsupervised learning, association rules, and recommendation models can share a coherent Chatbot-first training and apply contract.
- Hypothesis: the correct abstraction is not `sklearn estimator`, but `reusable analyzer`: a persisted, reusable model artifact with declared input roles, training parameters, apply parameters, result artifacts, and preview metadata.

## Product Claim To Promote

- Candidate PRD truth:
  - In Xenix, a model is a reusable analyzer.
  - A model may be a supervised predictor, unsupervised segmenter, anomaly scorer, association-rule miner, recommender, or another persisted analysis engine.
  - The common lifecycle is train a reusable artifact, apply it to compatible input, and return reviewable artifacts through Chatbot.
- This should be promoted into `docs/10-prd/product-scope.md` after confirmation.

## Current Facts

- `docs/10-prd/product-scope.md` already says the retained product direction is Chatbot-first and the removed concepts include `Scenario-first screens as the product operator path`.
- Current code and tests still contain scenario-centric services and UI:
  - `ScenarioHomeView`
  - `ScenarioTemplateService`
  - `scenario_workflow`
  - scenario training and inference dialogs
- Current Agent tools expose a narrow ML lifecycle:
  - `model.metadata`
  - `model.train`
  - `model.hyper_train`
  - `model.inference` currently exists, but the target contract is `model.apply`
- Current `model.train` depends on a `selection_id` created by `data.feature.select`.
- Current selection is feature/target oriented:
  - `feature_columns`
  - `target_columns`
- Current supervised model services naturally support:
  - fit
  - optional hyperparameter tuning
  - holdout evaluation
  - joblib artifact persistence
  - inference over required feature columns in the existing implementation
- Current clustering and anomaly services already prove that not every model needs a supervised target or evaluation.
- Legacy association and recommendation scripts are script-like flows, not reusable service objects.
- User confirmed:
  - non-model scripts should not be integrated
  - new dependencies are acceptable
  - association and recommendation should be integrated through the model lifecycle, not separate analysis tools

## Guardrails Touched

- Do not mutate production code until explicit implementation start.
- Keep legacy `F:\CODING\Project\Xenix\ml` scripts read-only as reference material.
- Avoid reinforcing scenario-first UI or service paths for new capability.
- Preserve Chatbot-first as the user-facing product path.
- Prefer explicit contracts over heuristic fallback logic.
- Keep task packet updated as the discussion converges.

## Desired State

- `model.metadata` can describe models whose training inputs are not only feature/target selections.
- `model.train` can train analyzers using typed input roles, not only supervised feature/target pairs.
- `model.apply` can apply trained analyzers using typed apply inputs, not only tabular feature rows.
- Trained model metadata becomes the source of truth for:
  - required training roles
  - required apply roles
  - artifact paths
  - preview kinds
  - export/open affordances
- Result handling supports multiple output forms:
  - CSV/XLSX tables
  - images
  - plain text or markdown
  - model/rule/report artifacts
  - future preview payloads
- Agent tools remain simple and coherent for the LLM:
  - inspect metadata
  - select or bind input roles
  - train
  - apply
  - return artifacts

## Candidate Model Families

### Existing Lifecycle Families

- Supervised predictors:
  - regression
  - classification
- Feature-only analyzers:
  - clustering
  - anomaly detection

### New Families

- Association rules:
  - `association.apriori`
  - `association.mlxtend_apriori`
  - training roles may include `transaction_id_column`, `item_column`, or wide `item_columns`
  - apply input may be basket items
  - output may include antecedents, consequents, support, confidence, lift, and recommendation rows
- Recommendation:
  - `recommendation.item_similarity`
  - training roles may include `user_column`, `item_column`, and optional `rating_column`
  - apply input may be a seed item, a user id, or inline user history
  - output may include top-N recommended items and similarity/evidence fields
- Dependency-heavy supervised models:
  - `regression.xgboost`
  - `regression.light_gbm`
  - `classification.xgboost`
  - `classification.light_gbm`

## Contract Direction

### Selection Generalization

- Current `ColumnSelection` is too narrow for all model families.
- Accepted replacement:
  - replace column selection with typed role binding
  - use `binding_id` for generalized train/apply contracts
  - examples:
    - `{"features": [...], "target": ["churn"]}`
    - `{"transaction_id": ["order_id"], "item": ["sku"]}`
    - `{"item_columns": ["Item_1", "Item_2", "Item_3"]}`
    - `{"user": ["user_id"], "item": ["movie_id"], "rating": ["rating"]}`

### Model Metadata Generalization

- `ModelCatalogEntry` should expose:
  - model key
  - family / problem kind
  - train role schema
  - apply input schema
  - parameter schema
  - artifact/result schemas
  - supported operations
- This makes the LLM plan with contracts instead of memorizing special cases.

### Apply Result Generalization

- Current inference result assumes prediction CSV.
- Generalized apply should return:
  - `result_kind`
  - `artifacts`
  - `preview_payload`
  - `summary`
  - optional registered derived dataset id when output is tabular
- Preview/open/export should be artifact-driven, not tied to a specific dialog.

## Implementation Plan Location

- Implementation sequencing lives in `implementation-plan.md`.
- Data model and contract design lives in `data-model-design.md`.
- This file should stay focused on facts, constraints, unknowns, and discussion history.

## Blast Radius Forecast

- High:
  - Agent tool schemas
  - model lifecycle contracts
  - trained model metadata
  - inference result shape
  - tests that assume feature/target-only selection
- Medium:
  - artifact registration and preview handling
  - ML task result payloads
  - storage enum expansion if new problem kinds are introduced
  - packaging for new dependencies
- Low:
  - existing sklearn model implementations if compatibility adapters are preserved

## Invariants Check

- Existing regression/classification train/evaluate/inference must keep working.
- Existing clustering/anomaly feature-only output must keep working.
- Existing database rows should be migrated when a concrete migration path exists; runtime compatibility aliases are not required.
- Chatbot remains the main user-facing path.
- New association/recommendation capabilities should not create scenario-home entry points.
- Generated outputs must be registered artifacts with stable open/export behavior.
- Non-model legacy scripts remain out of scope.

## Unknowns

- How much historical trained-model metadata migration is required beyond active database row migration?
- How many existing tests, docs, and persisted task rows refer to `inference`, and what exact migration should convert them to `apply`?
- What preview payload schema should be canonical for text, table, image, and multi-artifact outputs?
- Should the scenario-centric cleanup happen before or after the new generalized lifecycle is in place?

## Verification Anchors

- Agent tool tests:
  - metadata exposes role schemas
  - role binding supports supervised, association, and recommendation inputs
  - train/apply accept generalized contracts
- ML service tests:
  - supervised lifecycle still passes
  - clustering/anomaly still pass
  - association train writes rule artifact
  - association apply writes recommendation artifact
  - recommendation train writes similarity artifact
  - recommendation apply writes top-N artifact
- Artifact tests:
  - CSV/XLSX/text/image outputs can be registered, previewed, opened, and exported where supported
- Documentation tests or review:
  - PRD reflects `model = reusable analyzer`
  - ML lifecycle docs no longer describe feature/target as the only path
  - forward-looking docs use `apply`, not `inference`

## Smallest Confirmation Needed

- Confirm whether Slice 0 should be executed first as a documentation/contract update before production code.
- Confirm whether to evolve `data.feature.select` into a generalized role-binding tool or introduce a new tool while preserving `data.feature.select`.
- Confirm whether scenario-centric cleanup should be a parallel cleanup stream or wait until generalized model lifecycle is implemented.

## Discussion Log

- 2026-05-20:
  - User rejected treating association and recommendation as separate `analysis.*` tools.
  - User identified `model = reusable analyzer` as a key product definition worth preserving in docs.
  - User encouraged a more thorough lifecycle refactor rather than only patching supervised-learning assumptions.
  - User suggested expanding selection and supporting multiple apply result preview/open/export forms.
  - User requested this task packet and ongoing packet updates during discussion.
  - User chose direct evolution of `data.feature.select` into a generalized role-binding tool.
  - User chose broader `ModelFamily` / `ModelTaskKind` concepts instead of overloading `ProblemKind`.
  - User called out the initial packet as a monofile anti-pattern; packet was split into `README.md`, `data-model-design.md`, and `implementation-plan.md`.
  - User accepted the role-binding design.
  - User stated table renaming is acceptable if database schema migration and data migration are implemented.
  - User asked whether `ModelCatalogEntry` changes are in this task; answer: yes, in this task packet.
  - Review found stale `selection_id`/compatibility language; task packet was corrected to use `binding_id` and to require canonical `role_bindings`.
  - User decided persisted `feature_columns` / `target_columns` metadata should be removed rather than kept as supervised convenience fields.
  - User accepted renaming inference to apply; target lifecycle is now `model.train -> model.apply`.

## Promotion Candidate Truths

- `model` should be documented as a reusable analyzer, not just a supervised estimator.
- `model.train -> model.apply` should be the unified lifecycle for supervised, unsupervised, association, and recommendation analyzers.
- Selection should be replaced by typed role binding.
- Apply results should be artifact/result-kind driven, supporting table, image, and text outputs.
