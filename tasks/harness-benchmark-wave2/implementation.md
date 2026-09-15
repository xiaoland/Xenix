# 第二批实施与验证

基线 `974db27`；2026-09-13 用户批准开始实现。正式代码、离线验证、七个真实任务试跑与月结 Judge 校准均已完成，用户已批准整理提交。

## 已落地的 State Diff

| 对象 | 改变与边界 |
| --- | --- |
| 默认任务与选择 | [dispatch.py](../../tests/e2e/agent_harness/_infra/dispatch.py) 按 `test_business_*.py::同名函数` 选择四个代表节点；同文件中的对照不会因默认发现而一起运行。显式选择文件/参数节点仍由 pytest 处理，没有新增注册器。 |
| 补货决策家族 | [case](../../tests/e2e/agent_harness/test_business_restock_decision.py) 与 [正式材料](../../tests/e2e/agent_harness/fixtures/business_tasks/restock/README.md)：普通、五个单条件对照、一个独立确认。普通目录 12 个报价，确认目录 10 个不同报价；可订多批，包含到货、仓容、供应与计划毛利取舍。 |
| 多解与不下单 | 程序核对可行性和达到公开目标的毛利，不固定最优 SKU 清单；Judge 确认实际推荐列/表和解释。原型进一步明确为：没有可采购批次时允许直接说明不下单与依据，不强制生成空文件。 |
| 回访对照 | [case](../../tests/e2e/agent_harness/test_business_campaign_eligibility.py) 新增 `spending_threshold` / `contact_interval`，保持七月请求与客户快照不变，分别只改消费门槛或回访间隔。旧 standard/confirmation 输入未变。 |
| 月结 Judge | [case](../../tests/e2e/agent_harness/test_business_revenue_revision.py) 补入用户侧源记录事实，并明确“正确表 + 实质错误解释”仍应 fail；缺少解释才是 partial。事实补充先解决判据缺证据的问题，未修改全局 Judge 框架。 |
| 月结校准 | [四包材料](../../tests/e2e/agent_harness/fixtures/business_tasks/revenue/judge_calibration.json) 保留一个真实错误交付，另三包明确为作者改写：完整正确、合法合计、遗漏第二轮说明。标签在运行前确定，原始 Subject 报告不覆盖。 |
| 共享边界 | [交付证据](../../tests/e2e/agent_harness/_infra/business_tasks.py) 增加表头信息，使空表仍可解释。未修改 runner、预算、报告版本、生产服务、Skills 或 migration；v6 的既有兼容与比较策略保留。 |

## 验证与复现

- `pdm run benchmark-agent-harness-check -q`：41 passed，6.97 秒；只更新已有默认发现验证，没有新增回归测试。
- `pdm run check`：全部通过；任务 packet 的实验脚本另经 Ruff 检查与格式化。
- 默认 headless 和 headed `--collect-only -q`：各四个代表任务。显式选择补货与回访两个文件：九个节点，含七个对照。
- `.venv/Scripts/python.exe tasks/harness-benchmark-wave2/experiments/verify_wave2.py`：独立穷举对照作者侧动态规划，七个补货场景最优值全部一致；检验多解、行序、审计全表、合法合计、超额/负数/分数批量、错误身份、空计划，以及两项回访规则变化。结果见 [formal_observations.json](experiments/formal_observations.json)。
- `.venv/Scripts/python.exe tasks/harness-benchmark-wave2/experiments/prepare_calibration.py`：从首批保留的月结真实交付生成四包标注材料。只用于复现材料；正式 calibration 从静态 manifest 读取，不依赖 task packet 或 `build/`。

新补货程序会给候选数量列计算事实，Judge 必须选择实际推荐方案。对“正确备选列存在但实际推荐空计划”“正确计划多出不存在的采购报价”两个作者反例，程序候选匹配通过，但 Judge 都判 fail。这是对职责分工的实测，不是把程序检查通过冒充完整任务成功；两次均为 Judge 调用，新增 Subject 调用为零。命令与来源见 [check_judge_boundaries.py](experiments/check_judge_boundaries.py)，完整结果位于本地 `build/agent-harness-wave2/judge-boundaries.json`。

## 真实运行设置

Subject 使用项目开发配置中的 `deepseek/deepseek-v4-flash`，Judge 使用 `deepseek/deepseek-v4-pro`；回访另使用开发 Embedding 配置。配置路径为 `.runtime/dev/config/agent_settings.json`、`judge_settings.json`、`embedding_settings.json`，没有改配置文件。默认预算继续作用于整项任务；没有因题目增加而提高阈值。

普通/对照系列显式选择补货代表节点、`test_restock_contrast[budget_tight]`、`[arrival_earlier]`、`[no_purchase]` 和两个 `test_campaign_contrast`，输出在 `build/agent-harness-wave2/live`。独立补货确认只选代表节点并加 `--business-variant confirmation`，输出在 `build/agent-harness-wave2/confirmation`。毛利提高/降低对照只做独立离线验证，避免机械地将每个设计变化都变成付费必跑项。

月结校准命令：`pdm run benchmark-agent-harness-calibrate-judge --manifest tests/e2e/agent_harness/fixtures/business_tasks/revenue/judge_calibration.json --manifest-suite revenue_severity --judge-llm-settings .runtime/dev/config/judge_settings.json --subject-model deepseek/deepseek-v4-flash --output build/agent-harness-wave2/revenue-calibration.json`；四包各三次，仅 Judge，没有新的 Subject 请求。

## 真实结果

七项均 completed、程序检查 pass、输入保留检查通过且未超预算；六项 Judge pass，一项 Judge fail。命令的 pytest 汇总表示执行完成，不能将它的 `passed` 当成业务任务全通过。以下轮数与 token 均为 Subject 用量；完整身份、判据、调用用量和原始报告索引见 [live_observations.json](experiments/live_observations.json)。

| 任务实例 | Subject 轮数 | Subject token | Judge | 可观察结果 |
| --- | ---: | ---: | --- | --- |
| 补货 standard | 5 | 48,099 | pass | 毛利 1,845 元；选择两个同等最优计划之一。 |
| 补货 budget_tight | 6 | 52,306 | fail | 采购计划毛利 1,415 元正确，解释包含实质错误。 |
| 补货 arrival_earlier | 8 | 96,629 | pass | 因提前到货改变计划，毛利提高至 2,050 元。 |
| 补货 no_purchase | 5 | 40,287 | pass | 依据 120 元预算低于最低批成本 150 元给出不下单结论，没有生成空文件。 |
| 补货 confirmation | 6 | 63,438 | pass | 在不同商品、价格和资源条件下达到 1,280.65 元。 |
| 回访 spending_threshold | 5 | 50,005 | pass | 只提高消费门槛，交付正确的 5 人名单。 |
| 回访 contact_interval | 6 | 58,970 | pass | 只延长回访间隔，交付正确的 8 人名单。 |

Subject 合计 409,734 token、41 个采样轮次；七项 live Judge 合计 61,961 token。月结校准另用 109,810 Judge token，两个作者反例另用 7,067 Judge token；全批 Judge 合计 178,838 token。均为供应商报告的用量，未估算货币费用，也没有把校准调用计入 Subject 成本。

| 月结校准材料 | 运行前标注 | 三次观察 |
| --- | --- | --- |
| 完整正确解释与真实表 | pass | pass / pass / pass |
| 同样正确、调整行序并增加合法合计 | pass | pass / pass / pass |
| 正确表，遗漏第二轮变化说明 | partial | partial / partial / partial |
| 首批保留的实质错误解释，未改写 | fail | fail / fail / fail |

四包十二次全部匹配。该结论只适用于本次材料、rubric 与 Judge 配置；未据此追改首批原始结果。月结 rubric 内容指纹已改变，因此新旧 Judge 结果不能当作同一评判口径下的模型改进对比。

## 当前发现与结论边界

预算收紧运行 `5726ff5454c9405098557feed50ecba0` 的方案达到最优毛利 1,415 元，程序通过，Judge 以 incorrect_business_claim 判 fail。逐项核对发现解释把所选各项单位成本毛利都说成高于其他报价，但 Q204 的 235/440 低于 Q509 的 430/680，也低于 Q101 的 460/780；又把毛利仅 1,395 的方案称为“并列最优”。这些是解释错误，不能通过放宽格式或再次跑 Subject 来掩盖。

不下单运行 `8cea0ea513b5445a8fe5eff61af72ef1` 的业务行动与成本依据正确，但解释混用了“没有非零可行采购”和“整个模型无解”，末尾又正确承认零采购可行且最优。保留 Judge pass 与这项文字质量观察，未因此增加逐句一致性校验；任务通过不代表每句话均准确。

本轮验证题库和评判方式能区分实际业务结果，没有承诺所有模型都通过。合成目录不代表真实采购需求或收益分布；单次 Subject 试跑、少量作者反例和单 rubric 校准不能代替三次 headless 加一次 headed 的正式能力验收，也不能证明整体 Judge 已充分校准。
