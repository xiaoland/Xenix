# Issue 74 Result

## Task

- Issue: `#74 Native: Windows 打包、VSCode 工作流与最小回归验证`
- Date: `2026-03-11`

## Delivered

- Added a canonical Windows PyInstaller `onedir` spec at `xenix.spec`
- Added stable packaging and verification entrypoints:
  - `pdm run package`
  - `pdm run smoke`
  - `pdm run smoke-package`
- Extended the native CLI with `--smoke-test`
- Hardened resource resolution so package resources resolve in both source and PyInstaller-frozen runs
- Added packaged-smoke verification that launches `dist/xenix/xenix.exe --smoke-test` with a fresh temporary `XENIX_APP_HOME`
- Updated VSCode launch/task workflow for:
  - debugger startup
  - workspace-home startup
  - smoke startup
  - package build
  - packaged smoke verification
- Added regression coverage for:
  - smoke startup with a fresh app home
  - frozen-resource resolution via `sys._MEIPASS`

## Acceptance Criteria

- [x] VSCode 调试与构建流程可直接使用
- [x] 可产出可运行的 Windows PyInstaller 包
- [x] 在干净环境中可成功启动应用
- [x] 关键路径具备最小回归测试覆盖
- [x] 打包、发布、故障排查流程已文档化

## Verification

Commands executed successfully:

```bash
pdm run test
pdm run check
pdm run package
pdm run smoke-package
```

Observed result:

- `30` tests passed
- source and scripts compiled successfully
- Windows package built successfully to `dist/xenix/`
- packaged executable smoke verification passed

## Notes

- The packaging deliverable is intentionally `onedir`, not `onefile`
- “Clean environment” is verified as a fresh empty `XENIX_APP_HOME` on a prepared Windows machine
- Packaged startup verification reuses the same CLI contract as source startup through `--smoke-test`
