# 分流诊断后的两项修复

用户已授权修复 benchmark 自设的十二轮限制和 Harness 训练反馈，不新增回归测试或 benchmark 自动化测试，不改任务、oracle、模型评估算法或生产配额。

## Impact / State diff

- Benchmark：删除跨请求累计十二轮和单任务 token 拒绝条件，同时删除每轮两次 provider attempt 的独立限制与 retry_attempts 覆盖；生产 Harness 当前没有采样轮数/累计 token 上限，provider 重试沿用 LLMSettings。轮次和实际请求继续计量。外部费用控制只决定是否启动下一项任务，保留进程超时，并在新资源策略中明确它们是 benchmark 运行限制。资源策略版本变化，旧报告不会与新报告合并为同配置比较。
- Harness：model.train / model.hyper_train 按 retained model 关联训练参数、评估指标、基线、分组/留出口径和公开交付入口，取消 FIT/EVALUATE 持久化 payload 的重复直出。model.task.query 默认使用相同的结果摘要，完整任务诊断改为显式 include_details；日志仍由 include_logs 控制。持久化结果和 ML 原生计算不变。
- 验证：运行已有 Agent / LLM / ML 行为测试和静态检查，收集 headless/headed benchmark，用隔离原生实验核对真实工具返回与体积；必要时选择单个真实业务任务验证两请求交付。诊断探针不进入 pytest，也不参与业务判分。

## 结果

- 已删除 benchmark 的 sampling / provider-attempt / 单项 token 限制和 Subject/Judge retry_attempts 覆盖；`agent-harness-budget-v2` 保留费用计量、每项 900 秒及每次 invocation 4,000,000 token 的下一任务启动门槛。`_MeteredLLMService` 只记录真实调用，费用计量不会阻断当前生产采样。使用量缺失仍是 measurement error，在当前用户请求结束后停止继续测量。没有把十二轮改成每请求十二轮，也没有新增生产配额。
- 新增 Agent 层 `_model_feedback.py` 负责业务反馈，训练完成仍保留 task_ids / trained_model_ids / artifacts，`models` 将各候选及其 FIT/EVALUATE 关联起来。公共指标与标签不做按名字的递归过滤；机械身份仅在 ML 自有事实结构中省略，完整 request/result/artifact 记录可用 `include_details=true` 读取。
- model.task.query 对训练根任务同时展示关联评估，默认保留成功/失败/运行中状态、error_summary、精简结果和公开链接；`include_logs` 继续显式控制日志。既有训练交付测试只调整 stub 以提供真实 TrainedModelRow 的关联字段，没有新增测试或断言。
- `pdm run pytest --direct tests/agent tests/llm tests/ml/test_ml_execution.py tests/ml/test_ml_registry.py -q`：32 passed，24 个现有 joblib/NumPy 弃用警告。`pdm run check` 通过。Headless 与 headed 默认收集均为 4 项；未新增 benchmark 自测。
- 原生分流回放 `probe_model_evidence.py --limit 1`：训练返回 13,449 → 5,671 bytes（减少 57.8%），默认查询 6,149 bytes；完整诊断 27,351 bytes，其中两个任务的 result_payload 与存储一致。两个公开链接均可解析。评估与前一调查相同：留出 14/18、新批 28/30。详见 [反馈证据](feedback-evidence.json)，旧 [原生证据](model-evidence.json) 未覆盖。
- 原生 ridge 调参探针：真实 TUNE → EVALUATE 后返回 2,707 bytes，包含最佳参数、CV 摘要、独立留出指标及训练/应用范围说明；三个公开链接均可解析。详见 [调参证据](tuning-feedback-evidence.json)。两项探针使用临时隔离运行目录，不读写开发数据库，也不加入测试收集。
- 中间版本只删除轮次限制、尚保留单项 token 上限时，standard 分流 `33c5313fa3044ba6abc1820772d39f0e` 正常越过十二轮，但在第十七轮 / 522,020 tokens / 228.095 秒被 `subject_token_limit_exceeded` 截断；首请求未完成，Judge blocked。轨迹中十次训练、两次调用失败。该实验说明仅删除十二轮仍未贯彻“benchmark 不另设生产配额”的原则，因此最终实现也删除了 token 采样拦截。原报告保留于 `build/agent-harness-routing-repair/`，不冒称是最终版本通过证据。
- 去除全部单项配额后的 standard 分流 `8dbb12247e1b462ba89185b87aad107b` 已完成两个用户请求，17 轮 / 571,425 tokens / Subject 201.644 秒；Judge 在第 204 秒开始、14.355 秒后返回 completed。但原 `run_isolated_call` 在读 Pipe 前 join 子进程，较大返回值填满管道后无法退出，父进程也不开始读。这次已保存完整 trace journal，然后仅停止本次阻塞子进程；恢复报告的 runtime_error/child_process_no_result 来自这次终止，不能用作产品失败或 Judge 判分证据。没有捏造未收回的 Judge verdict。
- 已修复同一隔离执行入口：返回对象用临时文件传输，子进程落盘退出后父进程读取，正常完成/失败/超时都会清理临时传输；原有进程超时和杀进程树保留。它同时作用于 Subject cell 和独立 Judge 校准。一次手工 2 MiB 回传实验对比 `ae83667` 原实现与修改实现：旧实现 3.10 秒超时，新实现 0.117 秒返回完整 2,097,152 bytes，见 [传输证据](transport-evidence.json)。这是本地一次性诊断，没有加入 benchmark 自动化测试。
- 修复传输后的最终 standard 分流 `6d4a4c531dc747cbb58f653c2cc7aaf6` 完整通过：两请求分别 12 / 6 轮、323,969 / 328,588 tokens，合计 18 轮 / 652,557 tokens / Subject 235.721 秒。7 项结构检查通过，Judge completed/pass、4 维均为 2，Judge 14,371 tokens；260,728-byte JSON 报告成功落盘。这同时验证了第二请求能越过旧共享配额、训练反馈能支持交付，以及较大完整报告能正常回传。未改题面、oracle 或选模算法；这是 standard 的单次验证，不是全题库或 confirmation 验收。
- 三次真实运行的原报告引用、SHA256、阶段、各请求用量和 Judge 状态见 [运行索引](live-verification.json)。没有删除中间失败或把不同实现阶段合并计算成功率。最终报告位于 `build/agent-harness-routing-final/`；最后一次 `pdm run check` 和 `git diff --check` 通过，用户已批准本轮整理提交。

## 整体验收范围

本次最终实现只完成 standard 分流的一次真实 headless 验证，不能据此宣布完整 benchmark 通过。月结、回访、补货已有各自历史通过记录，但没有在本次生产执行/资源策略下统一重跑；分流 confirmation、其他业务对照和历史题目也没有本版本的全量结果。若采用当前正式验收口径，还缺少同条件三次 headless 加一次 headed；这些与静态检查、现有服务测试、benchmark 入口收集通过是不同层面的证据。
