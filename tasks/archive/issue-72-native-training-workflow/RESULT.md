# Task Result

## Task

- Issue: `#72 Native: 调优与训练工作流（调优 / 训练）`
- Date: `2026-03-10`

## Delivered

- Advanced local storage schema to version `3`
- Added `trained_model` persistence plus `work_item.best_trained_model_id`
- Removed dataset temp-copy ownership from the dataset domain
- Added native ML contracts, evaluation policies, model registry, and model services for:
  - `regression.linear`
  - `regression.ridge`
  - `regression.random_forest`
  - `classification.logistic_regression`
  - `classification.random_forest`
- Added background ML task runtime with:
  - sequential queueing
  - `multiprocessing` worker execution
  - task-owned `request.json`, `result.json`, and `logs.jsonl`
  - canonical trained-model persistence
- Added workflow-facing `MLService` with:
  - `fit_with_evaluate()`
  - `tune_with_evaluate()`
  - bulk tuning fan-out
  - automatic follow-up `evaluate` task submission
  - best-model replacement based on evaluation policy
- Extended the desktop shell with a dedicated training workspace and reusable JSON-schema form widget
- Added ML-domain guidance in `src/xenix/services/ml/AGENTS.md`
- Updated storage and runtime documentation for trained-model and ML task ownership

## Acceptance Criteria

- [x] 超参数调优可勾选模型
- [x] 超参数调优可配置选中模型的超参数
- [x] 手动训练支持单模型参数编辑与执行
- [x] `fit` 完成后会自动执行独立的 `evaluation` 步骤
- [x] 训练过程在后台执行，UI 可见状态/日志/失败原因
- [x] 训练完成后的模型会被本地持久化
- [x] 系统可基于评估结果识别并记录当前最佳模型（记录在 WorkItem 中）

## Verification

Commands executed successfully:

```bash
pdm install
pdm run test
pdm run check
```

Observed result:

- `25` tests passed
- source, UI, and tests compiled successfully

## Important Notes

- `MLService` is workflow-facing; `MLTaskService` owns atomic task execution and finalization.
- `DatasetService` still owns dataset inspection. The training workspace consumes stored work-item dataset selection rather than rebuilding dataset setup.
- Evaluation remains an independent atomic ML task even when workflow methods submit it automatically after fit or tuning.
- Canonical model files live under `artifacts/models/<work-item-id>/`, while task working files remain under `artifacts/ml-tasks/<ml-task-id>/`.

## Deferred

- inference workflow
- restart-resume semantics for pending ML tasks across app relaunch
- richer widget-level UI test coverage beyond the generic JSON-schema form
