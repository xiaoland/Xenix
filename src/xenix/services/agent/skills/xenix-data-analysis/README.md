# xenix-data-analysis

这是一个面向 Xenix Agent 的 Agent Skill 包，用于提升表格数据分析任务中的任务识别、`data.query` DuckDB SQL 规划、`analysis.graph` Vega 可视化、`model.train` / `model.hyper_train` / `model.apply` 建模调用、结果解释、报告生成和风险控制能力。

## 运行环境假设

Xenix Agent 没有脚本执行环境。这个版本不包含 `scripts/` 目录，不要求 Python、shell 或任何本地包。

Skill 只假设 Agent 可以使用以下工具：

- `data.peek`
- `data.query`，DuckDB SQL
- `analysis.graph`，Vega spec
- `model.train`
- `model.hyper_train`
- `model.apply`

## 安装

将整个目录放到支持 Agent Skills 的 skills 目录中，目录名保持为：

```text
xenix-data-analysis/
```

## 目录结构

```text
xenix-data-analysis/
├── SKILL.md
├── references/
│   ├── association-analysis.md
│   ├── duckdb-sql-recipes.md
│   ├── model-presets.md
│   ├── neural-network.md
│   ├── reporting-and-risk.md
│   ├── semi-supervised-learning.md
│   ├── supervised-learning.md
│   ├── task-routing.md
│   ├── tools-and-io.md
│   └── visualization-vega.md
└── assets/
    ├── analysis-plan-template.json
    ├── management-report-template.md
    ├── model-presets.json
    └── vega/
        ├── heatmap.vg.json
        ├── time-line.vg.json
        ├── topn-bar.vg.json
        └── wordcloud.vg.json
```

## 设计取向

- `SKILL.md` 只保留触发后的主流程和硬约束。
- 详细任务知识放进 `references/`，按需加载。
- 可视化模板和模型参数模板放进 `assets/`。
- 不包含任何可执行脚本。

## 版本

0.2.0。相比 0.1.0，本版删除 `scripts/`，并改为面向 Xenix 现有工具：DuckDB SQL、Vega spec、模型训练/调参/应用工具。
