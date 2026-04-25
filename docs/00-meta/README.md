# 00 Meta

This layer holds repository-local meta guidance for the Xenix Native application of SVC v9.7.

It exists to support routing and working posture. It does not own product truth, cross-unit technical truth, runtime truth, or volatile task records.

## What lives here

- reusable mode overlays
- repository-local SOPs that apply across owners
- lightweight routing language when the root `AGENTS.md` needs local support

## Working model

- Root `AGENTS.md` is the front door.
- Classify incoming work as `Intent`, `Constraint`, `Reality`, or `Artifact` before selecting a mode.
- Identify the durable owner before mutating docs or code.
- Use mode documents as overlays that shape posture, not as truth owners.
- Keep non-trivial work in `tasks/<task-slug>/` with three minimum anchors:
  - `Objective & Hypothesis`
  - `Guardrails Touched`
  - `Verification`

## Current documents

- `mode-a-explore.md`
- `mode-b-solidify.md`
- `mode-c-execute.md`
- `mode-d-diagnose.md`
