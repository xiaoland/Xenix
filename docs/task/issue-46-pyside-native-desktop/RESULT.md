# Issue 46 Result

## Task

- Issue: `#46 基于PySide开发本地版`
- Date: `2026-03-11`

## Summary

The native desktop branch now satisfies the parent issue end to end: Qt Widgets desktop shell, local SQLite and filesystem ownership, dataset import, training workflow, inference workflow, Windows packaging, VSCode workflow, and the required documentation model.

## Acceptance Mapping

- [x] 已建立 `native` 分支并用于桌面版开发；`master -> web` 重命名影响已记录并完成相关仓库配置调整。
  Evidence: current branch structure and `docs/runbooks/branch-governance.md`
- [x] 应用可在 Windows 上通过开发模式启动，也可通过 PyInstaller 打包后正常启动。
  Evidence: `pdm run dev`, `pdm run package`, `pdm run smoke-package`
- [x] Native 版不再包含用户管理与 ML-Backend Deployment 选择器，也不存在相关持久化模型。
  Evidence: current `src/xenix` native-only shell and storage model set
- [x] 用户可通过拖拽或文件选择导入本地 `.csv` / `.xlsx` 数据。
  Evidence: issue `#75`
- [x] 导入后，应用可展示列名、推断类型、样本量，并允许选择特征列与目标列。
  Evidence: issue `#75`
- [x] 自动训练支持“所有支持模型”与“部分勾选模型”。
  Evidence: issue `#72`
- [x] 手动训练支持选择单个模型并编辑参数后执行。
  Evidence: issue `#72`
- [x] 训练过程在后台执行，UI 可见状态/进度/失败原因。
  Evidence: issue `#72`
- [x] 训练完成后的模型会被本地持久化，并可在后续会话中重新选择使用。
  Evidence: issues `#72` and `#73`
- [x] 推理默认选用当前最佳模型，但允许手动切换到其他已训练模型。
  Evidence: issue `#73`
- [x] 推理同时支持手动录入数据与文件批量推理。
  Evidence: issue `#73`
- [x] 推理结果可在应用内查看摘要，并可在本地直接打开导出结果文件。
  Evidence: issue `#73`
- [x] SQLite 用于本地元数据存储；数据集、模型、结果等文件目录有明确且文档化的约定。
  Evidence: issues `#70`, `#72`, `#73`, docs under `docs/contracts`, `docs/migrations`, and `docs/runbooks`
- [x] 最小文档集已落地：`docs/contracts`、`docs/adr`、`docs/runbooks`、`docs/migrations`、`tests`、`CONTRIBUTING.md`。
  Evidence: repo structure
- [x] VSCode 调试与构建流程已配置并文档化。
  Evidence: issue `#74`

## Delivered Sub-Issues

- `#70` native local data/model storage layer
- `#72` native training workflow
- `#73` native inference workflow, result viewing, and export
- `#74` Windows packaging, VSCode workflow, and regression verification
- `#75` dataset import, drag-and-drop, and column analysis

## Verification

Commands executed successfully for final close-out:

```bash
pdm run test
pdm run check
pdm run package
pdm run smoke-package
```

Observed result:

- `30` tests passed
- desktop source tree compiled successfully
- Windows package built and passed packaged startup smoke verification

## Notes

- The native desktop package is delivered as a Windows PyInstaller `onedir` bundle
- Packaging-safe startup is validated through the shared `--smoke-test` CLI
- The parent issue is now closed by the combined delivery of issues `#70`, `#72`, `#73`, `#74`, and `#75`
