# 回答生成的受控诊断

用户要求继续定位提示词、skill 和 Harness 信息设计的问题；本实验不把“最终文字错了”视为根因，不预设需要更换模型，也不修改生产提示词、工具或 benchmark 判据。

## 预先声明的比较

先使用原配置与既有 standard 月结 case，观察真实 production provider payload，不改变请求；再固定该次首请求最后一次采样前的完整 payload，进行三个分支各两次独立采样：原样 baseline、只修改 analysis skill 的首段回答要求、只压缩 data.query/data.transform 的表格反馈格式。

skill 分支强调沿用用户已确定的业务尺度和规则，将解释限定于影响答案的事实；没有任何先后步骤或特定月结答案；反馈分支保留数据行、列名、类型、完整性标志及结果对象 ID，删除重复元数据和格式外壳；不删除或修改既有历史 reasoning_content、工具定义、用户输入和模型配置。

三组采用相同的非流式传输，固定同一个完整请求；各次只取一次模型响应，不执行新工具，不重试直至成功；若模型要求额外工具，将它记作该分支的行为，不能宣称完成了用户任务。

观察回答是否遵守用户已经确定的规则、是否新增没有证据的经营评价或反事实、解释是否完整、是否继续调用工具，以及 token 和回答长度；不以更短或 Judge 分数单独宣称更正确；所有尝试保留，六次采样只用于选择后续干预方向，不构成稳定通过率。

原始完整题库失败的网络 payload 未冻结；本实验使用新采集的 production 上下文，不冒称精确重现原两次失败；同一模型的控制实验先行，更换模型不作为本轮自变量。

## 已确认的信息路径

实际分析 skill 从 `catalog.json` 加载，其 activation 序列化长度与原题库的 4,091 bytes 相同，正文为当前简化版；不是读取了陈旧、长流程版 skill；activation 仍重复返回 description 和嵌套 metadata 中的 description。

最新真实采样主动同时激活 analysis 和 preprocessing，因此暴露 14 个工具；首请求最后一次采样之前，业务输入文本不足 700 字符，而 skill 目录、激活结果、工具定义、历史 SQL 和历史推理累积为更大的上下文；其影响大小需与控制结果一起判断，不能只凭长度断言因果。

默认 system 指定界面 locale `en_US`，skill 又要求使用用户语言，本次出现英文长报告；这是另一个提示语义不一致的线索，本实验暂不改变它，以保持自变量单一。

[DeepSeek 当前工具调用文档](https://api-docs.deepseek.com/guides/thinking_mode/) 要求带 tools 的后续请求回传历史 reasoning_content，故本轮不通过随意删除历史推理来制造不符合 provider 契约的“精简”；如果以后改这一边界，需要另行验证适配方式。

## 首批结果后的补充实验声明

六次固定末端上下文采样已完成，单独修改历史 skill 首段或压缩表格格式都未形成稳定的改进；在已有思路和行为历史全部固定时，后加的目标约束不能代表从任务开始就使用该约束的效果。

因此再进行一次同配置、同 standard 题目的完整 production 路径实验，仅在 analysis skill 激活时替换同一个首段，其余 skill、工具 schema/结果、system prompt、模型与 Judge 均保留；实验分支为 `skill-scope-from-start`，保存完整请求观察与原 benchmark 报告，不覆盖 baseline。
