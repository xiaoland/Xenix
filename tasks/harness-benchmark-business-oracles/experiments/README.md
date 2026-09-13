# 任务设计实验

这里保存一次性设计探针、新建的微型业务材料和观察结果，不被 pytest 或正式 benchmark 收集，也不修改 Xenix 服务。原型与正式材料探针不调用 provider；交付复评明确调用配置的 Judge，绝不冒充新增 Subject 运行。实验脚本不是生产 oracle 框架或新增回归测试套件。

## 实施验证入口

| 脚本/材料 | 用途与运行 |
| --- | --- |
| [verify_formal_tasks.py](verify_formal_tasks.py) | `.venv/Scripts/python.exe tasks/harness-benchmark-business-oracles/experiments/verify_formal_tasks.py`；独立 DuckDB 计算复核两变体金额与资格，检查错误业务策略、合法合计/资格标记、替代标签、模型身份及实际交付冻结。结果见 [formal_observations.json](formal_observations.json)。 |
| [verify_task_execution.py](verify_task_execution.py) | 同样以项目 Python 执行；真实可见 UI、离线 provider，连续两次请求并各附 CSV，验证共享会话、逐轮消耗和中断恢复。结果见 [headed_turn_observations.json](headed_turn_observations.json) 与 [interrupted_turn_observations.json](interrupted_turn_observations.json)。这不是新业务题的 headed live 验收。 |
| [reassess_deliveries.py](reassess_deliveries.py) | 项目 Python 执行，参数 `<原始报告> --judge-settings <配置> --output <新复评文件>`；仅用于本轮 campaign/revenue 的保存交付复评，不调用 Subject、不覆盖原报告。 |
| [live_observations.json](live_observations.json) | 本次 10 个真实 Subject cell 的精简索引、逐轮状态和成本，以及两个单独的交付复评。原始完整报告留在本地 `build/`；不将运行中不同 fixture/判据的草稿混作可比重复。 |

正式文本参考方法在两变体均为 29/30，渠道捷径为 0/30；这是可学信号探针，不是 Xenix 模型效果或真实数据代表性的证明。确认变化已经用于本次试跑；若下一轮依据这些失败定向调优，就不能继续把相同数据称作未见确认集。

下文保留早期微型原型的结果，不能与正式数据的数值或样本数混用。真实运行及判据修正见 [验证记录](../verification.md)。

## 复现与材料

从仓库根目录运行 `.venv/Scripts/python.exe tasks/harness-benchmark-business-oracles/experiments/probe_design.py`。脚本需要项目已有的 scikit-learn，生成或更新本目录中自己拥有的输入文件和 [observations.json](observations.json)；结果包含实际运行时间和 sklearn 版本。

[probe_design.py](probe_design.py) 拥有原型数据和实验计算；[任务规格](../design.md) 解释业务目标、具体题面和可接受结果。`inputs/` 是用户侧材料的原型，`observations.json` 和脚本包含作者侧真值，不能作为 Subject 附件。正式知识场景只把规则导入知识库，正式两轮场景按所属轮次提供附件。

## 已观察结果

| 实验 | 结果 | 支持的判断 |
| --- | --- | --- |
| A：按既定口径月结与更正 | 东区 39,700 → 28,700，西区 32,000 → 32,000；领先区域反转 | 第二轮不是换一种措辞复述第一轮，需要结合既有口径与新材料修订结论 |
| A：四种首轮错误、两种续轮错误 | 六种错误均与对应正确答案不同，具体数值保存在 JSON | 重复计数、遗漏以前月份订单退款、混入其他月退款、忽略退款、更正当新增、沿用旧答案均可被此任务区分 |
| A：输入等价变化 | 行序改变、额外同编号重复导出不改变答案 | 原型没有依赖行位置或将导出行数当作业务记录数 |
| B：规则适用 | 7 名客户入选；使用过期规则或错误处理边界与例外的六种策略均改变名单 | 这些业务条件在数据中确实有作用，不是题面中的无效装饰 |
| B：当前门槛从 1,000 改为 1,200 | 入选集合从 C01/C03/C06/C08/C11/C15/C16 变为 C06/C08/C16 | 规则内容改变时有明确可计算后果；不能仅记住名单 |
| B：输入等价变化 | 行序与一致的编号更换保留业务资格 | 客户编号是身份，不应成为入选规则 |
| C：文本参考与渠道捷径 | 36 条历史训练；18 条新工单上字符 TF-IDF + 逻辑回归准确率和 macro-F1 均为 1.0；多数类准确率 1/3，渠道捷径准确率 0 | 原型具有可学的正文信号，历史渠道相关性不能代表新工单的业务类别 |
| C：等价与含义变化 | 行列重排和备注列不改变映射；正文语义变化后参考方法跟随新队列，准确率 1.0 | 区别应该保持的结果和应该变化的结果，而非要求所有变体输出相同 |

## 如何解释这些实验

A/B 的正确值分别由小例子的手算与逐条业务条件审阅给出，脚本复核它们。错误策略用于检查数据是否让某项业务判断真正影响答案；实验没有调用完整交付提取器或 LLM judge，不能声称已经校准正式评判链。

C 只训练了本地参考分类器，没有运行 Xenix 模型服务、验证已保存分析器复用或测量 Subject。手写文本与标签很清楚；含义变化的探针重复使用三种代表正文，因此不构成 18 个独立语言泛化样本。结果不能用作正式准确率估计，也不能确定业务九成目标在真实数据上是否合理。

原型的城市、区域、编号、行数和数值都是设计探针，不应固化为未来所有数据版本的判据。正式数据应推广实体关系与语言表达、审阅真值、保留独立语义变化；不通过简单复制行或批量改名伪造覆盖增长。

## 本轮推演导致的调整

- A 明确采用退款发生月，并保留原订单关联，避免“六月销售”和“六月净回款”混成隐藏口径；更正与新增的区别写在业务请求中，没有要求指定数据处理步骤。
- B 金额门槛、间隔边界、VIP 的有限例外和未回访状态均有对应记录；版本差异由有效期和规则正文决定，不依赖作者文件名。
- C 业务目标的至少九成写入题面，避免 oracle 隐藏阈值；原型展示的全部正确仍只是参考方法表现。跨轮复用是用户明确要求的工作目标，不以工具调用序列判定。
- 对原先“vip_bypasses_open_case”的实验标签作了修正：该探针实际忽略全部未结服务单，现名为 `ignore_open_service_cases`；避免把观察结果解释成更窄的缺陷。

剩余问题与最小支持需求见 [任务规格](../design.md)，当前优先级见 [任务入口](../packet.md)。
