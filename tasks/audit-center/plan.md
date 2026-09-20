# 线性实现计划与预演

设计基线提交为 `749ce92` 后，按用户授权执行本计划；01–10 已完成，实际实现落点、验证证据及限制见[验收记录](results.md)。下方预演部分保留设计阶段的调查事实。

## 实现顺序

每一步消费前一步已经验证的接口并交付一个可独立检查的结果；同一主线推进，不建立并行 tracks，不提前删除替代能力尚未完成的窗口。

| 步骤 | 具体工作及代码落点 | 本步出口 |
| --- | --- | --- |
| 01 固定合同 | 在 services 的新审计模块定义对象引用、发起来源、说明状态、列表/详情/分页类型和 query/command ports；明确 draft rationale 与 append-only interpretation，不让 UI 编排 ORM。 | 类型与业务用例映射清楚；来源和说明不存在第二套任务/产物权威；验收 A1–A10 有落点。 |
| 02 存储与迁移 | storage/models.py、repositories、新前向 migration 增加 ML 来源、DatasetDerivation 会话来源、无领域 owner 的 Artifact 生成记录及说明版本；迁移历史只采用明确创建者证据。 | fresh/upgrade、ORM 读回、事务回滚、延迟消息引用与删除保留测试通过；不读取用户数据库。 |
| 03 产出写入 | dataset_service、agent/_data_tools、preprocessing_worker 串通来源/执行前说明；ml_service 输入至 CreateMLTaskInput 保存，并向自动评估/应用产出传播；analysis_graph 返回实际配置，_analysis_tools 原子注册。 | 真实领域边界覆盖数据、模型、图表；至少一次真实子进程登记；新产出来源不依赖 ToolResult 成功。 |
| 04 只读查询 | 实现 AuditQueryService 与复用的会话引用解析，分列表摘要/按需详情；加入 JobQueryService 范围查询及详情端口；支持 ML 日志、领域文件关联、历史缺失和过滤后分页。 | A3/A4/A7 的真实读回成立，当前/全部不串数据，查询不加载所有文件/日志来画清单。 |
| 05 Agent 说明闭环 | tool_inputs.py 为产出操作要求执行前解释，批量模型解释按候选区分；新增解释写入工具及注册、证据校验和追加版本；更新适用 prompt/Skill/工具说明和 result 中的审计引用。 | scripted provider 经真实 registry 完成创建→解读→保存→最终答复；旧 Thread 和 XTT/paged ToolResult 可工作；Stop 不额外采样。 |
| 06 审计 UI 与 Lab | 新建生产 AuditCenterDialog 与内部详情控件，使用步骤 01/04 的端口；实现解释优先、来源往返、参数层次、空态/失败/键盘/异步代次，立即接入 audit.* Lab 工厂和 Qt 测试。 | 无运行目录也能构建/捕获生产控件；默认/紧凑/双语和异步交互通过，截图人工审阅。 |
| 07 Jobs UI 与 Lab | 扩展 JobCenterDialog 范围、会话标签、起止/输入摘要、错误/日志和产出导航；保留 scheduler 取消；增加 jobs.* Lab 场景和行为测试。 | 新任务详情已可替代旧状态/日志能力，生命周期和筛选后分页通过。 |
| 08 装配与跨中心导航 | application_composition、agent/composition、MainWindow、ChatWorkspace、AuxiliaryWindowCoordinator 装配服务/工厂；显式通知会话变化，支持两中心定位与来源会话导航；替换 Datasets 主入口。 | centers.navigation、主窗会话切换/删除/新建、关闭清理、隔离 smoke 通过；无反向 service→UI 依赖。 |
| 09 删除旧链路 | 删除 ToolCallDetailView、DetailWindowFactory、旧按钮/动作/注入 callback/专用样式与旧测试；保留通用 Tool 展开、Dataset 派生摘要及 model.task.query/stop。 | 生产代码检索无旧链路；替代路径日志、取消、打开 Artifact 回归通过，不能靠空实现保留兼容壳。 |
| 10 收口 | 提取并完成双语翻译，compile/prepare；更新 durable owners、审计契约与索引；运行完整验收组合、生产场景捕获及 native/isolated 检查，按导入变化补打包验证。 | 验收结果、实际截图、剩余限制写回 packet；用户于 2026-09-20 手动验收通过并明确授权提交、推送及 PR 合并，按 develop → main 和 Native CI 门禁完成交付。 |

各步同步更新相关耐久文档的已实现契约，不将所有文档工作拖到最后一次性猜补；第 10 步只做一致性收口。中途失败先修当前出口，不累积多个未经验证的阶段。
执行时若源码与本次预演不同，先复核受影响锚点；只有产品范围、解释语义、数据生命周期或验证成本发生实质变化才重新提出决策，普通文件拆分无需确认。

## 代码路径预演发现与修正

| 预演 | 已核实代码路径/障碍 | 已纳入计划的处理 |
| --- | --- | --- |
| R1 数据派生 | _data_tools._register_generated_dataset_result 将 derivation 序列化后调用 preprocessing_worker 的 data.register_generated_dataset；不是主进程直接落库。 | 步骤 03 同时改序列化输入和 worker 消费边界；用真实 spawn 路径检验，不只测 Inline runner。 |
| R2 模型及自动评估 | MLService._create_task_from_request 构造 CreateMLTaskInput；_submit_follow_up_evaluation 在训练完成后单独创建评估任务；apply 也走创建方法。 | 发起来源在 task 持久化前传递，评估继承 root 来源；不能在 Tool 返回后才补写，不能只改 fit。 |
| R3 应用输入 | ApplyTaskRequest.dataset_id 可指向训练上下文，真正应用输入存在 input_files/最终 source_dataset_ids 等事实。 | 应用谱系按 source_dataset_ids/source_artifact_ids 和 trained_model_id 组合；验收不允许把训练数据误标为应用数据。 |
| R4 绘图 | AnalysisGraphService 已在 _prepare_spec 注入 datasets.data 行，_analysis_tools 只存 graph_metadata。 | 在清晰的注入边界保存实际 spec 的无行数据版本，保留用户合法字面量；词云必须记录全部实际选项，而非把摘要冒充完整配置。 |
| R5 说明工具发现 | AgentToolCatalog 的工具目录会展示未激活工具；当前业务工具按需加载，旧 Thread 保留旧 system prompt。 | 新工具走既有目录/激活机制，工具描述和产出返回明确指向解读入口；不只改新会话 prompt，也不引入新的 completion guard。 |
| R6 大结果与成员 | 表格工具可能返回 XTT 字符串，LLM 边界还会将大结果分页；原会话审计只在 dict 中提取部分公开句柄。 | 新来源不能依赖扫描结果文本；以写入时的来源查询为主，历史兼容仅读取可证明的公开结构，未知不猜；新说明工具允许稳定对象引用直接写入。 |
| R7 当前会话同步 | ChatWorkspace._select_conversation_thread 统一选择，但目前没有专门的会话变化 signal；Jobs 的 show_jobs 不接收 thread。 | 步骤 08 增加窄的会话变化通知，覆盖创建/历史选择/删除；MainWindow/Coordinator 转发上下文，不让窗口自行读取主窗私有状态。 |
| R8 异步隔离 | JobCenter 已有 generation、pending load、隐藏停 timer；只改 UI ComboBox 不会自动把 thread 纳入后台查询。 | 把范围/thread/筛选组成同一个查询输入，变动更新代次；列表与详情分别隔离返回，补关闭期间返回测试。 |
| R9 删除范围 | 旧动作从 chatbot_events → conversation/widgets/items → ChatWorkspace callback → MainWindow → AuxiliaryWindowCoordinator → ToolCallDetailView，多处测试和工厂依赖。 | 步骤 09 连贯删除整条链，先验证替代入口；不误删普通 detail_blocks 或公共 TaskLogView。 |
| R10 Lab 可测试性 | 现有 DatasetAuditDialog 构造就从 Harness 同步读取；JobCenter 接受具体服务并自建 QThreadPool；现有 Lab 尚无两中心。 | 窄 ports 与清楚的 query/UI 状态边界先于窗口装配，Lab 用内存服务协议替身，生产行为仍由同一控件负责。 |
| R11 解释就绪边界 | 任务成功与结果解读成功是两个不同事实，暂停后 Harness 不得自动采样。 | 两种状态独立展示，后置解释失败不把 ML 成功改为失败；不自动收费或伪造解释完成。 |
| R12 解释修订与跨会话 | 允许 B 引用 A 模型后解释，会出现多个解释上下文，不能全局覆盖 A 的旧解读。 | 说明按对象与作者会话保留追加历史，默认当前会话解读，其次原始生成说明；明确来源和时间，不能把他会话说明冒充本会话。 |

预演结论：上述问题可在线性步骤中处理，没有发现必须并行拆分或先改整体任务生命周期的依赖；预演是代码路径审查，不等于新迁移、工具和 UI 已经运行通过。

## 本轮执行证据

- `pdm run ui-lab -- --list --json` 已运行成功，当前 5 个场景：chat.empty、chat.mixed-timeline、chat.running-with-attachments、main.history-populated、settings.provider-and-ocr；拟新增 audit/jobs 场景尚不存在。
- `pdm run ui-capture -- chat.mixed-timeline --output tasks/audit-center/evidence/ui-baseline` 已成功；已查看 actual.png，manifest 报告 900×720、Fusion、en_US、Segoe UI exact_match、Qt/PySide 6.11.1、offscreen、DPR 1。证据位于 [现有 UI Lab 基线](evidence/ui-baseline/chat.mixed-timeline/manifest.json)，不代表新中心设计已渲染。
- `pdm run pytest --direct tests/ui/test_ui_lab.py tests/runtime/test_job_center.py tests/ui/test_auxiliary_windows.py -q` 已通过：23 passed in 13.03s；这是既有基线，不是新功能验收。
- `Get-Command gammaray -ErrorAction SilentlyContinue` 未返回命令；本轮未使用 GammaRay，后续使用前按 UI 设计核实可用性与兼容性，不将其列为实施阻塞。
- 产品源码未更改，测试 runner 只按既有流程生成 ignored catalog/翻译资源；Git 变化应限定在本任务目录。没有运行真实 provider、真实用户数据库迁移或打包发布。
- 本地 HTML 草图已编写；浏览器工具 URL 安全策略拒绝 file:// 页面，未采用其他服务/浏览器绕过，未完成其浏览器交互与视觉验证。草图只做静态检查，验收仍以未来生产 Qt 场景为准。
- 草图内嵌脚本经 `node --check` 语法检查通过；task packet 的本地 Markdown 链接均已检查存在，基线 manifest 引用的文件齐全，HTML 字面量元素 ID 无重复；这些静态检查不证明浏览器交互正确。
