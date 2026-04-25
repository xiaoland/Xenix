# Tasks Workspace

This directory is the volatility buffer for planning, exploration, solidification, diagnosis, execution notes, and temporary artifacts.

## Structure

- `<task-slug>/`: active packet for one workstream
- `archive/<task-slug>/`: completed historical records
- `templates/`: reusable task templates

## Usage Rules

- Start ambiguous, exploratory, diagnosis-first, or reference-sensitive work in a named packet under `tasks/`.
- Keep uncertain exploration, evidence, temporary inventories, and migration reasoning in task docs until stable truths emerge.
- Promote only stable, reusable, expensive-to-rediscover truths into durable docs.

## Packet Minimums

- `Objective & Hypothesis`
- `Guardrails Touched`
- `Verification`

## Mode Guidance

- Explore: keep work in the current task packet only.
- Solidify: restate scope and affected durable layers before confirmation.
- Execute: keep implementation notes in the task packet while editing durable docs or code.
- Diagnose: keep diagnosis read-only and record evidence before fixing anything.

## Templates

- `templates/exploration.md`
- `templates/execution.md`
- `templates/result.md`
