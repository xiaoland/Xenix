# Data Cleaning

`services/data_cleaning.py` is the caller-facing boundary. It exports serializable request/result models, compact operation metadata, and the service that submits a preprocessing worker request. Importing this boundary must not load pandas or SQLModel; metadata lookup and Agent construction need no execution engine or persistence model.

```text
Agent / caller -> data_cleaning -> preprocessing worker
                                     -> cleaning.engine
                                          -> cleaning.operations
                                               -> cleaning.parameters
```

`cleaning/contracts.py` owns Pydantic request/result shapes. `cleaning/catalog.py` owns concise routing hints, not a second input-validation schema. Keep an operation's name, summary, and parameter hints together; full execution validation remains with its implementation. Do not restore verbose unused JSON Schemas merely to render compact strings.

`cleaning/engine.py` owns reading the source, applying the plan left to right, and writing the resulting Parquet file. `operations.py` owns frame transformations and their reports; `parameters.py` resolves parameters and column identity against the current intermediate frame. Neither helper owns runtime paths, worker processes, or database records.

The operation sequence is observable: filtering before imputation changes the population that determines fill values. Operations that can add/remove columns invalidate later index references within the same call, even when an individual input happens to make that operation a no-op. Use names or split the plan into separate calls after inspecting the new schema. Empty plans return the source path; nonempty successful plans publish a separate result and leave source bytes untouched.

Generated-dataset registration, lineage, and public Artifact finalization remain with the existing Dataset/Artifact service boundary. The cleaning engine cannot become another registry or mark a filesystem result as a registered Dataset.

Verification: `tests/ml/test_data_cleaning_service.py` covers ordering, nullable rows, source preservation, spawned/inline feature preparation, and rejection of stale column indexes without partial output; `tests/ml/test_ml_foundation_profile_cleaning.py` covers the Agent Tool through registered finalization. Check metadata guidance at `tests/agent/test_agent_data_cleaning_guidance.py`.
