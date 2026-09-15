# 第三批验证与结论边界

基线 `6666b2f`。本次仅修改 benchmark 报告解释、调度总预算归属、CLI/CI 展示及其文档，没有修改生产 Harness、题面、oracle、Judge rubric 或单任务预算；没有新增针对 benchmark 的自动化测试。下面是显式执行的保存报告分析与一次性内存扰动，未建立可自动运行的自测集合。

## 真实报告的新解释

[修改前单次描述](before-characterize.json) 把最终分流超轮报告判为不具备测量资格，理由是执行未完成和预算超限。[修改前比较](before-compare.json) 又因 Judge 没有执行而拒绝比较。[修改后单次描述](after-characterize.json) 保留同一报告的 fail、十二轮和 254,625 token；[修改后比较](after-compare.json) 正常呈现两次失败及其资源差异。历史原件没有改写。

两次分流分别消耗 317,951 和 254,625 token，都使用十二轮、都没有完成业务任务。新策略报告 token 差 -63,326、轮数差 0、通过率差 0；没有成功时总 token/成功数为 null。它们跨实现阶段，每阶段只有一次，不能由 token 较少推断 Harness 改善或稳定效率收益。

[八个原有 cell 的逐次重投影](reprojected-runs.json) 保留六个分流失败和两个业务通过，每项附原路径、SHA256、实现阶段和独立摘要；没有跨阶段汇总能力通过率。[补货前后两次观察](restock-compare.json) 同时呈现原 Judge fail 与后续 pass，以及不同消耗。这证明比较不再筛掉失败，不证明一次成功消除了说明幻觉。

以上通过正式 `load_agent_report`、`evaluate_characterization`、`compare_report_cohorts` 与 CLI 执行，Subject/Judge 新增调用均为零。复核入口示例：`pdm run benchmark-agent-harness-evaluate characterize build/agent-harness-failures/content-standard/business.routing.v1.standard-deepseek-deepseek-v4-flash-eda04287e17742d8b51f180d1155917d.json`。

## 手动边界观察

[边界观察](boundary-observations.json) 以原补货通过报告为内存输入，明确标记 author-edited run id，只改变待观察的结果/计量字段。它们不是新的 Subject 运行、真实重复、headed 验收或能力分数。

- 将同一份报告的副本改为 Judge fail，与 pass 副本一起描述：两次投入均保留，总 token 为 107,920，一次成功的有效 token 投入也是 107,920，而非只计算成功那次的 53,960。
- 只去掉一次响应的 usage 覆盖：已观察 token 仍保留，覆盖为 1/2，完整 token 总量、完整 token 中位数与成功成本均为 null；不把缺失部分算成零。
- 只把一份 Judge 改为 provider_error：一项 pass、一项 unscored；分母明确为一项已评分结果，有未知结果时不报告成功成本，也不计算比较的通过率差。
- 三份 headless 加一份 headed 的内存模式标记观察：全 pass 接受；两个 headless pass、一个 partial 与 headed pass 接受；仅一个 headless pass、两个 partial 拒绝。此处只核对原政策，修改模式字段不代表运行过 UI。
- 不同任务混入同一集合不输出总摘要；[重复 run id](collection-review.json) 也不增加分母。报告的逐次观察仍可阅读。

另外检查了“无法计量而停止”与“真实超时且计量不完整”的区别。原 runner 在捕获所有 BenchmarkBudgetError 时统一标记超限，可能把 usage 缺失也当成 Agent 超预算；现按预算控制器的 unverifiable 状态记录 measurement_error。对旧报告的 [一次性反事实投影](accounting-observations.json) 显示前者 unscored，后者仍 fail，两者完整成本均未知。这没有将未知成本误当成零，也没有借未知成本免除已观察的超时失败。

## 调用预算不再改写单任务结果

[调度边界观察](dispatch-observations.json) 用原补货的 53,960 token 和已完成状态，替换 `run_isolated_call` 的返回值，直接执行真实 `run_benchmark` 父调度及 `_InvocationBudgetState.observe`；临时报告在临时目录退出时清理，不产生可混入正式集合的假 cell。实验没有启动 child、生产会话或 provider。

| 前序调用消耗 | 单任务结果 | 调用累计 | 后续调度 |
| ---: | --- | ---: | --- |
| 0 | completed、semantic pass、Judge pass、自身预算合规 | 53,960 | 可继续 |
| 3,999,999 | 同一结果仍 completed、pass、自身预算合规 | 4,053,959 | 停止后续任务 |
| 4,000,000 | 单任务未执行，保留 invocation_token_limit_reached | 4,000,000 | 停止 |

修改前父调度会在第二种情形把 completed 改为 budget_exceeded、semantic 改为 not_evaluated。第三种情形以及历史受总预算干扰的报告在 v3 投影中是 unscored，不能当作已尝试但失败的业务任务，也不重建已经丢失的历史终态。

## 交付检查与限制

`pdm run check` 通过；headless/headed 的 `--collect-only -q` 均恰好四个默认业务任务。工作流 YAML 可以解析，真实运行步骤失败后也会保存描述性判定；原执行失败仍保留其 CI 状态。CLI 摘要补充 Judge verdict，避免把 Judge 请求完成误看成业务通过。`git diff --check` 通过，当前源码、配置和文档没有自测目录或已删除命令的引用。

未执行新的付费全量 benchmark，未作新的 3+1 正式验收，也未声称解决分流超轮。缺少事实的完整性异常仍保留 unscored，未擅自把它解释成源数据被破坏；需要实际追溯后才能改进该类 oracle 的错误归属。下一步的高价值工作是利用现在可比较的失败，设计直接针对 Harness 完成决策的实验；其他疑似误报再按具体交付证据推进全链复评。
