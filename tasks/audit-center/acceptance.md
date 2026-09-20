# 审计中心验收方案

本文件保留设计阶段的验收目标；[验收记录](results.md) 记录本轮实际执行和结果。脚本化 Agent 验证解释写入链路，合成截图验证生产 UI 布局，都不能代替真实模型业务判断质量。

## 验收组合

| 编号 | 不可替代的用户结果 | 自动验证及边界 | 通过条件 |
| --- | --- | --- | --- |
| A1 | 重启后仍能核对一个产出的来源与说明。 | fresh bootstrap、上一版本升级、关闭/重建服务后重读；升级包含有/无解释、孤立来源和有歧义旧创建者。 | ORM 可读，已有值不丢，未知保持未知，无伪造说明/默认值；只追加新迁移。 |
| A2 | 数据处理可以说明为什么做、输入是什么。 | 扩展现有 cleaning/transform 服务测试和 ToolRegistry 边界，至少一个测试经过真实 spawn 登记，不全部替换为 InlinePreprocessingWorkerRunner。 | 多输入/别名、操作、执行前解释与真实 thread/ToolCall 一起落盘；来源文件内容不变。 |
| A3 | 模型选择与应用证据准确。 | 扩展 tests/ml/test_ml_execution.py 的 grouped training/evaluation/apply 接受路径；小型真实训练及有界调参数据，避免每项都重新跑全链。 | 提交/实际/选中参数区别明确，自动评估继承来源，holdout/OOF 不冒充 refit 指标，apply 连接应用输入而非错误连接训练输入。 |
| A4 | 图表可解释且配置可核对。 | 新增或扩展 graph 的服务边界测试，普通 Vega-Lite 与词云各覆盖一个实际渲染案例。 | 实际配置含生效值、无注入数据行副本，保留合法字面量；记录截断/警告；注册与来源事务一致，打开经 Artifact 身份。 |
| A5 | Agent 确实能保存可查的结果解读。 | 用真实工具注册和 scripted provider 执行：创建产出 → 工具结果 → audit 说明写入 → 最终答复 → 重开会话；错误参数修复路径复用现有 Harness 测试。 | 非空前置说明约束在工具边界执行；结果后说明和证据关联可重读；多模型候选不串说明；篡改来源字段/不存在引用被拒绝且领域记录不变。 |
| A6 | 历史与失败不会被包装成成功。 | Tool 超时后完成、一次调用部分创建后失败、Stop 后不再采样、解释写入失败/修订、删除来源会话。 | 产出仍有归属与证据；未解读/历史缺失正确，修订保留先前版本；不隐式发起 LLM、不造 ToolResult、不级联删产物。 |
| A7 | 当前/全部范围准确。 | 两会话共享输入、B 引用 A 模型及查询 A 任务、全局 Knowledge、未知旧任务、超过一页的匹配项。 | 审计引用和任务发起语义不同；过滤先于分页；全局/未知不混入当前；导出/模型文件不重复为主条目。 |
| A8 | 非专业用户可读、可追问证据。 | 生产控件 UI Lab 场景 + pytest-qt 点击/键盘/resize/切语言 + 捕获后人工检查。 | 默认看到解释与局限；证据可定位并返回；不要求先读 JSON；主体无裁切，固定动作可达。 |
| A9 | 两中心交互可靠。 | 有控制的异步返回顺序：A 后返回于 B、筛选/会话/选择改变、关闭后返回；跨中心一对多产出导航。 | 旧结果不能覆盖新上下文；选择稳定，无错误对象打开/取消；关闭停止轮询并清理 owned work。 |
| A10 | 移除旧入口不丢能力。 | Jobs 日志、取消与 Audit 文件打开真实服务集成；既有 chat 通用展开和工具 query/stop 回归；主程序隔离启动与 native smoke。 | 新路径完整可用，生产专属 Details 窗口/工厂/信号/动作已删除，通用功能保持；诊断日志无新增异常。 |

优先在已有业务验收路径增加结果断言，不为每个字段、控件个数、枚举成员或私有函数新增测试；A1–A10 是验收主题，不要求每格机械拆成一个测试文件。
异步用事件、可控 future 或服务 wait_idle 确定顺序；不靠 sleep 猜完成，不用宽泛超时掩盖阻塞。ML、Qt 和存储均在 fixture 清理中停止，失败时也关闭 worker/engine。

## UI Lab 场景目录

下列 ID 均已注册，可通过 UI Lab 运行；沿用 ScenarioSpec、ScenarioHandle、attach_scenario，同一工厂供 Gallery、Capture 和 pytest-qt 使用，禁止另写只用于截图的假窗口。
场景使用生产窗口/控件及窄的内存 query/command ports，不导入 application_composition，不创建数据库、运行目录、网络、LLM 或 ML worker；动作由记录端口接收，取消/打开只验证意图，不操作真实任务/文件。

| 场景 ID | 合成状态 | 核心检查 |
| --- | --- | --- |
| audit.model-explained | 默认选中已有说明的模型，含基线和评估范围。 | 解释先于记录，重要局限可见，证据往返与文件动作。 |
| audit.dataset-lineage | 多输入、别名、两级上游及来自另一会话的输入。 | 逐级展开、返回恢复、引用不扩大清单。 |
| audit.chart-limits | 截断图表，提交/实际配置有差异，带长字段名。 | 截断不藏在 JSON，参数分层，图表与说明关联。 |
| audit.awaiting-interpretation | 任务已完成，只有执行前说明。 | 不显示“仍在运行”或“已解释”，文件可打开。 |
| audit.history-incomplete | 无解释、未知来源、一个缺失文件。 | 三种缺失分别显示；可查数据库证据。 |
| audit.empty-and-error | 可控端口依次返回无会话、无结果、无匹配、错误。 | 四种状态不同，重试/清除筛选行为正确。 |
| audit.compact-zh | 800×600、zh_CN、长说明和长参数。 | 无裁切，主动作与键盘焦点可达，详情主滚动明确。 |
| audit.wide-en | 1280×800、en_US、长标题/缺失状态。 | 英文不溢出；同一对象语义不因语言变化改变。 |
| jobs.session-and-global | 当前与全部可切，ML/Knowledge/未知来源并存。 | 范围筛选、会话标签、加载更多及选中任务稳定。 |
| jobs.running-and-failed | 可取消任务、失败任务/日志、多个关联产出。 | 取消只发一次正确命令，错误可读，无产出时不误导航。 |
| centers.navigation | 两个生产窗口挂在轻量协调器宿主，共用合成端口。 | 定位不偷偷改主会话，多产出过滤、返回、隐藏/关闭。 |

除注明的尺寸外默认 1100×740；每个 ScenarioSpec 显式固定 locale、Fusion 与字体大小；新增中心场景使用系统 Microsoft YaHei，避免 Windows 离屏环境缺少中文字体，并先配置 render identity 再构建窗口。
readiness 使用“预期请求完成且可显示对象/状态已应用”的有界条件；不能一概 ready_immediately 后随机截取加载中。场景 cleanup 停止所有计时器/排队请求；qtbot 通过 before_close_func 清理，避免双重删除。
错误场景的状态切换属于同一场景工厂的受控端口，pytest 逐态操作；捕获固定一个命名状态，额外错误截图作为该场景证据，不伪称单张图覆盖所有状态。

## 自动捕获与人工 UX 检查

新增场景注册后先逐个运行 `pdm run ui-lab -- <scenario-id>` 检查操作，再执行 `pdm run ui-capture -- <scenario-id> --output ui-artifacts/audit-center`；场景名要替换为上表真实注册的 ID。
最终执行 `pdm run ui-capture-all --output ui-artifacts/audit-center-final`，使用其输出的真实 run-dir 执行 `pdm run ui-capture-all -- --output ui-artifacts/audit-center-final --verify <run-dir>`，必须 expected == captured、无失败，每个场景都有 manifest.json、tree.json、actual.png。
截图验证不做像素相等断言；自动合同检查动作、范围、状态和资源清理，人工逐图检查文本裁切、对比、解释密度、局限可见性和表格可读性，不能用“文件已生成”代替 UX 通过。
Windows 原生窗口另查焦点/激活、非模态行为、关闭清理及 100%/150% 缩放，缩放测试记录实际 DPR/逻辑 DPI，不能仅把截图放大声称验证 DPI。
GammaRay 可用于重现这些场景的布局或对象生命周期故障，使用方式与兼容前提见 [UI 设计](ui-design.md)；它不替代 pytest、截图审查或原生窗口验证。

## 解释质量检查

离线 scripted provider 只证明生成和保存链路，不证明真实模型会写出高质量说明；本轮不因新增字段就宣称用户可理解性已经达标。
用清洗、模型比较、图表、应用结果四类业务示例逐项检查：说明是否连接用户目标，是否解释关键选择的实际影响，结论是否对应具体证据，是否给出真实限制和可操作的核对项；空洞套话、单纯复述字段、未说明专业词汇或夸大评估均不通过。
人工使用 UI Lab 中的审定样例检查阅读体验，实施时再检查至少一条隔离集成演示产出的实际保存说明；若不运行真实 provider，报告明确保留“真实 Agent 遵循率未测”，不得用手写样例消除该限制。
实际模型行为如需进一步量化，沿用既有 live benchmark 流程单独明确模型、场景和费用范围，不把付费调用暗藏在普通测试或打开审计中心过程中。

## 实施时验证命令

本轮已存在且适用的入口包括 `tests/storage/test_migrations.py`、`tests/storage/test_storage_bootstrap.py`、`tests/storage/test_storage_artifacts.py`、`tests/ml/test_ml_execution.py`、`tests/ml/test_ml_foundation_profile_cleaning.py`、`tests/ml/test_data_transform_service.py`、`tests/agent/test_agent_harness_first_slice.py`、`tests/runtime/test_job_center.py`、`tests/ui/test_auxiliary_windows.py`、`tests/ui/test_chatbot_contract.py`、`tests/ui/test_main_window_conversation.py` 和 `tests/ui/test_ui_lab.py`。
新增审计领域及 UI 测试文件在实现中按职责命名后加入针对性命令，不预写尚不存在的可执行 selector；每步通过其小集合，末尾统一运行 `pdm run prepare`、`pdm run check`、`pdm run test`、`pdm run smoke --isolated`、`pdm run ui-native-smoke`。
如触及 packaged worker/import 入口，还需按 CONTRIBUTING 执行 `pdm run package --dist-dir dist/review` 与 `pdm run smoke-package --executable dist/review/xenix/xenix.exe`；不能用普通 Python 测试替代实际打包导入验证。

完成条件是 A1–A10 的结果证据可定位、生产捕获与人工 UX 检查完成、必要检查通过且无未披露阻塞；报告保留真实 Agent 质量未测等事实限制，不混淆“代码可交付”和“所有模型行为已验证”。
