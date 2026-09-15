# 业务对象使用整数序列的设计判断

用户提出让 Artifact、Dataset 等对象直接使用 int sequence；本轮支持将其作为业务对象标识的整体方向，取代此前优先试验“短引用映射”的建议；当前授权仍是设计与诊断，没有修改 schema、生产代码或本地应用数据。

## 为什么适合本项目

[PRD](../../docs/10-prd/README.md) 明确产品服务一个本地操作者，SQLite 与本地服务拥有对象权威，远程 ML worker 只负责执行和缓存；目前没有已实现的跨数据库、多端独立分配对象后再合并的产品要求，因此不能用假设性的分布式需求维持所有业务对象的 UUID。

整数能够降低工具调用、公开链接、日志和人工排查中的引用负担；目标是 `dataset_id: 42`、`artifact://57`、`trained_model_id: 68` 这类真实身份，不是让 LLM 使用另一套会话短码再映射到底层 UUID。

缩短 ID 不能保证模型永远引用正确对象；本轮捕获的一个月结最终请求中，32 位 ID 出现 26 次、只有 6 个不同值，替换为整数只会减少整个请求中很小的一部分字符；其首要价值是对象引用的易用性和一致的工程接口，不能把它当作月结文字矛盾的主要修复。

## 建议的目标状态

- Xenix 自己拥有的持久业务对象使用整数身份，工具参数和服务 DTO 保持 int；URI、目录名等文本边界做十进制编码，不在业务层继续到处 `str(id)`。
- 数值递增但允许跳号；已经发布到链接、ToolResult 或派生关系的编号不复用，不以 ID 推断对象数量或时间先后。
- SQLite 负责分配；不使用进程内自增变量，不按当前对象数量生成，不创建 UUID 与短码长期并存的第二套身份。
- Provider 自己分配的 tool-call/request ID、内容摘要、第三方文档内部引用、临时文件随机名不属于这次业务主键替换，继续遵守各自协议。

## 真正需要处理的创建顺序

[storage models](../../src/xenix/services/storage/models.py) 当前有 21 张 ORM 表，主键均为字符串；其中 DatasetDerivation 的主键沿用 Dataset 身份，其他大多使用 `generate_id()`；这不是只改 Dataset 和 Artifact 两处字段。

[DatasetService](../../src/xenix/services/dataset_service.py) 在写 parquet 和创建 DatasetRow 之前生成 ID，并将 ID 用于存储路径；[LLMConversationService](../../src/xenix/services/llm/conversation.py) 在工具执行之前分配 `staged_call_id`，数据集派生记录可以先提交这个未来 ToolCall 引用，ToolCall 本身随后才与 ToolResult 原子提交；这两个具体流程需要提前取得编号。

我倾向于由 storage 提供一个很小的持久整数分配器，使用数据库级序列并支持一次领取多个编号；这样业务对象仍能在最终落库前取得身份，不必为领取主键提前提交半成品对象，也不改变 Conversation 的原子提交边界；数据库级还是按对象类型分序列都能满足整数目标，前者更接近当前跨对象类型不重号的 UUID 语义，作为初步推荐，待实施设计评估调用点成本后定稿。

序列领取应先完成短事务，工具执行和文件生成不持有领取序列的写锁；领取后失败允许留下空号；计数器只是身份分配元数据，不代表 ToolCall 已提交、任务已完成或存在新的执行状态。

[SQLite 官方说明](https://www.sqlite.org/autoinc.html) 区分了普通 INTEGER PRIMARY KEY 与 AUTOINCREMENT：前者可能复用已删除最大编号，后者防止复用已提交的旧编号，但回滚事务的编号仍可重新分配；因此不能仅把所有 `str` 改成 `int`，就宣称现有“身份先发布、记录后提交”的引用契约已经满足。

## 变更边界

| 边界 | 需要一起转换的内容 |
| --- | --- |
| 持久关系 | 业务主键、外键、Job 的领域引用、Dataset 派生边、训练与输出关联 |
| 工具和服务 | Pydantic 输入类型、返回值、DatasetBlock、Artifact URI、模型和任务句柄 |
| 创建与存储 | 提前领取 ID 的 ToolCall、以 Dataset ID 构造的路径、批量 Knowledge 对象创建 |
| 历史记录 | 既有 ToolCall 参数、ToolResult JSON/XTT、Dataset blocks、回答中的 artifact 链接；仅转换关系表不足以保存旧会话可用性 |
| 展示与远端 | Qt 信号/缓存键/选择项、本地与远程 worker 的领域 ID 编解码；远端不取得身份权威 |

既有数据库转换是实质工作量；下一阶段需要明确是做已有身份与历史引用的完整转换，还是对明确授权的开发数据重建；本轮不继承先前另一项本地修复中的“不要 migration”为本次永久规则，也不默默清空用户数据库；长期目标保持单一整数身份，迁移过程不演变为常驻双 ID 机制。
