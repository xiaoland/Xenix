# ML Service Topology

This diagram reflects the current L2/L3 planning direction for issue `#72`.

```mermaid
flowchart LR
    UI["Qt UI
    ml_workspace"]

    MLS["MLService
    workflow boundary"]
    DS["DatasetService"]
    WIS["WorkItemService"]
    MTS["MLTaskService"]
    REG["Model Registry"]
    WR["MLWorkerRunner"]

    WM["Worker Process"]
    MS["Model Services"]
    DL["Dataset Loader"]
    EV["Evaluation Policy"]

    DB[("SQLite
    project/work_item/dataset/ml_task/trained_model")]
    TASKFS[("artifacts/ml-tasks/<task-id>/")]
    MODELFS[("artifacts/models/<work-item-id>/")]

    UI --> MLS

    MLS --> DS
    MLS --> WIS
    MLS --> MTS
    MLS --> REG

    DS --> DB
    WIS --> DB
    MTS --> DB

    MTS --> WR
    WR --> WM
    WM --> MS
    MS --> DL
    MS --> EV

    MTS --> TASKFS
    MTS --> MODELFS

    MTS -. "task completed" .-> MLS
    MLS -. "request EVALUATE task" .-> MTS
```

## Reading Notes

- `MLService` is the workflow-facing boundary used by the UI.
- `MLTaskService` owns atomic task queueing, dispatch, lifecycle, and artifact registration.
- `MLWorkerRunner` is a pure process helper.
- the worker process runs the already-resolved operation entrypoint directly.
- `FIT` and `HYPERPARAMETER_TUNING` can trigger workflow-owned follow-up `EVALUATE` task requests through `MLService`.
- worker processes never mutate SQLite directly.
- task-scoped artifacts live under `artifacts/ml-tasks/<task-id>/`.
- canonical persisted model artifacts live under `artifacts/models/<work-item-id>/`.
