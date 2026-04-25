# Operation Taxonomy

Use this taxonomy to route work before execution.

## Input Lens

- `Intent`: desired product behavior, scope, or user-visible outcome
- `Constraint`: technical rule, boundary, or implementation guardrail
- `Reality`: evidence about a bug, anomaly, migration fact, or current repository state
- `Artifact`: temporary notes, plans, inventories, or generated supporting material

## Mode Overlays

- `Explore`: use when causality or scope is unclear; keep output in `tasks/<task-slug>/`
- `Solidify`: classify truths, restate scope, and settle durable destinations before edits
- `Execute`: make bounded code or doc changes once owner and causality are clear
- `Diagnose`: gather read-only evidence in `tasks/<task-slug>/` before fixing anything

## Routing Notes

- Route by owner first, then pick the working mode.
- Keep temporary reasoning and transition-state artifacts in `tasks/<task-slug>/`.
- Promote only stable, reusable, expensive-to-rediscover truth into durable docs or local `AGENTS.md`.
