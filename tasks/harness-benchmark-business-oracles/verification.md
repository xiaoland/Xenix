# 实施验证与发现

2026-09-13；实施基线 `dcec815b23369832307e26b96daf1a6961541a8b`。已落实获批 [State Diff](impact-handshake.md)，改动限于 benchmark、已有相关 infra 覆盖、文档与任务材料。未新增回归测试文件，未修改生产服务、Skill、migration、运行配置；用户已批准随本轮提交归档。

## 验证结果

| 验证 | 实际结果 |
| --- | --- |
| `pdm run benchmark-agent-harness-check -q` | 41 passed，6.10 秒；现有组合测试改为两请求真实 Harness 加离线 provider，覆盖共享会话、累计预算与首轮结果保留；原有报告/选择覆盖同步更新。 |
| `pdm run check` | 全部通过，包括 Ruff、53 个文件的类型检查、Skill catalog 与 OCR lock 检查。 |
| 默认 headless / headed `--collect-only -q` | 各收集同样三个业务任务；显式选择旧文件仍有效；显式选择整个 `tests/e2e/agent_harness` 收集 16 项。 |
| 正式任务离线探针 | 两变体独立 SQL 金额/资格复核通过；错误口径、旧答案、缺失客户、重复区域、替换模型等反例可区分；合法合计行、资格标记全表、行列变换可接受。详见 [formal_observations.json](experiments/formal_observations.json)。 |
| 可见 UI 双请求探针 | 真实桌面、离线 provider，分别附 CSV 的两次请求通过；实际 UI 提交、渲染、共享状态和关闭通过，逐轮 15 tokens、整项 30。中断第二次 provider 请求后能保留第一轮和已知成本，未返回 usage 标为未知。详见 [实验入口](experiments/README.md)。 |
| 实验静态检查与 diff | 实验脚本 Ruff 通过；`git diff --check` 通过。 |

headed 探针同时发现并修复了 benchmark 适配器对旧 MainWindow/composer 私有字段的引用，现改用当前 workspace、composer、timeline 和语义控件入口。未通过修改生产 UI 来配合测试。可见探针验证了执行适配，不能替代三项业务任务的真实 headed 验收。

## 真实运行

使用本项目开发设置：Subject `.runtime/dev/config/agent_settings.json` 中的 `deepseek/deepseek-v4-flash`，Judge `.runtime/dev/config/judge_settings.json` 中的 `deepseek/deepseek-v4-pro`，Embedding 使用 `.runtime/dev/config/embedding_settings.json`。仅有下面标明的一项额外诊断将 Subject 改为 `deepseek/deepseek-v4-pro`。设置文件未改动。

最终核心运行命令：`pdm run benchmark-agent-harness -- --llm-settings .runtime/dev/config/agent_settings.json --embedding-settings .runtime/dev/config/embedding_settings.json --judge-llm-settings .runtime/dev/config/judge_settings.json --output-dir build/agent-harness-business-final -q`。确认变化另加 `--business-variant confirmation`，使用独立输出目录。默认仍为整项 900 秒、12 次 Subject sampling、500,000 reported tokens；未给第二次用户请求重置预算。

| 系列 / 任务 | 原始结果 | Subject sampling / reported tokens |
| --- | --- | --- |
| 草稿 standard：回访 | 程序与 Judge 均 pass | 6 / 61,445 |
| 草稿 standard：月结 | 两请求完成，程序与 Judge 均 pass | 4 + 3 / 86,896 |
| 草稿 standard：分流 | 第一请求 11 轮完成，第二请求只运行 1 轮即达整项上限 | 12 / 248,799 |
| confirmation：回访 | 实际名单正确；初始 oracle 不接受带标记全表而误判。修正后独立复评程序与 Judge 均 pass | 5 / 45,292 |
| confirmation：月结 | 两轮金额正确，Judge partial；存在实质解释错误，不能当作完整成功 | 4 + 3 / 80,830 |
| confirmation：分流 | 第一请求耗尽预算，多次训练失败，第二请求未提交 | 12 / 335,289 |
| standard 分流，Subject pro | 第一请求用完 12 轮，第二请求已开始但没有获准 sampling；未交付新批次 | 12 / 264,304 |
| 最终 standard：回访 | 程序与 Judge 均 pass | 6 / 69,634 |
| 最终 standard：月结 | 两轮交付正确；初始 oracle 因首轮合计行误判。修正后独立复评程序与 Judge 均 pass | 5 + 4 / 178,546 |
| 最终 standard：分流 | 第一请求耗尽预算且未交付，第二请求未提交；本次已完整计量未完成请求的 usage | 12 / 216,190 |

共 10 个实际 Subject cell，累计 **1,587,225 reported Subject tokens**；Judge、Embedding 分开，不含于该数字。运行中调整了 fixture 编号、交付措辞和评分语义，这些 cell 不构成同一条件下的可比重复，也不能合并成产品通过率。完整运行身份、原始报告路径、逐轮状态及两次复评结果保存在 [live_observations.json](experiments/live_observations.json)。原始报告位于本机 `build/`，精简索引随 packet 保存。

之前还有零 Subject 响应的准备失败：`.txt` 被误当作 Dataset 附件、已安装应用的 trial provider 在开发配置中不可用、已安装应用的另一个 provider 返回配额 403。最终修正为正文业务说明加真实 CSV 附件，并使用本项目开发配置；这些准备失败不解释为 Subject 能力失败。

## 评测器修正与判定边界

回访确认运行 `817b507d101747e0826fd5b805bbcf02` 给出了正确的 12 人推荐名单，链接表包含全部 32 客户并明确标记 `eligible`。要求文件恰好 12 行是隐藏格式偏好；现在接受过滤名单或带资格标记的完整表，Judge 检查该列是否真的是推荐资格。

月结最终运行 `032f5ebc5681499dbf48bf02111615c4` 的首轮链接表含正确四区域及“合计”。原来的严格行数条件误判；现在要求各区域准确出现一次，允许合计等附加行，Judge 检查实际推荐金额列、额外汇总和矛盾。重复区域或漏区域仍不能靠子集匹配通过。

两项都使用原报告中冻结的真实交付调用当前 oracle/Judge，结果分别写入 `build/agent-harness-business-reassessments/campaign-confirmation.json` 与 `revenue-standard.json`；新增 Subject 调用均为 0，Judge usage 分别 6,719 和 12,363 tokens。原报告未覆盖，复评也不作为新 live cell 或正式验收重复。

月结确认运行 `66f6f9ecc29f466995ee090e5b8190a9` 展示了事实与解释分离的必要性：四区域数字全部正确，解释却声称东区退款额仍最高，实际西区为 14,400.25、东区为 9,000.50；又把转入七月的退款影响说成西/北区，实际涉及南/北区。Judge 报 partial 并给出 incorrect_business_claim，发现了问题，但对于本 rubric 中“实质错误应 fail”的严重程度仍偏松。保留原 verdict，作为后续 Judge 校准材料，未为了获得特定判词反复重跑。

正式工单编号已去除草稿中的类别前缀，避免从编号猜标签；所有预测候选列分别计算事实，Judge 选择真正交付的建议队列列并确认编码含义。输入渠道即使经排列与真值高度相关，也不能代替模型预测。离线文本参考两变体均 29/30，渠道捷径均 0/30，仅说明可学信号存在。

## 暴露的生产问题与下一轮优先级

**首轮工作缺乏收束会耗尽整项预算。** 最终分流运行 `3606366b03dc45e397d1119fa895fb0c` 的 12 轮中共有 25 个 Tool 调用：14 次 `data.query`、4 次 `model.train`，随后还把所选模型应用于全部历史记录并分析训练集预测、置信度分布和混淆计数，尚未交付第一轮答案。期间只有一次 SQL 正则 `\u` 转义失败，训练本身成功，因此不能把这次超轮全部归因于服务错误。另一 standard 运行首轮成功用了 11 轮，续轮仅剩 1 轮，同样无法完成复用。下一轮值得直接检查 Subject 的完成判断、额外分析的收益与预算感知。

**文本模型自动分组与默认评估策略存在冲突。** [ml_service.py](../../src/xenix/services/ml_service.py) 的 `_training_context` 在约 634 行仅根据显式 `group` role 决定 `group_aware`；[text_analysis.py](../../src/xenix/services/ml/models/text_analysis.py) 约 304 行却将自动构造的 `prepared.connected_groups` 交给训练准备；[preparation.py](../../src/xenix/services/ml/preparation.py) 约 57–62 行在存在 groups 而策略不是 `group_hash_holdout.v1` 时拒绝训练。确认分流运行 `ab16b65b247d423a8d2532ad4903777d` 触发了该错误。应先在生产设计层协调自动分组与策略选择，再判断是否还需要显式业务分组。

**训练失败对 Agent 的原因投影不足。** 同一确认运行中，实际内部错误含评估策略原因，Agent 收到的却只是 `ML task '<id>' finished with status 'failed'.`；[ml_service.py](../../src/xenix/services/ml_service.py) 约 407/440 行保留了这种通用报错。Agent 曾修改 group 却沿用旧 binding，并继续尝试参数，额外消耗轮次。下一轮需连同异常信息和 binding 使用一起定位，不能只增加训练重试。

上述生产问题本轮仅调查和记录，没有修改 `src/xenix/` 或 Skills。新任务要能保留这些失败，才能用于下一轮验证改进；本轮没有提高预算或降低 90% 目标。

## 结论边界

这是题库实施与 characterization，不是正式 Harness 验收。尚未完成同一条件的三次 headless 加一次 headed；工单分流尚无端到端真实成功，Judge 对正确金额配错误解释的严重程度尚需校准；合成数据没有真实用户频率或代表性统计。确认数据已经用于本次观察，后续若针对它调优，应另建独立业务变化，不能继续声称未见验证。
