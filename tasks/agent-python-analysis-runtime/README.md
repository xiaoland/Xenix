# Agent Python Analysis Runtime

## Objective & Hypothesis

- Objective: explore a product and technical contract that lets the Agent run self-authored, analysis-specific Python logic without exposing a fully freeform local scripting surface.
- Hypothesis: the useful middle ground is a typed "analysis lambda" runtime: the Agent can author one bounded function against registered datasets and declared parameters, while Xenix owns input binding, output shape, artifact registration, execution limits, and user-visible review.

## Prompt

- User wants to discuss giving the Agent the ability to run Python code it writes itself.
- The desired balance is between freeform code execution and rigid operation orchestration.
- The MVP is provisionally scoped to data analysis.
- The task packet should be poly-file and updated during discussion.
- Existing issue-98 descriptive analysis work and broader business data-analysis needs should inform the design.

## Guardrails Touched

- PRD: `docs/10-prd/product-scope.md`
- Alignment taxonomy: `docs/15-alignment/operation-taxonomy.md`
- Runtime boundary: `docs/20-product-tdd/runtime-boundaries.md`
- Agent Harness unit contract: `docs/30-unit-tdd/agent-harness.md`
- Existing issue-98 packet: `tasks/issue-98/`
- Existing AI-first script-runtime deferral: `tasks/native-ai-first/script-runtime-design.md`

## Current Facts

- Xenix currently exposes stable Agent tools through a static registry rather than generic Python execution.
- `analysis.profile` and `analysis.graph` already cover bounded descriptive analysis and chart generation for registered datasets.
- `tasks/issue-98/common-descriptive-analysis.py` is broad and useful, but it is file-path based, Excel-report oriented, and not safe as an Agent-facing freeform runtime contract.
- Existing docs explicitly deferred LLM-authored arbitrary Python scripts beyond the first AI-first slice.
- Current runtime boundaries require tools to work through registered datasets, service-owned artifacts, and validated arguments rather than arbitrary local filesystem access.
- Code-side evidence confirms current Agent execution dispatches only static registered tools with JSON arguments; no Agent-facing `eval`, `exec`, or `compile` code path was found.
- Confirmed MVP choices: broad analysis library set, local subprocess worker first, no user approval, one-off execution, generated code/manifest persisted only in tool-call records, output accepts any JSON-serializable `dict`, and the threat model protects against accidental bad Agent code rather than hostile code.

## Working Classification

- Input type: `Intent`, with technical `Constraint` implications.
- Current mode: `Explore`.
- Durable owner is not settled. This packet should stay exploratory until product contract, security posture, and MVP acceptance criteria are confirmed.

## Packet Files

- `product-design.md`: user value, workflow, MVP/non-MVP, and product contract.
- `technical-decisions.md`: architecture candidates, runtime constraints, and decision ledger.
- `data-analysis-demand-map.md`: data-analysis demand taxonomy and where rigid operation orchestration breaks down.
- `discussion-log.md`: running notes and confirmation points from the conversation.

## Smallest Confirmation Needed

- Confirm the exact `analysis.lambda` function signature and result envelope.
- Confirm the minimum artifact API exposed inside the lambda context.
- Confirm the execution threat model now that MVP does not include user approval.

## Verification

- Current packet is discussion-only; no code or durable docs are changed.
- Later verification should include threat-model review, schema examples, execution lifecycle diagrams, and tests only after an explicit implementation start.
