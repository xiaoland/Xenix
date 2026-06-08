# 00 Meta

This layer holds repository-local meta guidance for the Xenix Native application of SVC v9.8.

It exists to support routing and working posture. It does not own product truth, cross-unit technical truth, runtime truth, or volatile task records.

## What lives here

- typed input route protocols
- reusable mode overlays
- implementation taste for non-trivial code design and implementation changes
- repository-local SOPs that apply across owners
- lightweight routing language when the root `AGENTS.md` needs local support

## Working model

- Root `AGENTS.md` is the front door.
- Classify incoming work as `Intent`, `Constraint`, `Reality`, or `Artifact` before selecting a mode.
- Identify the durable owner before mutating docs or code.
- Use mode documents as overlays that shape posture, not as truth owners.
- Use `implementation-taste.md` when code work shapes structure, boundaries, data shape, authority flow, durable naming, abstraction, or complexity budget.
- Search source and durable docs with volatile task workspaces, generated output, dependencies, virtual environments, and caches excluded by default.
- Keep non-trivial work in agent-owned `tasks/<task-slug>/` workspaces with a compact control surface:
  - `Objective & Hypothesis`
  - `Guardrails Touched`
  - `Verification`
  - current understanding
  - next step

## Current documents

- `input-intent.md`
- `input-constraint.md`
- `input-reality.md`
- `input-artifact.md`
- `mode-a-explore.md`
- `mode-b-solidify.md`
- `mode-c-execute.md`
- `mode-d-diagnose.md`
- `implementation-taste.md`
- `concepts.md`
