# Probe Catalog

Instrument for the optimization loop. Each probe states input, expected
outcome, and a judge-free criterion where possible. Offline probes run
provider-free; live probes use the external subject model and are paid.

## A. Routing probes (activation correctness — judge-free)

The activation gate makes these deterministic: observe the recorded
agent.skill.activate call, not the final answer.

| # | Input | Expected activation | Negative control |
| --- | --- | --- | --- |
| R1 | “帮我看看这个数据” / “分析一下这个表” | xenix-data-analysis | must not activate modeling/preprocessing |
| R2 | “清洗一下数据 / 去重 / 处理缺失值” | xenix-data-preprocessing | must not activate analysis as primary |
| R3 | “预测一下销量 / 客户流失 / 训练模型” | xenix-data-modeling | must not activate analysis as primary |
| R4 | “用神经网络分析这个表，更高级” | xenix-data-analysis (no escalation) | must not activate modeling |
| R5 | “先预测销量，再画个趋势图” | exactly one primary + correct handoff | no dual-primary |

Criterion: the activation set matches expected, within a fixed round budget.
This is the prime surface for ablation of the description trigger words
(frontmatter description in each SKILL.md).

## B. Fault-injection / ablation probes

Each is a controlled mutation of a skill asset, run against a fixed subject
model, compared to a baseline cell. Success = the wall held and the
observable outcome is unchanged (or the intended delta appeared).

| # | Mutation | Measured effect | Expected |
| --- | --- | --- | --- |
| F1 | Remove a W-class prohibition (e.g. the destructive-SQL clause) from xenix-data-analysis | token count, activation correctness, SQL statement validity | SQL still passes DuckDbSqlValidator; success rate unchanged; tokens ↓ |
| F2 | Inject a fake tool name into a reference (e.g. analysis.fake_tool) | tool-call hallucination rate | provider schema never exposes it; no fake_tool call |
| F3 | Delete a reference file (e.g. association-analysis.md) | graceful degradation of agent.skill.read_reference | not-found is handled; no invented workflow |
| F4 | Rewrite/delete a routing trigger word in description | R1-R5 activation matrix | routing score drops measurably → proves the word carries load |
| F5 | Remove a B-class economy line (broad-preview ban) | token/latency per cell | correctness unchanged; tokens ↑ (evidences the economy load) |
| F6 | Remove an S-class negative line (causality clause) | Judge verdict on the final answer | Judge score unchanged → line was dead weight (or drops → keep as positive standard) |

## C. Consumption probes

- Token/latency per cell, per case, at fixed subject model + settings hash.
- Tool-call count and data.query row-request width (broad SELECT * vs focused
  projection) as the leading economy signal.

## Loop

delete/move/compress one rule → run the matching probe against the baseline →
record the delta → keep or roll back. Each accepted edit is a separate Impact
Handshake before it lands in SKILL.md / catalog.json.
