# Model Lifecycle Generalization

## Purpose

Generalize Xenix Native's model lifecycle from supervised estimator workflows to reusable analyzers that can be trained, persisted, applied, previewed, opened, and exported through the Chatbot-first product path.

## Packet Files

- `exploration.md`: facts, constraints, unknowns, and discussion log.
- `data-model-design.md`: proposed role-binding, catalog, task, and artifact data contracts.
- `implementation-plan.md`: staged implementation plan and verification strategy.

## Current Direction

- `model` means reusable analyzer, not only a supervised sklearn estimator.
- `model.train -> model.apply` is the unified lifecycle for supervised models, clustering, anomaly detection, association rules, and recommendation.
- `data.feature.select` should evolve directly into a general column role-binding tool.
- Introduce broader `ModelFamily` and `ModelTaskKind` concepts so `ProblemKind` no longer carries every model-family semantic.
- Introduce `EvaluationKind` so evaluation and metric policy semantics stop depending on `ProblemKind`.
- Replace `dataset_column_selection` with `dataset_column_binding` through schema and data migration.
- Use `binding_id` for the generalized contract instead of carrying forward `selection_id`.
- Use `apply` terminology for new service, Agent, storage, and documentation contracts instead of carrying forward `inference`.
- `ModelCatalogEntry` changes are in scope for this task packet.
- New association/recommendation capability must enter through Agent tools and artifacts, not scenario-home UI.
- Current association-rule apply supports wide basket columns; current recommendation apply supports seed item columns.
- Slice 8 removes transitional `ProblemKind.ANALYSIS`; association and recommendation analyzers now use `EvaluationKind.SUMMARY` with nullable legacy `problem_kind`.
