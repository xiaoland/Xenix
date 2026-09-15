# 1.5.0 开发阶段收尾

- **Objective**: 结束 benchmark 及相关失败排查，整理本地开发环境与文档，准备下一次 minor 版本 1.5.0。
- **Guardrails**: 用户授权提交前轮修复及本轮收尾；不再运行或修复 benchmark case，不删除业务数据、原始实验记录或本地配置，用户已进一步授权提交、推送、合并 develop 对应 PR，并从主分支发布 1.5.0；遵循现有推广和发布流程。
- **Verification**: 工具链与锁文件一致，源码版本和发布预检读取 1.5.0，静态检查、隔离启动、文档文件链接和 diff 检查通过；区分已有功能验证与最终发布提交的验收。
- **Current Truth**: 前轮修复已提交 24edc1b；PDM 从 2.28.0 对齐到项目/CI 的 2.26.6，Python 3.14.2，SVC CLI/Corpus 14.0.0；锁文件同步移除多余 types-jsonschema，后续 dry-run 无差异；本地 VSCode preLaunch 改为 pdm run prepare，显式 install 改为锁文件 sync。源码声明 1.5.0，文档整理与 18 个历史 packet 的阶段归档完成。缓存与旧 review 包批量删除被自动审批拒绝，未执行。
- **Next Step**: 提交并推送收尾改动，等待 PR #125 的新提交 CI，通过后合并并从主分支合并结果发布 v1.5.0；推广、CI、tag 及发布构建按 Windows Distribution 执行。待执行的物理清理不影响现有业务数据，清单见 cleanup-result.json。

## 范围与证据

单一 packet 负责本轮，没有子任务树。过去的完整 benchmark 不通过项作为历史证据保留，阶段结束不等于全部通过。历史交付诊断目录及账本更正早于本轮，继续保留并通过 tasks/README.md 收口入口。

- [候选版本说明](../../docs/40-deployment/release-1.5.md)、[开发收尾原则](../../docs/40-deployment/development-closeout.md)、[任务归档入口](../README.md)。
- [清理前盘点](local-inventory.json)、[删除操作结果](cleanup-result.json)、[文档文件链接检查](doc-link-audit.json)。链接检查覆盖 README、CONTRIBUTING 与 docs 下的 Markdown 相对文件目标，不证明外部 URL 或段落锚点有效。
- build/minor-1-5-pdm-align.log、minor-1-5-sync.log、minor-1-5-prepare.log、minor-1-5-check.log、minor-1-5-smoke.log 保留本地命令结果。prepare、check、smoke 退出码均为 0；pdm lock --check 通过，pdm sync --dry-run --clean -G :all 无变更；源码 xenix.__version__ 为 1.5.0。
- 项目声明 distribution=false，因此 importlib.metadata 不存在发行包元数据属于预期；源码版本由 build_info 读取 pyproject，未为此额外安装项目或改变分发模型。
- 前轮 303 项离线测试和 packaged smoke 仍是功能证据；本轮没有修改业务算法，也没有重跑付费 benchmark。旧 review 包不是 1.5.0 发布制品，最终发布必须从正式提交重建。

## 清理未执行的原因

自动审批拒绝对已列明的缓存及两个旧 review 目录执行批量 Remove-Item，只返回 blocked by policy。没有换用另一种删除方式，也没有声称释放了磁盘空间。build、dist、.runtime 的大部分空间包含有价值的制品或运行数据，不能以目录体积代替生命周期判断。

## 发布尝试 — 2026-09-15

收尾提交 58539a0 已推送，PR #125 的 Native CI 通过后合并至 main（adb0dbc）。v1.5.0 指向该合并结果，本地身份校验与远端 Linux preflight 通过。发布运行 34952724297 在 Windows 的 Re-verify exact release identity 阶段失败，尚未执行打包或发布步骤。

根因是 scripts/verify_release_identity.py 的 subprocess 文本输出使用 Windows 默认 CP1252 解码 gh 的 UTF-8 中文 PR 信息，后台读取线程抛出 UnicodeDecodeError，随后 stdout 为 None 引发 AttributeError。修复为显式 encoding="utf-8"，不改变发布身份或推广校验。手工以 PYTHONUTF8=0 验证中文子进程输出及当前 tag 身份均通过，Ruff 与 diff 检查通过；未新增自动化测试。

v1.5.0 已推送且不可移动。已向用户请求改发 1.5.1 或暂停发布的决定；确定前不创建新版本 tag，也不重试相同的确定性编码错误。原始失败日志保存在 build/release-1-5-failure.log。
