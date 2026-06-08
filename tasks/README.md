# Tasks Workspace

This directory is the agent-owned volatility buffer for planning, exploration, solidification, diagnosis, evidence, collaboration state, execution notes, and temporary artifacts.

## Structure

- `<task-slug>/`: active task-local workspace for one workstream
- `archive/<task-slug>/`: completed historical records
- `templates/`: reusable task templates

## Usage Rules

- Start ambiguous, exploratory, diagnosis-first, or reference-sensitive work in a named packet under `tasks/`.
- Treat each active packet as agent-owned inside its own boundary: the agent may update, split, and reorganize it without separate approval.
- Keep every packet readable, inspectable, and steerable by the human.
- Keep a compact control surface for current state; do not turn packet files into hidden durable architecture docs or raw log dumps.
- Keep uncertain exploration, evidence, temporary inventories, and migration reasoning in task docs until stable truths emerge.
- Promote only stable, reusable, expensive-to-rediscover truths into durable docs.
- Exclude task packets from ordinary source and durable-doc search unless the task explicitly targets them, recovers task state, or reviews stored evidence.

## Packet Minimums

- `Objective & Hypothesis`
- `Guardrails Touched`
- `Verification`
- `Current Understanding`
- `Next Step`

## Progressive Split

Start single-file when the control surface is compact.

Use directory mode when current state, history, evidence, decisions, temporary work, or verification begin to interfere with each other:

```text
tasks/<task-slug>/
|-- packet.md
|-- notes.md
`-- work/
```

Split by collaboration pressure, not ceremony. Common split directions include current versus history, state versus evidence, decision versus exploration, and control surface versus scratch work.

## Mode Guidance

- Explore: keep work in the current task packet only.
- Solidify: restate scope, affected durable layers, invariants, and verification shape before confirmation.
- Execute: keep implementation notes and verification results in the task packet while editing durable docs or code.
- Diagnose: keep diagnosis read-only and record evidence before fixing anything.
- Mode transitions are non-linear; one task may revisit Explore, Solidify, Execute, and Diagnose as evidence changes.

## Templates

- `templates/packet.md`
- `templates/exploration.md`
- `templates/execution.md`
- `templates/result.md`
